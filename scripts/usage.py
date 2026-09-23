#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Direct usage evidence: strict JSONL event parsing plus name/path resolvers.

Discovery lives in adapters.  This module only walks explicit transcript roots and
decides facts from top-level and direct-payload fields — it never recursively searches
component references in nested objects.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_CMD_RE = re.compile(r"<command-name>\s*/([^\s<]+?)\s*</command-name>")
# Slash references shaped like known skill names (optionally namespaced with ":" or
# scoped with "/") are kept even when unresolved; single-token built-ins such as /model
# or /compact are dropped as noise.
_PLAUSIBLE_SLASH_RE = re.compile(r"^[^\s/:]+[:/][^\s]+$|^[^\s/]+/[^\s/]+(?:/[^\s/]*)?$")
_TS_RE = re.compile(r'"timestamp"\s*:\s*"([^"]+)"')
_CODEX_SKILL_RE = re.compile(r"/[^\s\"'\\]+/SKILL\.md")
_SKILL_TOOL_LINE_HINT = '"name": "Skill"'
_SKILL_TOOL_LINE_HINT_COMPACT = '"name":"Skill"'
_COMMAND_HINT = "<command-name>"


def parse_iso(ts):
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _source_kind_hash(agent, source_kind, normalized_ref):
    material = "\0".join([agent, source_kind, normalized_ref])
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def record_id_for_unmatched(agent, source_kind, normalized_ref):
    return "%s::unmatched::%s" % (agent, _source_kind_hash(agent, source_kind, normalized_ref)[:20])


def empty_matched_record(skill):
    return {
        "record_id": "%s::usage::%s" % (skill["agent"], skill["instance_id"]),
        "agent": skill["agent"],
        "skill_instance_id": skill["instance_id"],
        "skill_id": skill.get("logical_id"),
        "matched": True,
        "match_status": "matched",
        "candidate_instance_ids": [skill["instance_id"]],
        "source_ref": None,
        "source_ref_hash": None,
        "name_hint": None,
        "source_counts": {},
        "activations": 0,
        "first_seen": None,
        "last_seen": None,
        "lifetime_count": None,
    }


def empty_unmatched_record(agent, source_kind, normalized_ref, name_hint=None):
    digest = _source_kind_hash(agent, source_kind, normalized_ref)
    return {
        "record_id": "%s::unmatched::%s" % (agent, digest[len("sha256:"):]),
        "agent": agent,
        "skill_instance_id": None,
        "skill_id": None,
        "matched": False,
        "match_status": "unmatched",
        "candidate_instance_ids": [],
        "source_ref": normalized_ref,
        "source_ref_hash": digest,
        "name_hint": name_hint,
        "source_counts": {},
        "activations": 0,
        "first_seen": None,
        "last_seen": None,
        "lifetime_count": None,
    }


def empty_ambiguous_record(agent, source_kind, normalized_ref, candidate_ids, name_hint=None):
    digest = _source_kind_hash(agent, "ambiguous:" + source_kind, normalized_ref)
    return {
        "record_id": "%s::unmatched::%s" % (agent, digest[len("sha256:"):]),
        "agent": agent,
        "skill_instance_id": None,
        "skill_id": None,
        "matched": False,
        "match_status": "ambiguous",
        "candidate_instance_ids": list(candidate_ids),
        "source_ref": normalized_ref,
        "source_ref_hash": digest,
        "name_hint": name_hint,
        "source_counts": {},
        "activations": 0,
        "first_seen": None,
        "last_seen": None,
        "lifetime_count": None,
    }


def record_sort_key(row):
    return (
        0 if row.get("match_status") == "matched" else 1,
        -int(row.get("activations", 0) or 0),
        str(row.get("record_id") or ""),
        str(row.get("source_ref") or ""),
    )


def _bump_date(row, dt):
    ds = dt.date().isoformat()
    if row["first_seen"] is None or ds < row["first_seen"]:
        row["first_seen"] = ds
    if row["last_seen"] is None or ds > row["last_seen"]:
        row["last_seen"] = ds


class NameResolver(object):
    """Resolve Claude runtime names: exact canonical match, then unique tail match."""

    def __init__(self, skills):
        self.by_instance = {}
        self.by_exact = {}
        self.by_tail = {}
        for skill in skills:
            instance = skill["instance_id"]
            self.by_instance[instance] = skill
            for name in (skill.get("runtime_name"), skill.get("name")):
                if isinstance(name, str) and name:
                    self.by_exact.setdefault(name, set()).add(instance)
                    self.by_tail.setdefault(name.rsplit(":", 1)[-1], set()).add(instance)

    def resolve(self, name):
        if not isinstance(name, str) or not name:
            return {"status": "unmatched", "candidate_instance_ids": []}
        candidates = self.by_exact.get(name)
        if candidates is None:
            candidates = self.by_tail.get(name.rsplit(":", 1)[-1])
        if not candidates:
            return {"status": "unmatched", "candidate_instance_ids": []}
        if len(candidates) > 1:
            return {"status": "ambiguous", "candidate_instance_ids": sorted(candidates)}
        return {"status": "matched", "candidate_instance_ids": [next(iter(candidates))]}


class PathResolver(object):
    """Resolve absolute SKILL.md paths against lexical/real/symlink inventory aliases."""

    def __init__(self, skills):
        self.by_instance = {}
        self.aliases = {}
        for skill in skills:
            instance = skill["instance_id"]
            self.by_instance[instance] = skill
            for key in ("source_file", "source_realpath", "symlink_target"):
                value = skill.get(key)
                if isinstance(value, str) and value:
                    normalized = os.path.normpath(os.path.abspath(value))
                    self.aliases.setdefault(normalized, set()).add(instance)

    def resolve(self, path):
        if not isinstance(path, str) or not path:
            return {"status": "unmatched", "candidate_instance_ids": []}
        normalized = os.path.normpath(os.path.abspath(path))
        candidates = self.aliases.get(normalized)
        if candidates:
            if len(candidates) > 1:
                return {"status": "ambiguous", "candidate_instance_ids": sorted(candidates)}
            return {"status": "matched", "candidate_instance_ids": [next(iter(candidates))]}
        if os.path.exists(normalized):
            real = os.path.realpath(normalized)
            if real != normalized:
                candidates = self.aliases.get(real)
                if candidates:
                    if len(candidates) > 1:
                        return {"status": "ambiguous", "candidate_instance_ids": sorted(candidates)}
                    return {"status": "matched", "candidate_instance_ids": [next(iter(candidates))]}
        return {"status": "unmatched", "candidate_instance_ids": []}


def build_name_resolver(skills, agent):
    return NameResolver([skill for skill in skills if skill.get("agent") == agent])


def build_path_resolver(skills, agent):
    return PathResolver([skill for skill in skills if skill.get("agent") == agent])


class _Aggregator(object):
    def __init__(self, agent):
        self.agent = agent
        self.matched = {}
        self.others = {}
        self.direct_events = 0
        self.undated_events = 0
        self.unmatched_activations = 0
        self.ambiguous_activations = 0

    def _other(self, record):
        key = record["record_id"]
        row = self.others.get(key)
        if row is None:
            self.others[key] = record
            return record
        return row

    def add(self, resolver_result, source_kind, normalized_ref, dt, name_hint=None):
        status = resolver_result["status"]
        if status == "matched":
            instance = resolver_result["candidate_instance_ids"][0]
            row = self.matched.get(instance)
            if row is None:
                row = empty_matched_record({"agent": self.agent, "instance_id": instance,
                                            "logical_id": None})
                self.matched[instance] = row
            counts = row["source_counts"].setdefault(source_kind, {"count": 0, "first": None, "last": None})
            counts["count"] += 1
            self._touch_counts(counts, dt)
            _bump_date(row, dt)
            row["activations"] += 1
            return row
        if status == "ambiguous":
            record = self._other(empty_ambiguous_record(
                self.agent, source_kind, normalized_ref,
                resolver_result["candidate_instance_ids"], name_hint,
            ))
            self.ambiguous_activations += 1
        else:
            record = self._other(empty_unmatched_record(
                self.agent, source_kind, normalized_ref, name_hint,
            ))
            self.unmatched_activations += 1
        counts = record["source_counts"].setdefault(source_kind, {"count": 0, "first": None, "last": None})
        counts["count"] += 1
        self._touch_counts(counts, dt)
        _bump_date(record, dt)
        record["activations"] += 1
        return record

    @staticmethod
    def _touch_counts(counts, dt):
        ds = dt.date().isoformat()
        if counts["first"] is None or ds < counts["first"]:
            counts["first"] = ds
        if counts["last"] is None or ds > counts["last"]:
            counts["last"] = ds

    def records(self):
        rows = list(self.matched.values()) + list(self.others.values())
        rows.sort(key=record_sort_key)
        return rows

    def counts(self):
        matched = sum(row["activations"] for row in self.matched.values())
        return matched, self.unmatched_activations, self.ambiguous_activations


def _iter_jsonl_files(roots, pattern):
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob(pattern)):
            if path.is_file():
                yield path


def scan_claude_transcripts(window_days, resolve, roots=None, now=None):
    """Strict top-level scan of Claude transcript JSONL.

    Positive facts: top-level ``type=assistant`` with ``message.role=assistant`` direct
    ``content[]`` tool_use blocks named Skill, plus ordinary top-level user messages with
    a direct string content ``<command-name>`` block.  Snapshots, listing echoes, dynamic
    skills, invoked-skill summaries, compact summaries and attributions are excluded.
    """
    if window_days <= 0:
        raise ValueError("window_days must be a positive integer")
    if isinstance(resolve, NameResolver):
        resolver = resolve
    else:
        resolver = _LegacyNameResolveAdapter(resolve)
    if roots is None:
        roots = [Path.home() / ".claude" / "projects"]
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    agg = _Aggregator("claude-code")
    files = 0
    unreadable = 0
    parse_errors = 0
    found = False
    for path in _iter_jsonl_files(roots, "*.jsonl"):
        files += 1
        found = True
        try:
            handle = open(path, "r", encoding="utf-8", errors="replace")
        except OSError:
            unreadable += 1
            continue
        try:
            with handle:
                for line in handle:
                    hint = (_SKILL_TOOL_LINE_HINT in line
                            or _SKILL_TOOL_LINE_HINT_COMPACT in line
                            or _COMMAND_HINT in line)
                    if not hint:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        parse_errors += 1
                        continue
                    if not isinstance(obj, dict):
                        continue
                    events = _claude_events(obj, resolver)
                    if not events:
                        continue
                    timestamp = parse_iso(obj.get("timestamp"))
                    for source_kind, ref, name_hint in events:
                        agg.direct_events += 1
                        if timestamp is None:
                            agg.undated_events += 1
                            continue
                        if timestamp < cutoff:
                            continue
                        result = resolver.resolve(ref)
                        agg.add(result, source_kind, ref, timestamp, name_hint)
        except OSError:
            unreadable += 1
    matched, unmatched, ambiguous = agg.counts()
    coverage = {
        "status": "complete" if found else "unavailable",
        "sessions_scanned": files,
        "transcripts_found": found,
        "history_disabled": _skip_env_detected(),
        "files_unreadable": unreadable,
        "parse_errors": parse_errors,
        "undated_events": agg.undated_events,
        "direct_events": agg.direct_events,
        "matched_activations": matched,
        "unmatched_activations": unmatched,
        "ambiguous_activations": ambiguous,
        "limitations": [],
    }
    if coverage["history_disabled"]:
        coverage["limitations"].append("检测到 prompt history 跳过环境变量，窗口可能不完整")
    if not found:
        coverage["limitations"].append("未找到任何会话文件，无法区分零使用与数据不可用")
    meta = {"sessions_scanned": files, "coverage": coverage, "warnings": [], "issues": []}
    return agg.records(), meta


def _skip_env_detected():
    return os.environ.get("CLAUDE_CODE_SKIP_PROMPT_HISTORY") not in (None, "", "0", "false")


def _claude_events(obj, resolver):
    """Extract direct skill references from one top-level transcript event."""
    top_type = obj.get("type")
    if top_type not in ("assistant", "user"):
        return []
    if obj.get("isCompactSummary") is True:
        return []
    message = obj.get("message")
    if not isinstance(message, dict) or message.get("role") != top_type:
        return []
    if obj.get("attributionSkill"):
        return []
    content = message.get("content")
    events = []
    if top_type == "assistant" and isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use" and item.get("name") == "Skill":
                payload = item.get("input")
                if isinstance(payload, dict) and isinstance(payload.get("skill"), str):
                    events.append(("skill_tool_use", payload["skill"], payload["skill"]))
    elif top_type == "user" and isinstance(content, str):
        for match in _CMD_RE.finditer(content):
            command = match.group(1)
            # Slash commands only count when they plausibly name a known skill.
            # Built-ins (/model, /compact, …) are dropped as noise; unrecognized
            # skill-shaped names still surface as unmatched evidence.
            status = resolver.resolve(command)["status"]
            if status == "unmatched" and not _PLAUSIBLE_SLASH_RE.match(command):
                continue
            events.append(("slash_command", command, None))
    return events


class _LegacyNameResolveAdapter(object):
    """Adapt v1 ``resolve(name) -> skill_id`` callbacks to the status resolver shape."""

    def __init__(self, legacy):
        self._legacy = legacy
        self.by_instance = {}

    def resolve(self, name):
        mapped = self._legacy(name)
        if mapped is None:
            return {"status": "unmatched", "candidate_instance_ids": []}
        return {"status": "matched", "candidate_instance_ids": [mapped]}


def scan_codex_rollouts(window_days, resolve_path, roots=None, now=None):
    """Strict top-level scan of Codex rollout JSONL.

    Only top-level ``type=response_item`` rows whose direct payload is a
    ``function_call``/``custom_tool_call`` named exec/shell/exec are considered.  Each
    top-level call references a given instance at most once; nested history, world
    state, outputs, messages and reasoning are never inspected.
    """
    if window_days <= 0:
        raise ValueError("window_days must be a positive integer")
    if isinstance(resolve_path, PathResolver):
        resolver = resolve_path
    else:
        resolver = _LegacyPathResolveAdapter(resolve_path)
    if roots is None:
        home = Path.home() / ".codex"
        roots = [home / "sessions", home / "archived_sessions"]
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    agg = _Aggregator("codex")
    files = 0
    unreadable = 0
    parse_errors = 0
    found = False
    for path in _iter_jsonl_files(roots, "rollout-*.jsonl"):
        files += 1
        found = True
        try:
            handle = open(path, "r", encoding="utf-8", errors="replace")
        except OSError:
            unreadable += 1
            continue
        try:
            with handle:
                for line in handle:
                    if "SKILL.md" not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        parse_errors += 1
                        continue
                    if not isinstance(obj, dict) or obj.get("type") != "response_item":
                        continue
                    refs = _codex_call_references(obj)
                    if not refs:
                        continue
                    timestamp = parse_iso(obj.get("timestamp"))
                    # Normalize aliases first so one top-level call counts each distinct
                    # instance at most once even when several path spellings appear.
                    per_instance = {}
                    synthetic = []
                    for normalized in refs:
                        result = resolver.resolve(normalized)
                        if result["status"] == "matched":
                            per_instance.setdefault(result["candidate_instance_ids"][0], normalized)
                        else:
                            synthetic.append((normalized, result))
                    for instance, _normalized in sorted(per_instance.items()):
                        agg.direct_events += 1
                        if timestamp is None:
                            agg.undated_events += 1
                            continue
                        if timestamp < cutoff:
                            continue
                        agg.add(
                            {"status": "matched", "candidate_instance_ids": [instance]},
                            "skill_file_reference", _normalized, timestamp,
                        )
                    for normalized, result in synthetic:
                        agg.direct_events += 1
                        if timestamp is None:
                            agg.undated_events += 1
                            continue
                        if timestamp < cutoff:
                            continue
                        agg.add(result, "skill_file_reference", normalized, timestamp)
        except OSError:
            unreadable += 1
    matched, unmatched, ambiguous = agg.counts()
    coverage = {
        "status": "complete" if found else "unavailable",
        "sessions_scanned": files,
        "transcripts_found": found,
        "history_disabled": False,
        "files_unreadable": unreadable,
        "parse_errors": parse_errors,
        "undated_events": agg.undated_events,
        "direct_events": agg.direct_events,
        "matched_activations": matched,
        "unmatched_activations": unmatched,
        "ambiguous_activations": ambiguous,
        "limitations": [],
    }
    if not found:
        coverage["limitations"].append("未找到任何 rollout 文件，无法区分零使用与数据不可用")
    meta = {"sessions_scanned": files, "coverage": coverage, "warnings": [], "issues": []}
    return agg.records(), meta


_CODEX_FUNCTION_NAMES = {"exec_command", "shell"}
_CODEX_CUSTOM_NAMES = {"exec"}


def _codex_call_references(obj):
    payload = obj.get("payload")
    if not isinstance(payload, dict):
        return []
    payload_type = payload.get("type")
    name = payload.get("name")
    raw = None
    if payload_type == "function_call" and name in _CODEX_FUNCTION_NAMES:
        raw = payload.get("arguments")
        if not isinstance(raw, str):
            raw = None
    elif payload_type == "custom_tool_call" and name in _CODEX_CUSTOM_NAMES:
        raw = payload.get("input")
        if not isinstance(raw, str):
            raw = None
    if raw is None:
        return []
    refs = set()
    for match in _CODEX_SKILL_RE.finditer(raw):
        path = match.group(0)
        # Shell glob spellings such as /*/SKILL.md are not concrete file references.
        if "*" in path or "?" in path or "{" in path:
            continue
        if os.path.isabs(path):
            refs.add(os.path.normpath(path))
    return sorted(refs)


class _LegacyPathResolveAdapter(object):
    def __init__(self, legacy):
        self._legacy = legacy

    def resolve(self, path):
        mapped = self._legacy(path)
        if mapped is None:
            return {"status": "unmatched", "candidate_instance_ids": []}
        return {"status": "matched", "candidate_instance_ids": [mapped]}


def _plausible_skill_usage(obj):
    if not isinstance(obj, dict) or not obj:
        return False
    ok = sum(1 for value in obj.values()
             if isinstance(value, dict) and isinstance(value.get("usageCount"), int))
    return ok * 2 >= len(obj)


def extract_top_level_object(path, field, max_obj_bytes=16 * 1024 * 1024):
    """Stream-extract one top-level object field (e.g. skillUsage) from a huge JSON file."""
    needle = '"' + field + '"'
    try:
        handle = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return {}
    decoder = json.JSONDecoder()
    with handle:
        carry = ""
        while True:
            chunk = handle.read(1024 * 1024)
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
                if j < len(data) and data[j] == ":":
                    j += 1
                    while j < len(data) and data[j] in " \t\r\n":
                        j += 1
                if j < len(data) and data[j] == "{":
                    candidate = data[j:]
                    while True:
                        try:
                            obj, _end = decoder.raw_decode(candidate)
                            break
                        except ValueError:
                            nxt = handle.read(1024 * 1024)
                            if not nxt or len(candidate) > max_obj_bytes:
                                obj = None
                                break
                            candidate += nxt
                    if _plausible_skill_usage(obj):
                        return obj
                start = idx + 1
            carry = data[-len(needle):]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="只读解析 Claude/Codex 直接使用事件并输出窗口聚合。")
    parser.add_argument("--window-days", type=int, default=30, help="正整数窗口天数（默认 30）")
    parser.add_argument("--agents", default="claude-code,codex",
                        help="逗号分隔（默认 claude-code,codex）")
    parser.add_argument("--json", default=None, help="结果 JSON 输出路径")
    args = parser.parse_args(argv)
    if args.window_days <= 0:
        print("--window-days 必须是正整数", file=sys.stderr)
        return 2
    from adapters import ALL_AGENTS, get_adapters
    names = [item.strip() for item in args.agents.split(",") if item.strip()]
    bad = [name for name in names if name not in ALL_AGENTS]
    if bad:
        print("未知 agent: %s；可选：%s" % (",".join(bad), ",".join(ALL_AGENTS)), file=sys.stderr)
        return 2
    records = []
    for name, module in get_adapters(names):
        if not module.detect():
            print("[usage] %s: 未安装，跳过" % name)
            continue
        rows = module.usage_records(args.window_days)
        records.extend(rows)
        meta = dict(getattr(module, "USAGE_META", {}) or {})
        print("[usage] %s: %d 条记录，扫会话文件 %d 个" % (
            name, len(rows), meta.get("sessions_scanned", 0)))
    records.sort(key=record_sort_key)
    print("[usage] 合计 %d 条记录（窗口 %d 天）" % (len(records), args.window_days))
    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump({"window_days": args.window_days, "records": records},
                      fh, ensure_ascii=False, indent=2)
        print("[usage] JSON → %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
