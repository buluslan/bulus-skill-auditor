#!/usr/bin/env python3
"""Offline regression tests for share-copy path redaction."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "redact_report.py"


def load_module():
    spec = importlib.util.spec_from_file_location("redact_report", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(source, target):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--out", str(target)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def assert_no_private_paths(text):
    for fragment in (
        "/Users/alice",
        "/home/bob",
        "/root/private",
        "/private/var/folders",
        "/tmp/auditor-private",
        r"C:\Users\Carol",
        "C:/Users/Dan",
        r"D:\work\auditor-private",
        r"\\server\share\auditor-private",
    ):
        assert fragment not in text, "private path leaked: %s\n%s" % (fragment, text)


def case_embedded_text_redaction(module):
    source = (
        "mac=/Users/alice/Work/audit/SKILL.md; "
        "linux=/home/bob/private/cases.json; "
        "root=/root/private/raw.json; "
        "mac-tmp=/private/var/folders/ab/cd/auditor-private/result.json; "
        "linux-tmp=/tmp/auditor-private/result.log; "
        r"win=C:\Users\Carol\Private\result.json; "
        r"drive=D:\work\auditor-private\result.txt; "
        r"unc=\\server\share\auditor-private\result.csv; "
        "slash=C:/Users/Dan/Private/report.md; "
        "url=https://example.com/docs/report.md; command=/doctor; "
        "relative=references/guide.md"
    )
    output = module.redact_text(source)
    assert_no_private_paths(output)
    assert output.count("<local-path>") == 9, output
    assert "<local-path>/SKILL.md" in output
    assert "<local-path>/cases.json" in output
    assert "<local-path>/raw.json" in output
    assert "<local-path>/result.json" in output
    assert "<local-path>/result.log" in output
    assert "<local-path>/result.txt" in output
    assert "<local-path>/result.csv" in output
    assert "<local-path>/report.md" in output
    assert "https://example.com/docs/report.md" in output
    assert "command=/doctor" in output
    assert "references/guide.md" in output


def case_structured_json_redaction(module):
    payload = {
        "source_file": "/Users/alice/Skill One/SKILL.md",
        "source_realpath": "/home/bob/skills/one/SKILL.md",
        "realpath": "/root/private/one",
        "installPath": r"C:\Users\Carol\AppData\Local\plugin-one",
        "raw_result_path": "C:/Users/Dan/output/eval.json",
        "source_ref": "loaded /Users/alice/Skill One/SKILL.md from transcript",
        "skill_roots": ["/Users/alice/.claude/skills", "relative/root"],
        "description": "keep this value",
        "relative": "references/guide.md",
    }
    output = module.redact(payload)
    serialized = json.dumps(output, ensure_ascii=False)
    assert_no_private_paths(serialized)
    assert output["source_file"] == "<local-path>/SKILL.md"
    assert output["source_realpath"] == "<local-path>/SKILL.md"
    assert output["installPath"] == "<local-path>/plugin-one"
    assert output["raw_result_path"] == "<local-path>/eval.json"
    assert output["description"] == "keep this value"
    assert output["relative"] == "references/guide.md"
    assert output["skill_roots"][1] == "relative/root"


def case_directory_share_copy(module):
    del module  # The CLI is the public behavior under test here.
    with tempfile.TemporaryDirectory(prefix="redaction-fixture-") as temp:
        root = Path(temp)
        source = root / "audit-output"
        target = root / "audit-output-share"
        nested = source / "eval-raw" / "agent-one"
        nested.mkdir(parents=True)

        inventory = {
            "source_file": "/Users/alice/skills/one/SKILL.md",
            "source_realpath": "/home/bob/skills/one/SKILL.md",
            "plugin": {"installPath": r"C:\Users\Carol\plugins\one"},
            "issues": [
                {
                    "message": "failed to read /Users/alice/skills/two/SKILL.md",
                    "safe_context": "command /doctor remains a slash command",
                }
            ],
        }
        (source / "00-inventory.json").write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (source / "03-report.md").write_text(
            "# Report\n\nRaw: `/home/bob/output/02-eval-results.json`\n\n"
            r"Windows: `C:\Users\Carol\output\raw.json`" + "\n\n"
            "Docs: https://example.com/a/b and /doctor.\n",
            encoding="utf-8",
        )
        jsonl_records = [
            {"raw_result_path": "C:/Users/Dan/output/raw.json"},
            {"raw_result_path": r"C:\Users\Carol\output\raw-win.json"},
            {"message": r"loaded C:\Users\Carol\output\embedded-win.json"},
        ]
        (nested / "attempt.jsonl").write_text(
            "\n".join(json.dumps(item) for item in jsonl_records) + "\n",
            encoding="utf-8",
        )
        original_bytes = {
            path.relative_to(source): path.read_bytes()
            for path in source.rglob("*")
            if path.is_file()
        }

        result = run_cli(source, target)
        assert result.returncode == 0, result.stderr
        assert target.is_dir()
        assert sorted(
            str(path.relative_to(target)) for path in target.rglob("*") if path.is_file()
        ) == sorted(str(path) for path in original_bytes)

        for relative, original in original_bytes.items():
            assert (source / relative).read_bytes() == original, "source changed: %s" % relative

        inventory_share = (target / "00-inventory.json").read_text(encoding="utf-8")
        report_share = (target / "03-report.md").read_text(encoding="utf-8")
        raw_share = (target / "eval-raw" / "agent-one" / "attempt.jsonl").read_text(
            encoding="utf-8"
        )
        for text in (inventory_share, report_share, raw_share):
            assert_no_private_paths(text)
        assert "https://example.com/a/b" in report_share
        assert "/doctor" in report_share
        assert "<local-path>/02-eval-results.json" in report_share
        assert "<local-path>/raw.json" in report_share


def case_refuses_in_place_and_nested_output(module):
    del module
    with tempfile.TemporaryDirectory(prefix="redaction-safety-") as temp:
        root = Path(temp)
        source_file = root / "report.json"
        source_file.write_text('{"path":"/Users/alice/private/report.json"}\n', encoding="utf-8")
        before = source_file.read_bytes()
        same = run_cli(source_file, source_file)
        assert same.returncode != 0
        assert source_file.read_bytes() == before

        source_dir = root / "output"
        source_dir.mkdir()
        (source_dir / "report.md").write_text("/home/bob/private/report.md\n", encoding="utf-8")
        nested = run_cli(source_dir, source_dir / "share")
        assert nested.returncode != 0
        assert not (source_dir / "share").exists()


def case_refuses_symlink_input(module):
    del module
    if not hasattr(os, "symlink"):
        return
    with tempfile.TemporaryDirectory(prefix="redaction-symlink-") as temp:
        root = Path(temp)
        original = root / "original.json"
        link = root / "input-link.json"
        target = root / "share.json"
        original.write_text('{"path":"/Users/alice/private/report.json"}\n', encoding="utf-8")
        before = original.read_bytes()
        try:
            link.symlink_to(original)
        except OSError:
            return
        result = run_cli(link, target)
        assert result.returncode != 0
        assert original.read_bytes() == before
        assert not target.exists()


def case_resolves_symlinked_output_parent(module):
    if not hasattr(os, "symlink"):
        return
    with tempfile.TemporaryDirectory(prefix="redaction-parent-link-") as temp:
        root = Path(temp)
        source = root / "source"
        alias = root / "source-alias"
        source.mkdir()
        try:
            alias.symlink_to(source, target_is_directory=True)
        except OSError:
            return
        assert module._is_within(alias / "share", source), (
            "output parents must be resolved before checking whether a share copy "
            "would be created inside its source"
        )


def main():
    module = load_module()
    case_embedded_text_redaction(module)
    case_structured_json_redaction(module)
    case_directory_share_copy(module)
    case_refuses_in_place_and_nested_output(module)
    case_refuses_symlink_input(module)
    case_resolves_symlinked_output_parent(module)
    print("redaction: all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
