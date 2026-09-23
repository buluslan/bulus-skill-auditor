#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime-aware, model-correct orchestration for official Claude plugin evals.

The source component and its cases are read-only.  Temporary packages, raw evidence,
cache entries, and the current-run report are written only below ``--out-dir``.
No paid process is started for unsupported runtimes, ambiguous component selectors,
or an unpinned execution model.
"""
import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime


CLI_BIN = "claude"
DEFAULT_RUNS = 2
DEFAULT_BUDGET = 2.0
DEFAULT_ABLATION = "with-without"
SCHEMA_VERSION = "2.0"
SCHEMA_NAME = "bulus-skill-auditor.eval"
SUPPORTED_EVAL_SCHEMA_VERSIONS = ("1", "1.0")
DEFAULT_JUDGE_SENTINEL = "cli-default-unpinned"
COST_NOTE = (
    "total_budget_usd 是本次串行启动上限，不是绝对硬封顶；concurrency=1 时，"
    "一个已经在途的 run 仍可能让最终花费小幅超过上限。total_cost_usd 只统计"
    "本次新启动且 CLI 可验证的 costUsd，精确缓存命中为 $0。"
)
COPY_IGNORE = shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", ".git")
IGNORE_DIR_NAMES = {".git", "__pycache__"}
IGNORE_FILE_PATTERNS = (".DS_Store", "*.pyc")
DELTA_FLAT = 0.1
LOW_SCORE = 0.5
PRESCREEN = {
    "verdict": "agent-upstream",
    "reason": "预筛由 Agent 按 references/audit-rubric.md 完成；脚本只验证官方 eval 证据",
}


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sanitize(text):
    """Return a portable filename fragment without evaluating input as a command."""
    value = str(text or "")
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in value)
    return safe or "value"


def safe_component(text):
    """Create a collision-resistant path component while preserving already-safe names."""
    value = str(text or "")
    safe = sanitize(value)
    if safe == value and len(safe) <= 96:
        return safe
    prefix = safe[:80].rstrip("._-") or "value"
    return "%s--%s" % (prefix, hashlib.sha256(value.encode("utf-8")).hexdigest()[:12])


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def clean_text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def normalize_schema_version(value):
    if isinstance(value, bool) or value is None:
        return "unknown"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or "unknown"


def concrete_model(value):
    model = clean_text(value)
    return bool(model and model.lower() not in {"unknown", "mixed", "auto", "default"})


def route_runtime_agent(requested, environ=None):
    """Resolve a backend without using PATH presence as runtime evidence."""
    env = os.environ if environ is None else environ
    if requested == "claude-code":
        return "claude-code", "claude-plugin-eval"
    if requested == "other":
        return "other", "none"
    if env.get("CLAUDECODE") == "1":
        return "claude-code", "claude-plugin-eval"
    return "unknown", "none"


def _legacy_instance_id(skill):
    agent = str(skill.get("agent") or "unknown")
    component_type = str(skill.get("component_type") or "skill")
    runtime_name = str(skill.get("runtime_name") or skill.get("name") or "unknown")
    install_scope = str(skill.get("install_scope") or skill.get("scope") or "unknown")
    source_file = str(skill.get("source_file") or "")
    if not source_file and skill.get("path"):
        source_file = os.path.join(str(skill.get("path")), "SKILL.md")
    lexical = os.path.normpath(os.path.abspath(os.path.expanduser(source_file))) if source_file else ""
    realpath = os.path.realpath(lexical) if lexical else ""
    material = "\0".join((agent, component_type, runtime_name, install_scope, lexical, realpath))
    return "%s::i::%s" % (agent, hashlib.sha256(material.encode("utf-8")).hexdigest()[:20])


def load_inventory(path):
    """Load v2 inventory, adapting v1 records conservatively at the boundary."""
    with open(path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError("inventory 顶层必须是 JSON object")
    version = normalize_schema_version(document.get("schema_version"))
    if version != "unknown":
        major = version.split(".", 1)[0]
        if major not in {"1", "2"}:
            raise ValueError("不支持 inventory schema major %s" % major)
    raw_skills = document.get("skills") or []
    if not isinstance(raw_skills, list):
        raise ValueError("inventory.skills 必须是 array")
    adapted = []
    legacy = version == "unknown" or version.startswith("1")
    for raw in raw_skills:
        if not isinstance(raw, dict):
            continue
        skill = dict(raw)
        skill.setdefault("component_type", "skill")
        runtime_name = skill.get("runtime_name") or skill.get("name")
        skill.setdefault("runtime_name", runtime_name)
        skill.setdefault("name", runtime_name)
        logical_id = skill.get("logical_id") or skill.get("id")
        skill["logical_id"] = logical_id
        skill["id"] = logical_id
        source_file = skill.get("source_file")
        if source_file and not isinstance(source_file, str):
            # 非 str 的 source_file 视为无效，走回退路径；不把任意 JSON 值编造成路径
            source_file = None
        if not source_file and skill.get("path"):
            source_file = os.path.join(str(skill.get("path")), "SKILL.md")
        skill["source_file"] = source_file
        if source_file and not skill.get("source_realpath"):
            skill["source_realpath"] = os.path.realpath(source_file)
        if not skill.get("instance_id"):
            skill["instance_id"] = _legacy_instance_id(skill)
        if "auditable" not in skill:
            # A v1 input cannot prove runtime visibility.  It may still be evaluated when
            # it exposes a concrete source file, but this is an inferred compatibility path.
            skill["auditable"] = bool(legacy and source_file and os.path.isfile(source_file))
        adapted.append(skill)
    return adapted


def resolve_skill_selectors(skills, selectors):
    """Resolve exact instance IDs, then uniquely resolvable legacy logical IDs."""
    by_instance = {}
    by_logical = {}
    for skill in skills:
        instance_id = skill.get("instance_id")
        if instance_id:
            by_instance.setdefault(instance_id, []).append(skill)
        logical_id = skill.get("logical_id") or skill.get("id")
        if logical_id:
            by_logical.setdefault(logical_id, []).append(skill)

    resolved = []
    problems = []
    seen = set()
    for selector in selectors:
        candidates = by_instance.get(selector) or []
        if len(candidates) > 1:
            problems.append({
                "code": "duplicate_instance_id",
                "selector": selector,
                "message": "inventory 中 instance_id 重复，无法安全关联",
            })
            continue
        if not candidates:
            candidates = by_logical.get(selector) or []
            if len(candidates) > 1:
                problems.append({
                    "code": "ambiguous_skill_selector",
                    "selector": selector,
                    "message": "旧 logical id 命中 %d 个实例；请改传唯一 instance_id" % len(candidates),
                })
                continue
        if not candidates:
            problems.append({
                "code": "skill_selector_not_found",
                "selector": selector,
                "message": "inventory 中找不到该 instance_id/logical id",
            })
            continue
        skill = candidates[0]
        if skill.get("auditable") is not True:
            problems.append({
                "code": "component_not_auditable",
                "selector": selector,
                "message": "该组件 auditable 不是 true，禁止进入付费评测",
                "skill_instance_id": skill.get("instance_id"),
            })
            continue
        instance_id = skill.get("instance_id")
        if instance_id not in seen:
            resolved.append(skill)
            seen.add(instance_id)
    return resolved, problems


def _safe_child(root, child):
    root_abs = os.path.abspath(root)
    path = os.path.abspath(os.path.join(root_abs, str(child)))
    try:
        if os.path.commonpath((root_abs, path)) != root_abs:
            return None
    except ValueError:
        return None
    return path


def find_cases(out_dir, skill):
    """Find deterministic case directories, preferring the canonical instance ID."""
    cases_root = os.path.join(out_dir, "cases")
    identifiers = [skill.get("instance_id"), skill.get("logical_id") or skill.get("id")]
    root = None
    used_identifier = None
    for identifier in identifiers:
        if not identifier:
            continue
        candidate = _safe_child(cases_root, identifier)
        if candidate and os.path.isdir(candidate):
            root = candidate
            used_identifier = identifier
            break
    warnings = []
    if root is None:
        return [], warnings
    if used_identifier != skill.get("instance_id"):
        warnings.append(
            "%s: case 库沿用旧 logical id 路径；建议迁移到 instance_id 路径"
            % skill.get("instance_id")
        )
    cases = []
    for name in sorted(os.listdir(root)):
        case_dir = os.path.join(root, name)
        if not os.path.isdir(case_dir):
            continue
        if not os.path.isfile(os.path.join(case_dir, "prompt.md")):
            warnings.append("%s/%s: 缺 prompt.md，跳过" % (used_identifier, name))
            continue
        cases.append((name, case_dir))
        if not os.path.isdir(os.path.join(case_dir, "graders")):
            warnings.append("%s/%s: 无 graders/；官方默认评分仍可能产生付费 judge" % (used_identifier, name))
    return cases, warnings


def source_root_for(skill):
    source_file = skill.get("source_file")
    path = skill.get("symlink_target") or skill.get("path")
    if source_file and os.path.isfile(source_file):
        if os.path.basename(source_file).lower() == "skill.md":
            return os.path.dirname(source_file)
        if path and os.path.isdir(path):
            return path
        return os.path.dirname(source_file)
    if path and os.path.isdir(path):
        return path
    return None


def _ignored_file(name):
    return any(fnmatch.fnmatch(name, pattern) for pattern in IGNORE_FILE_PATTERNS)


def _hash_tree(hasher, label, root):
    if not root or not os.path.isdir(root):
        raise OSError("目录不存在：%s" % root)
    root_abs = os.path.abspath(root)
    hasher.update(("TREE\0%s\0" % label).encode("utf-8"))
    for current, dirnames, filenames in os.walk(root_abs, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in IGNORE_DIR_NAMES)
        rel_dir = os.path.relpath(current, root_abs)
        for dirname in list(dirnames):
            full = os.path.join(current, dirname)
            if os.path.islink(full):
                rel = os.path.normpath(os.path.join(rel_dir, dirname)).replace(os.sep, "/")
                hasher.update(("DLINK\0%s\0%s\0" % (rel, os.readlink(full))).encode("utf-8"))
        for filename in sorted(filenames):
            if _ignored_file(filename):
                continue
            full = os.path.join(current, filename)
            rel = os.path.normpath(os.path.join(rel_dir, filename)).replace(os.sep, "/")
            if rel.startswith("./"):
                rel = rel[2:]
            hasher.update(("FILE\0%s\0" % rel).encode("utf-8"))
            if os.path.islink(full):
                hasher.update(("LINK\0%s\0" % os.readlink(full)).encode("utf-8"))
            try:
                with open(full, "rb") as handle:
                    while True:
                        block = handle.read(1024 * 1024)
                        if not block:
                            break
                        hasher.update(block)
            except OSError as exc:
                raise OSError("无法读取指纹文件 %s：%s" % (full, exc))
            hasher.update(b"\0END\0")


def compute_fingerprint(skill_instance_id, source_root, cases, runs, execution_model,
                        judge_model, ablation_mode, claude_version,
                        schema_versions=SUPPORTED_EVAL_SCHEMA_VERSIONS):
    """Hash every cache-relevant input; no path or label is treated as executable."""
    metadata = {
        "skill_instance_id": skill_instance_id,
        "runs": runs,
        "execution_model": execution_model,
        "judge_model": judge_model or DEFAULT_JUDGE_SENTINEL,
        "ablation_mode": ablation_mode,
        "claude_version": claude_version,
        "supported_eval_schema_versions": list(schema_versions),
    }
    hasher = hashlib.sha256()
    hasher.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    _hash_tree(hasher, "skill", source_root)
    for case_name, case_dir in sorted(cases, key=lambda item: item[0]):
        _hash_tree(hasher, "case:%s" % case_name, case_dir)
    return hasher.hexdigest()


def _assert_below(path, root):
    path_abs = os.path.abspath(path)
    root_abs = os.path.abspath(root)
    try:
        ok = os.path.commonpath((path_abs, root_abs)) == root_abs
    except ValueError:
        ok = False
    if not ok:
        raise OSError("拒绝写出 --out-dir：%s" % path)


def assemble_pkg(pkg_dir, out_dir, skill, cases):
    """Assemble an isolated plugin package below out_dir, never touching the source."""
    _assert_below(pkg_dir, out_dir)
    source_root = source_root_for(skill)
    source_file = skill.get("source_file")
    if not source_root:
        raise OSError("组件来源目录不存在")
    if os.path.isdir(pkg_dir):
        shutil.rmtree(pkg_dir)
    manifest_dir = os.path.join(pkg_dir, ".claude-plugin")
    os.makedirs(manifest_dir)
    component_name = skill.get("component_name") or skill.get("runtime_name") or skill.get("name") or "skill"
    package_name = sanitize(component_name)
    with open(os.path.join(manifest_dir, "plugin.json"), "w", encoding="utf-8") as handle:
        json.dump({"name": package_name + "-test"}, handle, ensure_ascii=False)
    destination = os.path.join(pkg_dir, "skills", package_name)
    if source_file and os.path.isfile(source_file) and os.path.basename(source_file).lower() != "skill.md":
        os.makedirs(destination)
        shutil.copy2(source_file, os.path.join(destination, "SKILL.md"))
    else:
        shutil.copytree(source_root, destination, ignore=COPY_IGNORE)
    for case_name, case_dir in cases:
        shutil.copytree(case_dir, os.path.join(pkg_dir, "evals", case_name), ignore=COPY_IGNORE)
    return package_name


def cli_command(runs, budget, raw_path, execution_model, judge_model=None,
                ablation_mode=DEFAULT_ABLATION):
    command = [
        CLI_BIN,
        "plugin",
        "eval",
        ".",
        "--runs",
        str(runs),
        "--max-cost-usd",
        str(budget),
        "--no-publish",
        "--trust-plugin",
        "--json",
        raw_path,
        "--model",
        execution_model,
        "--concurrency",
        "1",
        "--ablation",
        ablation_mode,
    ]
    if judge_model:
        command.extend(("--judge-model", judge_model))
    return command


def run_cli(pkg_dir, command, timeout_seconds):
    """Execute one fixed argv list.  Never use shell=True or cached command strings."""
    try:
        process = subprocess.run(
            command,
            cwd=pkg_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "started": True,
            "returncode": process.returncode,
            "timed_out": False,
            "launch_error": None,
        }
    except subprocess.TimeoutExpired:
        return {
            "started": True,
            "returncode": None,
            "timed_out": True,
            "launch_error": None,
        }
    except OSError as exc:
        return {
            "started": False,
            "returncode": None,
            "timed_out": False,
            "launch_error": "%s: %s" % (exc.__class__.__name__, exc),
        }


def load_capability_cache(path):
    """Read a strict data-only cache; command/probe fields are intentionally ignored."""
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("capability cache 顶层必须是 JSON object")
    result = {}
    schema_version = clean_text(raw.get("schema_version"))
    claude_version = clean_text(raw.get("claude_version"))
    if schema_version:
        result["schema_version"] = schema_version
    if claude_version:
        result["claude_version"] = claude_version
    allowed_supports = {"plugin_eval", "model", "judge_model", "concurrency", "ablation"}
    supports = raw.get("supports")
    if isinstance(supports, dict):
        safe_supports = {
            key: value for key, value in supports.items()
            if key in allowed_supports and isinstance(value, bool)
        }
        if safe_supports:
            result["supports"] = safe_supports
    return result


def query_claude_version(timeout_seconds=10):
    """Use one fixed, free argv probe; return (version, error)."""
    try:
        process = subprocess.run(
            [CLI_BIN, "--version"], capture_output=True, text=True, timeout=timeout_seconds
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "%s: %s" % (exc.__class__.__name__, exc)
    if process.returncode != 0:
        return None, "claude --version exit %d" % process.returncode
    lines = (process.stdout or process.stderr or "").strip().splitlines()
    version = lines[0].strip() if lines else ""
    return (version[:200], None) if version else (None, "claude --version 未返回版本")


def judge(with_score, without_score, delta):
    if with_score < LOW_SCORE and without_score < LOW_SCORE:
        return "inconclusive", "两臂均低分，case/grader 可能失效"
    if delta > DELTA_FLAT:
        return "valuable", "官方 Δ 显示 with 明显高于 without"
    if delta < -DELTA_FLAT:
        return "inconclusive", "with 低于 without，先查 judge 与 skill 干扰"
    return "suspected_native_coverage", "官方 Δ 接近平，仍须人工复核 case 区分度"


def _contains_true_flag(node, key):
    if isinstance(node, dict):
        if node.get(key) is True:
            return True
        return any(_contains_true_flag(value, key) for value in node.values())
    if isinstance(node, list):
        return any(_contains_true_flag(value, key) for value in node)
    return False


def _run_failed(run):
    if not isinstance(run, dict):
        return True
    if run.get("error") not in (None, "", False):
        return True
    status = str(run.get("status") or "").lower()
    return status in {"error", "failed", "cancelled", "canceled"}


def _dedupe(items):
    result = []
    seen = set()
    for item in items:
        text = str(item)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _raw_case_name(case):
    return clean_text(case.get("name")) or clean_text(case.get("id")) or "?"


def _case_result(raw_case, effective_model, ablation_mode):
    name = _raw_case_name(raw_case)
    arms = raw_case.get("arms") if isinstance(raw_case.get("arms"), dict) else {}
    with_present = "with" in arms and isinstance(arms.get("with"), list)
    without_present = "without" in arms and isinstance(arms.get("without"), list)
    with_runs = arms.get("with") if with_present else []
    without_runs = arms.get("without") if without_present else []
    aggregates = raw_case.get("aggregates") if isinstance(raw_case.get("aggregates"), dict) else {}
    with_score = aggregates.get("score") if is_number(aggregates.get("score")) else None
    without_score = aggregates.get("scoreWithout") if is_number(aggregates.get("scoreWithout")) else None
    delta = aggregates.get("delta") if is_number(aggregates.get("delta")) else None
    skipped = _contains_true_flag(raw_case, "skippedPaidGraders")
    failures = []
    run_error = False
    for arm_name, runs in (("with", with_runs), ("without", without_runs)):
        for index, run in enumerate(runs, 1):
            if _run_failed(run):
                run_error = True
                failures.append("%s run %d failed" % (arm_name, index))
    case_status = str(raw_case.get("status") or "").lower()
    if case_status in {"error", "failed"} or raw_case.get("error") not in (None, "", False):
        run_error = True
        failures.append("case reported an error")

    incomplete = []
    if not with_present or not with_runs:
        incomplete.append("missing with arm")
    if with_score is None:
        incomplete.append("missing official aggregates.score")
    if ablation_mode == "with-without":
        if not without_present or not without_runs:
            incomplete.append("missing without arm")
        if without_score is None:
            incomplete.append("missing official aggregates.scoreWithout")
        if delta is None:
            incomplete.append("missing official aggregates.delta")
    else:
        incomplete.append("ablation none has no comparable baseline arm")
    if skipped:
        incomplete.append("skippedPaidGraders=true")

    if run_error:
        status = "error"
    elif incomplete:
        status = "incomplete"
    else:
        status = "complete"
    return {
        "name": name,
        "effective_model": effective_model or "unknown",
        "status": status,
        "with_score": with_score,
        "without_score": without_score,
        "delta": delta,
        "with_runs": len(with_runs),
        "without_runs": len(without_runs),
        "skipped_paid_graders": skipped,
        "errors": _dedupe(failures + incomplete),
    }


def parse_raw_result(raw, expected_case_names, requested_model, ablation_mode,
                     raw_path, forced_partial_reason=None, requested_judge_model=None):
    """Validate official raw JSON and derive a result without rebuilding official scores."""
    if not isinstance(raw, dict):
        raise ValueError("eval raw 顶层必须是 JSON object")
    source_schema = normalize_schema_version(raw.get("schemaVersion"))
    known_schema = source_schema in SUPPORTED_EVAL_SCHEMA_VERSIONS
    suite = raw.get("suite") if isinstance(raw.get("suite"), dict) else {}
    suite_model = clean_text(suite.get("modelOverride"))
    raw_cases = raw.get("cases") if isinstance(raw.get("cases"), list) else []
    case_models = []
    by_name = {}
    duplicate_names = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            continue
        name = _raw_case_name(raw_case)
        if name in by_name:
            duplicate_names.add(name)
        else:
            by_name[name] = raw_case
        model = suite_model or clean_text(raw_case.get("model"))
        if model:
            case_models.append(model)

    if suite_model:
        actual_model = suite_model
    else:
        distinct_models = sorted(set(case_models))
        if len(distinct_models) == 1:
            actual_model = distinct_models[0]
        elif len(distinct_models) > 1:
            actual_model = "mixed"
        else:
            actual_model = "unknown"

    judge_model = (
        clean_text(suite.get("judgeModelOverride"))
        or clean_text(suite.get("judgeModel"))
        or clean_text(raw.get("judgeModel"))
        or clean_text(requested_judge_model)
        or DEFAULT_JUDGE_SENTINEL
    )
    cases_out = []
    blockers = []
    expected = list(expected_case_names)
    for name in expected:
        raw_case = by_name.get(name)
        if raw_case is None:
            cases_out.append({
                "name": name,
                "effective_model": suite_model or "unknown",
                "status": "incomplete",
                "with_score": None,
                "without_score": None,
                "delta": None,
                "with_runs": 0,
                "without_runs": 0,
                "skipped_paid_graders": False,
                "errors": ["raw missing expected case"],
            })
            blockers.append("缺 case: %s" % name)
            continue
        effective_model = suite_model or clean_text(raw_case.get("model")) or "unknown"
        parsed_case = _case_result(raw_case, effective_model, ablation_mode)
        cases_out.append(parsed_case)
        if parsed_case["status"] != "complete":
            blockers.append("case %s %s" % (name, parsed_case["status"]))
    extras = sorted(name for name in by_name if name not in set(expected))
    if extras:
        blockers.append("raw 含未请求 case: %s" % ",".join(extras))
    if duplicate_names:
        blockers.append("raw case 名重复: %s" % ",".join(sorted(duplicate_names)))
    if not expected:
        blockers.append("未声明预期 case")
    if not known_schema:
        blockers.append("不支持 raw schemaVersion=%s" % source_schema)
    raw_partial = raw.get("partial") is True
    if raw_partial:
        blockers.append(clean_text(raw.get("partialReason")) or "raw partial=true")
    if forced_partial_reason:
        blockers.append(forced_partial_reason)
    if raw.get("error") not in (None, "", False):
        blockers.append("raw 顶层报告 error")
    if raw.get("errors"):
        blockers.append("raw 顶层报告 errors")
    if _contains_true_flag(raw, "skippedPaidGraders"):
        blockers.append("存在 skippedPaidGraders=true")
    if actual_model in {"unknown", "mixed"}:
        blockers.append("effective model=%s" % actual_model)
    if requested_model and actual_model != requested_model:
        blockers.append("请求模型 %s 与实际模型 %s 不一致" % (requested_model, actual_model))

    cost = raw.get("costUsd") if is_number(raw.get("costUsd")) and raw.get("costUsd") >= 0 else None
    duration = raw.get("durationSeconds") if is_number(raw.get("durationSeconds")) and raw.get("durationSeconds") >= 0 else None
    if cost is None:
        blockers.append("costUsd 缺失或无效")

    official_delta = None
    top_aggregates = raw.get("aggregates") if isinstance(raw.get("aggregates"), dict) else {}
    if is_number(top_aggregates.get("meanDelta")):
        official_delta = top_aggregates.get("meanDelta")
    elif is_number(top_aggregates.get("delta")):
        official_delta = top_aggregates.get("delta")
    elif len(cases_out) == 1 and is_number(cases_out[0].get("delta")):
        # This remains an official case aggregate, not a mean rebuilt from run scores.
        official_delta = cases_out[0]["delta"]
    else:
        blockers.append("缺官方 suite aggregate delta")

    blockers = _dedupe(blockers)
    partial = bool(blockers)
    if partial:
        delta = None
        verdict = "inconclusive"
        note = "；".join(blockers)
        evidence = "评测证据不完整，禁止判分：%s；raw：%s" % (note, raw_path)
        status = "partial"
    else:
        delta = round(float(official_delta), 6)
        with_scores = [case["with_score"] for case in cases_out]
        without_scores = [case["without_score"] for case in cases_out]
        mean_with = sum(with_scores) / len(with_scores)
        mean_without = sum(without_scores) / len(without_scores)
        verdict, note = judge(mean_with, mean_without, delta)
        evidence = (
            "official aggregates: with=%.3f without=%.3f Δ=%.3f（%d case）；"
            "effective model=%s；%s；raw：%s"
            % (mean_with, mean_without, delta, len(cases_out), actual_model, note, raw_path)
        )
        status = "complete"
    cacheable = bool(
        status == "complete"
        and requested_model
        and actual_model == requested_model
        and actual_model not in {"unknown", "mixed"}
        and known_schema
        and cost is not None
    )
    return {
        "status": status,
        "requested_model": requested_model,
        "model": actual_model,
        "judge_model": judge_model,
        "source_schema_version": source_schema,
        "cases": cases_out,
        "delta": delta,
        "verdict": verdict,
        "evidence": evidence,
        "cost_usd": cost,
        "duration_seconds": duration,
        "partial": partial,
        "partial_reason": "；".join(blockers) if blockers else None,
        "error": None,
        "cacheable": cacheable,
    }


def parse_result(raw, raw_path):
    """Backward-compatible helper for callers that already hold one raw document."""
    names = [_raw_case_name(case) for case in (raw.get("cases") or []) if isinstance(case, dict)]
    return parse_raw_result(raw, names, None, DEFAULT_ABLATION, raw_path)


def fake_result(case_names, model, judge_model, ablation_mode):
    cases = []
    for name in case_names:
        arms = {"with": [{"score": 0.9}]}
        aggregate = {"score": 0.9}
        if ablation_mode == "with-without":
            arms["without"] = [{"score": 0.5}]
            aggregate.update({"scoreWithout": 0.5, "delta": 0.4})
        cases.append({"name": name, "model": model, "arms": arms, "aggregates": aggregate})
    raw = {
        "schemaVersion": 1,
        "suite": {"modelOverride": model},
        "costUsd": 0.0,
        "durationSeconds": 0.0,
        "partial": False,
        "cases": cases,
        "aggregates": {"meanDelta": 0.4} if ablation_mode == "with-without" else {},
        "dryRunFake": True,
    }
    if judge_model:
        raw["suite"]["judgeModel"] = judge_model
    return raw


def _result_identity(skill):
    return {
        "skill_instance_id": skill.get("instance_id"),
        "skill_id": skill.get("logical_id") or skill.get("id"),
    }


def base_result(skill, requested_model, requested_judge_model, claude_version,
                fingerprint, runs):
    result = _result_identity(skill)
    result.update({
        "status": "error",
        "prescreen": dict(PRESCREEN),
        "requested_model": requested_model,
        "model": "unknown",
        "judge_model": requested_judge_model or DEFAULT_JUDGE_SENTINEL,
        "claude_version": claude_version,
        "source_schema_version": None,
        "fingerprint": fingerprint,
        "cache_hit": False,
        "cacheable": False,
        "raw_result_path": None,
        "cases": [],
        "delta": None,
        "verdict": "inconclusive",
        "evidence": "",
        "cost_usd": 0.0,
        "cost_usd_this_run": 0.0,
        "duration_seconds": None,
        "partial": False,
        "partial_reason": None,
        "error": None,
        "runs": runs,
    })
    return result


def set_result_error(result, message, status="error", partial=False, cost_unknown=False):
    result.update({
        "status": status,
        "verdict": "inconclusive",
        "delta": None,
        "evidence": "内容价值未完成验证：%s" % message,
        "partial": partial,
        "partial_reason": message if partial else None,
        "error": message,
        "cacheable": False,
    })
    if cost_unknown:
        result["cost_usd"] = None
        result["cost_usd_this_run"] = None
    return result


def unsupported_result(skill, requested_model, requested_judge_model, runs,
                       runtime_agent):
    material = json.dumps(
        {
            "instance": skill.get("instance_id"),
            "runtime": runtime_agent,
            "model": requested_model,
            "runs": runs,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    result = base_result(
        skill,
        requested_model,
        requested_judge_model,
        None,
        hashlib.sha256(material.encode("utf-8")).hexdigest(),
        runs,
    )
    result.update({
        "status": "unsupported_runtime",
        "verdict": "content_value_unverified",
        "evidence": "运行时 %s 未注册付费评测后端；未调用 Claude，内容价值未验证" % runtime_agent,
        "cost_usd": 0.0,
        "cost_usd_this_run": 0.0,
        "partial": False,
        "error": None,
    })
    return result


def structured_error(code, stage, message, skill=None, selector=None):
    return {
        "code": code,
        "stage": stage,
        "skill_instance_id": skill.get("instance_id") if skill else None,
        "skill_id": (skill.get("logical_id") or skill.get("id")) if skill else selector,
        "detail": message,
    }


def raw_parent(out_dir, skill_instance_id, execution_model, fingerprint):
    return os.path.join(
        out_dir,
        "eval-raw",
        safe_component(skill_instance_id),
        safe_component(execution_model),
        fingerprint,
    )


def next_attempt_path(parent):
    os.makedirs(parent, exist_ok=True)
    index = 1
    while True:
        path = os.path.join(parent, "attempt-%04d.json" % index)
        if not os.path.exists(path):
            return path
        index += 1


def cache_path_for(parent):
    return os.path.join(parent, "cache-result.json")


def load_exact_cache(path, fingerprint, skill_instance_id, requested_model,
                     claude_version):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            wrapper = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(wrapper, dict) or wrapper.get("cache_schema_version") != "1":
        return None
    expected = {
        "fingerprint": fingerprint,
        "skill_instance_id": skill_instance_id,
        "requested_model": requested_model,
        "claude_version": claude_version,
    }
    if any(wrapper.get(key) != value for key, value in expected.items()):
        return None
    result = wrapper.get("result")
    if not isinstance(result, dict):
        return None
    if result.get("cacheable") is not True or result.get("model") in {None, "unknown", "mixed"}:
        return None
    if result.get("model") != requested_model or result.get("status") != "complete":
        return None
    raw_path = result.get("raw_result_path")
    if not raw_path or not os.path.isfile(raw_path):
        return None
    cached = dict(result)
    cached["status"] = "cached"
    cached["cache_hit"] = True
    cached["cost_usd_this_run"] = 0.0
    cached["error"] = None
    return cached


def write_exact_cache(path, result):
    wrapper = {
        "cache_schema_version": "1",
        "fingerprint": result.get("fingerprint"),
        "skill_instance_id": result.get("skill_instance_id"),
        "requested_model": result.get("requested_model"),
        "claude_version": result.get("claude_version"),
        "result": result,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp-%d" % os.getpid()
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(wrapper, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def aggregate_value(results, key, default="unknown"):
    values = []
    for result in results:
        value = result.get(key)
        if value and value not in {"unknown", None}:
            values.append(value)
    distinct = sorted(set(values))
    if not distinct:
        return default
    if len(distinct) == 1:
        return distinct[0]
    return "mixed"


def overall_status(results, runtime_agent, dry_run, cost_verification):
    if runtime_agent != "claude-code":
        return "unsupported_runtime"
    if dry_run:
        return "dry_run"
    if cost_verification == "incomplete":
        return "error"
    statuses = {result.get("status") for result in results}
    if "partial" in statuses:
        return "partial"
    if "error" in statuses:
        return "error"
    if statuses and statuses.issubset({"complete", "cached"}):
        return "complete"
    return "error"


def write_json(path, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp-%d" % os.getpid()
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def build_document(args, runtime_agent, backend, total_budget, spent, results,
                   errors, warnings, cost_verification):
    status = overall_status(results, runtime_agent, args.dry_run, cost_verification)
    return {
        "schema_version": SCHEMA_VERSION,
        "schema_name": SCHEMA_NAME,
        "evaluated_at": now_iso(),
        "model": aggregate_value(results, "model"),
        "budget_usd": args.max_cost_usd,
        "total_budget_usd": total_budget,
        "total_cost_usd": round(spent, 6),
        "cost_note": COST_NOTE,
        "runs": args.runs,
        "dry_run": args.dry_run,
        "runtime_agent": runtime_agent,
        "backend": backend,
        "status": status,
        "requested_model": args.model,
        "requested_judge_model": args.judge_model,
        "judge_model": aggregate_value(results, "judge_model", DEFAULT_JUDGE_SENTINEL),
        "concurrency": 1,
        "ablation_mode": args.ablation,
        "cost_scope": "this_run_only",
        "cost_verification": cost_verification,
        "results": results,
        "errors": errors,
        "warnings": _dedupe(warnings),
    }


def _parse_selectors(value):
    return [item for item in re.split(r"[,\s]+", value or "") if item]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "按运行时路由官方对比评测；Claude Code 后端固定串行并透传 execution model。"
            "其他运行时零成本输出 content_value_unverified。"
        )
    )
    parser.add_argument("--skills", required=True, help="逗号或空白分隔的 instance_id；旧 logical id 仅唯一时可用")
    parser.add_argument("--inventory", default=None, help="00-inventory.json；默认 <out-dir>/00-inventory.json")
    parser.add_argument("--out-dir", default="skill-audit-output", help="唯一允许写入的输出目录")
    parser.add_argument("--max-cost-usd", type=float, default=DEFAULT_BUDGET, help="每次 CLI 启动上限 USD")
    parser.add_argument("--total-budget-usd", type=float, default=None, help="本次所有新启动评测的启动上限 USD")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="每 case 每臂运行次数")
    parser.add_argument("--skip-cached", action="store_true", help="只复用 fingerprint 完全一致的精确缓存")
    parser.add_argument("--model", default=None, help="execution model；Claude 非 dry-run 必须显式提供")
    parser.add_argument("--judge-model", default=None, help="可选 judge model；不提供时不向 CLI 传该参数")
    parser.add_argument("--ablation", choices=("with-without", "none"), default=DEFAULT_ABLATION)
    parser.add_argument("--runtime-agent", choices=("auto", "claude-code", "other"), default="auto")
    parser.add_argument("--capability-cache", default=None, help="可选只读 JSON 数据缓存；不接受命令字段")
    parser.add_argument("--dry-run", action="store_true", help="不调用 Claude；仅在 claude-code 路由下组装并走假 raw")
    parser.add_argument("--keep-temp", action="store_true", help="保留 out-dir/.eval-tmp 临时包")
    parser.add_argument("--json", action="store_true", help="stdout 追加机器可读摘要")
    args = parser.parse_args(argv)

    if args.runs <= 0:
        parser.error("--runs 必须大于 0")
    # NaN/inf 满足 <=0 == False 会绕过下限检查，再经 min()/str() 进入付费 CLI argv——
    # 预算闸门必须拒绝一切非有限值
    if not math.isfinite(args.max_cost_usd):
        parser.error("--max-cost-usd 必须是有限正数（拒绝 nan/inf）")
    if args.max_cost_usd <= 0:
        parser.error("--max-cost-usd 必须大于 0")
    if args.total_budget_usd is not None:
        if not math.isfinite(args.total_budget_usd):
            parser.error("--total-budget-usd 必须是有限正数（拒绝 nan/inf）")
        if args.total_budget_usd <= 0:
            parser.error("--total-budget-usd 必须大于 0")
    runtime_agent, backend = route_runtime_agent(args.runtime_agent)
    if backend == "claude-plugin-eval" and not args.dry_run and not concrete_model(args.model):
        parser.error("Claude Code 非 dry-run 评测必须显式提供 concrete --model，且不能是 unknown/mixed/auto/default")

    out_dir = os.path.abspath(args.out_dir)
    args.inventory = args.inventory or os.path.join(out_dir, "00-inventory.json")
    try:
        os.makedirs(out_dir, exist_ok=True)
        _assert_below(os.path.join(out_dir, "eval-raw"), out_dir)
    except OSError as exc:
        print("evaluate.py: 输出目录写不进 %s（%s）" % (out_dir, exc), file=sys.stderr)
        return 2
    try:
        skills = load_inventory(args.inventory)
    except (OSError, ValueError) as exc:
        print("evaluate.py: 读 inventory 失败 %s（%s）" % (args.inventory, exc), file=sys.stderr)
        return 2

    selectors = _parse_selectors(args.skills)
    if not selectors:
        print("evaluate.py: --skills 解析后为空（未指定任何组件，不会启动评测）", file=sys.stderr)
        return 2
    resolved, problems = resolve_skill_selectors(skills, selectors)
    total_budget = (
        args.total_budget_usd
        if args.total_budget_usd is not None
        else args.max_cost_usd * max(1, len(resolved) or len(selectors))
    )
    errors = []
    warnings = []
    results = []
    spent = 0.0
    cost_verification = "complete"
    out_path = os.path.join(
        out_dir, "02-eval-results.dry-run.json" if args.dry_run else "02-eval-results.json"
    )

    if problems:
        for problem in problems:
            errors.append(structured_error(
                problem["code"], "resolve", problem["message"], selector=problem.get("selector")
            ))
        document = build_document(
            args, runtime_agent, backend, total_budget, spent, results, errors, warnings,
            cost_verification,
        )
        try:
            write_json(out_path, document)
        except OSError as exc:
            print("evaluate.py: 写结果失败 %s（%s）" % (out_path, exc), file=sys.stderr)
            return 2
        print("evaluate: 解析失败，未启动任何付费进程 → %s" % out_path)
        return 0

    if backend == "none":
        for skill in resolved:
            results.append(unsupported_result(
                skill, args.model, args.judge_model, args.runs, runtime_agent
            ))
        warnings.append(
            "%s: unsupported_runtime；无注册评测后端，未调用 Claude，内容价值未验证"
            % runtime_agent
        )
        document = build_document(
            args, runtime_agent, backend, total_budget, spent, results, errors, warnings,
            cost_verification,
        )
        try:
            write_json(out_path, document)
        except OSError as exc:
            print("evaluate.py: 写结果失败 %s（%s）" % (out_path, exc), file=sys.stderr)
            return 2
        print("evaluate: runtime=%s 不支持付费评测，$0 → %s" % (runtime_agent, out_path))
        return 0

    execution_model = args.model or "dry-run-unpinned"
    plans = []
    for skill in resolved:
        cases, case_warnings = find_cases(out_dir, skill)
        warnings.extend(case_warnings)
        source_root = source_root_for(skill)
        if not source_root:
            result = base_result(skill, args.model, args.judge_model, None, None, args.runs)
            message = "组件来源文件/目录不存在"
            set_result_error(result, message)
            results.append(result)
            errors.append(structured_error("source_missing", "assemble", message, skill=skill))
            continue
        if not cases:
            result = base_result(skill, args.model, args.judge_model, None, None, args.runs)
            message = "case 库为空；请先按 references/case-authoring.md 生成并人审"
            set_result_error(result, message)
            results.append(result)
            errors.append(structured_error("cases_missing", "cases", message, skill=skill))
            continue
        plans.append({"skill": skill, "cases": cases, "source_root": source_root})

    capability = {}
    if args.capability_cache:
        try:
            capability = load_capability_cache(args.capability_cache)
        except (OSError, ValueError) as exc:
            warnings.append("capability cache 无效，忽略：%s" % exc)
    supports = capability.get("supports") or {}
    if supports.get("plugin_eval") is False:
        message = "capability cache 明确标记 plugin_eval=false；未启动付费进程"
        for plan in plans:
            result = base_result(
                plan["skill"], args.model, args.judge_model,
                capability.get("claude_version"), None, args.runs,
            )
            set_result_error(result, message)
            results.append(result)
            errors.append(structured_error("eval_capability_unavailable", "eval", message, skill=plan["skill"]))
        plans = []

    if args.dry_run:
        claude_version = "dry-run"
    else:
        claude_version = capability.get("claude_version")
        if not claude_version and plans:
            claude_version, version_error = query_claude_version()
            if version_error:
                message = "无法取得 Claude Code 版本，拒绝启动不可可靠缓存的付费评测：%s" % version_error
                for plan in plans:
                    result = base_result(plan["skill"], args.model, args.judge_model, None, None, args.runs)
                    set_result_error(result, message)
                    results.append(result)
                    errors.append(structured_error("claude_version_unavailable", "eval", message, skill=plan["skill"]))
                plans = []

    prepared = []
    for plan in plans:
        try:
            fingerprint = compute_fingerprint(
                skill_instance_id=plan["skill"].get("instance_id"),
                source_root=plan["source_root"],
                cases=plan["cases"],
                runs=args.runs,
                execution_model=execution_model,
                judge_model=args.judge_model,
                ablation_mode=args.ablation,
                claude_version=claude_version,
            )
        except OSError as exc:
            result = base_result(plan["skill"], args.model, args.judge_model, claude_version, None, args.runs)
            message = "fingerprint 读取失败：%s" % exc
            set_result_error(result, message)
            results.append(result)
            errors.append(structured_error("fingerprint_failed", "cache", message, skill=plan["skill"]))
            continue
        plan["fingerprint"] = fingerprint
        plan["raw_parent"] = raw_parent(
            out_dir, plan["skill"].get("instance_id"), execution_model, fingerprint
        )
        prepared.append(plan)

    stop_paid_runs = False
    stop_reason = None
    stop_due_unknown_cost = False
    cached_count = 0
    for plan in prepared:
        skill = plan["skill"]
        fingerprint = plan["fingerprint"]
        parent = plan["raw_parent"]
        cache_file = cache_path_for(parent)
        if args.skip_cached and not args.dry_run:
            cached = load_exact_cache(
                cache_file,
                fingerprint,
                skill.get("instance_id"),
                args.model,
                claude_version,
            )
            if cached is not None:
                results.append(cached)
                cached_count += 1
                warnings.append("%s: 精确 fingerprint 缓存命中，本次成本 $0" % skill.get("instance_id"))
                continue

        if stop_paid_runs:
            result = base_result(
                skill, args.model, args.judge_model, claude_version, fingerprint, args.runs
            )
            status = "error" if stop_due_unknown_cost else "partial"
            set_result_error(result, stop_reason, status=status, partial=(status == "partial"))
            results.append(result)
            errors.append(structured_error("paid_runs_stopped", "budget", stop_reason, skill=skill))
            continue

        remaining = total_budget - spent
        if not args.dry_run and remaining <= 0:
            message = "本次总预算启动上限已用完，未启动该组件"
            result = base_result(
                skill, args.model, args.judge_model, claude_version, fingerprint, args.runs
            )
            set_result_error(result, message, status="partial", partial=True)
            results.append(result)
            errors.append(structured_error("budget_launch_limit_reached", "budget", message, skill=skill))
            continue

        pkg_dir = os.path.join(
            out_dir,
            ".eval-tmp",
            safe_component(skill.get("instance_id")),
            fingerprint,
            "pkg",
        )
        try:
            assemble_pkg(pkg_dir, out_dir, skill, plan["cases"])
        except OSError as exc:
            result = base_result(
                skill, args.model, args.judge_model, claude_version, fingerprint, args.runs
            )
            message = "临时 plugin package 组装失败：%s" % exc
            set_result_error(result, message)
            results.append(result)
            errors.append(structured_error("package_assembly_failed", "assemble", message, skill=skill))
            continue

        raw_path = next_attempt_path(parent)
        result = base_result(
            skill, args.model, args.judge_model, claude_version, fingerprint, args.runs
        )
        result["raw_result_path"] = raw_path
        skill_budget = args.max_cost_usd if args.dry_run else min(args.max_cost_usd, remaining)
        command = cli_command(
            args.runs,
            skill_budget,
            raw_path,
            execution_model,
            args.judge_model,
            args.ablation,
        )
        print(
            "[$ %s]（cwd=%s；剩余启动预算 $%.6f）"
            % (" ".join(command), pkg_dir, max(0.0, remaining)),
            flush=True,
        )
        try:
            if args.dry_run:
                raw = fake_result(
                    [name for name, _ in plan["cases"]],
                    execution_model,
                    args.judge_model,
                    args.ablation,
                )
                write_json(raw_path, raw)
                parsed = parse_raw_result(
                    raw,
                    [name for name, _ in plan["cases"]],
                    execution_model,
                    args.ablation,
                    raw_path,
                    requested_judge_model=args.judge_model,
                )
                result.update(parsed)
                result.update({
                    "status": "dry_run",
                    "requested_model": args.model,
                    "verdict": "inconclusive",
                    "evidence": "dry-run 假 raw，仅验证编排与 schema，不代表内容价值；raw：%s" % raw_path,
                    "cost_usd": 0.0,
                    "cost_usd_this_run": 0.0,
                    "cacheable": False,
                    "partial": False,
                    "partial_reason": None,
                })
                results.append(result)
                continue

            timeout_seconds = 60 + args.runs * 300
            process = run_cli(pkg_dir, command, timeout_seconds)
            if not process["started"]:
                message = "Claude CLI 启动失败；未读取任何旧 raw：%s" % process["launch_error"]
                set_result_error(result, message)
                result["raw_result_path"] = None
                results.append(result)
                errors.append(structured_error("cli_start_failed", "eval", message, skill=skill))
                stop_paid_runs = True
                stop_reason = "前一 CLI 无法启动，已停止后续付费项"
                stop_due_unknown_cost = True
                continue

            raw = None
            raw_error = None
            try:
                with open(raw_path, "r", encoding="utf-8") as handle:
                    raw = json.load(handle)
            except (OSError, ValueError) as exc:
                raw_error = "%s: %s" % (exc.__class__.__name__, exc)
            if not isinstance(raw, dict):
                message = "CLI 已启动但没有可解析 raw JSON，成本无法验证，fail closed：%s" % raw_error
                set_result_error(result, message, cost_unknown=True)
                results.append(result)
                errors.append(structured_error("raw_or_cost_unavailable", "eval", message, skill=skill))
                cost_verification = "incomplete"
                stop_paid_runs = True
                stop_reason = "前一已启动评测的成本无法验证，已停止后续付费项"
                stop_due_unknown_cost = True
                continue

            forced_reason = None
            if process["timed_out"]:
                forced_reason = "Claude CLI 超时；即使 raw 可读也只能视为 partial"
            elif process["returncode"] not in (0, 1):
                forced_reason = "Claude CLI exit %s；raw 只能视为 partial" % process["returncode"]
            parsed = parse_raw_result(
                raw,
                [name for name, _ in plan["cases"]],
                args.model,
                args.ablation,
                raw_path,
                forced_partial_reason=forced_reason,
                requested_judge_model=args.judge_model,
            )
            result.update(parsed)
            result["cost_usd_this_run"] = parsed.get("cost_usd")
            if parsed.get("cost_usd") is None:
                message = "CLI 已启动但 costUsd 不可信，fail closed"
                set_result_error(result, message, cost_unknown=True)
                results.append(result)
                errors.append(structured_error("cost_unverified", "budget", message, skill=skill))
                cost_verification = "incomplete"
                stop_paid_runs = True
                stop_reason = "前一已启动评测的成本无法验证，已停止后续付费项"
                stop_due_unknown_cost = True
                continue

            spent += float(parsed["cost_usd"])
            results.append(result)
            if result["status"] == "complete" and result["cacheable"]:
                try:
                    write_exact_cache(cache_file, result)
                except OSError as exc:
                    warnings.append("%s: cache 写入失败（不影响本次结果）：%s" % (skill.get("instance_id"), exc))
            else:
                errors.append(structured_error(
                    "eval_inconclusive",
                    "eval",
                    result.get("partial_reason") or "eval 未满足完整判分门槛",
                    skill=skill,
                ))
                stop_paid_runs = True
                stop_reason = "前一评测为 partial/inconclusive，已停止后续付费项"
                stop_due_unknown_cost = False
        finally:
            if not args.keep_temp:
                shutil.rmtree(pkg_dir, ignore_errors=True)

    document = build_document(
        args,
        runtime_agent,
        backend,
        total_budget,
        spent,
        results,
        errors,
        warnings,
        cost_verification,
    )
    try:
        write_json(out_path, document)
    except OSError as exc:
        print("evaluate.py: 写结果失败 %s（%s）" % (out_path, exc), file=sys.stderr)
        return 2
    print(
        "evaluate%s: %d results（错误/未验证 %d，缓存 %d，本次成本 $%.6f）→ %s"
        % ("（dry-run）" if args.dry_run else "", len(results), len(errors), cached_count, spent, out_path)
    )
    if args.json:
        print(json.dumps({
            "ok": document["status"] in {"complete", "dry_run", "unsupported_runtime"},
            "out": out_path,
            "status": document["status"],
            "results": len(results),
            "errors": len(errors),
            "cached": cached_count,
            "dry_run": args.dry_run,
            "runtime_agent": runtime_agent,
            "total_cost_usd": round(spent, 6),
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
