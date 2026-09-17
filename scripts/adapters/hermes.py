#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hermes 适配器（契约事实见 CONTRACT.md；S4 文档来源，本机未装——detect()=False 优雅跳过，代码备用）。

skill 根：$HERMES_HOME/skills/<category>/<skill>/SKILL.md（HERMES_HOME 是官方权威 resolver，勿硬编码；
        也容忍无类别层直接 <skill>/SKILL.md）。external_dirs/profile/项目级(需 trust)暂不扫，见 notes。
使用统计：$HERMES_HOME/state.db（SQLite，官方 schema）messages 表 tool_name='skill_view'。
        文档 schema_version 迭代快，本适配器全 try 包裹：查询失败 → 无使用统计 + warning，不崩。
        【注意】此路径本机未实测，装了 hermes 后先跑：
        sqlite3 ~/.hermes/state.db '.schema messages' 核对再迭代（S4 建议）。
"""
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import skillmd

AGENT = "hermes"
SCAN_WARNINGS = []
USAGE_META = {}
_CACHE = None
_NAME_RE = re.compile(r"skill_view['\"\\\s,]*['\"]([A-Za-z0-9_.\-]+)['\"]")


def _home():
    v = os.environ.get("HERMES_HOME")
    return Path(v) if v else Path.home() / ".hermes"


def detect():
    return _home().is_dir()


def skill_roots():
    r = _home() / "skills"
    return [str(r)] if r.is_dir() else []


def iter_skills():
    global _CACHE
    SCAN_WARNINGS.clear()
    out = []
    root = _home() / "skills"
    if not root.is_dir():
        _CACHE = out
        return out
    try:
        with os.scandir(str(root)) as it:
            tops = sorted(it, key=lambda e: e.name)
    except OSError as e:
        SCAN_WARNINGS.append("hermes: 无法列目录 %s（%s）" % (root, e))
        _CACHE = out
        return out
    for top in tops:  # <category>/<skill>/SKILL.md；top 自带 SKILL.md 则视为无类别层
        if top.name.startswith("."):
            continue
        tp = Path(top.path)
        if (tp / "SKILL.md").is_file():
            entry, warns = skillmd.scan_skill_dir(tp, AGENT, "user")
            out.append(entry)
            SCAN_WARNINGS.extend(warns)
            continue
        try:
            with os.scandir(str(tp)) as it:
                subs = sorted(it, key=lambda e: e.name)
        except OSError:
            continue
        for sub in subs:
            if sub.name.startswith("."):
                continue
            sp = Path(sub.path)
            if (sp / "SKILL.md").is_file():
                entry, warns = skillmd.scan_skill_dir(sp, AGENT, "user")
                out.append(entry)
                SCAN_WARNINGS.extend(warns)
    _CACHE = out
    return out


def usage_stats_available():
    return (_home() / "state.db").is_file()


def usage_records(window_days):
    USAGE_META.clear()
    if _CACHE is None:
        iter_skills()
    names = {e["name"] for e in _CACHE}
    db = _home() / "state.db"
    agg, sessions = {}, 0
    warns = []
    if not db.is_file():
        USAGE_META.update({"sessions_scanned": 0,
                           "coverage": {"transcripts_found": False, "skip_env_detected": False},
                           "warnings": ["hermes: state.db 不存在，使用统计不可用"]})
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    con = None
    try:  # 只读打开（WAL 库官方建议）；任何 schema 漂移都降级为 warning
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        con.row_factory = sqlite3.Row
        sessions = con.execute("SELECT COUNT(DISTINCT session_id) FROM messages").fetchone()[0]
        rows = con.execute(
            "SELECT timestamp, coalesce(tool_calls,'') AS tc, coalesce(content,'') AS c "
            "FROM messages WHERE tool_name = 'skill_view'").fetchall()
        for r in rows:
            ts = r["timestamp"]
            dt = None
            if isinstance(ts, (int, float)):  # 官方 schema 存 epoch 秒/毫秒的可能性都有
                dt = datetime.fromtimestamp(ts / (1000 if ts > 1e11 else 1), tz=timezone.utc)
            elif isinstance(ts, str):
                dt = usage_parse_iso(ts)
            if dt is None or dt < cutoff:
                continue
            for name in set(_NAME_RE.findall("%s %s" % (r["tc"], r["c"][:500]))):
                if name in names:
                    d = agg.setdefault(name, {"activations": 0, "first": None, "last": None})
                    d["activations"] += 1
                    ds = dt.date().isoformat()
                    d["first"] = ds if d["first"] is None or ds < d["first"] else d["first"]
                    d["last"] = ds if d["last"] is None or ds > d["last"] else d["last"]
    except (sqlite3.Error, ValueError, OverflowError, OSError) as e:
        warns.append("hermes: state.db 查询失败（%s），使用统计降级为不可用" % e)
        agg, sessions = {}, 0
    finally:
        if con is not None:
            con.close()
    recs = [{"skill_id": "%s::%s" % (AGENT, k), "activations": v["activations"],
             "last_seen": v["last"], "first_seen": v["first"]} for k, v in agg.items()]
    recs.sort(key=lambda r: (-r["activations"], r["skill_id"]))
    USAGE_META.update({"sessions_scanned": sessions, "warnings": warns,
                       "coverage": {"transcripts_found": sessions > 0, "skip_env_detected": False}})
    return recs


def usage_parse_iso(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
