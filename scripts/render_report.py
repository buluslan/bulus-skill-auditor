#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_report.py — 报告骨架渲染器（两段式产出的骨架层，修复审核 M3 及其后果 B3/M1/M2/M5/M6）

从 01-metrics.json（可选并入 00-inventory.json 的 usage、02-eval-results.json）渲染 03-report.md 骨架：
口径声明、总览聚合、真账单全表、重复对统计、高嫌疑表、失配警示、复核命令附录。全部数字由脚本从
输入聚合计算，禁止手算聚合进报告（B3）；重跑等价（日期取自输入，不取当前时间）。判断层只输出
INJECT 占位注释；存在 report-inject.json（{"sections": {"diagnosis": "...", "recommendations": "...",
"suspect_actions": "...", "inventory_list": "..."}}）则填入——重跑骨架不丢判断层（report-format.md）。
骨架防住的错误类型（红队审核 2026-09-17）：B3 冗余 token 只从 duplication 聚合，不做"对数×平均"估算；
M1 终身计数分侧（claude-code 侧"无 skillUsage 条目=推断终身 0"≠官方硬信号；codex 侧"窗口 0 激活、
无终身数据源"分开统计分开表述）；M2 闲置算术链直接给分侧原始数；M5 真账单 8 列由代码构造保证；
M6 description 超长统一"超本工具 1024 警戒线（官方硬上限 1536，尚未触及）"；失配警示机械化
（usage 覆盖异常 / listing 超预算 / metrics_meta 与重算不一致 → 顶部警示行；0 个 skill → 报错不出报告）。
只读输入；唯一写操作是 --out 与 --inventory-list。Python 3.9+ 标准库。
用法：python3 scripts/render_report.py --metrics 01-metrics.json [--inventory 00-inventory.json]
      [--eval 02-eval-results.json] --out 03-report.md [--inventory-list Skill清单.md] [--inject ...] [--json]
"""
import argparse
import json
import os
import shlex
import sys
from collections import Counter, defaultdict

LISTING_BUDGET = 2000       # 契约：claude-code listing 预算 = 上下文×1%（200k→~2000 token≈官方 8000 字符，官方口径）；全部 always 之和超过 → 报告层警示（静默截断风险）
CONTEXT_WINDOW = 200000     # 仅百分比换算口径，报告内注明
NEAR_BUDGET_RATIO = 0.8     # ≥ 预算 80% 记"接近"（本工具自定义档，报告内注明）
MIN_SESSIONS = 10           # 会话文件数低于此值 → usage 覆盖异常警示
OVERSIZE_TOOL, OVERSIZE_OFFICIAL = 1024, 1536  # 自家警戒线 / 官方硬上限（措辞不混用，M6）
FLAG_LABEL = {"oversized_description": "desc超长", "heavy_body_no_refs": "超重无refs", "skeleton": "骨架"}
VERDICT_LABEL = {"suspected_native_coverage": "疑似模型已原生覆盖（须人工复核）", "valuable": "有价值（保留）", "inconclusive": "无结论"}
WARN_KINDS = [("重复出现", "跨根/多根重复去重"), ("ref 文件读取失败", "ref 读取失败"), ("未安装", "未安装跳过"),
              ("frontmatter", "frontmatter 解析失败"), ("未匹配", "使用记录未匹配")]


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def cell(v):
    """表格单元格：None→—，竖线转义保证列数不被内容破坏（M5）。"""
    return ("—" if v is None else str(v)).replace("|", "\\|")
def fmt(n):
    return f"{n:,}"
def tok(s, key):
    return (s.get("tokens") or {}).get(key) or 0
def act(s):
    return (s.get("usage_stats") or {}).get("activations") or 0


def aggregate(skills, usage):
    """全部总览/诊断数字的唯一计算点（骨架数字禁止散落手算）。"""
    by_id = {s["id"]: s for s in skills}
    a = {"by_id": by_id, "by_agent": Counter(s["agent"] for s in skills), "scope": defaultdict(Counter),
         "flags": Counter(f for s in skills for f in s.get("structure_flags") or []),
         "always_total": sum(tok(s, "always") for s in skills),
         "refs_total": sum(tok(s, "refs_total") for s in skills),
         "zero_act": [s for s in skills if act(s) == 0]}
    for s in skills:
        a["scope"][s["agent"]][s.get("scope") or "unknown"] += 1
    zero, recs = a["zero_act"], {r["skill_id"]: r for r in (usage or {}).get("records", [])}
    a["cc_infer0"] = [s for s in zero if s["agent"] == "claude-code" and s["id"] not in recs]  # M1 分侧
    a["cx_nolifetime"] = [s for s in zero if s["agent"] != "claude-code"]                      # M1 分侧
    a["lifetime_entries"] = sum(1 for r in recs.values() if r.get("lifetime_count") is not None)
    a["unmatched_records"] = len([i for i in recs if i not in by_id])
    cross_name, rename = set(), {}   # 重复对只从 duplication 聚合（B3），对按有序 id 去重
    for s in skills:
        for d in s.get("duplication") or []:
            w = d.get("with")
            if w and w != s["id"]:
                key = tuple(sorted((s["id"], w)))
                if d.get("note") == "跨 agent 同名":
                    cross_name.add(key)
                else:
                    rename[key] = max(rename.get(key, 0.0), d.get("jaccard") or 0.0)
    a["cross_name"], a["rename"] = cross_name, rename
    a["cx_dup_ids"] = {i for p in cross_name for i in p if i in by_id and by_id[i]["agent"] == "codex"}
    a["cx_dup_always"] = sum(by_id[i]["tokens"]["always"] for i in a["cx_dup_ids"])
    a["dup_both_always"] = sum(by_id[i]["tokens"]["always"] for p in cross_name for i in p if i in by_id)
    a["rename_cross"] = {k: v for k, v in rename.items() if k[0] in by_id and k[1] in by_id and by_id[k[0]]["agent"] != by_id[k[1]]["agent"]}
    a["rename_inner"] = {k: v for k, v in rename.items() if k not in a["rename_cross"]}
    ranked = sorted(skills, key=lambda s: (-(s.get("priority") or {}).get("score") or 0, s["id"]))
    a["suspects"] = [s for s in ranked if s["id"] not in a["cx_dup_ids"]][:15]  # 排除 codex 侧副本
    return a


def render(metrics, usage_src, usage, ev, inject, a):
    """返回报告行列表，按 references/report-format.md 结构拼接。"""
    skills, L, m = metrics["skills"], [], metrics
    mpath, upath = shlex.quote(metrics.get("_path", "")), shlex.quote(usage_src)
    date, ag = (m.get("generated_at") or "")[:10] or "unknown", m.get("agents") or []
    cov = (usage or {}).get("coverage") or {}
    sessions = (usage or {}).get("sessions_scanned") or 0
    bad_usage = ((not usage) or cov.get("transcripts_found") is False
                 or cov.get("skip_env_detected") or sessions < MIN_SESSIONS)
    ratio = a["always_total"] / LISTING_BUDGET
    meta_total = (m.get("metrics_meta") or {}).get("always_total_tokens")

    L += [f"# Skill 审计报告 · {date}", ""]
    warns = ([] if not bad_usage else
             ["使用数据不完整（会话扫描覆盖异常）：本报告所有“零激活/闲置”结论不可信（须人工复核）"])
    warns += ([] if ratio <= 1 else
              [f"listing 超预算：常驻 {fmt(a['always_total'])} / {fmt(LISTING_BUDGET)} token = {ratio:.1f} 倍"
               "——超限会静默截断，排在后面的 skill 从模型视野消失"])
    if meta_total is not None and meta_total != a["always_total"]:
        warns.append(f"数据失配：metrics_meta.always_total_tokens={fmt(meta_total)} 与重算值 {fmt(a['always_total'])}"
                     " 不一致——以复核命令重算值为准（须人工复核）")
    if warns:
        L += ["> **⚠️ 失配警示（脚本机械检查插入）**"] + [f"> - {w}" for w in warns] + [""]
    cost = (f"${sum(r.get('cost_usd') or 0 for r in ev['results']):.2f}（深度评测 {len(ev['results'])} 个 skill，"
            f"预算上限 ${ev.get('budget_usd', '?')}）" if ev else "$0（未跑深度评测）")
    detected = " / ".join(x["agent"] for x in ag if x.get("detected")) or "无"
    skipped = "；".join(x["agent"] + " 未安装，跳过" for x in ag if not x.get("detected"))
    wcount = f"；{fmt(len(m.get('warnings') or []))} 条 warnings（分类见附录）" if m.get("warnings") else ""
    L += ["> 口径声明（脚本固定渲染，数据诚实原则）：",
          "> - token 为本地计量（o200k_local），与官方 tokenizer 偏差 ≤10%",
          "> - always 口径只计 description、不含 name 字段（官方 listing 实为 name+description 一行，常驻因此系统性低估）",
          f"> - 使用统计窗口：最近 {(usage or {}).get('window_days') or '?'} 天（transcripts 扫描，扫 {sessions} 个会话文件）；"
          "终身计数仅 claude-code 侧有数据源（~/.claude.json skillUsage），codex 侧无终身数据源",
          f"> - 覆盖率：{detected} 已扫描" + (f"；{skipped}" if skipped else "") + wcount,
          f"> - 本次审计花费：{cost}", ""]

    L += ["## 一、总览（骨架：全部数字由脚本从 01-metrics.json 聚合，重跑等价）", ""]
    dist = "；".join(f"{g} {a['by_agent'][g]} = " + " + ".join(f"{sc} {n}" for sc, n in sorted(a["scope"][g].items())) for g in sorted(a["by_agent"]))
    L += [f"- {len(skills)} 个 skill，分布：{dist}",
          f"- 常驻总账：每次会话固定承载 {fmt(a['always_total'])} token（≈ 200K 上下文的 "
          f"{a['always_total'] / CONTEXT_WINDOW * 100:.1f}%，按 {fmt(CONTEXT_WINDOW)} 窗口换算；always 口径不含 name）"]
    if ratio > 1:
        L.append(f"- listing 预算状态：**超限——{fmt(a['always_total'])} / {fmt(LISTING_BUDGET)} = {ratio:.1f} 倍**"
                 "（超限会静默截断，排在后面的 skill 从模型视野消失）")
    else:
        st = "接近（≥预算 80%，本工具自定义档）" if ratio >= NEAR_BUDGET_RATIO else "健康"
        L.append(f"- listing 预算状态：{st}（{fmt(a['always_total'])} / {fmt(LISTING_BUDGET)}）")
    L += [f"- 30 天零激活：{len(a['zero_act'])} 个" + ("（usage 覆盖异常，数据不足，该结论不可信）" if bad_usage else "")
          + f"；其中 claude-code 侧 {len(a['cc_infer0'])} 个无 skillUsage 条目（推断终身 0，非官方 usageCount===0 硬信号）"
            f"、codex 侧 {len(a['cx_nolifetime'])} 个窗口 0 激活且无终身数据源",
          "- 结构问题：" + (" / ".join(f"{FLAG_LABEL.get(f, f)} {a['flags'][f]} 个" for f in sorted(a["flags"])) or "无")
          + f"（description 超长=超本工具 {OVERSIZE_TOOL} 警戒线，官方硬上限 {OVERSIZE_OFFICIAL}）",
          f"- 重复：跨 agent 同名 {len(a['cross_name'])} 对（codex 侧副本常驻合计 {fmt(a['cx_dup_always'])} token/会话，"
          f"为两份合计 {fmt(a['dup_both_always'])} 中冗余的一份）；换名疑似重复（须人工复核）{len(a['rename'])} 对，"
          f"其中跨 agent {len(a['rename_cross'])} 对", ""]

    L += [f"## 二、真账单（骨架：全量 {len(skills)} 行按常驻降序；refs=按需加载参考值；8 列由代码保证）", "",
          "| skill | agent | 常驻token | 触发token | refs | 30天激活 | 最后使用 | 标记 |",
          "|---|---|---|---|---|---|---|---|"]
    for s in sorted(skills, key=lambda x: (-tok(x, "always"), x["id"])):
        seen = (s.get("usage_stats") or {}).get("last_seen_days_ago")
        row = [s["name"], s["agent"], fmt(tok(s, "always")), fmt(tok(s, "on_trigger")), fmt(tok(s, "refs_total")),
               act(s), "—" if seen is None else ("今天" if seen == 0 else f"{seen} 天前"),
               "+".join(FLAG_LABEL.get(f, f) for f in s.get("structure_flags") or []) or "—"]
        L.append("| " + " | ".join(cell(x) for x in row) + " |")
    L.append("")

    L += ["## 三、诊断明细（骨架事实 + 注入判断）", "",
          f"### 重复（跨 agent 同名 {len(a['cross_name'])} 对 + 换名 {len(a['rename'])} 对，人工确认级）"]
    tops = sorted(((a["by_id"][i]["tokens"]["always"], a["by_id"][i]["name"]) for i in a["cx_dup_ids"]), reverse=True)
    L += [f"- 跨 agent 同名 {len(a['cross_name'])} 对：同一 skill 两侧各装一份物理副本（Jaccard=1.00）。codex 侧"
          f"副本常驻合计 {fmt(a['cx_dup_always'])} token，两份合计 {fmt(a['dup_both_always'])}，冗余的一份即"
          f"{fmt(a['cx_dup_always'])}。常驻降序 top10：" + "、".join(f"{n}（{fmt(t)} tok）" for t, n in tops[:10])]
    rk = sorted(a["rename"].items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    ik = sorted(a["rename_inner"].items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    L += [f"- 换名疑似重复（须人工复核）{len(a['rename'])} 对（跨 agent {len(a['rename_cross'])} / agent 内部 "
          f"{len(a['rename_inner'])}），Jaccard top5：" + "、".join(f"{x} ↔ {y}（{j:.2f}）" for (x, y), j in rk)]
    if ik:
        L.append("- agent 内部重复 top5：" + "、".join(f"{x} ↔ {y}（{j:.2f}）" for (x, y), j in ik))
    L += ["", "### 疑似过时 / 模型已原生覆盖"]
    if ev:
        vc = Counter(r.get("verdict") for r in ev["results"])
        L.append("- 已跑深度评测（明细见第六节）：" + " / ".join(
            f"{VERDICT_LABEL.get(v, v)} {n} 个" for v, n in sorted(vc.items())))
    else:
        L.append("- 未验证，跑深度评测可得（evaluate.py，报价见 SKILL.md 深度层）")
    heavy = sorted((s for s in skills if "heavy_body_no_refs" in (s.get("structure_flags") or [])),
                   key=lambda s: -tok(s, "on_trigger"))
    ov = [s for s in skills if "oversized_description" in (s.get("structure_flags") or [])]
    L += ["### 超重 / 结构问题",
          f"- 超重无 refs {len(heavy)} 个，最重 top5：" + "、".join(f"{s['name']}（{fmt(tok(s, 'on_trigger'))} tok）" for s in heavy[:5]),
          f"- description 超长 {len(ov)} 个：" + ("；".join(
              f"{s['name']}（{s['agent']}，{len(s.get('description') or '')} 字符，超本工具 {OVERSIZE_TOOL} 警戒线"
              f"——官方硬上限 {OVERSIZE_OFFICIAL}，尚未触及）" for s in ov) if ov else "无"),
          f"- 骨架 {a['flags'].get('skeleton', 0)} 个（<50 行且无 refs/scripts，可能是空壳或半成品）", "### 健康",
          f"- 在用（30 天有激活）且无结构问题 {sum(1 for s in skills if act(s) > 0 and not (s.get('structure_flags') or []))}"
          " 个，一句带过（明细见 metrics）", ""]
    L += ([inject["diagnosis"], ""] if inject.get("diagnosis") else
          ["<!-- INJECT: 诊断明细（Agent 按 references/audit-rubric.md 判读后写这里：重复对逐对判断、"
           "结构问题定性、健康面归纳）-->", ""])

    L += ["## 四、高嫌疑名单（骨架：priority 降序 top15，已排除跨 agent 同名对的 codex 侧副本；score 与 reasons 同现）", "",
          "| # | skill | agent | score | 上榜信号（reasons） |", "|---|---|---|---|---|"]
    for i, s in enumerate(a["suspects"], 1):
        p = s.get("priority") or {}
        L.append(f"| {i} | {cell(s['name'])} | {cell(s['agent'])} | {p.get('score', '—')} | "
                 f"{cell('；'.join(p.get('reasons') or []))} |")
    L += (["", inject["suspect_actions"], ""] if inject.get("suspect_actions") else ["", "<!-- INJECT: 高嫌疑“建议动作”列（Agent 逐行补：对应 R1-R6 哪条、先评测还是先改造）-->", ""])
    L += ["## 五、处置建议（注入位）", ""]
    L += ([inject["recommendations"], ""] if inject.get("recommendations") else ["<!-- INJECT: 处置建议（Agent 按 references/refactor-playbook.md 的 R1-R6 逐条写：信号 / 预计收益 / 风险前提 / [ ] 建议人工确认）-->", ""])

    if ev:
        L += ["## 六、深度评测结果（骨架，来自 02-eval-results.json）", "",
              f"- 模型：{ev.get('model', '?')}｜runs/case：{ev.get('runs', '?')}｜预算：${ev.get('budget_usd', '?')}"
              f"｜实际花费：${sum(r.get('cost_usd') or 0 for r in ev['results']):.2f}"
              f"{'｜dry-run' if ev.get('dry_run') else ''}｜口径：{ev.get('cost_note', '')}", "",
              "| skill | 预筛 | cases | with | without | Δ | 判定 |", "|---|---|---|---|---|---|---|"]
        for r in ev["results"]:
            cs = r.get("cases") or []
            avg = lambda k: (sum(c.get(k) or 0 for c in cs) / len(cs)) if cs else None  # noqa: E731
            w, o = avg("with_score"), avg("without_score")
            L.append(f"| {cell(r['skill_id'])} | {cell((r.get('prescreen') or {}).get('verdict'))} | {len(cs)} | "
                     f"{cell(f'{w:.2f}' if w is not None else None)} | {cell(f'{o:.2f}' if o is not None else None)} | "
                     f"{cell(f'{w - o:+.2f}' if w is not None and o is not None else None)} | "
                     f"{cell(VERDICT_LABEL.get(r.get('verdict'), r.get('verdict')))} |")
        L += [""] + [f"- {r['skill_id']}：{r.get('evidence', '')}" for r in ev["results"]] + [""]

    wc = Counter(next((k for p, k in WARN_KINDS if p in w), "其他") for w in m.get("warnings") or [])
    cmds = [("- 常驻总账（口径：仅 description）", f"jq '[.skills[].tokens.always] | add' {mpath}"),
            ("- 与 metrics_meta 对账", f"jq '.metrics_meta.always_total_tokens' {mpath}"),
            ("- 各 agent skill 数", f"jq '.skills | group_by(.agent) | map({{agent:.[0].agent,n:length}})' {mpath}"),
            ("- flags 计数", f"jq '[.skills[].structure_flags[]] | group_by(.) | map({{flag:.[0],n:length}})' {mpath}"),
            ("- 30 天零激活数", f"jq '[.skills[] | select((.usage_stats.activations // 0)==0)] | length' {mpath}"),
            ("- claude-code 侧无 skillUsage 条目（推断终身 0）", f"jq '[.usage.records[].skill_id] as $r | [.skills[] | select(.agent==\"claude-code\") | select(.id as $i | $r | index($i) | not)] | length' {upath}"),
            ("- codex 侧零激活（无终身数据源）", f"jq '[.skills[] | select(.agent==\"codex\") | select((.usage_stats.activations // 0)==0)] | length' {mpath}"),
            ("- 跨 agent 同名对数", f"jq '[.skills[].duplication[]? | select(.note==\"跨 agent 同名\")] | length/2' {mpath}"),
            ("- codex 侧副本冗余常驻", f"jq '[.skills[] | select(.agent==\"codex\") | select(any(.duplication[]?; .note==\"跨 agent 同名\")) | .tokens.always] | add' {mpath}"),
            ("- 两份合计常驻", f"jq '[.skills[] | select(any(.duplication[]?; .note==\"跨 agent 同名\")) | .tokens.always] | add' {mpath}"),
            ("- refs 合计", f"jq '[.skills[].tokens.refs_total] | add' {mpath}"),
            ("- description 字符数核对（以 claude-api 为例）", f"jq '.skills[] | select(.name==\"claude-api\") | .description | length' {mpath}")]
    L += ["## 七、附录：warnings / 复核命令表（骨架）", "",
          f"- warnings 合计 {len(m.get('warnings') or [])} 条，按类别："
          + (" / ".join(f"{k} {n} 条" for k, n in sorted(wc.items())) or "无"),
          f"- 使用记录未匹配到现存 skill：{a['unmatched_records']} 条（已删 skill 或内置命令，如实保留）",
          f"- 注入文件：report-inject.json（{'已填入：' + '、'.join(inject) if inject else '未找到/无内容，占位注释保留'}）",
          "- 数据文件：00-inventory.json / 01-metrics.json / 02-eval-results.json（每条结论的数字源）",
          "", "复核命令（每个聚合数字一行，可原样执行重算）："]
    L += [f"{lab}：`{cmd}`" for lab, cmd in cmds]
    return L


def render_list(metrics, a, inject):
    skills = metrics["skills"]
    date = (metrics.get("generated_at") or "")[:10] or "unknown"
    L = [f"# 我的 Skill 清单 · {date}（{len(skills)} 个）", "",
         "> 用法：记不起装了什么时，把本文件丢给 Agent 让它自己判断该用哪个",
         "> 骨架由 render_report.py 渲染（按 agent 分组、名称排序，重跑等价）；分类与场景建议为注入位", ""]
    L += ([inject["inventory_list"], ""] if inject.get("inventory_list") else
          ["<!-- INJECT: 清单分类与场景建议（Agent 按使用场景重排分组，并为每个 skill 在行末补“一行干什么 + 什么时候用”）-->", ""])
    for g in sorted(a["by_agent"]):
        L += [f"## {g}（{a['by_agent'][g]} 个）", ""]
        L += [f"- **{s['name']}**（30天 {act(s)} 次）"
              for s in sorted((x for x in skills if x["agent"] == g), key=lambda x: x["name"])] + [""]
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description="渲染 03-report.md 骨架（两段式产出：骨架脚本 + Agent 注入）")
    ap.add_argument("--metrics", required=True, help="01-metrics.json（必需）")
    ap.add_argument("--inventory", help="00-inventory.json（可选，usage/终身计数口径分侧用）")
    ap.add_argument("--eval", dest="eval_path", help="02-eval-results.json（可选，有则渲染第六节）")
    ap.add_argument("--out", required=True, help="输出 03-report.md 路径")
    ap.add_argument("--inventory-list", help="可选，一并渲染 Skill清单.md 骨架")
    ap.add_argument("--inject", help="report-inject.json 路径（缺省探测 --out 同目录）")
    ap.add_argument("--json", action="store_true", help="stdout 打印机器可读聚合")
    args = ap.parse_args(argv)
    metrics = load(args.metrics)
    metrics["_path"] = args.metrics  # 仅供附录复核命令引用原路径
    if not (metrics.get("skills") or []):
        print("error: 输入异常——扫描到 0 个 skill，不出报告（report-format.md 失配警示）", file=sys.stderr)
        return 2
    skills = metrics["skills"]
    inv = load(args.inventory) if args.inventory and os.path.isfile(args.inventory) else None
    usage_src = args.inventory if inv is not None else args.metrics
    usage = (inv or metrics).get("usage")
    ev = load(args.eval_path) if args.eval_path and os.path.isfile(args.eval_path) else None
    inject_path = args.inject or os.path.join(os.path.dirname(os.path.abspath(args.out)), "report-inject.json")
    inject = {}
    if os.path.isfile(inject_path):
        try:
            inject = (load(inject_path) or {}).get("sections") or {}
        except (ValueError, OSError) as e:
            print(f"warning: report-inject.json 解析失败（{e}），占位注释保留", file=sys.stderr)
    a = aggregate(skills, usage)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(render(metrics, usage_src, usage, ev, inject, a)).rstrip("\n") + "\n")
    if args.inventory_list:
        with open(args.inventory_list, "w", encoding="utf-8") as f:
            f.write("\n".join(render_list(metrics, a, inject)).rstrip("\n") + "\n")
    if args.json:
        print(json.dumps({"out": args.out, "skills": len(skills), "always_total": a["always_total"],
                          "by_agent": dict(a["by_agent"]), "flags": dict(a["flags"]),
                          "zero_act": len(a["zero_act"]), "cc_infer0": len(a["cc_infer0"]),
                          "cx_nolifetime": len(a["cx_nolifetime"]), "cross_name_pairs": len(a["cross_name"]),
                          "cx_dup_always": a["cx_dup_always"], "dup_both_always": a["dup_both_always"],
                          "rename_pairs": len(a["rename"])}, ensure_ascii=False))
    print(f"渲染完成：{args.out}" + (f"；{args.inventory_list}" if args.inventory_list else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
