#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""usage.py — skill 使用统计（transcripts 流式扫描 + ~/.claude.json skillUsage 抽取）。

被 collect.py 调用（from adapters import ... 后各适配器再调本模块），也可独立跑：
  python3 scripts/usage.py [--window-days 30] [--agents claude-code,codex,hermes] [--json out.json]

数据源（S1/S4 事实）：
  claude-code transcripts: ~/.claude/projects/**/*.jsonl
    - Skill 工具调用：assistant 消息 content[] 里的 {"type":"tool_use","name":"Skill","input":{"skill":…}}
    - slash 调用：user 行 content 里的 <command-name>/<name></command-name>（须匹配已知 skill 名，防内置命令误计）
  codex rollouts: ~/.codex/sessions/**/rollout-*.jsonl（+ ~/.codex/archived_sessions/）
    - response_item.payload.type ∈ {function_call, custom_tool_call} 且命令行含 /…/skills/<name>/SKILL.md 绝对路径
    - world_state.host_skills 是 listing 注入快照（不算使用）；旧版 listing 嵌在 session_meta 里（同样不算）
  claude-code 终身计数：~/.claude.json 顶层 skillUsage（流式抽字段，不整文件 load；pluginUsage 不读，S1 种子化陷阱）

工程约束：jsonl 很大（本机 ~/.claude/projects 540MB）→ 流式逐行 + 子串预过滤，绝不整体 load；
单行/单文件解析失败跳过并计入 warnings（meta），不崩。对被扫描对象 100% 只读。

本机实测（2026-09-17）：数字见 collect.py 头注。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_CMD_RE = re.compile(r"<command-name>/([A-Za-z0-9_.\-:]+)</command-name>")
_TS_RE = re.compile(r'"timestamp":"([^"]+)"')
_CODEX_SKILL_RE = re.compile(r"(/[^\s\"'\\]+/skills/([^/\s\"'\\]+)/SKILL\.md)")


def parse_iso(ts):
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _bump(agg, sid, dt):
    d = agg.setdefault(sid, {"activations": 0, "first": None, "last": None})
    d["activations"] += 1
    ds = dt.date().isoformat()
    if d["first"] is None or ds < d["first"]:
        d["first"] = ds
    if d["last"] is None or ds > d["last"]:
        d["last"] = ds


def _records(agg):
    out = [{"skill_id": k, "activations": v["activations"], "last_seen": v["last"],
            "first_seen": v["first"]} for k, v in agg.items()]
    out.sort(key=lambda r: (-r["activations"], r["skill_id"]))
    return out


def _meta(label, files, unreadable, bad_lines, undated, unmatched, found):
    w = []
    if unreadable:
        w.append("%s: %d 个会话文件读不了，已跳过" % (label, unreadable))
    if bad_lines:
        w.append("%s: %d 行有使用痕迹但解析不出结构，已跳过" % (label, bad_lines))
    if undated:
        w.append("%s: %d 行无有效时间戳，不计入窗口统计" % (label, undated))
    if unmatched:
        w.append("%s: %d 次使用引用了未扫描到的 skill（可能已删除/换名），未计入" % (label, unmatched))
    skip_env = os.environ.get("CLAUDE_CODE_SKIP_PROMPT_HISTORY") not in (None, "", "0", "false")
    return {"sessions_scanned": files, "warnings": w,
            "coverage": {"transcripts_found": found, "skip_env_detected": skip_env}}


def _claude_skill_tool(line):
    """解析一行里的 Skill tool_use，返回 (datetime, [skill 名])；行 JSON 坏 → None。"""
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    names = []
    msg = obj.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Skill":
                    inp = c.get("input")
                    if isinstance(inp, dict) and isinstance(inp.get("skill"), str):
                        names.append(inp["skill"])
    return parse_iso(obj.get("timestamp")), names


def scan_claude_transcripts(window_days, resolve):
    """resolve(name) -> skill_id 或 None。返回 (records, meta)。流式逐行。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    root = Path.home() / ".claude" / "projects"
    agg, files, unreadable, bad_lines, undated, unmatched = {}, 0, 0, 0, 0, 0
    if not root.is_dir():
        return [], _meta("claude-code", 0, 0, 0, 0, 0, False)
    for fp in sorted(root.rglob("*.jsonl")):
        files += 1
        try:
            fh = open(fp, "r", encoding="utf-8", errors="replace")
        except OSError:
            unreadable += 1
            continue
        try:
            with fh:
                for line in fh:
                    if '"name":"Skill"' in line:
                        parsed = _claude_skill_tool(line)
                        if parsed is None:
                            bad_lines += 1
                            continue
                        dt, names = parsed
                    elif "<command-name>" in line and '"type":"user"' in line:
                        m = _TS_RE.search(line)
                        dt = parse_iso(m.group(1) if m else None)
                        names = _CMD_RE.findall(line)
                    else:
                        continue
                    if dt is None:
                        undated += len(names) if names else 1
                        continue
                    if dt < cutoff:
                        continue
                    for n in names:
                        sid = resolve(n)
                        if sid is None:
                            # 只把 Skill 工具调用的未匹配当信号（已删/换名/内置）；
                            # slash 命令未匹配多为 /model /compact 等内置命令，不计数防噪音
                            if '"name":"Skill"' in line:
                                unmatched += 1
                        else:
                            _bump(agg, sid, dt)
        except OSError:
            unreadable += 1
    return _records(agg), _meta("claude-code", files, unreadable, bad_lines, undated, unmatched, True)


def scan_codex_rollouts(window_days, resolve_path):
    """resolve_path('/…/skills/<name>/SKILL.md') -> skill_id 或 None。返回 (records, meta)。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    home = Path.home() / ".codex"
    agg, files, unreadable, undated, unmatched = {}, 0, 0, 0, 0
    roots = [home / "sessions", home / "archived_sessions"]
    any_found = False
    for root in roots:
        if not root.is_dir():
            continue
        any_found = True
        for fp in sorted(root.rglob("rollout-*.jsonl")):
            files += 1
            try:
                fh = open(fp, "r", encoding="utf-8", errors="replace")
            except OSError:
                unreadable += 1
                continue
            try:
                with fh:
                    for line in fh:
                        if "SKILL.md" not in line:
                            continue
                        if '"function_call"' not in line and '"custom_tool_call"' not in line:
                            continue  # world_state/session_meta 里的 listing 是注入快照，不是使用
                        m = _TS_RE.search(line)
                        dt = parse_iso(m.group(1) if m else None)
                        if dt is None:
                            undated += 1
                            continue
                        if dt < cutoff:
                            continue
                        for full, _name in set(_CODEX_SKILL_RE.findall(line)):
                            sid = resolve_path(full)
                            if sid is None:
                                unmatched += 1
                            else:
                                _bump(agg, sid, dt)
            except OSError:
                unreadable += 1
    return _records(agg), _meta("codex", files, unreadable, 0, undated, unmatched, any_found)


def _plausible_skill_usage(obj):
    if not isinstance(obj, dict) or not obj:
        return False
    ok = sum(1 for v in obj.values()
             if isinstance(v, dict) and isinstance(v.get("usageCount"), int))
    return ok * 2 >= len(obj)


def extract_top_level_object(path, field, max_obj_bytes=16 * 1024 * 1024):
    """从可能很大的 JSON 文件流式抽一个顶层对象字段（如 skillUsage），不整文件 load。

    实现：按 1MB 块搜索 '"field"' 键，命中后从随后的 '{' 起 raw_decode（不够就继续读块）。
    假阳性（字段名出现在别的字符串值里）靠形状校验剔除。失败 → {}。
    """
    needle = '"' + field + '"'
    try:
        f = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return {}
    dec = json.JSONDecoder()
    with f:
        carry = ""
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                return {}
            data = carry + chunk if carry else chunk
            start = 0
            while True:
                idx = data.find(needle, start)
                if idx == -1:
                    break
                j = idx + len(needle)
                while j < len(data) and data[j] in " \t\r\n":
                    j += 1
                if j < len(data) and data[j] == ":":  # 跳过 "键": 空白 值
                    j += 1
                    while j < len(data) and data[j] in " \t\r\n":
                        j += 1
                if j < len(data) and data[j] == "{":
                    cand = data[j:]
                    obj = None
                    while True:
                        try:
                            obj, _end = dec.raw_decode(cand)
                            break
                        except ValueError:
                            nxt = f.read(1024 * 1024)
                            if not nxt or len(cand) > max_obj_bytes:
                                obj = None
                                break
                            cand += nxt
                    if _plausible_skill_usage(obj):
                        return obj
                start = idx + 1
            carry = data[-len(needle):]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="skill 使用统计（transcripts 窗口扫描；claude-code 另含 skillUsage 终身计数）。只读。")
    ap.add_argument("--window-days", type=int, default=30, help="统计窗口天数（默认 30）")
    ap.add_argument("--agents", default="claude-code,codex,hermes",
                    help="逗号分隔（默认全开）")
    ap.add_argument("--json", default=None, help="机器可读结果写入该路径")
    args = ap.parse_args(argv)

    from adapters import ALL_AGENTS, get_adapters  # 延迟导入，避免与适配器互相 import 打架
    names = [x.strip() for x in args.agents.split(",") if x.strip()]
    bad = [n for n in names if n not in ALL_AGENTS]
    if bad:
        print("未知 agent: %s；可选：%s" % (",".join(bad), ",".join(ALL_AGENTS)), file=sys.stderr)
        return 2

    records, warnings, sessions = [], [], 0
    for name, mod in get_adapters(names):
        if not mod.detect():
            print("[usage] %s: 未安装，跳过" % name)
            continue
        recs = mod.usage_records(args.window_days)
        meta = dict(getattr(mod, "USAGE_META", {}))
        records.extend(recs)
        sessions += meta.get("sessions_scanned", 0)
        warnings.extend("%s usage: %s" % (name, w) for w in meta.get("warnings", []))
        print("[usage] %s: %d 条记录，扫会话文件 %d 个" % (name, len(recs), meta.get("sessions_scanned", 0)))
    records.sort(key=lambda r: (-r.get("activations", 0), r["skill_id"]))
    out = {"window_days": args.window_days, "sessions_scanned": sessions,
           "records": records, "warnings": warnings}
    print("[usage] 合计 %d 条记录（窗口 %d 天，会话文件 %d 个），warnings %d 条"
          % (len(records), args.window_days, sessions, len(warnings)))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print("[usage] JSON → %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
