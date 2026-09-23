#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure an inventory without rediscovering or modifying audited components.

The v2 output keeps every runtime-visible component instance and measures content from
``source_file``.  Legacy v1 inventories are accepted at the boundary, but their active
state/accounting is deliberately downgraded to unknown/inferred.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime

import tiktoken

SCHEMA_VERSION = "2.0"
SCHEMA_NAME = "bulus-skill-auditor.metrics"
INVENTORY_SCHEMA_NAME = "bulus-skill-auditor.inventory"
OVERSIZE_DESC_CHARS = 1024
HEAVY_BODY_TOKENS = 8000
LISTING_BUDGET_TOKENS = 2000
SKELETON_LINES = 50
DUP_JACCARD = 0.55
W_ALWAYS, W_UNUSED, W_BODY = 0.5, 0.3, 0.2

CJK_RUN = re.compile(r"[㐀-䶿一-鿿豈-﫿]+")
WORD = re.compile(r"\w+")


def mixed_tokens(text):
    """Token set for deterministic Jaccard candidates (CJK 2-grams + lower words)."""
    toks, pos = set(), 0
    for match in CJK_RUN.finditer(text or ""):
        for word in WORD.findall((text or "")[pos:match.start()]):
            toks.add(word.lower())
        segment = match.group()
        if len(segment) == 1:
            toks.add(segment)
        else:
            for index in range(len(segment) - 1):
                toks.add(segment[index:index + 2])
        pos = match.end()
    for word in WORD.findall((text or "")[pos:]):
        toks.add(word.lower())
    return toks


def split_frontmatter(text):
    """Return body text after a leading YAML-style frontmatter block."""
    lines = (text or "").lstrip("﻿").split("\n")
    if not lines or lines[0].strip() != "---":
        return "\n".join(lines)
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1:])
    return "\n".join(lines)


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _major_version(document):
    raw = document.get("schema_version")
    if raw in (None, ""):
        return 1
    try:
        return int(str(raw).split(".", 1)[0])
    except (TypeError, ValueError):
        return None


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


def _normal_path(path):
    if not isinstance(path, str) or not path:
        return ""
    return os.path.normpath(os.path.abspath(os.path.expanduser(path)))


def _synthetic_instance_id(skill, ordinal=0):
    agent = _text(skill.get("agent"), "unknown")
    fields = [
        agent,
        _text(skill.get("component_type"), "skill"),
        _text(skill.get("runtime_name") or skill.get("name") or skill.get("id"), "unknown"),
        _text(skill.get("install_scope") or skill.get("scope"), "unknown"),
        _normal_path(skill.get("source_file") or skill.get("path")),
        _normal_path(skill.get("source_realpath") or skill.get("realpath") or skill.get("symlink_target")),
    ]
    if ordinal:
        fields.append(str(ordinal))
    digest = hashlib.sha256("\0".join(fields).encode("utf-8", errors="replace")).hexdigest()[:20]
    return "%s::i::%s" % (agent, digest)


def _prepare_skills(raw_skills, legacy):
    """Normalize transition fields without claiming unproved runtime activity."""
    skills = [dict(item) for item in (raw_skills or []) if isinstance(item, dict)]
    logical_counts = Counter(_text(item.get("id") or item.get("logical_id")) for item in skills)
    used = set()
    for ordinal, skill in enumerate(skills):
        agent = _text(skill.get("agent"), "unknown")
        runtime_name = _text(skill.get("runtime_name") or skill.get("name") or skill.get("id"), "unknown")
        logical_id = _text(skill.get("logical_id") or skill.get("id"), "%s::%s" % (agent, runtime_name))
        skill["agent"] = agent
        skill["runtime_name"] = runtime_name
        skill["name"] = runtime_name
        skill["id"] = logical_id
        skill["logical_id"] = logical_id
        skill["component_type"] = _text(skill.get("component_type"), "skill")
        skill["component_name"] = _text(skill.get("component_name"), runtime_name.split(":")[-1])
        skill["install_scope"] = _text(skill.get("install_scope") or skill.get("scope"), "unknown")
        skill["scope"] = _text(skill.get("scope"), skill["install_scope"])
        skill["source_kind"] = _text(skill.get("source_kind"), "standalone")
        if not skill.get("source_file") and skill.get("path") and skill.get("has_skill_md", True) \
                and skill.get("component_type") == "skill":
            skill["source_file"] = os.path.join(_text(skill.get("path")), "SKILL.md")
        if "auditable" not in skill:
            skill["auditable"] = bool(skill.get("source_file") and skill.get("has_skill_md", True))
        if legacy:
            skill["active_state"] = "unknown"
            old_accounting = skill.get("accounting") if isinstance(skill.get("accounting"), dict) else {}
            listing = "excluded" if old_accounting.get("listing") == "excluded" else "estimated"
            trigger = "excluded" if old_accounting.get("trigger") == "excluded" else "estimated"
            skill["accounting"] = {
                "listing": listing,
                "trigger": trigger,
                "reason": "legacy v1 input: runtime activity is not proved",
            }
        else:
            if skill.get("active_state") not in ("active", "unknown"):
                skill["active_state"] = "unknown"
            accounting = skill.get("accounting") if isinstance(skill.get("accounting"), dict) else {}
            skill["accounting"] = {
                "listing": accounting.get("listing") if accounting.get("listing") in ("confirmed", "estimated", "excluded") else "estimated",
                "trigger": accounting.get("trigger") if accounting.get("trigger") in ("confirmed", "estimated", "excluded") else "estimated",
                "reason": _text(accounting.get("reason"), "transition default: accounting evidence missing"),
            }
        instance_id = _text(skill.get("instance_id"))
        if not instance_id and legacy and logical_id and logical_counts[logical_id] == 1:
            instance_id = logical_id
        if not instance_id:
            instance_id = _synthetic_instance_id(skill)
        collision = 0
        candidate = instance_id
        while candidate in used:
            collision += 1
            candidate = _synthetic_instance_id(skill, ordinal + collision + 1)
        skill["instance_id"] = candidate
        used.add(candidate)
    return sorted(skills, key=lambda item: (
        _text(item.get("instance_id")), _text(item.get("agent")), _text(item.get("runtime_name"))))


def _issue(code, severity, agent, stage, message, path=None, safe_context=None):
    return {
        "code": _text(code, "unknown"),
        "severity": severity if severity in ("info", "warning", "error") else "warning",
        "agent": _text(agent) or None,
        "stage": stage if stage in ("discovery", "parse", "usage", "eval", "report") else "parse",
        "message": _text(message, "unspecified issue"),
        "path": path if isinstance(path, str) else None,
        "safe_context": safe_context if isinstance(safe_context, dict) else None,
    }


def _issue_key(item):
    return (
        _text(item.get("agent")), _text(item.get("stage")), _text(item.get("code")),
        _text(item.get("path")), _text(item.get("message")),
        json.dumps(item.get("safe_context"), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def _normalize_issues(document):
    issues = []
    represented_messages = set()
    for raw in document.get("issues") or []:
        if not isinstance(raw, dict):
            continue
        item = _issue(
            raw.get("code"), raw.get("severity"), raw.get("agent"), raw.get("stage"),
            raw.get("message"), raw.get("path"), raw.get("safe_context"),
        )
        issues.append(item)
        represented_messages.add(item["message"])
    for warning in document.get("warnings") or []:
        if isinstance(warning, str) and warning not in represented_messages:
            issues.append(_issue("legacy_warning", "warning", None, "parse", warning))
    return issues


def _warning_projection(issues):
    return [item["message"] for item in sorted(issues, key=_issue_key)
            if item.get("severity") in ("warning", "error")]


def _listing_status(skill):
    listing = (skill.get("accounting") or {}).get("listing")
    if listing == "excluded":
        return "excluded"
    if skill.get("active_state") == "active" and listing == "confirmed":
        return "confirmed"
    return "inferred"


def _content_eligible(skill):
    accounting = skill.get("accounting") or {}
    return bool(
        skill.get("auditable") is True
        and skill.get("source_kind") != "builtin"
        and accounting.get("trigger") != "excluded"
    )


def _safe_reference_path(root, reference):
    """Resolve a declared text reference only when lexical and real paths stay in root."""
    if not isinstance(reference, str) or not reference or "\x00" in reference or os.path.isabs(reference):
        return None
    root_lexical = _normal_path(root)
    candidate = _normal_path(os.path.join(root_lexical, reference))
    try:
        if os.path.commonpath([root_lexical, candidate]) != root_lexical:
            return None
        root_real = os.path.realpath(root_lexical)
        candidate_real = os.path.realpath(candidate)
        if os.path.commonpath([root_real, candidate_real]) != root_real:
            return None
    except (OSError, ValueError):
        return None
    return candidate


def measure_skill(enc, skill):
    """Return tokens, flags, body, and structured parse issues for one component."""
    issues = []
    description = _text(skill.get("description"))
    instance_id = _text(skill.get("instance_id"), _text(skill.get("id"), "unknown"))
    agent = _text(skill.get("agent"), "unknown")
    listing_status = _listing_status(skill)
    tokens = {
        "always": len(enc.encode_ordinary(description)),
        "on_trigger": None,
        "refs_total": None,
        "tokenizer": "o200k_local",
        "accuracy_note": "本地计量；与目标 Agent tokenizer 可能存在偏差，按审计近似值使用",
        "accounting_status": listing_status,
        "measurement_status": "excluded",
    }
    flags = []
    if listing_status != "excluded" and len(description) > OVERSIZE_DESC_CHARS:
        flags.append("oversized_description")
    if not _content_eligible(skill):
        return tokens, flags, "", issues

    source_file = _text(skill.get("source_file"))
    if not source_file or not os.path.isfile(source_file):
        tokens["measurement_status"] = "incomplete"
        message = "%s: source_file/SKILL.md 读取失败（%s），触发 token 未确认" % (
            instance_id, source_file or "未提供路径")
        issues.append(_issue(
            "source_file_unreadable", "warning", agent, "parse", message,
            source_file or None, {"instance_id": instance_id},
        ))
        return tokens, flags, "", issues

    try:
        body = split_frontmatter(_read(source_file))
    except OSError as exc:
        tokens["measurement_status"] = "incomplete"
        issues.append(_issue(
            "source_file_unreadable", "warning", agent, "parse",
            "%s: source_file/SKILL.md 读取失败（%s），触发 token 未确认" % (instance_id, exc),
            source_file, {"instance_id": instance_id},
        ))
        return tokens, flags, "", issues

    tokens["on_trigger"] = len(enc.encode_ordinary(body))
    refs_total = 0
    refs_complete = True
    root = _text(skill.get("path"))
    if not root or not os.path.isdir(root):
        root = os.path.dirname(source_file)
    for reference in sorted(skill.get("ref_files") or [], key=lambda value: _text(value)):
        safe_path = _safe_reference_path(root, reference)
        if safe_path is None:
            refs_complete = False
            issues.append(_issue(
                "unsafe_reference_path", "warning", agent, "parse",
                "%s: ref 路径越界或不是安全相对文本路径，未读取：%s" % (instance_id, reference),
                reference if isinstance(reference, str) else None, {"instance_id": instance_id},
            ))
            continue
        try:
            refs_total += len(enc.encode_ordinary(_read(safe_path)))
        except OSError as exc:
            refs_complete = False
            issues.append(_issue(
                "reference_unreadable", "warning", agent, "parse",
                "%s: ref 文件读取失败 %s（%s），refs token 未确认" % (instance_id, reference, exc),
                safe_path, {"instance_id": instance_id, "reference": reference},
            ))
    tokens["refs_total"] = refs_total if refs_complete else None
    if not refs_complete:
        tokens["refs_measured_tokens"] = refs_total
        tokens["measurement_status"] = "incomplete"
        return tokens, flags, body, issues

    tokens["measurement_status"] = "complete"
    body_lines = skill.get("body_lines")
    if not isinstance(body_lines, int):
        body_lines = body.count("\n") + 1 if body else 0
    refs = skill.get("ref_files") or []
    scripts = skill.get("scripts_files") or []
    if tokens["on_trigger"] > HEAVY_BODY_TOKENS and not refs:
        flags.append("heavy_body_no_refs")
    if body_lines < SKELETON_LINES and not refs and not scripts:
        flags.append("skeleton")
    return tokens, flags, body, issues


def duplication_all(skills, bodies):
    """Return symmetric duplication candidates keyed only by canonical instance_id."""
    token_sets = []
    for skill in skills:
        instance_id = skill.get("instance_id")
        body = bodies.get(instance_id)
        if body is None:
            token_sets.append(None)
            continue
        text = " ".join([
            _text(skill.get("runtime_name") or skill.get("name")),
            _text(skill.get("description")), body,
        ])
        token_sets.append(mixed_tokens(text))
    duplicates = [[] for _ in skills]
    for left in range(len(skills)):
        if token_sets[left] is None:
            continue
        for right in range(left + 1, len(skills)):
            if token_sets[right] is None:
                continue
            union = len(token_sets[left] | token_sets[right])
            if not union:
                continue
            score = len(token_sets[left] & token_sets[right]) / union
            if score < DUP_JACCARD:
                continue
            first, second = skills[left], skills[right]
            same_agent = first.get("agent") == second.get("agent")
            same_name = first.get("runtime_name") == second.get("runtime_name")
            if not same_agent:
                note = "跨 Agent 维护副本（非单会话节省）" if same_name else "跨 Agent 维护副本（换名疑似重复，非单会话节省）"
                relation = "cross_agent_maintenance_copy"
            elif same_name:
                note = "同 Agent 同名冲突候选"
                relation = "same_agent_name_conflict"
            else:
                note = "同 Agent 换名疑似重复"
                relation = "same_agent_possible_duplicate"
            duplicates[left].append({
                "with": second.get("instance_id"),
                "with_logical_id": second.get("logical_id") or second.get("id"),
                "jaccard": round(score, 3), "note": note, "relation": relation,
            })
            duplicates[right].append({
                "with": first.get("instance_id"),
                "with_logical_id": first.get("logical_id") or first.get("id"),
                "jaccard": round(score, 3), "note": note, "relation": relation,
            })
    for entries in duplicates:
        entries.sort(key=lambda item: (-item["jaccard"], _text(item.get("with"))))
    return duplicates


def _merge_usage_record(current, record):
    if current is None:
        return dict(record)
    merged = dict(current)
    merged["activations"] = _count(current.get("activations")) + _count(record.get("activations"))
    first_values = [value for value in (current.get("first_seen"), record.get("first_seen")) if value]
    last_values = [value for value in (current.get("last_seen"), record.get("last_seen")) if value]
    merged["first_seen"] = min(first_values) if first_values else None
    merged["last_seen"] = max(last_values) if last_values else None
    lifetime = [value for value in (current.get("lifetime_count"), record.get("lifetime_count"))
                if isinstance(value, (int, float))]
    merged["lifetime_count"] = max(lifetime) if lifetime else None
    return merged


def build_usage_index(usage, skills=None):
    """Build canonical usage joins and per-Agent coverage; never treat unknown as zero."""
    if not isinstance(usage, dict):
        return {}, {}, 30
    window = usage.get("window_days") if isinstance(usage.get("window_days"), int) else 30
    if window <= 0:
        window = 30
    skills = skills or []
    by_instance = {item.get("instance_id"): item for item in skills if item.get("instance_id")}
    by_logical = defaultdict(list)
    for item in skills:
        if item.get("logical_id") or item.get("id"):
            by_logical[item.get("logical_id") or item.get("id")].append(item.get("instance_id"))
    records = {}
    for record in sorted((item for item in (usage.get("records") or []) if isinstance(item, dict)),
                         key=lambda item: (_text(item.get("record_id")), _text(item.get("skill_instance_id")),
                                           _text(item.get("skill_id")))):
        match_status = record.get("match_status")
        matched = record.get("matched")
        if match_status is not None and match_status != "matched":
            continue
        if matched is False:
            continue
        instance_id = record.get("skill_instance_id")
        if instance_id not in by_instance:
            candidates = by_logical.get(record.get("skill_id")) or []
            if len(candidates) != 1:
                continue
            instance_id = candidates[0]
        skill = by_instance.get(instance_id)
        if skill is None:
            continue
        if record.get("agent") and record.get("agent") != skill.get("agent"):
            continue
        records[instance_id] = _merge_usage_record(records.get(instance_id), record)
    coverage = {}
    raw_by_agent = ((usage.get("coverage") or {}).get("by_agent")
                    if isinstance(usage.get("coverage"), dict) else None)
    if isinstance(raw_by_agent, dict):
        for agent, value in raw_by_agent.items():
            status = value.get("status") if isinstance(value, dict) else None
            coverage[agent] = status if status in ("complete", "partial", "unavailable") else "unavailable"
    else:
        global_complete = (usage.get("sessions_scanned") or 0) > 0
        for skill in skills:
            coverage[skill.get("agent")] = "complete" if global_complete else "unavailable"
    return records, coverage, window


def usage_stats_for(skill, records, coverage, window, ref_date):
    """Return usage stats and unused degree; unknown coverage remains ``None``."""
    record = records.get(skill.get("instance_id"))
    if record is None:
        if coverage.get(skill.get("agent")) != "complete":
            return None, None
        return {"activations": 0, "last_seen_days_ago": None, "daily_avg": 0.0}, 1.0
    activations = _count(record.get("activations"))
    days_ago = None
    if record.get("last_seen"):
        try:
            days_ago = max(0, (ref_date - date.fromisoformat(str(record["last_seen"])[:10])).days)
        except (TypeError, ValueError):
            days_ago = None
    daily = activations / float(window)
    frequency_degree = 1.0 - min(1.0, daily)
    recency_degree = min(1.0, days_ago / float(window)) if days_ago is not None else 0.0
    stats = {
        "activations": activations,
        "last_seen_days_ago": days_ago,
        "daily_avg": round(daily, 2),
    }
    return stats, max(frequency_degree, recency_degree)


def priority_for(tokens, unused, max_always, agent="unknown"):
    """Score within one Agent; cross-Agent scores are intentionally not normalized together."""
    dimensions, weights, reasons = [], [], []
    always = tokens.get("always") or 0
    always_normalized = always / float(max_always) if max_always else 0.0
    dimensions.append(always_normalized)
    weights.append(W_ALWAYS)
    reasons.append("Agent内always=%dtok(归一%.2f)" % (always, always_normalized))
    if unused is None:
        reasons.append("no_usage_data（少用维度未计，未知不按零使用）")
    else:
        dimensions.append(unused)
        weights.append(W_UNUSED)
        reasons.append("30天少用程度=%.2f" % unused)
    body_tokens = tokens.get("on_trigger")
    body_heavy = min(1.0, body_tokens / float(HEAVY_BODY_TOKENS)) if isinstance(body_tokens, int) else 0.0
    dimensions.append(body_heavy)
    weights.append(W_BODY)
    reasons.append("body重度=%.2f(%dtok/8000)" % (body_heavy, body_tokens or 0))
    score = round(100.0 * sum(value * weight for value, weight in zip(dimensions, weights)) / sum(weights))
    return {
        "score": score,
        "reasons": reasons,
        "normalization_scope": "agent",
        "normalization_agent": agent,
        "agent_max_always_tokens": max_always,
    }


def _agent_budget(agent, agent_meta):
    explicit = None
    if isinstance(agent_meta, dict):
        explicit = agent_meta.get("listing_budget_tokens")
        if explicit is None and isinstance(agent_meta.get("discovery"), dict):
            explicit = agent_meta["discovery"].get("listing_budget_tokens")
    if isinstance(explicit, int) and explicit > 0:
        return explicit, "adapter-provided token budget"
    if agent == "claude-code":
        return LISTING_BUDGET_TOKENS, "Claude Code 200k context × 1% 的近似 token 上限"
    return None, None


def _metrics_meta(skills, agents, measured_at, usage_coverage):
    # agent 字段可能是任意 JSON 值；统一文本化，防 unhashable/混型 sorted 崩溃
    for skill in skills:
        if not isinstance(skill.get("agent"), str):
            skill["agent"] = _text(skill.get("agent")) or "unknown"
    agent_meta = {
        (_text(item.get("agent")) or "unknown"): item
        for item in (agents or []) if isinstance(item, dict)
    }
    names = sorted(set([item["agent"] for item in skills if item.get("agent")] + list(agent_meta)))
    by_agent = {}
    for agent in names:
        subset = [item for item in skills if item.get("agent") == agent]
        statuses = Counter((item.get("tokens") or {}).get("accounting_status") or "inferred" for item in subset)
        confirmed = sum((item.get("tokens") or {}).get("always") or 0 for item in subset
                        if (item.get("tokens") or {}).get("accounting_status") == "confirmed")
        inferred = sum((item.get("tokens") or {}).get("always") or 0 for item in subset
                       if (item.get("tokens") or {}).get("accounting_status") == "inferred")
        excluded = sum((item.get("tokens") or {}).get("always") or 0 for item in subset
                       if (item.get("tokens") or {}).get("accounting_status") == "excluded")
        budget, budget_basis = _agent_budget(agent, agent_meta.get(agent))
        by_agent[agent] = {
            "confirmed_components": statuses.get("confirmed", 0),
            "inferred_components": statuses.get("inferred", 0),
            "excluded_components": statuses.get("excluded", 0),
            "confirmed_always_tokens": confirmed,
            "inferred_always_tokens": inferred,
            "excluded_always_tokens": excluded,
            "listing_demand_tokens": confirmed,
            "potential_listing_demand_tokens": confirmed + inferred,
            "listing_budget_tokens": budget,
            "injected_upper_bound_tokens": min(confirmed, budget) if budget is not None else None,
            "potential_overflow_tokens": max(0, confirmed - budget) if budget is not None else None,
            "potential_overflow_with_inferred_tokens": max(0, confirmed + inferred - budget) if budget is not None else None,
            "budget_basis": budget_basis,
            "usage_status": usage_coverage.get(agent, "unavailable"),
            "component_types": dict(sorted(Counter(item.get("component_type") or "skill" for item in subset).items())),
        }
    confirmed_total = sum(value["confirmed_always_tokens"] for value in by_agent.values())
    inferred_total = sum(value["inferred_always_tokens"] for value in by_agent.values())
    statuses = set(usage_coverage.values())
    if "complete" in statuses:
        usage_dimension = "available"
    elif "partial" in statuses:
        usage_dimension = "partial"
    else:
        usage_dimension = "no_usage_data"
    return {
        "measured_at": measured_at,
        "always_total_tokens": confirmed_total,
        "always_inferred_total_tokens": inferred_total,
        "total_note": "跨 Agent 字段仅供机器对账；每个 Agent 的 listing 账单必须分开解释",
        "usage_dimension": usage_dimension,
        "by_agent": by_agent,
    }


def _ordered_output(inventory, skills, issues, warnings, measured_at, metrics_meta):
    values = dict(inventory)
    values.update({
        "schema_version": SCHEMA_VERSION,
        "schema_name": SCHEMA_NAME,
        "measured_at": measured_at,
        "skills": skills,
        "issues": issues,
        "warnings": warnings,
        "metrics_meta": metrics_meta,
    })
    order = [
        "schema_version", "schema_name", "generated_at", "measured_at", "scan_seconds",
        "agents", "skills", "usage", "metrics_meta", "issues", "warnings",
    ]
    output = {}
    for key in order:
        if key in values:
            output[key] = values.pop(key)
    for key in sorted(values):
        output[key] = values[key]
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="度量层：读 00-inventory.json，按 Agent/instance_id 计 tokens、重复、usage 与 priority；输入只读。")
    parser.add_argument("inventory", help="00-inventory.json 路径")
    parser.add_argument("--out", default="skill-audit-output/01-metrics.json",
                        help="输出路径（默认：%(default)s）")
    parser.add_argument("--json", action="store_true", help="stdout 追加机器可读运行摘要")
    args = parser.parse_args(argv)
    try:
        with open(args.inventory, "r", encoding="utf-8") as handle:
            inventory = json.load(handle)
    except (OSError, ValueError) as exc:
        print("measure.py: 读 inventory 失败 %s（%s）" % (args.inventory, exc), file=sys.stderr)
        return 2
    if not isinstance(inventory, dict):
        print("measure.py: inventory 顶层必须是 JSON object（实际是 %s）" % type(inventory).__name__,
              file=sys.stderr)
        return 2
    major = _major_version(inventory)
    if major not in (1, 2):
        print("measure.py: 不支持 inventory schema major %s（仅支持 v1 兼容输入和 v2）" % (
            inventory.get("schema_version")), file=sys.stderr)
        return 2
    if major == 2 and inventory.get("schema_name") not in (None, INVENTORY_SCHEMA_NAME):
        print("measure.py: 不支持的 schema_name %s" % inventory.get("schema_name"), file=sys.stderr)
        return 2
    try:
        encoder = tiktoken.get_encoding("o200k_base")
    except Exception as exc:
        print("measure.py: tiktoken o200k_base 不可用（%s）" % exc, file=sys.stderr)
        return 2

    legacy = major == 1
    skills = _prepare_skills(inventory.get("skills"), legacy)
    issues = _normalize_issues(inventory)
    inherited_issue_count = len(issues)
    bodies = {}
    for skill in skills:
        tokens, flags, body, new_issues = measure_skill(encoder, skill)
        skill["tokens"] = tokens
        skill["structure_flags"] = sorted(flags)
        if tokens.get("measurement_status") == "complete":
            bodies[skill["instance_id"]] = body
        issues.extend(new_issues)
    for skill, duplicate_entries in zip(skills, duplication_all(skills, bodies)):
        skill["duplication"] = duplicate_entries

    try:
        reference_date = datetime.fromisoformat(_text(inventory.get("generated_at"))).date()
    except ValueError:
        reference_date = date.today()
    usage_records, usage_coverage, window = build_usage_index(inventory.get("usage"), skills)
    unused_by_instance = {}
    for skill in skills:
        stats, unused = usage_stats_for(skill, usage_records, usage_coverage, window, reference_date)
        skill["usage_stats"] = stats
        unused_by_instance[skill["instance_id"]] = unused

    eligible_by_agent = defaultdict(list)
    for skill in skills:
        tokens = skill.get("tokens") or {}
        if (skill.get("auditable") is True
                and tokens.get("accounting_status") != "excluded"
                and tokens.get("measurement_status") == "complete"):
            eligible_by_agent[skill.get("agent")].append(skill)
    maxima = {
        agent: max((item["tokens"].get("always") or 0 for item in subset), default=0)
        for agent, subset in eligible_by_agent.items()
    }
    for skill in skills:
        if skill not in eligible_by_agent.get(skill.get("agent"), []):
            skill["priority"] = None
            continue
        skill["priority"] = priority_for(
            skill["tokens"], unused_by_instance.get(skill["instance_id"]),
            maxima.get(skill.get("agent"), 0), skill.get("agent") or "unknown",
        )

    agents = sorted((item for item in (inventory.get("agents") or []) if isinstance(item, dict)),
                    key=lambda item: _text(item.get("agent")))
    inventory["agents"] = agents
    if isinstance(inventory.get("usage"), dict) and isinstance(inventory["usage"].get("records"), list):
        inventory["usage"]["records"] = sorted(
            inventory["usage"]["records"],
            key=lambda item: (_text(item.get("record_id")) if isinstance(item, dict) else "",
                              _text(item.get("skill_instance_id")) if isinstance(item, dict) else "",
                              _text(item.get("skill_id")) if isinstance(item, dict) else ""),
        )
    measured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    metrics_meta = _metrics_meta(skills, agents, measured_at, usage_coverage)
    issues = sorted(issues, key=_issue_key)
    warnings = _warning_projection(issues)
    output = _ordered_output(inventory, skills, issues, warnings, measured_at, metrics_meta)

    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError as exc:
        print("measure.py: 输出目录写不进 %s（%s）" % (args.out, exc), file=sys.stderr)
        return 2

    added = len(issues) - inherited_issue_count
    print("measure: %d components → %s（新增 issue %d 条）" % (len(skills), args.out, added))
    if args.json:
        print(json.dumps({
            "ok": True,
            "components": len(skills),
            "out": args.out,
            "always_total_tokens": metrics_meta["always_total_tokens"],
            "always_inferred_total_tokens": metrics_meta["always_inferred_total_tokens"],
            "by_agent": metrics_meta["by_agent"],
            "usage_dimension": metrics_meta["usage_dimension"],
            "issues_added": added,
        }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
