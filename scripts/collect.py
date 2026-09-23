#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect canonical v2 component inventory and direct usage evidence.

Management probes and all audited inputs are read-only.  Writes are limited to
``--out-dir`` (including atomic temporary files created inside it).
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from adapters import ALL_AGENTS, get_adapters, make_issue, normalize_lexical_path, path_is_within

SCHEMA_VERSION = "2.0"
SCHEMA_NAME = "bulus-skill-auditor.inventory"

NOTES = {
    "claude-code": "当前插件只认管理 CLI 选中的 enabled installPath；标准独立根按 Claude 语义读取。",
    "codex": "优先采用 model-visible prompt probe；失败时独立根仅列 inferred/unknown。",
    "hermes": "实验性只读适配器；文件系统发现默认 inferred/unknown。",
}

_REQUIRED_COMPONENT_FIELDS = (
    "agent", "component_type", "runtime_name", "install_scope", "source_file",
    "source_realpath", "active_state", "discovery_confidence", "accounting",
)


def _validate_component(row):
    missing = [key for key in _REQUIRED_COMPONENT_FIELDS if key not in row]
    if missing:
        raise ValueError("component missing required fields: %s" % ",".join(missing))
    if row["component_type"] not in ("skill", "command", "agent"):
        raise ValueError("invalid component_type: %s" % row["component_type"])
    if row["active_state"] not in ("active", "unknown"):
        raise ValueError("invalid active_state: %s" % row["active_state"])
    if row["discovery_confidence"] not in ("runtime_probe", "management_cli", "known_root", "inferred"):
        raise ValueError("invalid discovery_confidence: %s" % row["discovery_confidence"])
    if not isinstance(row["runtime_name"], str) or not row["runtime_name"]:
        raise ValueError("runtime_name must be a non-empty string")
    if not isinstance(row["source_file"], str) or not os.path.isabs(row["source_file"]):
        raise ValueError("source_file must be absolute")


def finalize_skills(raw_skills):
    """Assign canonical instance/logical identities, conflicts, and stable order.

    Returns (rows, issues)；同一物理实例重复出现时保留首个并降级为结构化 issue
    （适配器隔离：重复是输入类，不中断整个多 Agent 采集）。
    """
    rows = []
    issues = []
    seen_instances = set()
    for original in raw_skills:
        row = dict(original)
        _validate_component(row)
        row["source_file"] = normalize_lexical_path(row["source_file"])
        row["source_realpath"] = normalize_lexical_path(
            row.get("source_realpath") or os.path.realpath(row["source_file"])
        )
        row["path"] = normalize_lexical_path(row.get("path") or Path(row["source_file"]).parent)
        row["realpath"] = normalize_lexical_path(
            row.get("realpath") or os.path.realpath(row["path"])
        )
        if row.get("symlink_target"):
            row["symlink_target"] = normalize_lexical_path(row["symlink_target"])
        runtime_name = row["runtime_name"]
        logical_id = "%s::%s" % (row["agent"], runtime_name)
        material = "\0".join([
            row["agent"], row["component_type"], runtime_name,
            row["install_scope"], row["source_file"], row["source_realpath"],
        ])
        instance_id = "%s::i::%s" % (
            row["agent"], hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        )
        if instance_id in seen_instances:
            # 同一物理实例被重复发现（如 probe 重复行/双根同目录）：保留首个、降级为
            # 结构化 issue 继续跑——中断整个多 Agent 采集违背适配器隔离设计
            issues.append(make_issue(
                "duplicate_instance_deduped", "warning", row.get("agent"), "discovery",
                "同一物理实例重复发现，已去重保留首个",
                safe_context={"instance_id": instance_id,
                              "runtime_name": runtime_name},
            ))
            continue
        seen_instances.add(instance_id)
        row["instance_id"] = instance_id
        row["id"] = logical_id
        row["logical_id"] = logical_id
        row["name"] = runtime_name
        row["conflict_group"] = None
        # Keep every contract field explicit even when an adapter has no value.
        for key in ("declared_name", "directory_name", "namespace", "plugin_id",
                    "plugin_name", "marketplace", "plugin_version", "manifest_declared"):
            row.setdefault(key, None)
        row.setdefault("component_name", runtime_name.rsplit(":", 1)[-1])
        row.setdefault("scope", "unknown")
        row.setdefault("source_kind", "standalone")
        row.setdefault("discovery_method", "unknown")
        row.setdefault("auditable", False)
        rows.append(row)
    counts = Counter((row["agent"], row["runtime_name"]) for row in rows)
    for row in rows:
        if counts[(row["agent"], row["runtime_name"])] > 1:
            row["conflict_group"] = row["logical_id"]
    rows.sort(key=lambda row: (
        row["agent"], row["runtime_name"], row["component_type"],
        row["source_file"], row["instance_id"],
    ))
    return rows, issues


def sort_issues(issues):
    severity = {"error": 0, "warning": 1, "info": 2}
    normalized = []
    for issue in issues:
        row = {
            "code": str(issue.get("code") or "unknown_issue"),
            "severity": issue.get("severity") if issue.get("severity") in severity else "warning",
            "agent": issue.get("agent"),
            "stage": issue.get("stage") or "parse",
            "message": str(issue.get("message") or "unspecified issue"),
            "path": issue.get("path"),
            "safe_context": dict(sorted((issue.get("safe_context") or {}).items())),
        }
        normalized.append(row)
    normalized.sort(key=lambda row: (
        severity[row["severity"]], str(row["agent"] or ""), row["stage"], row["code"],
        str(row["path"] or ""), row["message"],
        json.dumps(row["safe_context"], ensure_ascii=False, sort_keys=True),
    ))
    return normalized


def issues_to_warnings(issues):
    out = []
    for issue in issues:
        if issue.get("severity") not in ("warning", "error"):
            continue
        prefix = " ".join(str(value) for value in (
            issue.get("agent"), issue.get("stage"), issue.get("code"),
        ) if value)
        text = "%s: %s" % (prefix, issue.get("message") or "")
        if issue.get("path"):
            text += " (%s)" % issue["path"]
        out.append(text)
    return out


def _empty_coverage(status="unavailable", limitation=None):
    return {
        "status": status,
        "sessions_scanned": 0,
        "transcripts_found": False,
        "history_disabled": False,
        "files_unreadable": 0,
        "parse_errors": 0,
        "undated_events": 0,
        "direct_events": 0,
        "matched_activations": 0,
        "unmatched_activations": 0,
        "ambiguous_activations": 0,
        "limitations": [limitation] if limitation else [],
    }


def _to_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_coverage(meta, available):
    raw = meta.get("coverage") if isinstance(meta.get("coverage"), dict) else {}
    base = _empty_coverage("complete" if available else "unavailable")
    for key in base:
        if key in raw:
            base[key] = raw[key]
    # 读不出的会话文件/解析错误 = 覆盖不完整：complete 必须降级为 partial，不虚标覆盖面
    if base["status"] == "complete" and (
        _to_int(base.get("files_unreadable")) > 0 or _to_int(base.get("parse_errors")) > 0
    ):
        base["status"] = "partial"
    if isinstance(raw.get("skip_env_detected"), bool):
        base["history_disabled"] = raw["skip_env_detected"]
    base["sessions_scanned"] = int(meta.get("sessions_scanned", base["sessions_scanned"]) or 0)
    if not isinstance(base["limitations"], list):
        base["limitations"] = [str(base["limitations"])]
    return base


def _agent_meta(name, detected, result=None, usage_available=False):
    if not detected:
        return {
            "agent": name,
            "detected": False,
            "capabilities": {
                "scan": False, "usage_stats": False, "active_probe": False,
                "plugin_listing": False, "component_types": [],
            },
            "skill_roots": [],
            "notes": "未安装，跳过",
            "discovery": {
                "status": "unavailable", "methods": [], "cli_version": None,
                "fallback_reason": "agent_not_detected", "excluded_counts": {},
                "component_coverage": {"skill": 0, "command": 0, "agent": 0},
            },
        }
    result = result or {}
    discovery = result.get("discovery") or {}
    methods = discovery.get("methods") or []
    coverage = discovery.get("component_coverage") or {}
    component_types = [kind for kind in ("skill", "command", "agent") if coverage.get(kind, 0)]
    return {
        "agent": name,
        "detected": True,
        "capabilities": {
            "scan": bool(result.get("skill_roots")),
            "usage_stats": bool(usage_available),
            "active_probe": any("probe" in method for method in methods),
            "plugin_listing": any("plugin list" in method for method in methods),
            "component_types": component_types,
        },
        "skill_roots": sorted(set(result.get("skill_roots") or [])),
        "notes": NOTES.get(name, ""),
        "discovery": {
            "status": discovery.get("status", "unavailable"),
            "methods": list(methods),
            "cli_version": discovery.get("cli_version"),
            "fallback_reason": discovery.get("fallback_reason"),
            "excluded_counts": dict(sorted((discovery.get("excluded_counts") or {}).items())),
            "component_coverage": {
                kind: int(coverage.get(kind, 0) or 0) for kind in ("skill", "command", "agent")
            },
        },
    }


def _atomic_json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(temp_path, str(path))
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _usage_status(by_agent):
    statuses = [value.get("status") for value in by_agent.values()]
    complete = sum(1 for status in statuses if status == "complete")
    partial = sum(1 for status in statuses if status == "partial")
    if statuses and complete == len(statuses):
        return "complete"
    if complete or partial:
        return "partial"
    return "unavailable"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="只读采集多 Agent v2 组件清单与直接使用证据。")
    parser.add_argument("--agents", default=",".join(ALL_AGENTS),
                        help="逗号分隔的 agent 适配器（默认：%s）" % ",".join(ALL_AGENTS))
    parser.add_argument("--out-dir", default="./skill-audit-output",
                        help="唯一允许写入的输出目录")
    parser.add_argument("--json", default=None,
                        help="兼容别名输出；路径必须位于 --out-dir 内")
    parser.add_argument("--window-days", type=int, default=30,
                        help="使用统计窗口天数，必须为正整数（默认 30）")
    args = parser.parse_args(argv)

    if args.window_days <= 0:
        print("--window-days 必须是正整数", file=sys.stderr)
        return 2
    requested = [item.strip() for item in args.agents.split(",") if item.strip()]
    names = []
    for name in requested:
        if name not in names:
            names.append(name)
    unknown = [name for name in names if name not in ALL_AGENTS]
    if unknown:
        print("未知 agent: %s；可选：%s" % (",".join(unknown), ",".join(ALL_AGENTS)), file=sys.stderr)
        return 2

    out_dir = Path(normalize_lexical_path(args.out_dir))
    targets = [out_dir / "00-inventory.json"]
    if args.json:
        extra = Path(normalize_lexical_path(args.json))
        if not path_is_within(extra, out_dir):
            print("--json 必须位于 --out-dir 内", file=sys.stderr)
            return 2
        if extra not in targets:
            targets.append(extra)

    started = time.time()
    issues = []
    discoveries = {}
    detected = {}
    usage_available = {}
    raw_skills = []
    adapter_modules = {}

    for name, module in get_adapters(names):
        adapter_modules[name] = module
        try:
            present = bool(module.detect())
        except Exception as exc:  # adapter isolation: one failure never aborts other agents
            present = False
            issues.append(make_issue(
                "adapter_detect_failed", "warning", name, "discovery",
                "adapter detection failed; agent was treated as unavailable",
                safe_context={"error_type": type(exc).__name__},
            ))
        detected[name] = present
        if not present:
            usage_available[name] = False
            issues.append(make_issue(
                "agent_not_detected", "info", name, "discovery",
                "agent runtime directory was not detected",
            ))
            continue
        try:
            result = module.discover()
        except Exception as exc:
            result = {
                "skills": [], "skill_roots": [], "issues": [],
                "discovery": {
                    "status": "unavailable", "methods": [], "cli_version": None,
                    "fallback_reason": "adapter_exception", "excluded_counts": {},
                    "component_coverage": {"skill": 0, "command": 0, "agent": 0},
                },
            }
            issues.append(make_issue(
                "adapter_discovery_failed", "warning", name, "discovery",
                "adapter discovery failed; other agents continued",
                safe_context={"error_type": type(exc).__name__},
            ))
        discoveries[name] = result
        issues.extend(result.get("issues") or [])
        raw_skills.extend(result.get("skills") or [])
        try:
            usage_available[name] = bool(module.usage_stats_available())
        except Exception:
            usage_available[name] = False

    try:
        skills, finalize_issues = finalize_skills(raw_skills)
        issues.extend(finalize_issues)
    except (KeyError, TypeError, ValueError) as exc:
        print("致命：inventory schema 内部不一致（%s）" % exc, file=sys.stderr)
        return 2

    agents_meta = [
        _agent_meta(name, detected.get(name, False), discoveries.get(name), usage_available.get(name, False))
        for name in names
    ]
    by_agent_skills = {name: [row for row in skills if row["agent"] == name] for name in names}
    usage_rows = []
    coverage_by_agent = {}

    for name in names:
        if not detected.get(name):
            coverage_by_agent[name] = _empty_coverage("unavailable", "agent not detected")
            continue
        module = adapter_modules[name]
        try:
            rows = module.usage_records(args.window_days, skills=by_agent_skills[name])
            meta = dict(getattr(module, "USAGE_META", {}) or {})
            coverage_by_agent[name] = _normalize_coverage(meta, usage_available.get(name, False))
            usage_rows.extend(rows)
            issues.extend(meta.get("issues") or [])
            for warning in meta.get("warnings") or []:
                issues.append(make_issue(
                    "usage_warning", "warning", name, "usage", str(warning),
                ))
        except Exception as exc:
            coverage_by_agent[name] = _empty_coverage("unavailable", "usage parser failed")
            issues.append(make_issue(
                "adapter_usage_failed", "warning", name, "usage",
                "usage parser failed; inventory collection continued",
                safe_context={"error_type": type(exc).__name__},
            ))

    usage_rows.sort(key=lambda row: (
        str(row.get("agent") or ""), str(row.get("record_id") or ""),
        str(row.get("skill_instance_id") or ""),
    ))
    issues = sort_issues(issues)
    sessions = sum(int(value.get("sessions_scanned", 0) or 0) for value in coverage_by_agent.values())
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "schema_name": SCHEMA_NAME,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scan_seconds": round(time.time() - started, 3),
        "agents": agents_meta,
        "skills": skills,
        "usage": {
            "window_days": args.window_days,
            "window_note": "只统计严格顶层直接事件；无时间戳事件只进入 coverage，窗口外事件忽略。",
            "sessions_scanned": sessions,
            "records": usage_rows,
            "coverage": {
                "status": _usage_status(coverage_by_agent),
                "transcripts_found": any(bool(value.get("transcripts_found"))
                                         for value in coverage_by_agent.values()),
                "skip_env_detected": any(bool(value.get("history_disabled"))
                                          for value in coverage_by_agent.values()),
                "by_agent": {name: coverage_by_agent[name] for name in names},
            },
        },
        "issues": issues,
        "warnings": issues_to_warnings(issues),
    }

    try:
        for target in targets:
            _atomic_json_write(target, inventory)
    except OSError as exc:
        print("致命：输出目录写不进（%s）" % exc, file=sys.stderr)
        return 2

    counts = Counter(row["agent"] for row in skills)
    summary = ", ".join("%s(%s, %d components)" % (
        item["agent"], "检出" if item["detected"] else "未装", counts[item["agent"]],
    ) for item in agents_meta)
    print("[collect] agents: %s" % summary)
    print("[collect] components %d；usage records %d；sessions %d；window %d days" % (
        len(skills), len(usage_rows), sessions, args.window_days,
    ))
    print("[collect] issues %d；耗时 %.3fs" % (len(issues), inventory["scan_seconds"]))
    for target in targets:
        print("[collect] 输出 → %s" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
