#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent 适配器注册表。新 agent = 新适配器文件 + 在 REGISTRY 加一行，边际成本一个文件。

统一接口（每个适配器模块必须实现）：
  detect() -> bool                 本机是否装了这家 agent（根目录存在）
  skill_roots() -> [path]          skill 根目录列表（只列真实存在的）
  iter_skills() -> [dict]          契约 skills[] 条目；扫描告警写入模块级 SCAN_WARNINGS
  usage_records(window_days) -> [dict]
                                   契约 usage.records 条目（每 skill 一条聚合记录）；
                                   sessions_scanned/coverage 等元信息写入模块级 USAGE_META

适配器对被扫描对象 100% 只读。
"""
import os
from pathlib import Path


def plugin_skill_dirs(cache_dir, max_depth=5):
    """在 plugins/cache 目录下找名为 skills* 的目录（claude-code 与 codex 同构，共享此发现逻辑）。

    实测形态（2026-09-17 本机）：cache/<org>/<plugin>/<ver>/skills 与 cache/<org>/<plugin>/<hash>/skills，
    深度不一，故做限深 DFS 而非固定 glob。
    """
    out = []
    base = Path(cache_dir)
    if not base.is_dir():
        return out

    def walk(d, depth):
        if depth > max_depth:
            return
        try:
            with os.scandir(str(d)) as it:
                children = sorted(it, key=lambda e: e.name)
        except OSError:
            return
        for ent in children:
            if not ent.is_dir():
                continue
            if ent.name.startswith("skills"):
                out.append(Path(ent.path))
            else:
                walk(ent.path, depth + 1)

    walk(base, 1)
    return out


# 适配器导入放在 plugin_skill_dirs 定义之后（适配器会 from . import 它，避免部分初始化循环导入）
from . import claude_code, codex, hermes  # noqa: F401,E402

REGISTRY = {
    "claude-code": claude_code,
    "codex": codex,
    "hermes": hermes,
}
ALL_AGENTS = ["claude-code", "codex", "hermes"]


def get_adapters(names):
    """按名字取适配器列表 [(name, module)]；未知名直接 KeyError（调用方先校验）。"""
    return [(n, REGISTRY[n]) for n in names]
