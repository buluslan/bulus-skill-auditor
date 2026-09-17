#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codex 适配器（契约事实见 CONTRACT.md「各适配器事实」节，S4 实测）。

skill 根（多根设计，竞品 janitor 恰好漏了 r0/.system/plugins）：
  ~/.codex/skills（r0，user）+ ~/.agents/skills（r1 跨 agent 共享，user）
  + ~/.codex/skills/.system（r2 系统 skill，scope 记 user）+ ~/.codex/plugins/cache/**/skills*（plugin）
  + $CWD/.agents/skills（REPO scope → project；与已有根同实体时去重）。
使用统计：~/.codex/sessions/**/rollout-*.jsonl（+archived_sessions）里 function_call/custom_tool_call
的命令行中出现的 /…/skills/<name>/SKILL.md 绝对路径（usage.scan_codex_rollouts）。
"""
import os
from pathlib import Path

import usage
from . import plugin_skill_dirs
from . import skillmd

AGENT = "codex"
SCAN_WARNINGS = []
USAGE_META = {}
_CACHE = None


def detect():
    return (Path.home() / ".codex").is_dir()


def _scoped_roots():
    home = Path.home()
    candidates = [
        (home / ".codex" / "skills", "user"),
        (home / ".agents" / "skills", "user"),
        (home / ".codex" / "skills" / ".system", "user"),
        (Path.cwd() / ".agents" / "skills", "project"),
    ]
    roots, seen = [], set()
    for p, scope in candidates:
        if not p.is_dir():
            continue
        rp = os.path.realpath(str(p))
        if rp in seen:
            continue
        seen.add(rp)
        roots.append((p, scope))
    for p in plugin_skill_dirs(home / ".codex" / "plugins" / "cache"):
        roots.append((p, "plugin"))
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
            SCAN_WARNINGS.append("codex: 无法列目录 %s（%s）" % (root, e))
            continue
        for ent in children:
            if ent.name.startswith("."):
                continue
            p = Path(ent.path)
            if not (p / "SKILL.md").is_file():
                continue
            entry, warns = skillmd.scan_skill_dir(p, AGENT, scope)
            out.append(entry)
            SCAN_WARNINGS.extend(warns)
    _CACHE = out
    return out


def usage_stats_available():
    return (Path.home() / ".codex" / "sessions").is_dir()


def usage_records(window_days):
    USAGE_META.clear()
    if _CACHE is None:
        iter_skills()
    lookup = {}
    for e in _CACHE:  # 字面路径 + realpath 双形态都能命中（usage 痕迹里是绝对路径）
        lookup[e["path"]] = e["id"]
        for alt in (os.path.realpath(e["path"]), e.get("symlink_target")):
            if alt:
                lookup.setdefault(alt, e["id"])

    def resolve_path(skill_md_path):  # "/…/skills/<name>/SKILL.md" → skill_id
        d = skill_md_path[: -len("/SKILL.md")]
        return lookup.get(d) or lookup.get(os.path.realpath(d))

    recs, meta = usage.scan_codex_rollouts(window_days, resolve_path)
    USAGE_META.update(meta)
    return recs
