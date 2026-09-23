#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experimental read-only Hermes adapter.

No runtime authority probe exists yet, so filesystem discovery stays
``active_state=unknown`` / ``discovery_confidence=inferred`` and must not be reported
as confirmed-active inventory.  SQLite usage parsing degrades to structured issues.
"""
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import usage
from . import make_issue, normalize_lexical_path
from . import skillmd

AGENT = "hermes"
SCAN_WARNINGS = []
USAGE_META = {}
_CACHE_RESULT = None
_NAME_RE = re.compile(r"skill_view['\"\\\s,]*['\"]([A-Za-z0-9_.\-]+)['\"]")
_VALID_DECLARED_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _home(home=None):
    if home is not None:
        return Path(home)
    value = os.environ.get("HERMES_HOME")
    return Path(value) if value else Path.home() / ".hermes"


def detect(home=None):
    return _home(home).is_dir()


def _valid_declared_name(name):
    return isinstance(name, str) and bool(_VALID_DECLARED_NAME.match(name))


def _content_issues(raw_issues, path):
    return [make_issue(
        item.get("code", "component_parse_failed"), "warning", AGENT, "parse",
        item.get("message", "component could not be parsed"),
        path=item.get("path") or path,
        safe_context=item.get("safe_context") or {},
    ) for item in raw_issues]


def _decorate(fact, runtime_name, scope, install_scope, source_kind):
    auditable = os.path.isfile(fact["source_file"]) and _valid_declared_name(fact.get("declared_name"))
    if not auditable:
        listing = trigger = "excluded"
        reason = "declared name missing/invalid or source unreadable"
    else:
        listing = trigger = "estimated"
        reason = "inferred candidate; hermes runtime activation is unknown"
    fact.update({
        "agent": AGENT,
        "name": runtime_name,
        "runtime_name": runtime_name,
        "component_name": runtime_name,
        "namespace": None,
        "scope": scope,
        "install_scope": install_scope,
        "source_kind": source_kind,
        "active_state": "unknown",
        "discovery_confidence": "inferred",
        "discovery_method": "hermes filesystem scan (experimental)",
        "plugin_id": None,
        "plugin_name": None,
        "marketplace": None,
        "plugin_version": None,
        "manifest_declared": None,
        "auditable": auditable,
        "accounting": {"listing": listing, "trigger": trigger, "reason": reason},
    })
    return fact


def _skill_files(root):
    """Collect <category>/<skill>/SKILL.md plus optional category-less entries."""
    out = []
    try:
        tops = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError:
        return out
    for top in tops:
        if top.name.startswith("."):
            continue
        if top.is_file() and top.name == "SKILL.md":
            out.append(top)
            continue
        if not top.is_dir():
            continue
        if (top / "SKILL.md").is_file():
            out.append(top / "SKILL.md")
            continue
        try:
            subs = sorted(top.iterdir(), key=lambda path: path.name)
        except OSError:
            continue
        for sub in subs:
            if sub.name.startswith(".") or not sub.is_dir():
                continue
            if (sub / "SKILL.md").is_file():
                out.append(sub / "SKILL.md")
    return out


def discover(home=None, cwd=None, runner=None):
    """Scan the Hermes home read-only; results are inferred candidates only."""
    global _CACHE_RESULT
    home = _home(home)
    issues = []
    excluded = defaultdict(int)
    rows = []
    roots = []
    skills_root = home / "skills"
    if skills_root.is_dir():
        roots.append(str(normalize_lexical_path(skills_root)))
    for source in _skill_files(skills_root):
        fact, raw_issues = skillmd.scan_component(source, "skill")
        issues.extend(_content_issues(raw_issues, source))
        declared = fact.get("declared_name")
        if not _valid_declared_name(declared):
            excluded["invalid_declared_name"] += 1
            issues.append(make_issue(
                "hermes_declared_name_invalid", "warning", AGENT, "parse",
                "inferred candidate omitted because frontmatter name is missing or invalid",
                path=source,
            ))
            continue
        rows.append(_decorate(fact, declared, "user", "user", "standalone"))
    rows.sort(key=lambda row: (row["runtime_name"], row["component_type"], row["source_file"]))
    status = "complete" if skills_root.is_dir() else "unavailable"
    if not skills_root.is_dir():
        issues.append(make_issue(
            "hermes_home_missing", "info", AGENT, "discovery",
            "hermes skills root was not found",
        ))
    result = {
        "skills": rows,
        "skill_roots": sorted(set(roots)),
        "issues": issues,
        "discovery": {
            "status": status,
            "methods": ["hermes filesystem scan (experimental)"],
            "cli_version": None,
            "fallback_reason": None if skills_root.is_dir() else "skills_root_missing",
            "excluded_counts": dict(sorted(excluded.items())),
            "component_coverage": {"skill": len(rows), "command": 0, "agent": 0},
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
    return (_home(home) / "state.db").is_file()


def usage_records(window_days, skills=None, home=None):
    USAGE_META.clear()
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    if skills is None:
        skills = (_CACHE_RESULT or discover())["skills"]
    resolver = usage.build_name_resolver(skills, AGENT)
    db = _home(home) / "state.db"
    if not db.is_file():
        coverage = {
            "status": "unavailable", "sessions_scanned": 0, "transcripts_found": False,
            "history_disabled": False, "files_unreadable": 0, "parse_errors": 0,
            "undated_events": 0, "direct_events": 0, "matched_activations": 0,
            "unmatched_activations": 0, "ambiguous_activations": 0,
            "limitations": ["state.db 不存在，使用统计不可用"],
        }
        USAGE_META.update({"sessions_scanned": 0, "coverage": coverage, "warnings": [], "issues": []})
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    con = None
    sessions = 0
    rows = []
    issues = []
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        con.row_factory = sqlite3.Row
        sessions = con.execute("SELECT COUNT(DISTINCT session_id) FROM messages").fetchone()[0]
        rows = con.execute(
            "SELECT timestamp, coalesce(tool_calls,'') AS tc, coalesce(content,'') AS c "
            "FROM messages WHERE tool_name = 'skill_view'").fetchall()
    except (sqlite3.Error, ValueError, OverflowError, OSError) as exc:
        issues.append(make_issue(
            "hermes_usage_query_failed", "warning", AGENT, "usage",
            "state.db 查询失败，使用统计降级为不可用",
            safe_context={"error_type": type(exc).__name__},
        ))
        rows = []
        sessions = 0
    finally:
        if con is not None:
            con.close()
    agg = usage._Aggregator(AGENT)
    undated = 0
    parse_errors = 0
    for row in rows:
        timestamp = row["timestamp"]
        dt = None
        if isinstance(timestamp, (int, float)):
            try:
                dt = datetime.fromtimestamp(timestamp / (1000 if timestamp > 1e11 else 1),
                                            tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                dt = None
        elif isinstance(timestamp, str):
            dt = usage.parse_iso(timestamp)
        names = set()
        try:
            names = set(_NAME_RE.findall("%s %s" % (row["tc"], row["c"][:500])))
        except (TypeError, ValueError):
            parse_errors += 1
        for name in sorted(names):
            agg.direct_events += 1
            if dt is None:
                undated += 1
                continue
            if dt < cutoff:
                continue
            result = resolver.resolve(name)
            agg.add(result, "skill_view", name, dt, name)
    matched, unmatched, ambiguous = agg.counts()
    coverage = {
        "status": "complete" if sessions else "unavailable",
        "sessions_scanned": sessions,
        "transcripts_found": bool(sessions),
        "history_disabled": False,
        "files_unreadable": 0,
        "parse_errors": parse_errors,
        "undated_events": undated,
        "direct_events": agg.direct_events,
        "matched_activations": matched,
        "unmatched_activations": unmatched,
        "ambiguous_activations": ambiguous,
        "limitations": [],
    }
    if not sessions:
        coverage["limitations"].append("state.db 无会话记录，无法区分零使用与数据不可用")
    USAGE_META.update({"sessions_scanned": sessions, "coverage": coverage,
                       "warnings": [], "issues": issues})
    return agg.records()
