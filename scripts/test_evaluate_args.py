#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts/evaluate.py"), *args], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


for bad_args, message in [
    (("--skills", "x", "--runs", "0"), "--runs 必须大于 0"),
    (("--skills", "x", "--max-cost-usd", "0"), "--max-cost-usd 必须大于 0"),
    (("--skills", "x", "--total-budget-usd", "-1"), "--total-budget-usd 必须大于 0"),
]:
    result = run(*bad_args)
    assert result.returncode != 0 and message in result.stderr, result.stderr

with tempfile.TemporaryDirectory() as temp:
    source = Path(temp) / "report.json"
    target = Path(temp) / "share.json"
    source.write_text(json.dumps({"path": "/Users/alice/private/skill", "label": "keep"}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/redact_report.py"), str(source), "--out", str(target)], check=True)
    output = target.read_text(encoding="utf-8")
    assert "/Users/alice" not in output and "<local-path>/skill" in output and '"label": "keep"' in output

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    skills = []
    for name in ("one", "two"):
        skill_dir = root / "skills" / name
        case_dir = root / "cases" / name / "case-1"
        skill_dir.mkdir(parents=True)
        case_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: %s\ndescription: fixture\n---\n" % name, encoding="utf-8")
        (case_dir / "prompt.md").write_text("Run the fixture.", encoding="utf-8")
        skills.append({"id": name, "name": name, "path": str(skill_dir)})
    (root / "00-inventory.json").write_text(json.dumps({"skills": skills}), encoding="utf-8")
    result = run("--skills", "one,two", "--inventory", str(root / "00-inventory.json"),
                 "--out-dir", str(root), "--max-cost-usd", "0.5", "--total-budget-usd", "0.5",
                 "--dry-run")
    assert result.returncode == 0, result.stderr
    report = json.loads((root / "02-eval-results.dry-run.json").read_text(encoding="utf-8"))
    assert report["total_cost_usd"] == 0.5
    assert report["results"][1]["error"] == "本次总预算已用完，未启动该 skill 的评测"

print("evaluate args and redaction: ok")
