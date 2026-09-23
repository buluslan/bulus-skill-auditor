#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex discovery adapter.

The model-visible ``codex debug prompt-input probe`` roots table and skill file entries
are the primary activation source.  Plugin metadata only enriches those entries.  If
probe parsing fails, standalone roots are recursive inferred candidates and plugins are
limited to installed+enabled roots returned by the management CLI.
"""
import os
import re
from collections import defaultdict
from pathlib import Path

import usage
from . import make_issue, normalize_lexical_path, path_is_within, run_cli_json
from . import skillmd

AGENT = "codex"
SCAN_WARNINGS = []
USAGE_META = {}
_CACHE_RESULT = None
_VALID_DECLARED_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_ROOT_LINE = re.compile(r"^- `(r[0-9]+)` = `([^`]+)`\s*$")


def _home_path(home=None):
    return Path(home) if home is not None else Path.home()


def _cwd_path(cwd=None):
    return Path(cwd) if cwd is not None else Path.cwd()


def detect(home=None):
    return (_home_path(home) / ".codex").is_dir()


def _scope(value):
    value = str(value or "").lower()
    if value in ("user", "global"):
        return "user"
    if value == "project":
        return "project"
    if value == "local":
        return "local"
    if value in ("system", "managed", "builtin"):
        return "system"
    if value == "shared":
        return "shared"
    return "unknown"


def _plugin_rows(payload):
    if isinstance(payload, dict):
        rows = payload.get("installed")
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _plugin_source(row):
    source = row.get("source")
    if isinstance(source, dict):
        candidate = source.get("path") or source.get("installPath") or source.get("root")
    else:
        candidate = row.get("installPath") or row.get("path") or row.get("root")
    if isinstance(candidate, str) and os.path.isabs(candidate):
        return Path(normalize_lexical_path(candidate))
    return None


def _plugin_id(row):
    value = row.get("pluginId") or row.get("id") or row.get("plugin_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _plugin_name(row, plugin_id):
    value = row.get("name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return plugin_id.split("@", 1)[0] if plugin_id else None


def _selected_plugins(payload, issues, excluded):
    grouped = defaultdict(list)
    for row in _plugin_rows(payload):
        if row.get("installed") is not True or row.get("enabled") is not True:
            excluded["inactive_plugins"] += 1
            continue
        pid = _plugin_id(row)
        root = _plugin_source(row)
        if not pid or root is None:
            excluded["invalid_plugin_entries"] += 1
            issues.append(make_issue(
                "plugin_entry_invalid", "warning", AGENT, "discovery",
                "installed+enabled plugin entry omitted because its id or source path is invalid",
                safe_context={"plugin_id": pid or "unknown"},
            ))
            continue
        grouped[pid].append((row, root))
    selected = []
    for pid in sorted(grouped):
        values = grouped[pid]
        if len(values) > 1:
            marked = [item for item in values
                      if item[0].get("selected") is True or item[0].get("current") is True]
            if len(marked) == 1:
                values = marked
                excluded["old_plugin_versions"] += len(grouped[pid]) - 1
            else:
                excluded["ambiguous_plugin_versions"] += len(values)
                issues.append(make_issue(
                    "plugin_selection_ambiguous", "warning", AGENT, "discovery",
                    "installed+enabled plugin id has no unique selected version",
                    safe_context={"plugin_id": pid, "count": len(values)},
                ))
                continue
        row, root = values[0]
        if not root.is_dir():
            excluded["missing_plugin_installs"] += 1
            issues.append(make_issue(
                "plugin_install_missing", "warning", AGENT, "discovery",
                "selected plugin source is not an accessible directory",
                path=root, safe_context={"plugin_id": pid},
            ))
            continue
        marketplace = row.get("marketplaceName")
        if not isinstance(marketplace, str) or not marketplace:
            marketplace = pid.split("@", 1)[1] if "@" in pid else None
        selected.append({
            "plugin_id": pid,
            "plugin_name": _plugin_name(row, pid),
            "marketplace": marketplace,
            "plugin_version": str(row.get("version")) if row.get("version") is not None else None,
            "install_path": root,
            "install_scope": _scope(row.get("scope")),
        })
    return selected


def _direct_texts(payload):
    if not isinstance(payload, list):
        return []
    out = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                out.append(part["text"])
            elif isinstance(part, str):
                out.append(part)
    return out


def _heading_block(text, heading):
    marker = "### " + heading
    start = text.find(marker)
    if start < 0:
        return None
    start = text.find("\n", start)
    if start < 0:
        return ""
    start += 1
    end = text.find("\n### ", start)
    return text[start:] if end < 0 else text[start:end]


def parse_prompt_probe(payload):
    """Return ``(roots, entries, error_reason)`` from the direct prompt JSON."""
    candidates = [text for text in _direct_texts(payload)
                  if "### Skill roots" in text or "### Available skills" in text]
    complete = [text for text in candidates
                if "### Skill roots" in text and "### Available skills" in text]
    if len(complete) != 1:
        return None, None, "missing_or_ambiguous_blocks"
    text = complete[0]
    root_block = _heading_block(text, "Skill roots")
    skills_block = _heading_block(text, "Available skills")
    if root_block is None or skills_block is None:
        return None, None, "missing_block"
    roots = {}
    for line in root_block.splitlines():
        if not line.strip():
            continue
        match = _ROOT_LINE.match(line.strip())
        if not match:
            return None, None, "root_format_drift"
        root_id, raw_path = match.groups()
        if root_id in roots or not os.path.isabs(raw_path):
            return None, None, "invalid_root"
        roots[root_id] = normalize_lexical_path(raw_path)
    if not roots:
        return None, None, "missing_roots"
    entries = []
    for line in skills_block.splitlines():
        if not line.strip():
            continue
        if not line.startswith("- "):
            # Wrapped description text is tolerated; only bullets define entries.
            continue
        body = line[2:]
        if ": " not in body or " (file: " not in body or not body.endswith(")"):
            return None, None, "skill_entry_format_drift"
        runtime_name, remainder = body.split(": ", 1)
        _description, reference = remainder.rsplit(" (file: ", 1)
        reference = reference[:-1]
        if "/" not in reference:
            return None, None, "invalid_file_reference"
        root_id, rel = reference.split("/", 1)
        root = roots.get(root_id)
        if root is None or not runtime_name or os.path.isabs(rel):
            return None, None, "unknown_root_reference"
        source = normalize_lexical_path(Path(root) / rel)
        if not path_is_within(source, root) or Path(source).name != "SKILL.md":
            return None, None, "out_of_bounds_reference"
        entries.append({
            "runtime_name": runtime_name,
            "root_id": root_id,
            "root": root,
            "relative_file": rel,
            "source_file": source,
        })
    return roots, entries, None


def _content_issues(raw_issues, path):
    return [make_issue(
        item.get("code", "component_parse_failed"), "warning", AGENT, "parse",
        item.get("message", "component could not be parsed"),
        path=item.get("path") or path,
        safe_context=item.get("safe_context") or {},
    ) for item in raw_issues]


def _plugin_for_path(path, plugins):
    matches = [plugin for plugin in plugins if path_is_within(path, plugin["install_path"])]
    if not matches:
        return None
    matches.sort(key=lambda item: (-len(str(item["install_path"])), item["plugin_id"]))
    return matches[0]


def _root_origin(root, home, cwd):
    codex_skills = normalize_lexical_path(home / ".codex" / "skills")
    shared_skills = normalize_lexical_path(home / ".agents" / "skills")
    project_skills = normalize_lexical_path(cwd / ".agents" / "skills")
    if path_is_within(root, codex_skills):
        parts = Path(root).parts
        if ".system" in parts:
            return "system", "system", "builtin"
        return "user", "user", "standalone"
    if path_is_within(root, shared_skills):
        return "shared", "shared", "standalone"
    if path_is_within(root, project_skills):
        return "project", "project", "standalone"
    return "unknown", "unknown", "standalone"


def _decorate(fact, runtime_name, component_name, scope, install_scope, source_kind,
              active_state, confidence, method, plugin=None, namespace=None):
    auditable = os.path.isfile(fact["source_file"])
    if not auditable:
        listing = trigger = "excluded"
        reason = "model-visible component source could not be read"
    elif active_state == "active":
        listing = trigger = "confirmed"
        reason = "current runtime or management evidence"
    else:
        listing = trigger = "estimated"
        reason = "fallback candidate; runtime activation is unknown"
    fact.update({
        "agent": AGENT,
        "name": runtime_name,
        "runtime_name": runtime_name,
        "component_name": component_name,
        "namespace": namespace,
        "scope": scope,
        "install_scope": install_scope,
        "source_kind": source_kind,
        "active_state": active_state,
        "discovery_confidence": confidence,
        "discovery_method": method,
        "plugin_id": plugin.get("plugin_id") if plugin else None,
        "plugin_name": namespace if plugin else None,
        "marketplace": plugin.get("marketplace") if plugin else None,
        "plugin_version": plugin.get("plugin_version") if plugin else None,
        "manifest_declared": False if plugin else None,
        "auditable": auditable,
        "accounting": {"listing": listing, "trigger": trigger, "reason": reason},
    })
    return fact


def _probe_components(entries, plugins, home, cwd, issues):
    rows = []
    # 同一物理 SKILL.md 可能被 probe 文本重复列出（重复行、或两个 root 指向同一目录）
    # ——它们是同一个实例，按归一化路径去重保留首个，绝不因重复而中断整个采集
    seen_lexical = set()
    for entry in entries:
        source = Path(entry["source_file"])
        lexical = normalize_lexical_path(source)
        if lexical in seen_lexical:
            issues.append({
                "code": "duplicate_probe_entry",
                "message": "probe 重复列出同一物理组件，已去重保留首个",
                "safe_context": {"runtime_name": entry.get("runtime_name"),
                                 "root": entry.get("root")},
            })
            continue
        seen_lexical.add(lexical)
        fact, raw_issues = skillmd.scan_component(source, "skill")
        issues.extend(_content_issues(raw_issues, source))
        plugin = _plugin_for_path(source, plugins)
        if plugin:
            namespace = plugin["plugin_name"]
            prefix = namespace + ":"
            component_name = (entry["runtime_name"][len(prefix):]
                              if entry["runtime_name"].startswith(prefix)
                              else (fact.get("declared_name") or source.parent.name))
            scope, install_scope, source_kind = "plugin", plugin["install_scope"], "plugin"
        else:
            namespace = None
            component_name = entry["runtime_name"]
            scope, install_scope, source_kind = _root_origin(entry["root"], home, cwd)
        rows.append(_decorate(
            fact, entry["runtime_name"], component_name, scope, install_scope, source_kind,
            "active", "runtime_probe", "codex debug prompt-input probe",
            plugin=plugin, namespace=namespace,
        ))
    return rows


def _valid_declared_name(name):
    return isinstance(name, str) and bool(_VALID_DECLARED_NAME.match(name))


def _recursive_skill_files(root):
    if not Path(root).is_dir():
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in (".git", "__pycache__", "node_modules", ".venv"))
        if "SKILL.md" in filenames:
            out.append(Path(dirpath) / "SKILL.md")
    return sorted(out, key=lambda path: normalize_lexical_path(path))


def _fallback_components(home, cwd, plugins, issues, excluded):
    rows = []
    roots = []
    standalone_roots = [
        (home / ".codex" / "skills", "user", "user"),
        (home / ".agents" / "skills", "shared", "shared"),
        (cwd / ".agents" / "skills", "project", "project"),
    ]
    seen_lexical = set()
    for root, scope, install_scope in standalone_roots:
        root = Path(normalize_lexical_path(root))
        if not root.is_dir():
            continue
        roots.append(str(root))
        for source in _recursive_skill_files(root):
            lexical = normalize_lexical_path(source)
            if lexical in seen_lexical:
                continue
            seen_lexical.add(lexical)
            fact, raw_issues = skillmd.scan_component(source, "skill")
            issues.extend(_content_issues(raw_issues, source))
            declared = fact.get("declared_name")
            if not _valid_declared_name(declared):
                excluded["invalid_declared_name"] += 1
                issues.append(make_issue(
                    "codex_declared_name_invalid", "warning", AGENT, "parse",
                    "fallback candidate omitted because frontmatter name is missing or invalid",
                    path=source,
                ))
                continue
            actual_scope, actual_install, source_kind = scope, install_scope, "standalone"
            if ".system" in Path(source).parts:
                actual_scope, actual_install, source_kind = "system", "system", "builtin"
            rows.append(_decorate(
                fact, declared, declared, actual_scope, actual_install, source_kind,
                "unknown", "inferred", "recursive standard-root fallback",
            ))
    for plugin in sorted(plugins, key=lambda item: (item["plugin_id"], str(item["install_path"]))):
        roots.append(str(plugin["install_path"]))
        for source in _recursive_skill_files(plugin["install_path"]):
            fact, raw_issues = skillmd.scan_component(source, "skill")
            issues.extend(_content_issues(raw_issues, source))
            declared = fact.get("declared_name")
            if not _valid_declared_name(declared):
                excluded["invalid_declared_name"] += 1
                issues.append(make_issue(
                    "codex_declared_name_invalid", "warning", AGENT, "parse",
                    "plugin fallback component omitted because frontmatter name is missing or invalid",
                    path=source, safe_context={"plugin_id": plugin["plugin_id"]},
                ))
                continue
            namespace = plugin["plugin_name"]
            runtime_name = "%s:%s" % (namespace, declared)
            rows.append(_decorate(
                fact, runtime_name, declared, "plugin", plugin["install_scope"], "plugin",
                "active", "management_cli", "codex plugin list --json fallback",
                plugin=plugin, namespace=namespace,
            ))
    return rows, roots


def discover(home=None, cwd=None, runner=None):
    global _CACHE_RESULT
    home = _home_path(home)
    cwd = _cwd_path(cwd)
    runner = runner or run_cli_json
    issues = []
    excluded = defaultdict(int)

    probe = runner(["codex", "debug", "prompt-input", "probe"], AGENT, "discovery", timeout=8)
    plugins_cli = runner(["codex", "plugin", "list", "--json"], AGENT, "discovery", timeout=5)
    if plugins_cli.get("ok"):
        plugins = _selected_plugins(plugins_cli.get("data"), issues, excluded)
    else:
        plugins = []
        if plugins_cli.get("issue"):
            issues.append(plugins_cli["issue"])

    roots = None
    entries = None
    probe_error = None
    if probe.get("ok"):
        roots, entries, probe_error = parse_prompt_probe(probe.get("data"))
    else:
        probe_error = "management_cli_failed"
        if probe.get("issue"):
            issues.append(probe["issue"])
    if probe_error is None:
        rows = _probe_components(entries, plugins, home, cwd, issues)
        adopted_roots = sorted(set(roots.values()))
        status = "complete" if plugins_cli.get("ok") else "partial"
        methods = ["codex debug prompt-input probe", "codex plugin list --json"]
        fallback_reason = None
    else:
        issues.append(make_issue(
            "codex_probe_invalid", "warning", AGENT, "discovery",
            "Codex prompt probe could not be validated; conservative fallback was used",
            safe_context={"reason": probe_error},
        ))
        rows, adopted_roots = _fallback_components(home, cwd, plugins, issues, excluded)
        status = "fallback"
        methods = ["recursive standard-root fallback", "codex plugin list --json"]
        fallback_reason = probe_error
    rows.sort(key=lambda row: (
        row["runtime_name"], row["component_type"], row["source_file"],
        row.get("plugin_id") or "",
    ))
    if status == "complete" and any(issue.get("severity") in ("warning", "error") for issue in issues):
        status = "partial"
    result = {
        "skills": rows,
        "skill_roots": sorted(set(adopted_roots)),
        "issues": issues,
        "discovery": {
            "status": status,
            "methods": methods,
            "cli_version": None,
            "fallback_reason": fallback_reason,
            "excluded_counts": dict(sorted(excluded.items())),
            "component_coverage": {
                "skill": len(rows), "command": 0, "agent": 0,
            },
        },
    }
    _CACHE_RESULT = result
    SCAN_WARNINGS[:] = [issue["message"] for issue in issues
                        if issue.get("severity") in ("warning", "error")]
    return result


def skill_roots():
    return list((_CACHE_RESULT or discover())["skill_roots"])


def iter_skills():
    return [dict(row) for row in (_CACHE_RESULT or discover())["skills"]]


def usage_stats_available(home=None):
    home = _home_path(home) / ".codex"
    return (home / "sessions").is_dir() or (home / "archived_sessions").is_dir()


def usage_records(window_days, skills=None, home=None):
    USAGE_META.clear()
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    if skills is None:
        skills = (_CACHE_RESULT or discover())["skills"]
    resolver = usage.build_path_resolver(skills, AGENT)
    home = _home_path(home) / ".codex"
    records, meta = usage.scan_codex_rollouts(
        window_days, resolver, roots=[home / "sessions", home / "archived_sessions"],
    )
    USAGE_META.update(meta)
    return records
