#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure/render v2 focused fixture tests (stdlib-only runner, no pytest dependency)."""
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import measure  # noqa: E402
import render_report  # noqa: E402


def write_component(root, dirname, name, description, body, refs=None):
    component_dir = root / dirname
    component_dir.mkdir(parents=True, exist_ok=True)
    source = component_dir / "SKILL.md"
    source.write_text(
        "---\nname: %s\ndescription: %s\n---\n%s\n" % (name, description, body),
        encoding="utf-8",
    )
    for relpath, text in (refs or {}).items():
        target = component_dir / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return source


def component(instance_id, logical_id, agent, runtime_name, source_file, description,
              active_state="active", listing="confirmed", trigger="confirmed",
              auditable=True, source_kind="standalone", component_type="skill",
              refs=None, scope="user"):
    source_path = str(source_file) if source_file is not None else None
    component_dir = str(Path(source_path).parent) if source_path else None
    return {
        "instance_id": instance_id,
        "id": logical_id,
        "logical_id": logical_id,
        "agent": agent,
        "component_type": component_type,
        "name": runtime_name,
        "runtime_name": runtime_name,
        "component_name": runtime_name.split(":")[-1],
        "declared_name": runtime_name.split(":")[-1],
        "directory_name": runtime_name.split(":")[-1],
        "namespace": runtime_name.split(":")[0] if ":" in runtime_name else None,
        "scope": scope,
        "install_scope": scope if scope in {"user", "project", "local", "system", "shared", "builtin"} else "unknown",
        "source_kind": source_kind,
        "path": component_dir,
        "realpath": component_dir,
        "source_file": source_path,
        "source_realpath": os.path.realpath(source_path) if source_path else None,
        "symlink_target": None,
        "active_state": active_state,
        "discovery_confidence": "runtime_probe" if active_state == "active" else "inferred",
        "discovery_method": "fixture",
        "description": description,
        "has_skill_md": source_path is not None,
        "body_chars": 0,
        "body_lines": None,
        "ref_files": list(refs or []),
        "ref_total_chars": 0,
        "scripts_files": [],
        "frontmatter_keys": ["name", "description"] if source_path else [],
        "auditable": auditable,
        "source_format": "skill-md" if component_type == "skill" else "markdown",
        "accounting": {"listing": listing, "trigger": trigger, "reason": "fixture"},
        "plugin_id": None,
        "plugin_name": None,
        "marketplace": None,
        "plugin_version": None,
        "manifest_declared": None,
        "conflict_group": logical_id if logical_id == "claude-code::alpha" else None,
    }


def build_inventory(root):
    alpha_desc = "Alpha routing description with enough distinct words for local accounting."
    alpha_body = "\n".join("Step %d: inspect evidence and preserve deterministic ordering." % i for i in range(1, 65))
    alpha = write_component(
        root, "alpha-a", "alpha", alpha_desc, alpha_body,
        {"references/guide.md": "safe reference text\n" * 12},
    )
    alpha_two = write_component(root, "alpha-b", "alpha", alpha_desc, alpha_body)
    beta = write_component(
        root, "beta", "beta", "Beta candidate inferred from a known root.",
        "\n".join("Beta line %d" % i for i in range(1, 60)),
    )
    codex_copy = write_component(root, "codex-copy", "alpha", alpha_desc, alpha_body)
    codex_other = write_component(
        root, "codex-other", "other", "Codex secondary component.",
        "\n".join("Other line %d" % i for i in range(1, 60)),
    )
    unsafe = write_component(
        root, "unsafe", "unsafe", "Unsafe reference fixture.",
        "\n".join("Unsafe line %d" % i for i in range(1, 60)),
    )
    outside = root / "outside.md"
    outside.write_text("THIS MUST NEVER BE READ\n" * 1000, encoding="utf-8")

    skills = [
        component("custom::i::missing", "custom::missing", "custom-agent", "missing", root / "missing" / "SKILL.md",
                  "Custom agent component with a missing source file."),
        component("cc::i::excluded", "claude-code::builtin", "claude-code", "evil|\n# injected", None,
                  "Builtin entry.", listing="excluded", trigger="excluded", auditable=False,
                  source_kind="builtin", component_type="command", scope="builtin"),
        component("codex::i::other", "codex::other", "codex", "other", codex_other,
                  "Codex secondary component."),
        component("cc::i::alpha-b", "claude-code::alpha", "claude-code", "alpha", alpha_two, alpha_desc),
        component("cc::i::beta", "claude-code::beta", "claude-code", "beta", beta,
                  "Beta candidate inferred from a known root.", active_state="unknown", listing="estimated", trigger="estimated"),
        component("codex::i::alpha", "codex::alpha", "codex", "alpha", codex_copy, alpha_desc),
        component("cc::i::unsafe", "claude-code::unsafe", "claude-code", "unsafe", unsafe,
                  "Unsafe reference fixture.", refs=["../outside.md"]),
        component("cc::i::alpha-a", "claude-code::alpha", "claude-code", "alpha", alpha, alpha_desc,
                  refs=["references/guide.md"]),
    ]
    return {
        "schema_version": "2.0",
        "schema_name": "bulus-skill-auditor.inventory",
        "generated_at": "2026-09-20T08:00:00+08:00",
        "scan_seconds": 1.25,
        "agents": [
            {
                "agent": "claude-code", "detected": True,
                "capabilities": {"scan": True, "usage_stats": True, "active_probe": True,
                                 "plugin_listing": True, "component_types": ["skill", "command"]},
                "skill_roots": [str(root)], "notes": "fixture",
                "discovery": {"status": "complete", "methods": ["fixture"], "cli_version": "x",
                              "fallback_reason": None, "excluded_counts": {"disabled": 1},
                              "component_coverage": ["skill", "command"]},
            },
            {
                "agent": "codex", "detected": True,
                "capabilities": {"scan": True, "usage_stats": True, "active_probe": True,
                                 "plugin_listing": True, "component_types": ["skill"]},
                "skill_roots": [str(root)], "notes": "fixture",
                "discovery": {"status": "complete", "methods": ["fixture"], "cli_version": "x",
                              "fallback_reason": None, "excluded_counts": {},
                              "component_coverage": ["skill"]},
            },
            {
                "agent": "custom-agent", "detected": True,
                "capabilities": {"scan": True, "usage_stats": True, "active_probe": False,
                                 "plugin_listing": False, "component_types": ["skill"]},
                "skill_roots": [str(root)], "notes": "generic fixture",
                "discovery": {"status": "partial", "methods": ["fixture"], "cli_version": None,
                              "fallback_reason": "no authoritative probe", "excluded_counts": {},
                              "component_coverage": ["skill"]},
            },
        ],
        "skills": skills,
        "usage": {
            "window_days": 30,
            "window_note": "fixture",
            "sessions_scanned": 15,
            "records": [
                {
                    "record_id": "r-direct", "agent": "claude-code",
                    "skill_instance_id": "cc::i::alpha-a", "skill_id": "claude-code::alpha",
                    "matched": True, "match_status": "matched", "candidate_instance_ids": ["cc::i::alpha-a"],
                    "source_ref": "alpha", "source_ref_hash": "h1", "name_hint": "alpha",
                    "source_counts": {"tool_use": 3}, "activations": 3,
                    "first_seen": "2026-09-10", "last_seen": "2026-09-19", "lifetime_count": 8,
                },
                {
                    "record_id": "r-old-ambiguous", "agent": "claude-code",
                    "skill_instance_id": None, "skill_id": "claude-code::alpha",
                    "matched": True, "match_status": "matched", "candidate_instance_ids": [],
                    "source_ref": "alpha", "source_ref_hash": "h2", "name_hint": "alpha",
                    "source_counts": {"legacy": 99}, "activations": 99,
                    "first_seen": "2026-09-10", "last_seen": "2026-09-19", "lifetime_count": None,
                },
                {
                    "record_id": "r-unmatched", "agent": "claude-code",
                    "skill_instance_id": None, "skill_id": "claude-code::alpha",
                    "matched": False, "match_status": "unmatched", "candidate_instance_ids": [],
                    "source_ref": "unknown", "source_ref_hash": "h3", "name_hint": "unknown",
                    "source_counts": {"tool_use": 4}, "activations": 4,
                    "first_seen": "2026-09-10", "last_seen": "2026-09-19", "lifetime_count": None,
                },
                {
                    "record_id": "r-codex-legacy", "agent": "codex",
                    "skill_instance_id": None, "skill_id": "codex::alpha",
                    "matched": True, "match_status": "matched", "candidate_instance_ids": [],
                    "source_ref": "path", "source_ref_hash": "h4", "name_hint": "alpha",
                    "source_counts": {"exec": 2}, "activations": 2,
                    "first_seen": "2026-09-18", "last_seen": "2026-09-20", "lifetime_count": None,
                },
                {
                    "record_id": "r-ambiguous", "agent": "claude-code",
                    "skill_instance_id": None, "skill_id": "claude-code::unmatched::x",
                    "matched": False, "match_status": "ambiguous",
                    "candidate_instance_ids": ["cc::i::alpha-a", "cc::i::alpha-b"],
                    "source_ref": "alpha", "source_ref_hash": "h5", "name_hint": "alpha",
                    "source_counts": {"slash": 1}, "activations": 1,
                    "first_seen": "2026-09-20", "last_seen": "2026-09-20", "lifetime_count": None,
                },
            ],
            "coverage": {
                "status": "partial", "transcripts_found": True, "skip_env_detected": False,
                "by_agent": {
                    "claude-code": {"status": "complete", "sessions_scanned": 10,
                                    "transcripts_found": True, "history_disabled": False,
                                    "files_unreadable": 0, "parse_errors": 0, "undated_events": 0,
                                    "direct_events": 8, "matched_activations": 3,
                                    "unmatched_activations": 4, "ambiguous_activations": 1,
                                    "limitations": []},
                    "codex": {"status": "partial", "sessions_scanned": 5,
                              "transcripts_found": True, "history_disabled": False,
                              "files_unreadable": 1, "parse_errors": 0, "undated_events": 0,
                              "direct_events": 2, "matched_activations": 2,
                              "unmatched_activations": 0, "ambiguous_activations": 0,
                              "limitations": ["one unreadable file"]},
                    "custom-agent": {"status": "unavailable", "sessions_scanned": 0,
                                     "transcripts_found": False, "history_disabled": False,
                                     "files_unreadable": 0, "parse_errors": 0, "undated_events": 0,
                                     "direct_events": 0, "matched_activations": 0,
                                     "unmatched_activations": 0, "ambiguous_activations": 0,
                                     "limitations": ["no history adapter"]},
                },
            },
        },
        "issues": [],
        "warnings": [],
    }


def normalize_metrics(doc):
    out = copy.deepcopy(doc)
    out.pop("measured_at", None)
    meta = out.get("metrics_meta") or {}
    meta.pop("measured_at", None)
    return out


def run_measure(inventory, root, suffix):
    inventory_path = root / ("00-inventory-%s.json" % suffix)
    metrics_path = root / ("01-metrics-%s.json" % suffix)
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    rc = measure.main([str(inventory_path), "--out", str(metrics_path)])
    assert rc == 0, "measure should succeed, got %r" % rc
    return json.loads(metrics_path.read_text(encoding="utf-8")), metrics_path


def test_measure_v2(root):
    inventory = build_inventory(root / "components")
    metrics, metrics_path = run_measure(inventory, root, "a")
    metrics_again, _ = run_measure(inventory, root, "b")

    assert metrics["schema_version"] == "2.0"
    assert metrics["schema_name"] == "bulus-skill-auditor.metrics"
    assert normalize_metrics(metrics) == normalize_metrics(metrics_again), "business output must be deterministic"

    instances = [s["instance_id"] for s in metrics["skills"]]
    assert len(instances) == len(set(instances)) == 8
    assert instances == sorted(instances), "component array must have a deterministic instance_id order"
    by = {s["instance_id"]: s for s in metrics["skills"]}

    alpha_a = by["cc::i::alpha-a"]
    alpha_b = by["cc::i::alpha-b"]
    beta = by["cc::i::beta"]
    codex_copy = by["codex::i::alpha"]
    codex_other = by["codex::i::other"]
    missing = by["custom::i::missing"]
    excluded = by["cc::i::excluded"]
    unsafe = by["cc::i::unsafe"]

    assert alpha_a["tokens"]["on_trigger"] > 100
    assert alpha_a["tokens"]["refs_total"] > 0
    assert alpha_a["usage_stats"]["activations"] == 3
    assert alpha_b["usage_stats"]["activations"] == 0, "complete coverage may establish zero"
    assert codex_copy["usage_stats"]["activations"] == 2, "unique legacy logical-id fallback should join"
    assert codex_other["usage_stats"] is None, "partial coverage absence is unknown, not zero"
    assert missing["usage_stats"] is None, "unavailable coverage absence is unknown, not zero"

    assert missing["tokens"]["on_trigger"] is None
    assert missing["tokens"]["measurement_status"] == "incomplete"
    assert missing["priority"] is None and "skeleton" not in missing["structure_flags"]
    assert excluded["tokens"]["accounting_status"] == "excluded"
    assert excluded["priority"] is None and "skeleton" not in excluded["structure_flags"]
    assert unsafe["tokens"]["refs_total"] is None
    assert unsafe["priority"] is None
    assert any(i["code"] == "unsafe_reference_path" and i["path"] == "../outside.md"
               for i in metrics["issues"])

    dup = {d["with"]: d for d in alpha_a["duplication"]}
    assert "codex::i::alpha" in dup
    assert dup["codex::i::alpha"]["with_logical_id"] == "codex::alpha"
    assert "维护副本" in dup["codex::i::alpha"]["note"]
    assert "cc::i::alpha-b" in dup, "same logical id instances must both survive"

    cc_priorities = [s["priority"] for s in by.values()
                     if s["agent"] == "claude-code" and s["priority"] is not None]
    assert cc_priorities
    assert all(p["normalization_scope"] == "agent" and p["normalization_agent"] == "claude-code"
               for p in cc_priorities)
    cc_max = max(s["tokens"]["always"] for s in by.values()
                 if s["agent"] == "claude-code" and s["priority"] is not None)
    assert all(p["agent_max_always_tokens"] == cc_max for p in cc_priorities)
    assert beta["tokens"]["accounting_status"] == "inferred"

    meta = metrics["metrics_meta"]
    cc = meta["by_agent"]["claude-code"]
    assert cc["confirmed_components"] == 3
    assert cc["inferred_components"] == 1
    assert cc["excluded_components"] == 1
    assert cc["confirmed_always_tokens"] == sum(
        by[i]["tokens"]["always"] for i in ("cc::i::alpha-a", "cc::i::alpha-b", "cc::i::unsafe")
    )
    assert cc["inferred_always_tokens"] == beta["tokens"]["always"]
    assert cc["listing_demand_tokens"] == cc["confirmed_always_tokens"]
    assert cc["injected_upper_bound_tokens"] == min(
        cc["listing_demand_tokens"], cc["listing_budget_tokens"]
    )
    assert cc["potential_overflow_tokens"] == max(
        0, cc["listing_demand_tokens"] - cc["listing_budget_tokens"]
    )
    assert meta["by_agent"]["codex"]["listing_budget_tokens"] is None
    assert meta["by_agent"]["codex"]["injected_upper_bound_tokens"] is None
    assert meta["by_agent"]["custom-agent"]["potential_overflow_tokens"] is None
    assert meta["always_total_tokens"] == sum(v["confirmed_always_tokens"] for v in meta["by_agent"].values())
    assert meta["always_inferred_total_tokens"] == sum(v["inferred_always_tokens"] for v in meta["by_agent"].values())
    return inventory, metrics, metrics_path


def test_render_v2(root, inventory, metrics, metrics_path):
    inventory_path = root / "00-inventory-render.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    eval_doc = {
        "schema_version": "2.0",
        "schema_name": "bulus-skill-auditor.eval",
        "evaluated_at": "2026-09-20T09:00:00+08:00",
        "runtime_agent": "claude-code",
        "backend": "claude-plugin-eval",
        "status": "partial",
        "requested_model": "claude-opus-5",
        "requested_judge_model": "judge-explicit",
        "judge_model": "judge-explicit",
        "model": "mixed",
        "budget_usd": 999.0,
        "total_budget_usd": 3.0,
        "total_cost_usd": 0.7,
        "cost_note": "fixture",
        "cost_scope": "this_run_only",
        "runs": 2,
        "concurrency": 1,
        "dry_run": False,
        "results": [
            {
                "skill_instance_id": "cc::i::alpha-a", "skill_id": "claude-code::alpha",
                "status": "complete", "prescreen": {"verdict": "uncertain"},
                "requested_model": "claude-opus-5", "model": "claude-opus-5",
                "judge_model": "judge-explicit", "cache_hit": False, "cacheable": True,
                "cases": [{"name": "official", "effective_model": "claude-opus-5", "status": "complete",
                           "with_score": 0.9, "without_score": 0.1, "delta": 0.8,
                           "with_runs": 2, "without_runs": 2, "skipped_paid_graders": False, "errors": []}],
                "delta": 0.123, "verdict": "valuable", "evidence": "official aggregate",
                "cost_usd": 99.0, "cost_usd_this_run": 0.7, "duration_seconds": 1.0,
                "partial": False, "partial_reason": None, "error": None,
            },
            {
                "skill_instance_id": "cc::i::alpha-b", "skill_id": "claude-code::alpha",
                "status": "cached", "prescreen": {"verdict": "uncertain"},
                "requested_model": "claude-opus-5", "model": "claude-opus-5",
                "judge_model": "judge-explicit", "cache_hit": True, "cacheable": True,
                "cases": [{"name": "cached", "effective_model": "claude-opus-5", "status": "complete",
                           "with_score": 1.0, "without_score": 1.0, "delta": 0.0,
                           "with_runs": 2, "without_runs": 2, "skipped_paid_graders": False, "errors": []}],
                "delta": 0.0, "verdict": "suspected_native_coverage", "evidence": "cache",
                "cost_usd": 88.0, "cost_usd_this_run": 0.0, "duration_seconds": 0.0,
                "partial": False, "partial_reason": None, "error": None,
            },
            {
                "skill_instance_id": "codex::i::alpha", "skill_id": "codex::alpha",
                "status": "partial", "prescreen": {"verdict": "uncertain"},
                "requested_model": "claude-opus-5", "model": "claude-sonnet-5",
                "judge_model": "judge-explicit", "cache_hit": False, "cacheable": False,
                "cases": [{"name": "partial", "effective_model": "claude-sonnet-5", "status": "incomplete",
                           "with_score": 0.8, "without_score": None, "delta": None,
                           "with_runs": 1, "without_runs": 0, "skipped_paid_graders": False,
                           "errors": ["missing arm"]}],
                "delta": None, "verdict": "inconclusive", "evidence": "partial",
                "cost_usd": 77.0, "cost_usd_this_run": 0.0, "duration_seconds": 1.0,
                "partial": True, "partial_reason": "exit 2", "error": None,
            },
            {
                "skill_instance_id": "codex::i::other", "skill_id": "codex::other",
                "status": "unsupported_runtime", "prescreen": {"verdict": "uncertain"},
                "requested_model": "claude-opus-5", "model": "unknown", "judge_model": "unknown",
                "cache_hit": False, "cacheable": False, "cases": [], "delta": None,
                "verdict": "content_value_unverified", "evidence": "$0 unsupported",
                "cost_usd": 0.0, "cost_usd_this_run": 0.0, "duration_seconds": 0.0,
                "partial": False, "partial_reason": None, "error": None,
            },
            {
                "skill_instance_id": "custom::i::missing", "skill_id": "custom::missing",
                "status": "error", "prescreen": {"verdict": "uncertain"},
                "requested_model": "claude-opus-5", "model": "unknown", "judge_model": "unknown",
                "cache_hit": False, "cacheable": False, "cases": [], "delta": None,
                "verdict": "inconclusive", "evidence": "failed",
                "cost_usd": None, "cost_usd_this_run": 0.0, "duration_seconds": 0.0,
                "partial": False, "partial_reason": None, "error": "fixture failure",
            },
            {
                "skill_instance_id": "cc::i::beta", "skill_id": "claude-code::beta",
                "status": "complete", "prescreen": {"verdict": "uncertain"},
                "requested_model": "claude-opus-5", "model": None,
                "judge_model": "judge-explicit", "cache_hit": False, "cacheable": True,
                "cases": [{"name": "looks-done", "effective_model": None, "status": "complete",
                           "with_score": 0.7, "without_score": 0.2, "delta": 0.5,
                           "with_runs": 2, "without_runs": 2, "skipped_paid_graders": False,
                           "errors": []}],
                "delta": 0.5, "verdict": "valuable", "evidence": "model missing",
                "cost_usd": 55.0, "cost_usd_this_run": 0.0, "duration_seconds": 0.0,
                "partial": False, "partial_reason": None, "error": None,
            },
        ],
        "errors": [],
        "warnings": [],
    }
    eval_path = root / "02-eval-results.json"
    eval_path.write_text(json.dumps(eval_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    report_a = root / "03-report-a.md"
    report_b = root / "03-report-b.md"
    list_a = root / "Skill-list-a.md"
    args = ["--metrics", str(metrics_path), "--inventory", str(inventory_path),
            "--eval", str(eval_path), "--out", str(report_a), "--inventory-list", str(list_a)]
    assert render_report.main(args) == 0
    args[args.index(str(report_a))] = str(report_b)
    args[args.index(str(list_a))] = str(root / "Skill-list-b.md")
    assert render_report.main(args) == 0
    text = report_a.read_text(encoding="utf-8")
    text_b = report_b.read_text(encoding="utf-8")
    assert text == text_b, "same inputs must render byte-identical reports regardless of output path"

    assert "按 Agent 分账" in text
    assert "listing demand" in text and "injected upper bound" in text and "potential overflow" in text
    assert "跨 Agent 维护副本" in text and "不代表单次会话可节省" in text
    assert "custom-agent" in text and "无可比 token 上限" in text
    assert "总预算（启动上限）：$3.00" in text
    assert "本次实际新增花费：$0.70" in text
    assert "$999.00" not in text and "$264.00" not in text, "must not show per-item limit as total or sum historical result cost"
    assert "在途 run" in text and "concurrency=1" in text
    assert "claude-opus-5" in text and "claude-sonnet-5" in text
    assert "complete" in text and "cached" in text and "partial" in text and "unsupported_runtime" in text
    assert "已验证 2" in text and "内容价值未验证 4" in text, (
        "a complete-looking result with model=None must stay unverified; "
        "requested_model must never masquerade as the actual model")
    beta_row = [line for line in text.splitlines()
                if "cc::i::beta" in line and "judge-explicit" in line and line.startswith("| ")]
    assert beta_row and "| unknown | claude-opus-5 |" in beta_row[0], (
        "actual-model cell must show unknown while requested stays separate")
    assert "+0.123" in text and "+0.80" not in text, "renderer must use official result.delta, not recompute"
    assert "未匹配 1" in text and "歧义 1" in text
    assert "evil\\|<br># injected" in text
    assert "\n# injected\n" not in text, "table text must not create a new markdown heading"
    assert "跨 Agent 常驻总账" not in text


def test_legacy_and_unknown_schema(root, metrics):
    legacy = copy.deepcopy(metrics)
    legacy.pop("schema_version", None)
    legacy.pop("schema_name", None)
    for skill in legacy["skills"]:
        skill.pop("active_state", None)
        skill.pop("accounting", None)
        (skill.get("tokens") or {}).pop("accounting_status", None)
    legacy_path = root / "legacy-metrics.json"
    legacy_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    legacy_report = root / "legacy-report.md"
    assert render_report.main(["--metrics", str(legacy_path), "--out", str(legacy_report)]) == 0
    legacy_text = legacy_report.read_text(encoding="utf-8")
    assert "legacy inferred" in legacy_text and "非当前活跃性证明" in legacy_text

    bad_inventory = {"schema_version": "9.0", "schema_name": "bulus-skill-auditor.inventory",
                     "skills": [], "issues": [], "warnings": []}
    bad_in = root / "bad-inventory.json"
    bad_out = root / "bad-metrics.json"
    bad_in.write_text(json.dumps(bad_inventory), encoding="utf-8")
    assert measure.main([str(bad_in), "--out", str(bad_out)]) == 2
    assert not bad_out.exists()

    bad_metrics = {"schema_version": "9.0", "schema_name": "bulus-skill-auditor.metrics",
                   "skills": [{"instance_id": "x"}]}
    bad_metrics_path = root / "bad-metrics-input.json"
    bad_report = root / "bad-report.md"
    bad_metrics_path.write_text(json.dumps(bad_metrics), encoding="utf-8")
    assert render_report.main(["--metrics", str(bad_metrics_path), "--out", str(bad_report)]) == 2
    assert not bad_report.exists()


def test_command_without_source_file(root):
    """v2: component_type=command must never get SKILL.md synthesized from path."""
    comp_root = root / "cmd-components"
    src = write_component(comp_root, "beta", "beta", "Beta body used as a trap.", "line\n" * 40)
    command = component("cc::i::cmd", "claude-code::cmd", "claude-code", "cmd", None,
                        "Command component without an explicit source_file.",
                        component_type="command")
    command["path"] = str(Path(src).parent)
    command["realpath"] = str(Path(src).parent)
    command["has_skill_md"] = True  # v1-style producer claiming content exists
    inventory = {
        "schema_version": "2.0",
        "schema_name": "bulus-skill-auditor.inventory",
        "generated_at": "2026-09-20T08:00:00+08:00",
        "scan_seconds": 0.1,
        "agents": [],
        "skills": [command],
        "usage": None,
        "issues": [],
        "warnings": [],
    }
    metrics, _ = run_measure(inventory, root, "cmd")
    skill = metrics["skills"][0]
    assert skill["tokens"]["on_trigger"] is None, "must not measure a synthesized path/SKILL.md for commands"
    assert skill["tokens"]["measurement_status"] == "incomplete"
    assert skill["priority"] is None and "skeleton" not in skill["structure_flags"]
    assert any(issue["code"] == "source_file_unreadable" for issue in metrics["issues"])


def test_malformed_activations_never_crash(root):
    """Wrong-typed activations must degrade to a number, never raise."""
    inventory = build_inventory(root / "components-malformed")
    inventory["usage"]["records"].append({
        "record_id": "r-string-count", "agent": "codex",
        "skill_instance_id": "codex::i::alpha", "skill_id": "codex::alpha",
        "matched": True, "match_status": "matched", "candidate_instance_ids": ["codex::i::alpha"],
        "source_ref": "path", "source_ref_hash": "h6", "name_hint": "alpha",
        "source_counts": {"exec": 5}, "activations": "5",
        "first_seen": "2026-09-19", "last_seen": "2026-09-20", "lifetime_count": None,
    })
    inventory["usage"]["records"].append({
        "record_id": "r-garbage-count", "agent": "claude-code",
        "skill_instance_id": "cc::i::alpha-b", "skill_id": "claude-code::alpha",
        "matched": True, "match_status": "matched", "candidate_instance_ids": ["cc::i::alpha-b"],
        "source_ref": "alpha", "source_ref_hash": "h7", "name_hint": "alpha",
        "source_counts": {"tool_use": 1}, "activations": "not-a-number",
        "first_seen": "2026-09-19", "last_seen": "2026-09-20", "lifetime_count": None,
    })
    inventory["usage"]["records"].append({
        "record_id": "r-inf-count", "agent": "codex",
        "skill_instance_id": "codex::i::other", "skill_id": "codex::other",
        "matched": True, "match_status": "matched", "candidate_instance_ids": ["codex::i::other"],
        "source_ref": "path", "source_ref_hash": "h8", "name_hint": "other",
        "source_counts": {"exec": 1}, "activations": "inf",
        "first_seen": "2026-09-19", "last_seen": "2026-09-20", "lifetime_count": None,
    })
    metrics, metrics_path = run_measure(inventory, root, "mal")
    by = {s["instance_id"]: s for s in metrics["skills"]}
    assert by["codex::i::alpha"]["usage_stats"]["activations"] == 7, "numeric string coerces and merges"
    assert by["cc::i::alpha-b"]["usage_stats"]["activations"] == 0, "garbage degrades to zero under complete coverage"
    assert by["codex::i::other"]["usage_stats"]["activations"] == 0, "inf string degrades to zero, never raises"
    inventory_path = root / "00-inventory-malformed.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    report = root / "03-report-malformed.md"
    assert render_report.main(["--metrics", str(metrics_path), "--inventory", str(inventory_path),
                               "--out", str(report)]) == 0
    text = report.read_text(encoding="utf-8")
    assert "未匹配 1" in text and "歧义 1" in text


def test_per_agent_priority_invariant(root):
    """agent_max_always_tokens must equal the max within that agent only."""
    inventory = build_inventory(root / "components-priority")
    metrics, _ = run_measure(inventory, root, "prio")
    by = {s["instance_id"]: s for s in metrics["skills"]}
    for skill in by.values():
        priority = skill.get("priority")
        if priority is None:
            continue
        peers = [item for item in by.values()
                 if item["agent"] == skill["agent"] and item.get("priority") is not None]
        assert priority["agent_max_always_tokens"] == max(item["tokens"]["always"] for item in peers)
        assert priority["normalization_agent"] == skill["agent"]
    codex_max = max(item["tokens"]["always"] for item in by.values()
                    if item["agent"] == "codex" and item.get("priority") is not None)
    for item in by.values():
        if item["agent"] == "codex" and item.get("priority") is not None:
            assert item["priority"]["agent_max_always_tokens"] == codex_max


def test_v2_missing_fields_transition(root):
    """v2 producer missing new fields: conservative inferred defaults, deterministic."""
    comp_root = root / "components-transition"
    one = write_component(comp_root, "one", "one", "One description.", "one body\n" * 30)
    two = write_component(comp_root, "two", "two", "Two description.", "two body\n" * 30)
    inventory = {
        "schema_version": "2.0",
        "schema_name": "bulus-skill-auditor.inventory",
        "generated_at": "2026-09-20T08:00:00+08:00",
        "scan_seconds": 0.1,
        "agents": [],
        "skills": [
            {"id": "claude-code::one", "agent": "claude-code", "name": "one", "path": str(Path(one).parent),
             "description": "One description.", "has_skill_md": True, "body_lines": 30,
             "ref_files": [], "scripts_files": [], "frontmatter_keys": ["name", "description"]},
            {"id": "codex::two", "agent": "codex", "name": "two", "path": str(Path(two).parent),
             "description": "Two description.", "has_skill_md": True, "body_lines": 30,
             "ref_files": [], "scripts_files": [], "frontmatter_keys": ["name", "description"]},
        ],
        "usage": None,
        "issues": [],
        "warnings": [],
    }
    metrics, metrics_path = run_measure(inventory, root, "trans-a")
    metrics_again, _ = run_measure(inventory, root, "trans-b")
    assert normalize_metrics(metrics) == normalize_metrics(metrics_again)
    for skill in metrics["skills"]:
        assert skill["instance_id"] and "::i::" in skill["instance_id"]
        assert skill["active_state"] == "unknown"
        assert skill["tokens"]["accounting_status"] == "inferred"
        assert skill["usage_stats"] is None, "no usage document means unknown, not zero"
    report = root / "03-report-transition.md"
    assert render_report.main(["--metrics", str(metrics_path), "--out", str(report)]) == 0
    text = report.read_text(encoding="utf-8")
    assert "legacy inferred" not in text, "v2 input must not carry the legacy banner"
    assert "已确认清单 + 推断候选" in text


def main():
    with tempfile.TemporaryDirectory(prefix="skill-auditor-measure-render-") as temp:
        root = Path(temp)
        inventory, metrics, metrics_path = test_measure_v2(root)
        test_render_v2(root, inventory, metrics, metrics_path)
        test_legacy_and_unknown_schema(root, metrics)
        test_command_without_source_file(root)
        test_malformed_activations_never_crash(root)
        test_per_agent_priority_invariant(root)
        test_v2_missing_fields_transition(root)
    print("measure/render v2 focused fixtures: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
