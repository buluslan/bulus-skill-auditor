#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a deterministic, per-Agent audit report from v2 artifacts.

The renderer never merges listing bills across Agents.  It consumes explicit discovery,
accounting, usage, and eval states; legacy inputs are boundary-adapted as inferred only.
"""
import argparse
import copy
import hashlib
import json
import os
import shlex
import sys
from collections import Counter, defaultdict

METRICS_SCHEMA_NAME = "bulus-skill-auditor.metrics"
INVENTORY_SCHEMA_NAME = "bulus-skill-auditor.inventory"
EVAL_SCHEMA_NAME = "bulus-skill-auditor.eval"
SUPPORTED_MAJORS = (1, 2)
CLAUDE_LISTING_BUDGET = 2000
CONTEXT_WINDOW = 200000
FLAG_LABEL = {
    "oversized_description": "desc超长",
    "heavy_body_no_refs": "超重无refs",
    "skeleton": "骨架",
}
VERDICT_LABEL = {
    "suspected_native_coverage": "疑似模型已原生覆盖（须人工复核）",
    "valuable": "有价值（保留）",
    "inconclusive": "无结论",
    "content_value_unverified": "内容价值未验证",
}


def load(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _text(value, default=""):
    return value if isinstance(value, str) else default


def _count(value):
    """Coerce an untrusted counter to int; malformed values degrade to 0, never crash."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except (TypeError, ValueError, OverflowError):
            return 0
    return 0


def _major(document):
    raw = document.get("schema_version")
    if raw in (None, ""):
        return 1
    try:
        return int(str(raw).split(".", 1)[0])
    except (TypeError, ValueError):
        return None


def _schema_supported(document, expected_name):
    if not isinstance(document, dict):
        # json.load 合法产出数组/字符串/数字；对契约输入必须是 object——干净拒绝不崩溃
        return False, "输入顶层必须是 JSON object，实际是 %s" % type(document).__name__
    major = _major(document)
    if major not in SUPPORTED_MAJORS:
        return False, "不支持 schema major %s（仅支持 v1 兼容输入和 v2）" % document.get("schema_version")
    if major == 2 and document.get("schema_name") not in (None, expected_name):
        return False, "不支持 schema_name %s（期望 %s）" % (document.get("schema_name"), expected_name)
    return True, ""


def safe_text(value):
    """Keep untrusted names/reasons inside one Markdown table cell or list line."""
    if value is None:
        return "—"
    text = str(value).replace("\x00", "�").replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(char if char == "\n" or char == "\t" or ord(char) >= 32 else "�" for char in text)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def cell(value):
    return safe_text(value)


def inline_code(value):
    text = safe_text(value).replace("`", "\\`")
    return "`%s`" % text


def fmt(value):
    if not isinstance(value, (int, float)):
        return "未确认"
    if isinstance(value, float) and not value.is_integer():
        return "%g" % value
    return format(int(value), ",")


def money(value):
    return "$%.2f" % value if isinstance(value, (int, float)) else "未知"


def tok(skill, key):
    value = (skill.get("tokens") or {}).get(key)
    return value if isinstance(value, (int, float)) else None


def act(skill):
    stats = skill.get("usage_stats")
    if not isinstance(stats, dict):
        return None
    value = stats.get("activations")
    return value if isinstance(value, (int, float)) else None


def _legacy_instance_id(skill, ordinal, duplicate=False):
    logical = _text(skill.get("id") or skill.get("logical_id"))
    if logical and not duplicate:
        return logical
    fields = [
        _text(skill.get("agent"), "unknown"),
        _text(skill.get("component_type"), "skill"),
        _text(skill.get("runtime_name") or skill.get("name") or logical, "unknown"),
        _text(skill.get("source_file") or skill.get("path")),
        str(ordinal),
    ]
    digest = hashlib.sha256("\0".join(fields).encode("utf-8", errors="replace")).hexdigest()[:20]
    return "%s::legacy::%s" % (fields[0], digest)


def adapt_metrics(document):
    """Return a copy with safe transition defaults; missing evidence never becomes confirmed."""
    metrics = copy.deepcopy(document)
    legacy = _major(metrics) == 1
    raw_skills = [item for item in (metrics.get("skills") or []) if isinstance(item, dict)]
    logical_counts = Counter(_text(item.get("logical_id") or item.get("id")) for item in raw_skills)
    used = set()
    skills = []
    for ordinal, raw in enumerate(raw_skills):
        skill = dict(raw)
        agent = _text(skill.get("agent"), "unknown")
        runtime_name = _text(skill.get("runtime_name") or skill.get("name") or skill.get("id"), "unknown")
        logical_id = _text(skill.get("logical_id") or skill.get("id"), "%s::%s" % (agent, runtime_name))
        instance_id = _text(skill.get("instance_id"))
        if not instance_id:
            instance_id = _legacy_instance_id(skill, ordinal, logical_counts[logical_id] > 1)
        if instance_id in used:
            instance_id = _legacy_instance_id(skill, ordinal, True)
        used.add(instance_id)
        skill.update({
            "instance_id": instance_id,
            "id": logical_id,
            "logical_id": logical_id,
            "agent": agent,
            "runtime_name": runtime_name,
            "name": runtime_name,
            "component_type": _text(skill.get("component_type"), "skill"),
        })
        accounting = skill.get("accounting") if isinstance(skill.get("accounting"), dict) else {}
        tokens = dict(skill.get("tokens") or {})
        if legacy:
            skill["active_state"] = "unknown"
            accounting = {
                "listing": "excluded" if accounting.get("listing") == "excluded" else "estimated",
                "trigger": "excluded" if accounting.get("trigger") == "excluded" else "estimated",
                "reason": "legacy v1 input: runtime activity is not proved",
            }
            if tokens.get("accounting_status") != "excluded":
                tokens["accounting_status"] = "inferred"
        else:
            if skill.get("active_state") not in ("active", "unknown"):
                skill["active_state"] = "unknown"
            accounting = {
                "listing": accounting.get("listing") if accounting.get("listing") in ("confirmed", "estimated", "excluded") else "estimated",
                "trigger": accounting.get("trigger") if accounting.get("trigger") in ("confirmed", "estimated", "excluded") else "estimated",
                "reason": _text(accounting.get("reason"), "transition default: evidence missing"),
            }
            if tokens.get("accounting_status") not in ("confirmed", "inferred", "excluded"):
                tokens["accounting_status"] = "inferred"
        if tokens.get("measurement_status") not in ("complete", "incomplete", "excluded"):
            tokens["measurement_status"] = "complete" if isinstance(tokens.get("on_trigger"), (int, float)) else "incomplete"
        skill["accounting"] = accounting
        skill["tokens"] = tokens
        skills.append(skill)
    metrics["skills"] = sorted(skills, key=lambda item: item["instance_id"])
    return metrics, legacy


def _usage_coverage(usage, agents):
    coverage = {}
    raw = (usage or {}).get("coverage") if isinstance(usage, dict) else None
    by_agent = raw.get("by_agent") if isinstance(raw, dict) else None
    if isinstance(by_agent, dict):
        for agent, detail in by_agent.items():
            status = detail.get("status") if isinstance(detail, dict) else None
            coverage[agent] = status if status in ("complete", "partial", "unavailable") else "unavailable"
    else:
        status = "complete" if isinstance(usage, dict) and (usage.get("sessions_scanned") or 0) > 0 else "unavailable"
        for agent in agents:
            coverage[agent] = status
    return coverage


def _budget_for_agent(agent, meta):
    value = meta.get("listing_budget_tokens") if isinstance(meta, dict) else None
    basis = meta.get("budget_basis") if isinstance(meta, dict) else None
    if isinstance(value, int) and value > 0:
        return value, basis
    if agent == "claude-code":
        return CLAUDE_LISTING_BUDGET, "Claude Code 200k context × 1% 的近似 token 上限"
    return None, None


def _usage_record_status(record, logical_counts, instance_ids):
    status = record.get("match_status")
    if status in ("matched", "unmatched", "ambiguous"):
        return status
    if record.get("matched") is False:
        return "unmatched"
    if record.get("skill_instance_id") in instance_ids:
        return "matched"
    logical = record.get("skill_id")
    if logical_counts.get(logical, 0) == 1:
        return "matched"
    if logical_counts.get(logical, 0) > 1:
        return "ambiguous"
    return "unmatched"


def aggregate(skills, usage, metrics=None):
    """Single deterministic aggregation point; identity is canonical instance_id only."""
    metrics = metrics or {}
    # agent 字段可能是任意 JSON 值；聚合键统一文本化，防 unhashable/混型 sorted 崩溃
    for skill in skills:
        if not isinstance(skill.get("agent"), str):
            skill["agent"] = safe_text(skill.get("agent")) or "unknown"
    by_instance = {skill["instance_id"]: skill for skill in skills}
    agent_names = sorted(set(skill.get("agent") or "unknown" for skill in skills))
    metric_agents = ((metrics.get("metrics_meta") or {}).get("by_agent") or {})
    agent_rows = {}
    for agent in agent_names:
        subset = [skill for skill in skills if (skill.get("agent") or "unknown") == agent]
        statuses = Counter((skill.get("tokens") or {}).get("accounting_status") or "inferred" for skill in subset)
        confirmed = sum(tok(skill, "always") or 0 for skill in subset
                        if (skill.get("tokens") or {}).get("accounting_status") == "confirmed")
        inferred = sum(tok(skill, "always") or 0 for skill in subset
                       if (skill.get("tokens") or {}).get("accounting_status") == "inferred")
        excluded = sum(tok(skill, "always") or 0 for skill in subset
                       if (skill.get("tokens") or {}).get("accounting_status") == "excluded")
        budget, budget_basis = _budget_for_agent(agent, metric_agents.get(agent) or {})
        agent_rows[agent] = {
            "confirmed_components": statuses.get("confirmed", 0),
            "inferred_components": statuses.get("inferred", 0),
            "excluded_components": statuses.get("excluded", 0),
            "confirmed_tokens": confirmed,
            "inferred_tokens": inferred,
            "excluded_tokens": excluded,
            "listing_demand": confirmed,
            "potential_demand": confirmed + inferred,
            "budget": budget,
            "budget_basis": budget_basis,
            "injected_upper_bound": min(confirmed, budget) if budget is not None else None,
            "potential_overflow": max(0, confirmed - budget) if budget is not None else None,
            "potential_overflow_with_inferred": max(0, confirmed + inferred - budget) if budget is not None else None,
            "component_types": Counter(skill.get("component_type") or "skill" for skill in subset),
        }

    logical_counts = Counter(skill.get("logical_id") or skill.get("id") for skill in skills)
    usage_records = [item for item in ((usage or {}).get("records") or []) if isinstance(item, dict)]
    usage_statuses = Counter()
    usage_activations = Counter()
    for record in usage_records:
        status = _usage_record_status(record, logical_counts, set(by_instance))
        usage_statuses[status] += 1
        usage_activations[status] += _count(record.get("activations"))
    coverage = _usage_coverage(usage, agent_names)

    pairs = {}
    for skill in skills:
        source_id = skill["instance_id"]
        for duplicate in skill.get("duplication") or []:
            target_id = duplicate.get("with")
            if target_id not in by_instance or target_id == source_id:
                continue
            key = tuple(sorted((source_id, target_id)))
            old = pairs.get(key)
            if old is None or (duplicate.get("jaccard") or 0) > (old.get("jaccard") or 0):
                pairs[key] = dict(duplicate)
    cross_pairs, same_agent_pairs = [], []
    for key, duplicate in sorted(pairs.items()):
        left, right = by_instance[key[0]], by_instance[key[1]]
        row = {"ids": key, "left": left, "right": right, "jaccard": duplicate.get("jaccard"),
               "note": duplicate.get("note"), "relation": duplicate.get("relation")}
        if left.get("agent") != right.get("agent"):
            cross_pairs.append(row)
        else:
            same_agent_pairs.append(row)

    priorities = defaultdict(list)
    for skill in skills:
        priority = skill.get("priority")
        if isinstance(priority, dict) and isinstance(priority.get("score"), (int, float)):
            priorities[skill.get("agent") or "unknown"].append(skill)
    for agent in priorities:
        priorities[agent].sort(key=lambda skill: (-skill["priority"]["score"], skill["instance_id"]))

    flags = Counter(flag for skill in skills for flag in (skill.get("structure_flags") or []))
    zero_confirmed = defaultdict(list)
    unknown_usage = defaultdict(list)
    for skill in skills:
        agent = skill.get("agent") or "unknown"
        activation = act(skill)
        if activation is None:
            unknown_usage[agent].append(skill)
        elif activation == 0 and coverage.get(agent) == "complete":
            zero_confirmed[agent].append(skill)
    return {
        "by_instance": by_instance,
        "agent_rows": agent_rows,
        "coverage": coverage,
        "usage_statuses": usage_statuses,
        "usage_activations": usage_activations,
        "cross_pairs": cross_pairs,
        "same_agent_pairs": same_agent_pairs,
        "priorities": priorities,
        "flags": flags,
        "zero_confirmed": zero_confirmed,
        "unknown_usage": unknown_usage,
    }


def _discovery_summary(metrics, agent_names):
    # agents[] 的 agent 字段可能是任意 JSON 值（list 不可哈希）——键化前先文本化
    meta = {}
    for item in (metrics.get("agents") or []):
        if isinstance(item, dict):
            meta[safe_text(item.get("agent")) or "unknown"] = item
    statuses = {}
    complete = bool(agent_names)
    for agent in agent_names:
        item = meta.get(agent) or {}
        discovery = item.get("discovery") if isinstance(item.get("discovery"), dict) else {}
        status = discovery.get("status")
        if status not in ("complete", "partial", "fallback", "unavailable"):
            status = "unavailable"
        statuses[agent] = status
        if status != "complete":
            complete = False
    return statuses, complete


def _eval_result_status(result):
    status = result.get("status")
    if status in ("complete", "cached", "partial", "unsupported_runtime", "error", "dry_run"):
        return status
    if result.get("error"):
        return "error"
    if result.get("partial"):
        return "partial"
    if result.get("cases") and result.get("delta") is not None:
        return "cached" if result.get("cache_hit") or result.get("cached") else "complete"
    return "partial"


def _case_scoreable(case):
    if case.get("status") not in (None, "complete"):
        return False
    if case.get("skipped_paid_graders") is True or case.get("errors"):
        return False
    return all(isinstance(case.get(key), (int, float)) for key in ("with_score", "without_score", "delta"))


def _result_verified(result):
    status = _eval_result_status(result)
    cases = [case for case in (result.get("cases") or []) if isinstance(case, dict)]
    return bool(
        status in ("complete", "cached")
        and not result.get("partial")
        and not result.get("error")
        and cases
        and all(_case_scoreable(case) for case in cases)
        and result.get("model") not in (None, "", "unknown", "mixed")
    )


def _eval_index(eval_document, skills):
    by_instance = {skill["instance_id"]: skill for skill in skills}
    by_logical = defaultdict(list)
    for skill in skills:
        by_logical[skill.get("logical_id") or skill.get("id")].append(skill)
    rows = []
    for result in (eval_document or {}).get("results") or []:
        if not isinstance(result, dict):
            continue
        instance_id = result.get("skill_instance_id")
        skill = by_instance.get(instance_id)
        if skill is None:
            candidates = by_logical.get(result.get("skill_id")) or []
            if len(candidates) == 1:
                skill = candidates[0]
                instance_id = skill["instance_id"]
        rows.append((instance_id or _text(result.get("skill_id"), "unknown"), skill, result))
    rows.sort(key=lambda row: (row[1].get("agent") if row[1] else "~", row[0]))
    return rows


def _eval_summary(eval_document, skills):
    rows = _eval_index(eval_document, skills)
    statuses = Counter(_eval_result_status(result) for _instance, _skill, result in rows)
    verified = sum(1 for _instance, _skill, result in rows if _result_verified(result))
    return rows, statuses, verified, len(rows) - verified


def _render_eval(lines, eval_document, skills, legacy_eval):
    rows, statuses, verified, unverified = _eval_summary(eval_document, skills)
    lines += ["## 六、深度评测结果（只消费官方聚合与显式状态）", ""]
    if legacy_eval:
        lines += ["> 输入为 legacy eval：缺失的新状态按保守口径适配，不能作为当前运行时完整性证明。", ""]
    lines += [
        "- 实际模型汇总：%s；请求执行模型：%s；judge：%s；运行时/后端：%s / %s；顶层状态：%s" % (
            safe_text(eval_document.get("model") or "unknown"),
            safe_text(eval_document.get("requested_model") or "unknown"),
            safe_text(eval_document.get("judge_model") or eval_document.get("requested_judge_model") or "unknown"),
            safe_text(eval_document.get("runtime_agent") or "unknown"),
            safe_text(eval_document.get("backend") or "unknown"),
            safe_text(eval_document.get("status") or ("legacy" if legacy_eval else "unknown")),
        ),
        "- 总预算（启动上限）：%s；本次实际新增花费：%s；cost scope：%s" % (
            money(eval_document.get("total_budget_usd")), money(eval_document.get("total_cost_usd")),
            safe_text(eval_document.get("cost_scope") or ("legacy-unknown" if legacy_eval else "unknown")),
        ),
        "- 预算说明：总预算是启动上限；即使 concurrency=1，一个已经启动的在途 run 仍可能让最终花费小幅突破。",
        "- 结果分桶：已验证 %d；内容价值未验证 %d；%s" % (
            verified, unverified,
            " / ".join("%s %d" % (key, statuses[key]) for key in sorted(statuses)) or "无结果",
        ),
        "",
        "| instance | runtime | actual model | requested model | judge | status | partial/cache | cases | 官方 Δ | 判定 | 本次成本 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for instance_id, skill, result in rows:
        status = _eval_result_status(result)
        cases = [case for case in (result.get("cases") or []) if isinstance(case, dict)]
        complete_cases = sum(1 for case in cases if _case_scoreable(case))
        partial = "partial=%s" % ("yes" if result.get("partial") else "no")
        cache = "cache=%s" % ("hit" if status == "cached" or result.get("cache_hit") else "miss")
        delta = result.get("delta")
        delta_text = "%+.3f" % delta if isinstance(delta, (int, float)) else "—"
        runtime_name = skill.get("runtime_name") if skill else result.get("skill_id")
        row = [
            instance_id, runtime_name,
            result.get("model") or "unknown", result.get("requested_model") or eval_document.get("requested_model") or "unknown",
            result.get("judge_model") or eval_document.get("judge_model") or "unknown",
            status, "%s; %s" % (partial, cache), "%d/%d complete" % (complete_cases, len(cases)),
            delta_text, VERDICT_LABEL.get(result.get("verdict"), result.get("verdict") or "—"),
            money(result.get("cost_usd_this_run")),
        ]
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
    lines.append("")
    for instance_id, _skill, result in rows:
        detail = result.get("partial_reason") or result.get("error") or result.get("evidence")
        if detail:
            lines.append("- %s：%s" % (safe_text(instance_id), safe_text(detail)))
    lines.append("")


def render(metrics, usage_src, usage, eval_document, inject, summary, legacy_metrics=False, legacy_eval=False):
    skills = metrics["skills"]
    lines = []
    report_date = (metrics.get("generated_at") or metrics.get("measured_at") or "")[:10] or "unknown"
    agent_names = sorted(summary["agent_rows"])
    discovery_statuses, discovery_complete = _discovery_summary(metrics, agent_names)
    lines += ["# Skill 审计报告 · %s" % report_date, ""]
    if legacy_metrics:
        lines += ["> 重要：legacy inferred，非当前活跃性证明。旧输入缺少运行时 active/accounting 证据，所有组件只按 inferred/unknown 展示。", ""]
    scope_label = "当前全量" if discovery_complete else "已确认清单 + 推断候选"
    lines += [
        "> 口径声明（脚本固定渲染）：",
        "> - 覆盖结论：%s；只有 discovery=complete 的 Agent 才能称为当前全量" % scope_label,
        "> - 按 Agent 分账：不同 Agent 的 listing demand 绝不相加成一张“每次会话账单”",
        "> - token 为 o200k_local 近似；always 只计 description，不含运行时可能附加的 name/格式开销",
        "> - active+listing confirmed 才进 confirmed 账单；unknown/estimated 与 excluded 分列",
        "> - 未知 usage 保持未知，不按 0 激活处理；跨 Agent 副本只表示维护关系",
    ]
    if eval_document:
        lines += [
            "> - 评测总预算（启动上限）：%s；本次实际新增花费：%s；实际模型：%s" % (
                money(eval_document.get("total_budget_usd")), money(eval_document.get("total_cost_usd")),
                safe_text(eval_document.get("model") or "unknown"),
            )
        ]
    else:
        lines += ["> - 深度评测：未运行；本次付费评测花费 $0.00"]
    lines.append("")

    lines += [
        "## 一、总览（按 Agent 分账）", "",
        "| Agent | discovery | confirmed active | confirmed token | inferred/unknown | inferred token | excluded | excluded token | listing demand | injected upper bound | potential overflow |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    budget_notes = []
    for agent in agent_names:
        row = summary["agent_rows"][agent]
        if row["budget"] is None:
            injected = "无可比 token 上限"
            overflow = "无可比 token 上限"
        else:
            injected = "%s / budget %s" % (fmt(row["injected_upper_bound"]), fmt(row["budget"]))
            overflow = fmt(row["potential_overflow"])
        values = [
            agent, discovery_statuses.get(agent, "unavailable"),
            row["confirmed_components"], row["confirmed_tokens"],
            row["inferred_components"], row["inferred_tokens"],
            row["excluded_components"], row["excluded_tokens"],
            row["listing_demand"], injected, overflow,
        ]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
        if row["budget"] is not None:
            budget_notes.append("%s 预算依据：%s；含推断的潜在需求=%s、含推断的溢出=%s" % (
                safe_text(agent), safe_text(row["budget_basis"]), fmt(row["potential_demand"]),
                fmt(row["potential_overflow_with_inferred"]),
            ))
    lines += [
        "",
        "说明：listing demand 是 confirmed active 的已确认需求；injected upper bound 是已知预算下最多可注入的 confirmed token；"
        "potential overflow 是 confirmed demand 超出该上限的部分。没有同单位、同口径上限的 Agent 不做猜测。",
    ]
    for note in budget_notes:
        lines.append("- " + note)
    lines += ["", ""]

    lines += [
        "## 二、真账单（canonical instance 全量明细）", "",
        "| instance | runtime | agent | type | active | listing/trigger | 常驻token | 触发token | refs | usage | priority | 标记 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    status_order = {"confirmed": 0, "inferred": 1, "excluded": 2}
    ordered_skills = sorted(skills, key=lambda skill: (
        skill.get("agent") or "unknown",
        status_order.get((skill.get("tokens") or {}).get("accounting_status"), 9),
        -(tok(skill, "always") or 0), skill["instance_id"],
    ))
    for skill in ordered_skills:
        accounting = skill.get("accounting") or {}
        activation = act(skill)
        usage_text = "未知" if activation is None else "%s 次" % fmt(activation)
        priority = skill.get("priority")
        priority_text = "—" if not isinstance(priority, dict) else "%s（Agent内归一）" % priority.get("score", "—")
        flags = "+".join(FLAG_LABEL.get(flag, flag) for flag in (skill.get("structure_flags") or [])) or "—"
        values = [
            skill["instance_id"], skill.get("runtime_name"), skill.get("agent"), skill.get("component_type"),
            skill.get("active_state") or "unknown",
            "%s/%s (%s)" % (accounting.get("listing", "estimated"), accounting.get("trigger", "estimated"),
                             (skill.get("tokens") or {}).get("accounting_status", "inferred")),
            fmt(tok(skill, "always")), fmt(tok(skill, "on_trigger")), fmt(tok(skill, "refs_total")),
            usage_text, priority_text, flags,
        ]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    lines.append("")

    lines += ["## 三、诊断事实（不替用户执行处置）", "", "### 使用覆盖"]
    raw_coverage = ((usage or {}).get("coverage") or {}).get("by_agent") if isinstance((usage or {}).get("coverage"), dict) else {}
    lines += [
        "| Agent | status | sessions | unreadable | parse errors | undated | matched activations | limitations |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for agent in agent_names:
        detail = raw_coverage.get(agent) if isinstance(raw_coverage, dict) else None
        detail = detail if isinstance(detail, dict) else {}
        values = [
            agent, summary["coverage"].get(agent, "unavailable"), detail.get("sessions_scanned"),
            detail.get("files_unreadable"), detail.get("parse_errors"), detail.get("undated_events"),
            detail.get("matched_activations"), "；".join(detail.get("limitations") or []) or "—",
        ]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    lines += [
        "",
        "- 使用记录：matched %d（%s 次激活） / 未匹配 %d（%s 次） / 歧义 %d（%s 次）；unmatched/ambiguous 不归入任何组件。" % (
            summary["usage_statuses"].get("matched", 0), fmt(summary["usage_activations"].get("matched", 0)),
            summary["usage_statuses"].get("unmatched", 0), fmt(summary["usage_activations"].get("unmatched", 0)),
            summary["usage_statuses"].get("ambiguous", 0), fmt(summary["usage_activations"].get("ambiguous", 0)),
        ),
    ]
    for agent in agent_names:
        lines.append("- %s：已确认窗口零激活 %d；usage 未知 %d。" % (
            safe_text(agent), len(summary["zero_confirmed"].get(agent, [])),
            len(summary["unknown_usage"].get(agent, [])),
        ))

    lines += ["", "### 重复候选"]
    lines += [
        "- 跨 Agent 维护副本 %d 对：这是安装/发布维护关系，不代表单次会话可节省，也不合并两个 Agent 的 listing 账单。" %
        len(summary["cross_pairs"]),
        "- 同 Agent 重复候选 %d 对：仅作为人工合并候选，不自动决定 precedence、删除或 winner。" %
        len(summary["same_agent_pairs"]),
    ]
    for pair in summary["cross_pairs"][:20]:
        lines.append("- 跨 Agent：%s/%s ↔ %s/%s（Jaccard %s，跨 Agent 维护副本）" % (
            safe_text(pair["left"].get("agent")), safe_text(pair["ids"][0]),
            safe_text(pair["right"].get("agent")), safe_text(pair["ids"][1]),
            fmt(pair.get("jaccard")),
        ))
    for pair in summary["same_agent_pairs"][:20]:
        lines.append("- 同 Agent：%s ↔ %s（Jaccard %s，须人工确认）" % (
            safe_text(pair["ids"][0]), safe_text(pair["ids"][1]), fmt(pair.get("jaccard"))))

    lines += ["", "### 结构问题"]
    lines.append("- " + (" / ".join("%s %d" % (FLAG_LABEL.get(flag, flag), summary["flags"][flag])
                                         for flag in sorted(summary["flags"])) or "无机器结构信号"))
    healthy = sum(1 for skill in skills
                  if not (skill.get("structure_flags") or [])
                  and not (skill.get("duplication") or [])
                  and act(skill) not in (None, 0)
                  and (skill.get("tokens") or {}).get("measurement_status") == "complete")
    lines.append("- 健康候选 %d（有直接使用、内容量测完整、无结构/重复信号；仍不等于语义价值已验证）。" % healthy)
    lines.append("")
    if inject.get("diagnosis"):
        lines += [inject["diagnosis"], ""]
    else:
        lines += ["<!-- INJECT: Agent 按 references/audit-rubric.md 补充诊断；所有疑似结论保留人工复核。 -->", ""]

    lines += [
        "## 四、高嫌疑名单（每个 Agent 独立归一，跨 Agent 分数不可直接比较）", "",
    ]
    for agent in agent_names:
        candidates = summary["priorities"].get(agent) or []
        lines += ["### %s（%d 个可排序组件）" % (safe_text(agent), len(candidates)), "",
                  "| # | instance | runtime | score | Agent 内归一理由 |", "|---|---|---|---|---|"]
        for index, skill in enumerate(candidates[:15], 1):
            priority = skill["priority"]
            values = [index, skill["instance_id"], skill.get("runtime_name"), priority.get("score"),
                      "；".join(priority.get("reasons") or [])]
            lines.append("| " + " | ".join(cell(value) for value in values) + " |")
        lines.append("")
    if inject.get("suspect_actions"):
        lines += [inject["suspect_actions"], ""]
    else:
        lines += ["<!-- INJECT: 高嫌疑建议动作；不要跨 Agent 比 priority 分数。 -->", ""]

    lines += ["## 五、处置建议（注入位）", ""]
    if inject.get("recommendations"):
        lines += [inject["recommendations"], ""]
    else:
        lines += ["<!-- INJECT: 按 references/refactor-playbook.md 写信号、预计收益、风险前提和人工确认框。 -->", ""]

    if eval_document:
        _render_eval(lines, eval_document, skills, legacy_eval)

    issue_rows = [item for item in (metrics.get("issues") or []) if isinstance(item, dict)]
    issue_counts = Counter(item.get("code") or "unknown" for item in issue_rows)
    metrics_path = _text(metrics.get("_path"))
    quoted_metrics = shlex.quote(metrics_path).replace("\n", "?").replace("`", "?")
    quoted_usage = shlex.quote(_text(usage_src)).replace("\n", "?").replace("`", "?")
    commands = [
        ("按 Agent 的 confirmed/inferred/excluded 数量与 token", "jq '.metrics_meta.by_agent' %s" % quoted_metrics),
        ("canonical instance 唯一性", "jq '[.skills[].instance_id] | length == (unique|length)' %s" % quoted_metrics),
        ("usage match_status 分桶", "jq '.usage.records | group_by(.match_status) | map({status:(.[0].match_status // \"legacy\"),n:length})' %s" % quoted_usage),
        ("跨 Agent 维护副本候选", "jq '[.skills[] as $s | $s.duplication[]? | select(.relation==\"cross_agent_maintenance_copy\") | {from:$s.instance_id,to:.with}]' %s" % quoted_metrics),
    ]
    lines += ["## 七、附录：issues 与复核入口", ""]
    lines.append("- structured issues %d：%s" % (
        len(issue_rows), " / ".join("%s %d" % (key, issue_counts[key]) for key in sorted(issue_counts)) or "无"))
    lines.append("- legacy warnings 投影 %d 条；机器判断只读 issues。" % len(metrics.get("warnings") or []))
    lines.append("- 注入文件：%s。" % ("已加载 " + "、".join(sorted(inject)) if inject else "未加载，占位注释保留"))
    lines += ["", "复核命令（所有账单仍按 Agent 分组）："]
    for label, command in commands:
        lines.append("- %s：%s" % (safe_text(label), inline_code(command)))
    return lines


def render_list(metrics, summary, inject):
    skills = metrics["skills"]
    report_date = (metrics.get("generated_at") or metrics.get("measured_at") or "")[:10] or "unknown"
    lines = [
        "# 我的 Skill 清单 · %s（%d 个实例）" % (report_date, len(skills)), "",
        "> 按 Agent 分组；active confirmed、inferred/unknown、excluded 不混写。", "",
    ]
    if inject.get("inventory_list"):
        lines += [inject["inventory_list"], ""]
    else:
        lines += ["<!-- INJECT: 仅补场景建议，不改脚本生成的实例与状态。 -->", ""]
    for agent in sorted(summary["agent_rows"]):
        subset = sorted((skill for skill in skills if skill.get("agent") == agent),
                        key=lambda skill: (skill.get("runtime_name") or "", skill["instance_id"]))
        lines += ["## %s（%d 个实例）" % (safe_text(agent), len(subset)), ""]
        for skill in subset:
            accounting_status = (skill.get("tokens") or {}).get("accounting_status") or "inferred"
            activation = act(skill)
            usage = "usage未知" if activation is None else "窗口%s次" % fmt(activation)
            lines.append("- %s — %s / %s / %s / %s" % (
                safe_text(skill.get("runtime_name")), safe_text(skill["instance_id"]),
                safe_text(skill.get("component_type")), accounting_status, usage,
            ))
        lines.append("")
    return lines


def _write_lines(path, lines):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip("\n") + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="按 Agent/instance_id 确定性渲染 03-report.md；输入只读。")
    parser.add_argument("--metrics", required=True, help="01-metrics.json（必需）")
    parser.add_argument("--inventory", help="00-inventory.json（可选，usage 事实源）")
    parser.add_argument("--eval", dest="eval_path", help="02-eval-results.json（可选）")
    parser.add_argument("--out", required=True, help="输出 03-report.md 路径")
    parser.add_argument("--inventory-list", help="可选，一并渲染 Skill清单.md")
    parser.add_argument("--inject", help="report-inject.json；默认探测 --out 同目录")
    parser.add_argument("--json", action="store_true", help="stdout 打印机器可读聚合")
    args = parser.parse_args(argv)

    try:
        raw_metrics = load(args.metrics)
    except (OSError, ValueError) as exc:
        print("render_report.py: 读取 metrics 失败（%s）" % exc, file=sys.stderr)
        return 2
    ok, message = _schema_supported(raw_metrics, METRICS_SCHEMA_NAME)
    if not ok:
        print("render_report.py: %s" % message, file=sys.stderr)
        return 2
    metrics, legacy_metrics = adapt_metrics(raw_metrics)
    metrics["_path"] = args.metrics
    if not metrics.get("skills"):
        print("error: 输入异常——扫描到 0 个 component，不出报告", file=sys.stderr)
        return 2

    inventory = None
    if args.inventory and os.path.isfile(args.inventory):
        try:
            inventory = load(args.inventory)
        except (OSError, ValueError) as exc:
            print("render_report.py: 读取 inventory 失败（%s）" % exc, file=sys.stderr)
            return 2
        ok, message = _schema_supported(inventory, INVENTORY_SCHEMA_NAME)
        if not ok:
            print("render_report.py: %s" % message, file=sys.stderr)
            return 2
    usage_source = args.inventory if inventory is not None else args.metrics
    usage = (inventory or metrics).get("usage")

    eval_document, legacy_eval = None, False
    if args.eval_path and os.path.isfile(args.eval_path):
        try:
            eval_document = load(args.eval_path)
        except (OSError, ValueError) as exc:
            print("render_report.py: 读取 eval 失败（%s）" % exc, file=sys.stderr)
            return 2
        ok, message = _schema_supported(eval_document, EVAL_SCHEMA_NAME)
        if not ok:
            print("render_report.py: %s" % message, file=sys.stderr)
            return 2
        legacy_eval = _major(eval_document) == 1

    inject_path = args.inject or os.path.join(os.path.dirname(os.path.abspath(args.out)), "report-inject.json")
    inject = {}
    if os.path.isfile(inject_path):
        try:
            loaded = load(inject_path)
            inject = loaded.get("sections") if isinstance(loaded, dict) else {}
            inject = {key: value for key, value in (inject or {}).items() if isinstance(key, str) and isinstance(value, str)}
        except (OSError, ValueError) as exc:
            print("warning: report-inject.json 解析失败（%s），占位注释保留" % exc, file=sys.stderr)

    summary = aggregate(metrics["skills"], usage, metrics)
    report_lines = render(metrics, usage_source, usage, eval_document, inject, summary,
                          legacy_metrics=legacy_metrics, legacy_eval=legacy_eval)
    try:
        _write_lines(args.out, report_lines)
        if args.inventory_list:
            _write_lines(args.inventory_list, render_list(metrics, summary, inject))
    except OSError as exc:
        print("render_report.py: 输出失败（%s）" % exc, file=sys.stderr)
        return 2

    if args.json:
        payload = {
            "out": args.out,
            "components": len(metrics["skills"]),
            "by_agent": summary["agent_rows"],
            "usage_match_status": dict(sorted(summary["usage_statuses"].items())),
            "cross_agent_maintenance_pairs": len(summary["cross_pairs"]),
            "same_agent_duplicate_pairs": len(summary["same_agent_pairs"]),
            "legacy_metrics": legacy_metrics,
            "eval": None,
        }
        if eval_document:
            _rows, statuses, verified, unverified = _eval_summary(eval_document, metrics["skills"])
            payload["eval"] = {
                "status": eval_document.get("status"),
                "model": eval_document.get("model"),
                "total_budget_usd": eval_document.get("total_budget_usd"),
                "total_cost_usd": eval_document.get("total_cost_usd"),
                "verified": verified,
                "unverified": unverified,
                "result_statuses": dict(sorted(statuses.items())),
            }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    print("渲染完成：%s%s" % (args.out, "；%s" % args.inventory_list if args.inventory_list else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
