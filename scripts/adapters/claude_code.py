#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude Code discovery adapter.

Only the current ``claude plugin list --json`` selection is authoritative for plugin
activation.  Cache directories are never traversed.  Standard standalone roots are
known runtime roots; ``~/.claude/agents/skills`` is admitted only when current runtime
evidence explicitly lists it.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

import usage
from . import make_issue, normalize_lexical_path, path_is_within, run_cli_json
from . import skillmd

AGENT = "claude-code"
SCAN_WARNINGS = []
USAGE_META = {}
_CACHE_RESULT = None


def _home_path(home=None):
    return Path(home) if home is not None else Path.home()


def _cwd_path(cwd=None):
    return Path(cwd) if cwd is not None else Path.cwd()


def detect(home=None):
    return (_home_path(home) / ".claude").is_dir()


def _scope(value):
    value = str(value or "").lower()
    if value in ("user", "global"):
        return "user"
    if value in ("project",):
        return "project"
    if value in ("local",):
        return "local"
    if value in ("system", "managed", "builtin"):
        return "system"
    if value in ("shared",):
        return "shared"
    return "unknown"


def _safe_json(path):
    try:
        text = skillmd.read_text(path)
        value = json.loads(text)
    except (OSError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _extract_rows(payload):
    roots = []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], roots
    if not isinstance(payload, dict):
        return [], roots
    rows = []
    for key in ("plugins", "installed", "installedPlugins", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            rows = [item for item in value if isinstance(item, dict)]
            break
    for key in ("skillRoots", "runtimeSkillRoots", "skill_roots"):
        value = payload.get(key)
        if isinstance(value, list):
            roots.extend(item for item in value if isinstance(item, str) and os.path.isabs(item))
    return rows, sorted(set(normalize_lexical_path(root) for root in roots))


def _plugin_id(row):
    value = row.get("id") or row.get("pluginId") or row.get("plugin_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _plugin_name(plugin_id):
    return plugin_id.split("@", 1)[0] if plugin_id else None


def _marketplace(plugin_id):
    return plugin_id.split("@", 1)[1] if plugin_id and "@" in plugin_id else None


def _selected_cli_plugins(payload, issues, excluded):
    rows, runtime_roots = _extract_rows(payload)
    groups = defaultdict(list)
    for row in rows:
        if row.get("enabled") is not True:
            excluded["disabled_plugins"] += 1
            continue
        pid = _plugin_id(row)
        install = row.get("installPath") or row.get("install_path")
        if not pid or not isinstance(install, str) or not os.path.isabs(install):
            excluded["invalid_plugin_entries"] += 1
            issues.append(make_issue(
                "plugin_entry_invalid", "warning", AGENT, "discovery",
                "enabled plugin entry omitted because its id or installPath is invalid",
                safe_context={"plugin_id": pid or "unknown"},
            ))
            continue
        groups[pid].append(row)
    selected = []
    for pid in sorted(groups):
        candidates = groups[pid]
        if len(candidates) != 1:
            excluded["ambiguous_plugin_entries"] += len(candidates)
            issues.append(make_issue(
                "plugin_selection_ambiguous", "warning", AGENT, "discovery",
                "enabled plugin id appeared more than once; no version was selected",
                safe_context={"plugin_id": pid, "count": len(candidates)},
            ))
            continue
        row = candidates[0]
        install = Path(normalize_lexical_path(row.get("installPath") or row.get("install_path")))
        if not install.is_dir():
            excluded["missing_plugin_installs"] += 1
            issues.append(make_issue(
                "plugin_install_missing", "warning", AGENT, "discovery",
                "enabled plugin installPath is not an accessible directory",
                path=install, safe_context={"plugin_id": pid},
            ))
            continue
        selected.append({
            "plugin_id": pid,
            "plugin_name": _plugin_name(pid),
            "marketplace": _marketplace(pid),
            "plugin_version": str(row.get("version")) if row.get("version") is not None else None,
            "install_path": install,
            "install_scope": _scope(row.get("scope")),
            "active_state": "active",
            "discovery_confidence": "management_cli",
            "discovery_method": "claude plugin list --json",
        })
    return selected, runtime_roots


def _fallback_plugins(home, issues, excluded):
    """Read only the installed-record and enabled-switch whitelist.

    A fallback candidate is never promoted to active.  When multiple installed records
    exist, the newest explicit record is selected and older records are counted as
    excluded; the cache itself is not enumerated.
    """
    enabled = {}
    for name in ("settings.json", "settings.local.json"):
        data = _safe_json(home / ".claude" / name)
        if not data:
            continue
        value = data.get("enabledPlugins")
        if isinstance(value, dict):
            for key, state in value.items():
                if isinstance(key, str) and isinstance(state, bool):
                    enabled[key] = state
    installed = _safe_json(home / ".claude" / "plugins" / "installed_plugins.json") or {}
    table = installed.get("plugins") if isinstance(installed.get("plugins"), dict) else {}
    selected = []
    for pid in sorted(enabled):
        if enabled[pid] is not True:
            excluded["disabled_plugins"] += 1
            continue
        records = table.get(pid)
        if not isinstance(records, list):
            excluded["missing_install_records"] += 1
            continue
        valid = []
        for row in records:
            if not isinstance(row, dict):
                continue
            install = row.get("installPath")
            if isinstance(install, str) and os.path.isabs(install):
                valid.append(row)
        if not valid:
            excluded["missing_install_records"] += 1
            continue
        valid.sort(key=lambda row: (
            str(row.get("lastUpdated") or ""), str(row.get("installedAt") or ""),
            str(row.get("version") or ""), str(row.get("installPath") or ""),
        ))
        row = valid[-1]
        excluded["old_install_records"] += max(0, len(valid) - 1)
        install = Path(normalize_lexical_path(row["installPath"]))
        if not install.is_dir():
            excluded["missing_plugin_installs"] += 1
            continue
        selected.append({
            "plugin_id": pid,
            "plugin_name": _plugin_name(pid),
            "marketplace": _marketplace(pid),
            "plugin_version": str(row.get("version")) if row.get("version") is not None else None,
            "install_path": install,
            "install_scope": _scope(row.get("scope")),
            "active_state": "unknown",
            "discovery_confidence": "inferred",
            "discovery_method": "installed record + enabled switch fallback",
        })
    if selected:
        issues.append(make_issue(
            "plugin_state_inferred", "warning", AGENT, "discovery",
            "plugin management CLI was unavailable; whitelisted plugin candidates remain unknown",
            safe_context={"count": len(selected)},
        ))
    return selected


def _manifest_paths(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _manifest_base(install_root, source):
    if not isinstance(source, str) or not source.strip():
        return install_root
    candidate = Path(normalize_lexical_path(install_root / source))
    if path_is_within(candidate, install_root):
        return candidate
    return None


def _load_manifest(plugin, issues, excluded):
    root = plugin["install_path"]
    market_path = root / ".claude-plugin" / "marketplace.json"
    plugin_path = root / ".claude-plugin" / "plugin.json"
    if market_path.is_file():
        data = _safe_json(market_path)
        if data is None or not isinstance(data.get("plugins"), list):
            excluded["invalid_manifests"] += 1
            issues.append(make_issue(
                "plugin_manifest_invalid", "warning", AGENT, "parse",
                "marketplace manifest is invalid; plugin components were omitted",
                path=market_path, safe_context={"plugin_id": plugin["plugin_id"]},
            ))
            return None
        target = plugin["plugin_name"]
        matches = [row for row in data["plugins"]
                   if isinstance(row, dict) and row.get("name") == target]
        if len(matches) != 1:
            excluded["manifest_selection_failures"] += 1
            issues.append(make_issue(
                "marketplace_plugin_selection_failed", "warning", AGENT, "parse",
                "marketplace manifest did not contain exactly one matching plugin entry",
                path=market_path,
                safe_context={"plugin_id": plugin["plugin_id"], "count": len(matches)},
            ))
            return None
        item = matches[0]
        base = _manifest_base(root, item.get("source"))
        if base is None:
            excluded["invalid_manifests"] += 1
            issues.append(make_issue(
                "plugin_source_outside_install", "warning", AGENT, "parse",
                "marketplace plugin source escaped the selected installPath",
                path=market_path, safe_context={"plugin_id": plugin["plugin_id"]},
            ))
            return None
        return {
            "namespace": item.get("name"),
            "base": base,
            "manifest_path": market_path,
            "paths": {kind: _manifest_paths(item.get(kind + "s"))
                      for kind in ("skill", "command", "agent")},
        }
    if plugin_path.is_file():
        data = _safe_json(plugin_path)
        if data is None:
            excluded["invalid_manifests"] += 1
            issues.append(make_issue(
                "plugin_manifest_invalid", "warning", AGENT, "parse",
                "plugin manifest is invalid; plugin components were omitted",
                path=plugin_path, safe_context={"plugin_id": plugin["plugin_id"]},
            ))
            return None
        namespace = data.get("name")
        if not isinstance(namespace, str) or not namespace.strip():
            namespace = plugin["plugin_name"]
        paths = {
            "skill": _manifest_paths(data.get("skills")) if "skills" in data else ["skills"],
            "command": _manifest_paths(data.get("commands")),
            "agent": _manifest_paths(data.get("agents")),
        }
        return {
            "namespace": namespace.strip(),
            "base": root,
            "manifest_path": plugin_path,
            "paths": paths,
        }
    excluded["missing_manifests"] += 1
    issues.append(make_issue(
        "plugin_manifest_missing", "warning", AGENT, "parse",
        "selected plugin has no supported Claude manifest; components were omitted",
        path=root, safe_context={"plugin_id": plugin["plugin_id"]},
    ))
    return None


def _component_files(base, install_root, declaration, component_type, issues, plugin_id):
    candidate = Path(normalize_lexical_path(base / declaration))
    if not path_is_within(candidate, install_root):
        issues.append(make_issue(
            "manifest_path_outside_install", "warning", AGENT, "parse",
            "manifest component path escaped the selected installPath",
            path=candidate, safe_context={"plugin_id": plugin_id, "component_type": component_type},
        ))
        return []
    if component_type == "skill":
        if candidate.is_file() and candidate.name == "SKILL.md":
            return [candidate]
        if candidate.is_dir() and (candidate / "SKILL.md").is_file():
            return [candidate / "SKILL.md"]
        if candidate.is_dir():
            try:
                children = sorted(candidate.iterdir(), key=lambda path: path.name)
            except OSError:
                return []
            return [child / "SKILL.md" for child in children
                    if child.is_dir() and (child / "SKILL.md").is_file()]
        return []
    if candidate.is_file() and candidate.suffix.lower() == ".md":
        return [candidate]
    if candidate.is_dir():
        try:
            return sorted((path for path in candidate.iterdir()
                           if path.is_file() and path.suffix.lower() == ".md"),
                          key=lambda path: path.name)
        except OSError:
            return []
    return []


def _content_issues(raw_issues, path):
    return [make_issue(
        item.get("code", "component_parse_failed"), "warning", AGENT, "parse",
        item.get("message", "component could not be parsed"),
        path=item.get("path") or path,
        safe_context=item.get("safe_context") or {},
    ) for item in raw_issues]


def _decorate(fact, runtime_name, component_name, scope, install_scope, source_kind,
              active_state, confidence, method, plugin=None, namespace=None,
              manifest_declared=None):
    auditable = fact["component_type"] in ("skill", "command") and os.path.isfile(fact["source_file"])
    if not auditable or fact["component_type"] == "agent":
        listing = trigger = "excluded"
        reason = "component has no reliable auditable loading semantics"
        auditable = False
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
        "manifest_declared": manifest_declared if plugin else None,
        "auditable": auditable,
        "accounting": {"listing": listing, "trigger": trigger, "reason": reason},
    })
    return fact


def _standalone_components(home, cwd, runtime_roots, issues, excluded):
    standard = [
        (home / ".claude" / "skills", "user"),
        (cwd / ".claude" / "skills", "project"),
    ]
    agents_root = home / ".claude" / "agents" / "skills"
    if normalize_lexical_path(agents_root) in runtime_roots:
        standard.append((agents_root, "user"))
    adopted_roots = []
    candidates = []
    for priority, (root, scope) in enumerate(standard):
        root = Path(normalize_lexical_path(root))
        if not root.is_dir():
            continue
        adopted_roots.append(str(root))
        try:
            children = sorted(root.iterdir(), key=lambda path: path.name)
        except OSError as exc:
            issues.append(make_issue(
                "standalone_root_unreadable", "warning", AGENT, "discovery",
                "standalone skill root could not be read",
                path=root, safe_context={"error_type": type(exc).__name__},
            ))
            continue
        for child in children:
            source = child / "SKILL.md"
            if child.name.startswith(".") or not source.is_file():
                continue
            candidates.append((child.is_symlink(), priority, str(source), source, scope))
    # Prefer a physical directory over a symlink alias, then root priority and lexical path.
    candidates.sort(key=lambda row: (row[0], row[1], row[2]))
    rows = []
    seen_real = set()
    for _is_link, _priority, _lex, source, scope in candidates:
        real = os.path.realpath(str(source))
        if real in seen_real:
            excluded["duplicate_realpaths"] += 1
            continue
        seen_real.add(real)
        fact, raw_issues = skillmd.scan_component(source, "skill")
        issues.extend(_content_issues(raw_issues, source))
        runtime_name = source.parent.name
        rows.append(_decorate(
            fact, runtime_name, runtime_name, scope, scope, "standalone",
            "active", "known_root", "claude standard skill root",
        ))
    return rows, adopted_roots


def _plugin_components(plugins, issues, excluded):
    rows = []
    roots = []
    seen = set()
    for plugin in sorted(plugins, key=lambda item: (item["plugin_id"], str(item["install_path"]))):
        manifest = _load_manifest(plugin, issues, excluded)
        if manifest is None:
            continue
        roots.append(str(plugin["install_path"]))
        namespace = manifest["namespace"]
        for component_type in ("skill", "command", "agent"):
            for declaration in manifest["paths"][component_type]:
                files = _component_files(
                    manifest["base"], plugin["install_path"], declaration,
                    component_type, issues, plugin["plugin_id"],
                )
                if not files:
                    excluded["missing_declared_components"] += 1
                    continue
                for source in files:
                    key = (component_type, normalize_lexical_path(source))
                    if key in seen:
                        excluded["duplicate_manifest_components"] += 1
                        continue
                    seen.add(key)
                    fact, raw_issues = skillmd.scan_component(source, component_type)
                    issues.extend(_content_issues(raw_issues, source))
                    component_name = source.parent.name if component_type == "skill" else source.stem
                    runtime_name = "%s:%s" % (namespace, component_name)
                    rows.append(_decorate(
                        fact, runtime_name, component_name, "plugin", plugin["install_scope"],
                        "plugin", plugin["active_state"], plugin["discovery_confidence"],
                        plugin["discovery_method"], plugin=plugin, namespace=namespace,
                        manifest_declared=True,
                    ))
    return rows, roots


def discover(home=None, cwd=None, runner=None):
    """Discover Claude components and activation evidence without mutating runtime state."""
    global _CACHE_RESULT
    home = _home_path(home)
    cwd = _cwd_path(cwd)
    runner = runner or run_cli_json
    issues = []
    excluded = defaultdict(int)
    cli = runner(["claude", "plugin", "list", "--json"], AGENT, "discovery", timeout=5)
    runtime_roots = []
    fallback_reason = None
    if cli.get("ok"):
        plugins, runtime_roots = _selected_cli_plugins(cli.get("data"), issues, excluded)
        status = "complete"
        methods = ["claude plugin list --json", "known standalone roots"]
    else:
        if cli.get("issue"):
            issues.append(cli["issue"])
            fallback_reason = cli["issue"].get("code")
        plugins = _fallback_plugins(home, issues, excluded)
        status = "fallback"
        methods = ["known standalone roots", "whitelisted install-record fallback"]
    standalone, standalone_roots = _standalone_components(
        home, cwd, runtime_roots, issues, excluded,
    )
    plugin_rows, plugin_roots = _plugin_components(plugins, issues, excluded)
    rows = standalone + plugin_rows
    rows.sort(key=lambda row: (
        row["runtime_name"], row["component_type"], row["source_file"],
        row.get("plugin_id") or "",
    ))
    if status == "complete" and any(issue.get("severity") in ("warning", "error") for issue in issues):
        status = "partial"
    coverage = {kind: sum(1 for row in rows if row["component_type"] == kind)
                for kind in ("skill", "command", "agent")}
    result = {
        "skills": rows,
        "skill_roots": sorted(set(standalone_roots + plugin_roots)),
        "issues": issues,
        "discovery": {
            "status": status,
            "methods": methods,
            "cli_version": None,
            "fallback_reason": fallback_reason,
            "excluded_counts": dict(sorted(excluded.items())),
            "component_coverage": coverage,
        },
    }
    _CACHE_RESULT = result
    SCAN_WARNINGS[:] = [issue["message"] for issue in issues
                        if issue.get("severity") in ("warning", "error")]
    return result


def skill_roots():
    result = _CACHE_RESULT or discover()
    return list(result["skill_roots"])


def iter_skills():
    result = _CACHE_RESULT or discover()
    return [dict(row) for row in result["skills"]]


def usage_stats_available(home=None):
    return (_home_path(home) / ".claude" / "projects").is_dir()


def usage_records(window_days, skills=None, home=None):
    """Aggregate strict transcript events against collect's canonical inventory."""
    USAGE_META.clear()
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    if skills is None:
        skills = (_CACHE_RESULT or discover())["skills"]
    resolver = usage.build_name_resolver(skills, AGENT)
    root = _home_path(home) / ".claude" / "projects"
    records, meta = usage.scan_claude_transcripts(window_days, resolver, roots=[root])

    # Lifetime data is supplementary only: it never creates unmatched/synthetic usage.
    lifetime = usage.extract_top_level_object(_home_path(home) / ".claude.json", "skillUsage")
    meta["lifetime_entries"] = len(lifetime)
    by_instance = {row.get("skill_instance_id"): row for row in records if row.get("matched")}
    for name, value in sorted(lifetime.items()):
        if not isinstance(value, dict) or not isinstance(value.get("usageCount"), int):
            continue
        resolved = resolver.resolve(name)
        if resolved["status"] != "matched":
            continue
        instance_id = resolved["candidate_instance_ids"][0]
        row = by_instance.get(instance_id)
        if row is None:
            skill = resolver.by_instance[instance_id]
            row = usage.empty_matched_record(skill)
            records.append(row)
            by_instance[instance_id] = row
        row["lifetime_count"] = value["usageCount"]
    records.sort(key=usage.record_sort_key)
    USAGE_META.update(meta)
    return records
