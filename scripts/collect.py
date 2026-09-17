#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect.py — 采集层主入口：编排各 agent 适配器 → 输出 00-inventory.json（格式契约见 ../CONTRACT.md）。

用法：
  python3 scripts/collect.py [--agents claude-code,codex,hermes] [--out-dir DIR] [--json PATH] [--window-days N]

对被扫描对象（skill 目录 / 会话记录 / ~/.claude.json）100% 只读；写只进输出目录。
失败降级不崩（记 warnings，退出码仍 0）；唯一致命 = 输出目录写不进（退出码 2）。

本机实测（2026-09-17，macOS Darwin 25.6.0，Python 3.9.6）：
  python3 scripts/collect.py --out-dir /tmp/sa-test-a/
  → agents 3：claude-code（检出）/ codex（检出）/ hermes（未装跳过）
  → skills 255 条：claude-code 140（user 118 = ~/.claude/skills 117 + ~/.claude/agents/skills 1（web-access）
                    + plugin 22，跨根同名去重 40）
                  codex 115（~/.codex/skills + ~/.agents/skills + .system + plugins，同名去重 45）
  → usage：会话文件 688 个（claude 563 含嵌套 subagents/ + codex 125），30 天窗口记录 65 条
    （web-access 的 7 次使用在第 4 根并入后正确匹配）；
    其中 56 条带 ~/.claude.json skillUsage 的 lifetime_count（85 条终身计数里 56 条匹配到已扫描 skill），
    42 条为"仅终身计数、窗口内 0 激活"（最重×最少用优先级排序的关键输入）
  → warnings 87 条（85 跨根同名 + 1 未匹配使用 10 次 + 1 hermes 未装）；耗时 1.5~2.3 秒
（数字随机器状态漂移，重跑以实际输出为准）
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from adapters import ALL_AGENTS, get_adapters

NOTES = {
    "claude-code": "skill listing 注入预算约 1% context 窗口；判据见 references/audit-rubric.md",
    "codex": "listing 预算 min(2% context, 8000 字符)，超载先截短描述再丢条目（官方文档）；"
             "含 ~/.codex/skills/.system 系统 skill（scope 记 user）",
    "hermes": "三级懒加载（skills_list/skill_view），无 listing 截断（文档来源，本机未实测）；"
              "external_dirs/profile/项目级(需 trust) 未扫",
}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="skill 清单采集：多 agent 适配器扫描 + 使用统计 → 00-inventory.json。只读审计。")
    ap.add_argument("--agents", default=",".join(ALL_AGENTS),
                    help="逗号分隔的 agent 适配器（默认全开：%s）" % ",".join(ALL_AGENTS))
    ap.add_argument("--out-dir", default="./skill-audit-output",
                    help="输出目录（默认 ./skill-audit-output/，00-inventory.json 写在这里）")
    ap.add_argument("--json", default=None,
                    help="机器可读结果另存到该路径（00-inventory.json 始终写进 out-dir）")
    ap.add_argument("--window-days", type=int, default=30, help="使用统计窗口天数（默认 30）")
    args = ap.parse_args(argv)

    names = [x.strip() for x in args.agents.split(",") if x.strip()]
    unknown = [n for n in names if n not in ALL_AGENTS]
    if unknown:
        print("未知 agent: %s；可选：%s" % (",".join(unknown), ",".join(ALL_AGENTS)), file=sys.stderr)
        return 2

    t0 = time.time()
    agents_meta, skills, warnings = [], [], []
    usage_records, sessions = [], 0
    transcripts_found = False
    skip_env = False
    counts = {}

    for name, mod in get_adapters(names):
        if not mod.detect():
            agents_meta.append({"agent": name, "detected": False,
                                "capabilities": {"scan": False, "usage_stats": False},
                                "skill_roots": [], "notes": "未安装，跳过"})
            warnings.append("%s: 未安装，跳过" % name)
            continue
        roots = mod.skill_roots()
        cap_usage = bool(mod.usage_stats_available())
        agents_meta.append({"agent": name, "detected": True,
                            "capabilities": {"scan": bool(roots), "usage_stats": cap_usage},
                            "skill_roots": roots, "notes": NOTES.get(name, "")})
        # --- 清单扫描（id 去重：同名 skill 在多个根出现时保留首个并记 warning）---
        by_id = {}
        for entry in mod.iter_skills():
            sid = entry["id"]
            if sid in by_id:
                warnings.append("%s: %s 重复出现（%s 与 %s），保留首个" % (
                    name, sid, by_id[sid]["path"], entry["path"]))
                continue
            by_id[sid] = entry
        skills.extend(by_id.values())
        counts[name] = len(by_id)
        warnings.extend("%s: %s" % (name, w) for w in getattr(mod, "SCAN_WARNINGS", []))
        # --- 使用统计（claude-code 双源：transcripts 窗口 + skillUsage 终身计数）---
        recs = mod.usage_records(args.window_days)
        meta = dict(getattr(mod, "USAGE_META", {}))
        usage_records.extend(recs)
        sessions += meta.get("sessions_scanned", 0)
        cov = meta.get("coverage", {})
        transcripts_found = transcripts_found or bool(cov.get("transcripts_found"))
        skip_env = skip_env or bool(cov.get("skip_env_detected"))
        warnings.extend("%s usage: %s" % (name, w) for w in meta.get("warnings", []))

    usage_records.sort(key=lambda r: (-r.get("activations", 0), r["skill_id"]))
    inventory = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scan_seconds": round(time.time() - t0, 1),
        "agents": agents_meta,
        "skills": skills,
        "usage": {
            "window_days": args.window_days,
            "window_note": "Claude Code transcripts 默认保留约 30 天，统计仅覆盖此窗口；"
                           "终身计数来自 ~/.claude.json skillUsage（官方静态文件，lifetime_count）",
            "sessions_scanned": sessions,
            "records": usage_records,
            "coverage": {"transcripts_found": transcripts_found, "skip_env_detected": skip_env},
        },
        "warnings": warnings,
    }

    out_dir = Path(args.out_dir)
    targets = [out_dir / "00-inventory.json"]
    if args.json:
        targets.append(Path(args.json))
    try:
        for t in targets:
            t.parent.mkdir(parents=True, exist_ok=True)
            with open(t, "w", encoding="utf-8") as fh:
                json.dump(inventory, fh, ensure_ascii=False, indent=2)
    except OSError as e:
        print("致命：输出目录写不进（%s）" % e, file=sys.stderr)
        return 2

    det = ", ".join("%s(%s, %d skills)" % (a["agent"], "检出" if a["detected"] else "未装",
                                           counts.get(a["agent"], 0)) for a in agents_meta)
    print("[collect] agents: %s" % det)
    print("[collect] skills 共 %d 条；usage: 会话文件 %d 个, 记录 %d 条（窗口 %d 天）"
          % (len(skills), sessions, len(usage_records), args.window_days))
    print("[collect] warnings %d 条；耗时 %.1fs" % (len(warnings), inventory["scan_seconds"]))
    for t in targets:
        print("[collect] 输出 → %s" % t.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
