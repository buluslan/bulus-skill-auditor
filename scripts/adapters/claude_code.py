#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""claude-code 适配器（契约事实见 CONTRACT.md「各适配器事实」节）。

skill 根：~/.claude/skills（user，symlink 跟到实体）+ ~/.claude/plugins/cache/**/skills*（plugin）
        + $CWD/.claude/skills（project，与 user 同实体时去重）。
使用统计双源：
  ① ~/.claude.json 顶层 skillUsage（name → {usageCount, lastUsedAt}，终身计数，流式抽字段不整文件 load）
    → usage.records 的 lifetime_count。pluginUsage 不读（其 lastUsedAt 有安装种子化陷阱，S1）。
  ② transcripts 窗口扫描（usage.scan_claude_transcripts）→ activations/first_seen/last_seen。
"""
import os
from pathlib import Path

import usage
from . import plugin_skill_dirs
from . import skillmd

AGENT = "claude-code"
SCAN_WARNINGS = []   # iter_skills() 每次重置并填充
USAGE_META = {}      # usage_records() 每次重置并填充
_CACHE = None        # iter_skills() 结果缓存，供 usage 阶段复用


def detect():
    return (Path.home() / ".claude").is_dir()


def _scoped_roots():
    home = Path.home()
    roots = []
    user = home / ".claude" / "skills"
    if user.is_dir():
        roots.append((user, "user"))
    agents_root = home / ".claude" / "agents" / "skills"  # 第 4 根：~/.claude/agents/skills（本机实测实际加载，如 web-access）
    if agents_root.is_dir():
        roots.append((agents_root, "user"))
    for p in plugin_skill_dirs(home / ".claude" / "plugins" / "cache"):
        roots.append((p, "plugin"))
    proj = Path.cwd() / ".claude" / "skills"
    if proj.is_dir() and os.path.realpath(str(proj)) != os.path.realpath(str(user)):
        roots.append((proj, "project"))
    return roots


def skill_roots():
    return [str(p) for p, _scope in _scoped_roots()]


def iter_skills():
    global _CACHE
    SCAN_WARNINGS.clear()
    out = []
    for root, scope in _scoped_roots():
        try:
            with os.scandir(str(root)) as it:
                children = sorted(it, key=lambda e: e.name)
        except OSError as e:
            SCAN_WARNINGS.append("claude-code: 无法列目录 %s（%s）" % (root, e))
            continue
        for ent in children:
            if ent.name.startswith("."):
                continue
            p = Path(ent.path)
            if not (p / "SKILL.md").is_file():  # is_file 会跟 symlink，目录级软链同样算数
                continue
            entry, warns = skillmd.scan_skill_dir(p, AGENT, scope)
            out.append(entry)
            SCAN_WARNINGS.extend(warns)
    _CACHE = out
    return out


def usage_stats_available():
    return (Path.home() / ".claude" / "projects").is_dir()


def usage_records(window_days):
    USAGE_META.clear()
    if _CACHE is None:
        iter_skills()
    names = {e["name"] for e in _CACHE}

    def resolve(n):  # Skill 工具入参/slash 命令名 → skill_id（容忍 plugin 前缀形态）
        if n in names:
            return "%s::%s" % (AGENT, n)
        tail = n.rsplit(":", 1)[-1]
        if tail in names:
            return "%s::%s" % (AGENT, tail)
        return None

    recs, meta = usage.scan_claude_transcripts(window_days, resolve)
    merged = {r["skill_id"]: dict(r) for r in recs}

    # 源①：~/.claude.json skillUsage → lifetime_count（查找按全名回退裸名）
    su = usage.extract_top_level_object(Path.home() / ".claude.json", "skillUsage")
    meta["lifetime_entries"] = len(su)
    for k, v in su.items():
        if not isinstance(v, dict) or not isinstance(v.get("usageCount"), int):
            continue
        name = None
        if k in names:
            name = k
        else:
            tail = k.rsplit(":", 1)[-1]
            if tail != k and tail in names:
                name = tail
        if name is None:
            continue
        sid = "%s::%s" % (AGENT, name)
        if sid not in merged:
            merged[sid] = {"skill_id": sid, "activations": 0,
                           "last_seen": None, "first_seen": None}
        merged[sid]["lifetime_count"] = v["usageCount"]

    out = sorted(merged.values(), key=lambda r: (-r.get("activations", 0), r["skill_id"]))
    USAGE_META.update(meta)
    return out
