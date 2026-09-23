#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evaluate.py 免费端到端测试：所有 Claude CLI 调用均由临时 fake 可执行文件接管。"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATE = ROOT / "scripts" / "evaluate.py"


FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json
import os
import sys

log_path = os.environ.get("FAKE_CLAUDE_LOG")
if log_path:
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\n")

if sys.argv[1:] == ["--version"]:
    print(os.environ.get("FAKE_CLAUDE_VERSION", "2.1.300 (Claude Code)"))
    raise SystemExit(0)

if len(sys.argv) < 4 or sys.argv[1:4] != ["plugin", "eval", "."]:
    raise SystemExit(96)

sequence_path = os.environ["FAKE_CLAUDE_SEQUENCE"]
counter_path = os.environ["FAKE_CLAUDE_COUNTER"]
with open(sequence_path, "r", encoding="utf-8") as handle:
    sequence = json.load(handle)
try:
    with open(counter_path, "r", encoding="utf-8") as handle:
        index = int(handle.read().strip() or "0")
except OSError:
    index = 0
with open(counter_path, "w", encoding="utf-8") as handle:
    handle.write(str(index + 1))
if index >= len(sequence):
    raise SystemExit(97)
item = sequence[index]
if item.get("raw") is not None:
    raw_index = sys.argv.index("--json") + 1
    raw_path = sys.argv[raw_index]
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump(item["raw"], handle, ensure_ascii=False)
if item.get("stderr"):
    print(item["stderr"], file=sys.stderr)
raise SystemExit(int(item.get("returncode", 0)))
'''


def raw_result(case_name="case-1", model="model-a", cost=0.25, partial=False,
               partial_reason=None, schema_version=1, skipped=False, run_error=False):
    with_run = {"score": 0.9}
    without_run = {"score": 0.5}
    if skipped:
        without_run["skippedPaidGraders"] = True
    if run_error:
        with_run["error"] = "fixture run error"
    raw = {
        "schemaVersion": schema_version,
        "suite": {"modelOverride": model, "judgeModel": "judge-a"},
        "costUsd": cost,
        "durationSeconds": 3.2,
        "partial": partial,
        "cases": [
            {
                "name": case_name,
                "model": model,
                "arms": {"with": [with_run], "without": [without_run]},
                "aggregates": {"score": 0.9, "scoreWithout": 0.5, "delta": 0.4},
            }
        ],
        "aggregates": {"meanDelta": 0.4},
    }
    if partial_reason is not None:
        raw["partialReason"] = partial_reason
    return raw


def tree_snapshot(path):
    rows = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            stat = item.stat()
            rows.append(
                (
                    str(item.relative_to(path)),
                    hashlib.sha256(item.read_bytes()).hexdigest(),
                    stat.st_mtime_ns,
                )
            )
    return rows


class EvaluateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="evaluate-integration-")
        self.root = Path(self.temp.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.fake = self.bin_dir / "claude"
        self.fake.write_text(FAKE_CLAUDE, encoding="utf-8")
        self.fake.chmod(0o755)
        self.log = self.root / "claude-calls.jsonl"
        self.sequence = self.root / "sequence.json"
        self.counter = self.root / "counter.txt"
        self.inventory = self.root / "00-inventory.json"
        self.skills = []
        self.env = dict(os.environ)
        self.env["PATH"] = str(self.bin_dir) + os.pathsep + self.env.get("PATH", "")
        self.env["CLAUDECODE"] = "1"
        self.env["FAKE_CLAUDE_LOG"] = str(self.log)
        self.env["FAKE_CLAUDE_SEQUENCE"] = str(self.sequence)
        self.env["FAKE_CLAUDE_COUNTER"] = str(self.counter)
        self.env["FAKE_CLAUDE_VERSION"] = "2.1.300 (Claude Code)"

    def tearDown(self):
        self.temp.cleanup()

    def add_skill(self, suffix, logical_id=None):
        logical_id = logical_id or "claude-code::%s" % suffix
        instance_id = "claude-code::i::%s" % suffix
        source = self.root / "source" / suffix
        source.mkdir(parents=True)
        source_file = source / "SKILL.md"
        source_file.write_text(
            "---\nname: %s\ndescription: fixture\n---\nBody %s\n" % (suffix, suffix),
            encoding="utf-8",
        )
        case = self.root / "cases" / instance_id / "case-1"
        graders = case / "graders"
        graders.mkdir(parents=True)
        (case / "prompt.md").write_text("Run fixture %s." % suffix, encoding="utf-8")
        (graders / "check.md").write_text("PASS if fixture is handled.", encoding="utf-8")
        skill = {
            "instance_id": instance_id,
            "id": logical_id,
            "logical_id": logical_id,
            "agent": "claude-code",
            "name": suffix,
            "runtime_name": suffix,
            "component_name": suffix,
            "component_type": "skill",
            "path": str(source),
            "realpath": str(source.resolve()),
            "source_file": str(source_file),
            "source_realpath": str(source_file.resolve()),
            "symlink_target": None,
            "auditable": True,
        }
        self.skills.append(skill)
        return skill

    def write_inventory(self):
        self.inventory.write_text(
            json.dumps(
                {
                    "schema_version": "2.0",
                    "schema_name": "bulus-skill-auditor.inventory",
                    "skills": self.skills,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def set_sequence(self, items):
        self.sequence.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        if self.counter.exists():
            self.counter.unlink()

    def run_eval(self, selectors, *extra, env=None, model="model-a", runtime="claude-code"):
        command = [
            sys.executable,
            str(EVALUATE),
            "--skills",
            ",".join(selectors),
            "--inventory",
            str(self.inventory),
            "--out-dir",
            str(self.root),
            "--runtime-agent",
            runtime,
            "--runs",
            "1",
            "--max-cost-usd",
            "1.0",
            "--total-budget-usd",
            "2.0",
        ]
        if model is not None:
            command += ["--model", model]
        command += list(extra)
        return subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env or self.env,
        )

    def report(self):
        return json.loads((self.root / "02-eval-results.json").read_text(encoding="utf-8"))

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def eval_calls(self):
        return [call for call in self.calls() if call[:3] == ["plugin", "eval", "."]]

    def test_exit_zero_full_result_forwards_models_and_keeps_source_read_only(self):
        skill = self.add_skill("one")
        self.write_inventory()
        self.set_sequence([{"returncode": 0, "raw": raw_result()}])
        source_root = Path(skill["path"])
        before = tree_snapshot(source_root)

        result = self.run_eval(
            [skill["instance_id"]], "--judge-model", "judge-a", "--skip-cached"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, tree_snapshot(source_root))
        report = self.report()
        self.assertEqual(report["schema_version"], "2.0")
        self.assertEqual(report["schema_name"], "bulus-skill-auditor.eval")
        self.assertEqual(report["runtime_agent"], "claude-code")
        self.assertEqual(report["backend"], "claude-plugin-eval")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["model"], "model-a")
        self.assertEqual(report["requested_model"], "model-a")
        self.assertEqual(report["requested_judge_model"], "judge-a")
        self.assertEqual(report["total_cost_usd"], 0.25)
        self.assertEqual(report["cost_scope"], "this_run_only")
        entry = report["results"][0]
        self.assertEqual(entry["skill_instance_id"], skill["instance_id"])
        self.assertEqual(entry["status"], "complete")
        self.assertEqual(entry["model"], "model-a")
        self.assertEqual(entry["cost_usd_this_run"], 0.25)
        self.assertFalse(entry["cache_hit"])
        self.assertTrue(entry["cacheable"])
        raw_path = Path(entry["raw_result_path"])
        self.assertTrue(raw_path.is_file())
        self.assertIn("eval-raw", raw_path.parts)
        self.assertIn("model-a", raw_path.parts)
        self.assertIn(entry["fingerprint"], raw_path.parts)

        call = self.eval_calls()[0]
        self.assertEqual(call[call.index("--model") + 1], "model-a")
        self.assertEqual(call[call.index("--judge-model") + 1], "judge-a")
        self.assertEqual(call[call.index("--concurrency") + 1], "1")

    def test_exit_one_with_valid_json_is_a_complete_evaluation(self):
        skill = self.add_skill("one")
        self.write_inventory()
        self.set_sequence([{"returncode": 1, "raw": raw_result()}])
        result = self.run_eval([skill["instance_id"]])
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = self.report()["results"][0]
        self.assertEqual(entry["status"], "complete")
        self.assertEqual(entry["verdict"], "valuable")
        self.assertEqual(entry["cost_usd_this_run"], 0.25)

    def test_exit_two_partial_counts_cost_allows_overshoot_and_stops_paid_work(self):
        one = self.add_skill("one")
        two = self.add_skill("two")
        self.write_inventory()
        self.set_sequence(
            [
                {
                    "returncode": 2,
                    "raw": raw_result(cost=1.25, partial=True, partial_reason="budget reached"),
                },
                {"returncode": 0, "raw": raw_result()},
            ]
        )
        result = self.run_eval(
            [one["instance_id"], two["instance_id"]], "--total-budget-usd", "1.0"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report()
        self.assertEqual(len(self.eval_calls()), 1)
        self.assertEqual(report["total_budget_usd"], 1.0)
        self.assertEqual(report["total_cost_usd"], 1.25)
        self.assertIn("启动上限", report["cost_note"])
        self.assertIn("在途", report["cost_note"])
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["results"][0]["status"], "partial")
        self.assertEqual(report["results"][0]["verdict"], "inconclusive")
        self.assertEqual(report["results"][1]["cost_usd_this_run"], 0.0)
        self.assertIn("停止", report["results"][1]["error"])

    def test_started_process_without_json_fails_closed_and_never_reads_history(self):
        one = self.add_skill("one")
        two = self.add_skill("two")
        self.write_inventory()
        stale_dir = self.root / "eval-raw" / "stale" / "model-a" / "old-fingerprint"
        stale_dir.mkdir(parents=True)
        (stale_dir / "attempt-0001.json").write_text(
            json.dumps(raw_result(cost=99.0)), encoding="utf-8"
        )
        self.set_sequence(
            [
                {"returncode": 0, "raw": None},
                {"returncode": 0, "raw": raw_result()},
            ]
        )
        result = self.run_eval([one["instance_id"], two["instance_id"]])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report()
        self.assertEqual(len(self.eval_calls()), 1)
        self.assertEqual(report["total_cost_usd"], 0.0)
        self.assertEqual(report["status"], "error")
        self.assertIsNone(report["results"][0]["cost_usd"])
        self.assertEqual(report["results"][0]["status"], "error")
        self.assertEqual(report["results"][1]["status"], "error")

    def test_exact_cache_hit_costs_zero_and_current_report_has_only_requested_results(self):
        one = self.add_skill("one")
        two = self.add_skill("two")
        self.write_inventory()
        self.set_sequence(
            [
                {"returncode": 0, "raw": raw_result()},
                {"returncode": 0, "raw": raw_result()},
            ]
        )
        first = self.run_eval(
            [one["instance_id"], two["instance_id"]], "--skip-cached"
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(len(self.eval_calls()), 2)

        before_count = len(self.eval_calls())
        self.set_sequence([])
        second = self.run_eval([one["instance_id"]], "--skip-cached")
        self.assertEqual(second.returncode, 0, second.stderr)
        report = self.report()
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(report["results"][0]["skill_instance_id"], one["instance_id"])
        self.assertEqual(report["results"][0]["status"], "cached")
        self.assertTrue(report["results"][0]["cache_hit"])
        self.assertEqual(report["results"][0]["cost_usd_this_run"], 0.0)
        self.assertEqual(report["total_cost_usd"], 0.0)
        self.assertEqual(len(self.eval_calls()), before_count)

    def test_explicit_other_and_auto_without_signal_never_call_claude(self):
        skill = self.add_skill("one")
        self.write_inventory()
        self.set_sequence([{"returncode": 0, "raw": raw_result()}])

        explicit = self.run_eval([skill["instance_id"]], runtime="other", model=None)
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        report = self.report()
        self.assertEqual(report["runtime_agent"], "other")
        self.assertEqual(report["backend"], "none")
        self.assertEqual(report["status"], "unsupported_runtime")
        self.assertEqual(report["total_cost_usd"], 0.0)
        self.assertEqual(report["results"][0]["status"], "unsupported_runtime")
        self.assertEqual(report["results"][0]["verdict"], "content_value_unverified")
        self.assertEqual(self.calls(), [])

        auto_env = dict(self.env)
        auto_env.pop("CLAUDECODE", None)
        auto = self.run_eval(
            [skill["instance_id"]], runtime="auto", model=None, env=auto_env
        )
        self.assertEqual(auto.returncode, 0, auto.stderr)
        report = self.report()
        self.assertEqual(report["runtime_agent"], "unknown")
        self.assertEqual(report["status"], "unsupported_runtime")
        self.assertEqual(self.calls(), [])

    def test_model_mismatch_is_partial_and_not_cacheable(self):
        skill = self.add_skill("one")
        self.write_inventory()
        self.set_sequence([{"returncode": 0, "raw": raw_result(model="actual-model")}])
        result = self.run_eval([skill["instance_id"]], model="requested-model")
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = self.report()["results"][0]
        self.assertEqual(entry["requested_model"], "requested-model")
        self.assertEqual(entry["model"], "actual-model")
        self.assertEqual(entry["status"], "partial")
        self.assertEqual(entry["verdict"], "inconclusive")
        self.assertFalse(entry["cacheable"])

    def test_ambiguous_logical_id_is_rejected_before_version_or_eval_call(self):
        self.add_skill("one", logical_id="claude-code::same")
        self.add_skill("two", logical_id="claude-code::same")
        self.write_inventory()
        self.set_sequence([{"returncode": 0, "raw": raw_result()}])
        result = self.run_eval(["claude-code::same"])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report()
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["total_cost_usd"], 0.0)
        self.assertEqual(self.calls(), [])
        self.assertEqual(report["errors"][0]["code"], "ambiguous_skill_selector")

    def test_deterministic_output_modulo_run_metadata(self):
        import shutil

        one = self.add_skill("one")
        two = self.add_skill("two")
        self.write_inventory()
        inventory_text = self.inventory.read_text(encoding="utf-8")
        documents = []
        for run_index in range(2):
            out_dir = self.root / ("run-%d" % run_index)
            out_dir.mkdir()
            (out_dir / "00-inventory.json").write_text(inventory_text, encoding="utf-8")
            # The case library lives under each out-dir so the two runs stay isolated.
            shutil.copytree(self.root / "cases", out_dir / "cases")
            log = out_dir / "claude-calls.jsonl"
            sequence = out_dir / "sequence.json"
            counter = out_dir / "counter.txt"
            sequence.write_text(
                json.dumps(
                    [
                        {"returncode": 0, "raw": raw_result()},
                        {"returncode": 0, "raw": raw_result()},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            env = dict(self.env)
            env["FAKE_CLAUDE_LOG"] = str(log)
            env["FAKE_CLAUDE_SEQUENCE"] = str(sequence)
            env["FAKE_CLAUDE_COUNTER"] = str(counter)
            result = subprocess.run(
                [
                    sys.executable,
                    str(EVALUATE),
                    "--skills",
                    ",".join(s["instance_id"] for s in (one, two)),
                    "--inventory",
                    str(out_dir / "00-inventory.json"),
                    "--out-dir",
                    str(out_dir),
                    "--runtime-agent",
                    "claude-code",
                    "--runs",
                    "1",
                    "--model",
                    "model-a",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            documents.append((
                str(out_dir),
                json.loads((out_dir / "02-eval-results.json").read_text(encoding="utf-8")),
            ))

        def normalize(out_dir, document):
            document = json.loads(json.dumps(document))
            document.pop("evaluated_at", None)
            for result in document.get("results") or []:
                result.pop("duration_seconds", None)
                for key in ("raw_result_path", "evidence"):
                    value = result.get(key)
                    if isinstance(value, str):
                        result[key] = value.replace(out_dir, "<out-dir>")
                raw_path = Path(result.get("raw_result_path") or "")
                result["raw_result_path"] = raw_path.name if raw_path.name else None
            return document

        first_out, first_doc = documents[0]
        second_out, second_doc = documents[1]
        self.assertEqual(normalize(first_out, first_doc), normalize(second_out, second_doc))


if __name__ == "__main__":
    unittest.main(verbosity=2)
