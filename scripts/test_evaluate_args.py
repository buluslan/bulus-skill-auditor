#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evaluate.py 的纯函数与参数契约测试（标准库，Python 3.9 可直接运行）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate  # noqa: E402


def complete_raw(model="model-a", judge_model="judge-a", return_delta=0.4):
    return {
        "schemaVersion": 1,
        "suite": {"modelOverride": model, "judgeModel": judge_model},
        "costUsd": 0.25,
        "durationSeconds": 4.5,
        "partial": False,
        "cases": [
            {
                "name": "case-1",
                "model": "ignored-by-suite-override",
                "arms": {
                    "with": [{"score": 0.9}],
                    "without": [{"score": 0.5}],
                },
                "aggregates": {
                    "score": 0.9,
                    "scoreWithout": 0.5,
                    "delta": return_delta,
                },
            }
        ],
        "aggregates": {"meanDelta": return_delta},
    }


class CliContractTests(unittest.TestCase):
    def test_cli_command_forwards_execution_and_optional_judge_models(self):
        command = evaluate.cli_command(
            runs=2,
            budget=1.25,
            raw_path="/tmp/result.json",
            execution_model="model-a",
            judge_model="judge-b",
            ablation_mode="with-without",
        )
        self.assertEqual(command[:4], ["claude", "plugin", "eval", "."])
        self.assertEqual(command[command.index("--model") + 1], "model-a")
        self.assertEqual(command[command.index("--judge-model") + 1], "judge-b")
        self.assertEqual(command[command.index("--concurrency") + 1], "1")
        self.assertEqual(command[command.index("--ablation") + 1], "with-without")

    def test_cli_command_does_not_copy_execution_model_to_judge(self):
        command = evaluate.cli_command(
            1, 1.0, "/tmp/result.json", "model-a", None, "with-without"
        )
        self.assertIn("--model", command)
        self.assertNotIn("--judge-model", command)

    def test_runtime_routing_only_auto_detects_reliable_claude_signal(self):
        self.assertEqual(
            evaluate.route_runtime_agent("auto", {"CLAUDECODE": "1"}),
            ("claude-code", "claude-plugin-eval"),
        )
        self.assertEqual(
            evaluate.route_runtime_agent("auto", {"PATH": "/fake/with/claude"}),
            ("unknown", "none"),
        )
        self.assertEqual(
            evaluate.route_runtime_agent("other", {"CLAUDECODE": "1"}),
            ("other", "none"),
        )
        self.assertEqual(
            evaluate.route_runtime_agent("claude-code", {}),
            ("claude-code", "claude-plugin-eval"),
        )


class RawSchemaTests(unittest.TestCase):
    def parse(self, raw, requested_model="model-a", forced_partial_reason=None):
        return evaluate.parse_raw_result(
            raw=raw,
            expected_case_names=["case-1"],
            requested_model=requested_model,
            ablation_mode="with-without",
            raw_path="/tmp/raw.json",
            forced_partial_reason=forced_partial_reason,
        )

    def test_complete_schema_uses_official_aggregates_and_suite_model(self):
        result = self.parse(complete_raw())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["model"], "model-a")
        self.assertEqual(result["judge_model"], "judge-a")
        self.assertEqual(result["delta"], 0.4)
        self.assertEqual(result["verdict"], "valuable")
        self.assertTrue(result["cacheable"])
        case = result["cases"][0]
        self.assertEqual(case["effective_model"], "model-a")
        self.assertEqual(case["with_score"], 0.9)
        self.assertEqual(case["without_score"], 0.5)
        self.assertEqual(case["with_runs"], 1)
        self.assertEqual(case["without_runs"], 1)

    def test_case_models_form_mixed_result_without_suite_override(self):
        raw = complete_raw()
        raw["suite"].pop("modelOverride")
        second = json.loads(json.dumps(raw["cases"][0]))
        second["name"] = "case-2"
        raw["cases"][0]["model"] = "model-a"
        second["model"] = "model-b"
        raw["cases"].append(second)
        parsed = evaluate.parse_raw_result(
            raw, ["case-1", "case-2"], None, "with-without", "/tmp/raw.json"
        )
        self.assertEqual(parsed["model"], "mixed")
        self.assertEqual(parsed["status"], "partial")
        self.assertEqual(parsed["verdict"], "inconclusive")
        self.assertFalse(parsed["cacheable"])

    def test_requested_model_mismatch_is_inconclusive(self):
        result = self.parse(complete_raw(model="actual-model"), requested_model="requested-model")
        self.assertEqual(result["model"], "actual-model")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["verdict"], "inconclusive")
        self.assertIn("requested-model", result["partial_reason"])
        self.assertFalse(result["cacheable"])

    def test_run_error_and_skipped_paid_graders_are_not_scored(self):
        for mutation in ("run_error", "skipped"):
            raw = complete_raw()
            if mutation == "run_error":
                raw["cases"][0]["arms"]["with"][0]["error"] = "boom"
            else:
                raw["cases"][0]["arms"]["without"][0]["skippedPaidGraders"] = True
            result = self.parse(raw)
            self.assertEqual(result["status"], "partial", mutation)
            self.assertEqual(result["verdict"], "inconclusive", mutation)
            self.assertIsNone(result["delta"], mutation)
            self.assertFalse(result["cacheable"], mutation)

    def test_missing_arm_or_case_is_inconclusive(self):
        raw = complete_raw()
        raw["cases"][0]["arms"].pop("without")
        result = self.parse(raw)
        self.assertEqual(result["cases"][0]["status"], "incomplete")
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["delta"])
        self.assertEqual(result["verdict"], "inconclusive")

        missing = evaluate.parse_raw_result(
            complete_raw(), ["case-1", "case-2"], "model-a", "with-without", "/tmp/raw.json"
        )
        self.assertEqual(missing["status"], "partial")
        self.assertTrue(any(c["name"] == "case-2" for c in missing["cases"]))

    def test_unknown_schema_preserves_cost_but_never_scores(self):
        raw = complete_raw()
        raw["schemaVersion"] = "future-999"
        result = self.parse(raw)
        self.assertEqual(result["cost_usd"], 0.25)
        self.assertEqual(result["source_schema_version"], "future-999")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["verdict"], "inconclusive")
        self.assertIsNone(result["delta"])

    def test_partial_and_forced_partial_never_score(self):
        raw = complete_raw()
        raw["partial"] = True
        raw["partialReason"] = "budget reached"
        result = self.parse(raw)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["verdict"], "inconclusive")
        self.assertIsNone(result["delta"])

        forced = self.parse(complete_raw(), forced_partial_reason="CLI exit 2")
        self.assertEqual(forced["status"], "partial")
        self.assertEqual(forced["verdict"], "inconclusive")

    def test_run_scores_do_not_reconstruct_missing_official_aggregate(self):
        raw = complete_raw()
        raw["cases"][0]["aggregates"] = {}
        raw["aggregates"] = {}
        result = self.parse(raw)
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["cases"][0]["with_score"])
        self.assertIsNone(result["delta"])


class FingerprintAndIdentityTests(unittest.TestCase):
    def test_fingerprint_covers_all_cache_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skill"
            case = root / "case-1"
            graders = case / "graders"
            skill.mkdir()
            graders.mkdir(parents=True)
            skill_file = skill / "SKILL.md"
            prompt = case / "prompt.md"
            grader = graders / "check.md"
            skill_file.write_text("skill-v1", encoding="utf-8")
            prompt.write_text("prompt-v1", encoding="utf-8")
            grader.write_text("grader-v1", encoding="utf-8")
            cases = [("case-1", str(case))]

            def fingerprint(**overrides):
                values = {
                    "skill_instance_id": "claude-code::i::abc",
                    "source_root": str(skill),
                    "cases": cases,
                    "runs": 2,
                    "execution_model": "model-a",
                    "judge_model": None,
                    "ablation_mode": "with-without",
                    "claude_version": "2.1.300",
                    "schema_versions": ("1", "1.0"),
                }
                values.update(overrides)
                return evaluate.compute_fingerprint(**values)

            baseline = fingerprint()
            parameter_changes = [
                {"runs": 3},
                {"execution_model": "model-b"},
                {"judge_model": "judge-b"},
                {"ablation_mode": "none"},
                {"claude_version": "2.1.301"},
                {"schema_versions": ("2",)},
                {"skill_instance_id": "claude-code::i::different"},
            ]
            for change in parameter_changes:
                self.assertNotEqual(baseline, fingerprint(**change), change)

            skill_file.write_text("skill-v2", encoding="utf-8")
            self.assertNotEqual(baseline, fingerprint())
            skill_file.write_text("skill-v1", encoding="utf-8")
            prompt.write_text("prompt-v2", encoding="utf-8")
            self.assertNotEqual(baseline, fingerprint())
            prompt.write_text("prompt-v1", encoding="utf-8")
            grader.write_text("grader-v2", encoding="utf-8")
            self.assertNotEqual(baseline, fingerprint())

    def test_legacy_logical_id_must_be_unique(self):
        skills = [
            {"instance_id": "i-1", "id": "claude-code::same", "auditable": True},
            {"instance_id": "i-2", "id": "claude-code::same", "auditable": True},
        ]
        resolved, problems = evaluate.resolve_skill_selectors(skills, ["claude-code::same"])
        self.assertEqual(resolved, [])
        self.assertEqual(problems[0]["code"], "ambiguous_skill_selector")
        resolved, problems = evaluate.resolve_skill_selectors(skills, ["i-2"])
        self.assertEqual([s["instance_id"] for s in resolved], ["i-2"])
        self.assertEqual(problems, [])

    def test_non_auditable_component_is_rejected(self):
        resolved, problems = evaluate.resolve_skill_selectors(
            [{"instance_id": "i-1", "id": "claude-code::x", "auditable": False}], ["i-1"]
        )
        self.assertEqual(resolved, [])
        self.assertEqual(problems[0]["code"], "component_not_auditable")

    def test_capability_cache_is_whitelisted_data_not_a_command(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "capabilities.json"
            marker = Path(temp) / "must-not-exist"
            cache.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "claude_version": "2.1.300",
                        "supports": {"plugin_eval": True},
                        "command": ["touch", str(marker)],
                        "probe_command": "touch %s" % marker,
                    }
                ),
                encoding="utf-8",
            )
            loaded = evaluate.load_capability_cache(str(cache))
            self.assertEqual(
                loaded,
                {
                    "schema_version": "1",
                    "claude_version": "2.1.300",
                    "supports": {"plugin_eval": True},
                },
            )
            self.assertFalse(marker.exists())


class ArgumentValidationTests(unittest.TestCase):
    def run_script(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/evaluate.py"), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def test_numeric_validation(self):
        for bad_args, message in [
            (("--skills", "x", "--runs", "0"), "--runs 必须大于 0"),
            (("--skills", "x", "--max-cost-usd", "0"), "--max-cost-usd 必须大于 0"),
            (("--skills", "x", "--total-budget-usd", "-1"), "--total-budget-usd 必须大于 0"),
            (("--skills", "x", "--max-cost-usd", "nan"), "拒绝 nan/inf"),
            (("--skills", "x", "--max-cost-usd", "inf"), "拒绝 nan/inf"),
            (("--skills", "x", "--max-cost-usd", "1", "--total-budget-usd", "nan"), "拒绝 nan/inf"),
            (("--skills", "x", "--max-cost-usd", "1", "--total-budget-usd", "inf"), "拒绝 nan/inf"),
        ]:
            result = self.run_script(*bad_args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)

    def test_claude_backend_requires_model_before_any_cli_process(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = root / "00-inventory.json"
            inventory.write_text(json.dumps({"skills": []}), encoding="utf-8")
            log = root / "fake.log"
            env = dict(os.environ)
            env["CLAUDECODE"] = "1"
            env["FAKE_CLAUDE_LOG"] = str(log)
            result = self.run_script(
                "--skills", "x", "--inventory", str(inventory), "--out-dir", str(root),
                "--runtime-agent", "claude-code", env=env
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--model", result.stderr)
            self.assertFalse(log.exists())

    def test_empty_skills_selector_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = root / "00-inventory.json"
            inventory.write_text(json.dumps({"skills": []}), encoding="utf-8")
            result = self.run_script(
                "--skills", "  ", "--inventory", str(inventory), "--out-dir", str(root), "--dry-run"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--skills 解析后为空", result.stderr)

    def test_v1_non_string_source_file_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = root / "00-inventory.json"
            inventory.write_text(
                json.dumps({"skills": [{"name": "odd", "source_file": ["/not/a/path"]}]}),
                encoding="utf-8",
            )
            adapted = evaluate.load_inventory(str(inventory))
            self.assertEqual(adapted[0]["source_file"], None)
            self.assertFalse(adapted[0]["auditable"])

    def test_redaction_smoke(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "report.json"
            target = Path(temp) / "share.json"
            source.write_text(
                json.dumps({"path": "/Users/alice/private/skill", "label": "keep"}),
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/redact_report.py"), str(source), "--out", str(target)],
                check=True,
            )
            output = target.read_text(encoding="utf-8")
            self.assertNotIn("/Users/alice", output)
            self.assertIn("<local-path>/skill", output)
            self.assertIn('"label": "keep"', output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
