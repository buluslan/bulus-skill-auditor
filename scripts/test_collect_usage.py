#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v0.2 discovery/usage fixed-fixture tests (stdlib only, no paid commands).

Run directly:
    python3 scripts/test_collect_usage.py
"""
import copy
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collect  # noqa: E402
import usage  # noqa: E402
from adapters import claude_code, codex, skillmd  # noqa: E402

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
RECENT = "2026-09-23T10:00:00Z"
OLD = "2026-08-01T10:00:00Z"


def _write(path, text=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _skill(path, name, description="fixture skill"):
    return _write(
        Path(path) / "SKILL.md",
        "---\nname: %s\ndescription: %s\n---\n# Body\nfixture\n" % (name, description),
    )


def _component(path, name, description="fixture component"):
    return _write(
        path,
        "---\nname: %s\ndescription: %s\n---\n# Body\nfixture\n" % (name, description),
    )


def _runner(payloads, calls):
    """Fake shared CLI runner keyed by the exact command tuple."""
    def run(command, agent, stage, timeout=5):
        key = tuple(command)
        calls.append(key)
        value = payloads[key]
        if isinstance(value, dict) and "ok" in value:
            return copy.deepcopy(value)
        return {"ok": True, "data": copy.deepcopy(value), "returncode": 0, "issue": None}
    return run


def _jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            if isinstance(row, str):
                fh.write(row + "\n")
            else:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _inventory_skill(agent, runtime_name, instance, source_file, **extra):
    source_file = str(source_file)
    row = {
        "agent": agent,
        "instance_id": instance,
        "id": "%s::%s" % (agent, runtime_name),
        "logical_id": "%s::%s" % (agent, runtime_name),
        "name": runtime_name,
        "runtime_name": runtime_name,
        "component_name": runtime_name.rsplit(":", 1)[-1],
        "declared_name": runtime_name.rsplit(":", 1)[-1],
        "directory_name": Path(source_file).parent.name,
        "component_type": "skill",
        "source_file": source_file,
        "source_realpath": os.path.realpath(source_file),
        "path": str(Path(source_file).parent),
        "realpath": os.path.realpath(str(Path(source_file).parent)),
        "symlink_target": None,
    }
    row.update(extra)
    return row


def case_skillmd_raw_facts(tmp):
    sm = _skill(Path(tmp) / "folder-name", "DeclaredName", "A description")
    fact, issues = skillmd.scan_component(sm, "skill")
    assert issues == []
    assert fact["declared_name"] == "DeclaredName"
    assert fact["directory_name"] == "folder-name"
    assert fact["description"] == "A description"
    assert fact["source_file"] == str(sm.absolute())
    assert fact["source_realpath"] == os.path.realpath(str(sm))
    assert fact["source_format"] == "skill-md"
    assert "runtime_name" not in fact and "instance_id" not in fact and "agent" not in fact

    command = _component(Path(tmp) / "commands" / "DoThing.md", "frontmatter-command")
    command_fact, command_issues = skillmd.scan_component(command, "command")
    assert command_issues == []
    assert command_fact["component_type"] == "command"
    assert command_fact["directory_name"] == "commands"
    assert command_fact["declared_name"] == "frontmatter-command"
    assert command_fact["source_format"] == "markdown"
    print("case_skillmd_raw_facts PASS")


def case_claude_discovery(tmp):
    home = Path(tmp) / "home"
    cwd = Path(tmp) / "repo"
    standalone = home / ".claude" / "skills" / "DirVisible"
    _skill(standalone, "FrontmatterIgnored")
    alias = home / ".claude" / "skills" / "AliasSame"
    alias.symlink_to(standalone, target_is_directory=True)
    _skill(cwd / ".claude" / "skills" / "ProjectOne", "ProjectDeclared")
    _skill(home / ".claude" / "agents" / "skills" / "HiddenAgent", "HiddenAgent")

    market_root = home / "active-market"
    _skill(market_root / "components" / "alpha", "DeclaredAlpha")
    _skill(market_root / "components" / "undeclared", "MustNotAppear")
    _component(market_root / "commands" / "do.md", "declared-do")
    _component(market_root / "agents" / "reviewer.md", "declared-reviewer")
    _skill(market_root / "other" / "leak", "MustNotAppearEither")
    _write(
        market_root / ".claude-plugin" / "marketplace.json",
        json.dumps({
            "name": "fixture-market",
            "plugins": [
                {
                    "name": "active-bundle",
                    "source": "./",
                    "skills": ["./components/alpha"],
                    "commands": ["./commands/do.md"],
                    "agents": ["./agents/reviewer.md"],
                },
                {"name": "other-bundle", "source": "./", "skills": ["./other/leak"]},
            ],
        }),
    )

    plugin_root = home / "active-plugin-json"
    _skill(plugin_root / "skills" / "beta", "BetaDeclared")
    _skill(plugin_root / "not-declared" / "gamma", "Gamma")
    _component(plugin_root / "commands" / "explicit.md", "explicit-command")
    _write(
        plugin_root / ".claude-plugin" / "plugin.json",
        json.dumps({
            "name": "VisibleSpace",
            "version": "9.1.0",
            "commands": ["./commands/explicit.md"],
        }),
    )

    disabled_root = home / "disabled"
    _skill(disabled_root / "skills" / "disabled-one", "disabled-one")
    cache_only = home / ".claude" / "plugins" / "cache" / "random" / "old" / "1.0"
    _skill(cache_only / "skills" / "cache-only", "cache-only")

    plugin_rows = [
        {
            "id": "active-bundle@fixture-market",
            "enabled": True,
            "installPath": str(market_root),
            "version": "abc123",
            "scope": "user",
        },
        {
            "id": "installation-id@fixture-market",
            "enabled": True,
            "installPath": str(plugin_root),
            "version": "9.1.0",
            "scope": "local",
        },
        {
            "id": "disabled@fixture-market",
            "enabled": False,
            "installPath": str(disabled_root),
            "version": "1.0.0",
            "scope": "user",
        },
    ]
    calls = []
    result = claude_code.discover(
        home=home,
        cwd=cwd,
        runner=_runner({("claude", "plugin", "list", "--json"): plugin_rows}, calls),
    )
    assert calls == [("claude", "plugin", "list", "--json")], "plugin list 必须只调用一次"
    assert result["discovery"]["status"] == "complete"
    assert result["discovery"]["excluded_counts"]["disabled_plugins"] == 1
    rows = result["skills"]
    names = [row["runtime_name"] for row in rows]
    assert "DirVisible" in names and "FrontmatterIgnored" not in names
    assert "ProjectOne" in names and "HiddenAgent" not in names
    assert "active-bundle:alpha" in names
    assert "active-bundle:do" in names
    assert "active-bundle:reviewer" in names
    assert "VisibleSpace:beta" in names
    assert "VisibleSpace:explicit" in names
    assert not any("disabled" in name or "cache-only" in name or "undeclared" in name or "leak" in name
                   for name in names)
    assert len([r for r in rows if r["source_realpath"] == os.path.realpath(str(standalone / "SKILL.md"))]) == 1
    alpha = next(r for r in rows if r["runtime_name"] == "active-bundle:alpha")
    assert alpha["plugin_id"] == "active-bundle@fixture-market"
    assert alpha["namespace"] == "active-bundle"
    assert alpha["declared_name"] == "DeclaredAlpha"
    assert alpha["directory_name"] == "alpha"
    assert alpha["active_state"] == "active" and alpha["discovery_confidence"] == "management_cli"
    beta = next(r for r in rows if r["runtime_name"] == "VisibleSpace:beta")
    assert beta["plugin_id"] == "installation-id@fixture-market"
    assert beta["namespace"] == "VisibleSpace"
    reviewer = next(r for r in rows if r["runtime_name"] == "active-bundle:reviewer")
    assert reviewer["component_type"] == "agent"
    assert reviewer["auditable"] is False
    assert reviewer["accounting"]["listing"] == "excluded"
    assert all(str(cache_only) not in root for root in result["skill_roots"])

    # ~/.claude/agents/skills is admitted only when current runtime evidence explicitly names it.
    calls2 = []
    payload = {"plugins": [], "skillRoots": [str(home / ".claude" / "agents" / "skills")]}
    with_agents = claude_code.discover(
        home=home,
        cwd=cwd,
        runner=_runner({("claude", "plugin", "list", "--json"): payload}, calls2),
    )
    assert "HiddenAgent" in [r["runtime_name"] for r in with_agents["skills"]]
    print("case_claude_discovery PASS")


def case_claude_cli_failure_is_conservative(tmp):
    home = Path(tmp) / "home-failure"
    cwd = Path(tmp) / "repo-failure"
    _skill(home / ".claude" / "skills" / "known", "ignored-declared")
    _skill(home / ".claude" / "plugins" / "cache" / "x" / "y" / "1" / "skills" / "leak", "leak")
    calls = []
    failed = {
        "ok": False,
        "data": None,
        "returncode": 9,
        "issue": {
            "code": "management_cli_nonzero",
            "severity": "warning",
            "agent": "claude-code",
            "stage": "discovery",
            "message": "plugin list failed with exit status 9",
            "path": None,
            "safe_context": {"returncode": 9},
        },
    }
    result = claude_code.discover(
        home=home,
        cwd=cwd,
        runner=_runner({("claude", "plugin", "list", "--json"): failed}, calls),
    )
    assert result["discovery"]["status"] == "fallback"
    assert [r["runtime_name"] for r in result["skills"]] == ["known"]
    assert all(r["source_kind"] == "standalone" for r in result["skills"])
    assert any(i["code"] == "management_cli_nonzero" for i in result["issues"])
    assert not any("leak" in r["runtime_name"] for r in result["skills"])
    print("case_claude_cli_failure_is_conservative PASS")


def _probe_json(text):
    return [{
        "type": "message",
        "role": "developer",
        "content": [{"type": "input_text", "text": text}],
    }]


def case_codex_probe_discovery(tmp):
    home = Path(tmp) / "codex-home"
    cwd = Path(tmp) / "codex-repo"
    r0 = home / ".codex" / "skills"
    r1 = r0 / ".system"
    r2 = cwd / ".agents" / "skills"
    plugin_root = home / "selected-plugin"
    one = _skill(r0 / "nested" / "one", "nested-one")
    dup_a = _skill(r0 / "dup-a", "duplicate")
    dup_b = _skill(r0 / "deep" / "dup-b", "duplicate")
    system = _skill(r1 / "sys-one", "sys-one")
    project = _skill(r2 / "project-one", "project-one")
    plugin = _skill(plugin_root / "skills" / "tool", "tool")
    text = """### Skill roots
- `r0` = `%s`
- `r1` = `%s`
- `r2` = `%s`
- `r3` = `%s`
### Available skills
- nested-one: Nested. (file: r0/nested/one/SKILL.md)
- duplicate: First. (file: r0/dup-a/SKILL.md)
- duplicate: Second. (file: r0/deep/dup-b/SKILL.md)
- sys-one: System. (file: r1/sys-one/SKILL.md)
- project-one: Project. (file: r2/project-one/SKILL.md)
- plug:tool: Plugin. (file: r3/skills/tool/SKILL.md)
""" % (r0, r1, r2, plugin_root)
    plugin_json = {
        "installed": [{
            "pluginId": "plug@market",
            "name": "plug",
            "marketplaceName": "market",
            "version": "2.0.0",
            "installed": True,
            "enabled": True,
            "source": {"source": "local", "path": str(plugin_root)},
        }],
        "available": [],
    }
    calls = []
    result = codex.discover(
        home=home,
        cwd=cwd,
        runner=_runner({
            ("codex", "debug", "prompt-input", "probe"): _probe_json(text),
            ("codex", "plugin", "list", "--json"): plugin_json,
        }, calls),
    )
    assert calls.count(("codex", "debug", "prompt-input", "probe")) == 1
    assert calls.count(("codex", "plugin", "list", "--json")) == 1
    assert result["discovery"]["status"] == "complete"
    rows = result["skills"]
    assert len(rows) == 6
    assert len([r for r in rows if r["runtime_name"] == "duplicate"]) == 2
    assert {r["source_file"] for r in rows} == {str(p.absolute()) for p in (one, dup_a, dup_b, system, project, plugin)}
    assert all(r["active_state"] == "active" and r["discovery_confidence"] == "runtime_probe" for r in rows)
    sys_row = next(r for r in rows if r["runtime_name"] == "sys-one")
    assert sys_row["scope"] == "system" and sys_row["install_scope"] == "system"
    project_row = next(r for r in rows if r["runtime_name"] == "project-one")
    assert project_row["scope"] == "project"
    plugin_row = next(r for r in rows if r["runtime_name"] == "plug:tool")
    assert plugin_row["plugin_id"] == "plug@market" and plugin_row["source_kind"] == "plugin"
    print("case_codex_probe_discovery PASS")


def case_codex_fallback_is_conservative(tmp):
    home = Path(tmp) / "fallback-home"
    cwd = Path(tmp) / "fallback-repo"
    valid = _skill(home / ".codex" / "skills" / "nested" / "valid-dir", "valid-name")
    _write(home / ".codex" / "skills" / "missing-name" / "SKILL.md", "---\ndescription: no name\n---\nbody\n")
    _skill(home / ".codex" / "skills" / "invalid-name", "Not Valid With Spaces")
    system = _skill(home / ".codex" / "skills" / ".system" / "sys", "sys")
    shared = _skill(home / ".agents" / "skills" / "deep" / "shared", "shared-name")
    project = _skill(cwd / ".agents" / "skills" / "deep" / "project", "project-name")

    selected = home / "plugins" / "selected-v2"
    plugin_skill = _skill(selected / "nested" / "tool-dir", "tool")
    disabled = home / "plugins" / "disabled"
    _skill(disabled / "skills" / "nope", "nope")
    cache_only = home / ".codex" / "plugins" / "cache" / "cache-only"
    _skill(cache_only / "skills" / "leak", "leak")
    _write(home / ".codex" / "config.toml", "provider_token='TOP-SECRET'\n[plugins.fake]\nenabled=true\n")

    bad_probe = _probe_json("### Available skills\n- bad: Missing roots. (file: r9/x/SKILL.md)\n")
    plugin_json = {
        "installed": [
            {
                "pluginId": "plug@market",
                "name": "plug",
                "version": "2.0.0",
                "installed": True,
                "enabled": True,
                "source": {"source": "local", "path": str(selected)},
            },
            {
                "pluginId": "disabled@market",
                "name": "disabled",
                "version": "1.0.0",
                "installed": True,
                "enabled": False,
                "source": {"source": "local", "path": str(disabled)},
            },
        ],
        "available": [],
    }
    calls = []
    result = codex.discover(
        home=home,
        cwd=cwd,
        runner=_runner({
            ("codex", "debug", "prompt-input", "probe"): bad_probe,
            ("codex", "plugin", "list", "--json"): plugin_json,
        }, calls),
    )
    assert result["discovery"]["status"] == "fallback"
    rows = result["skills"]
    non_plugin = [r for r in rows if r["source_kind"] != "plugin"]
    assert {r["source_file"] for r in non_plugin} == {
        str(p.absolute()) for p in (valid, system, shared, project)
    }
    assert all(r["active_state"] == "unknown" and r["discovery_confidence"] == "inferred"
               for r in non_plugin)
    plugin_rows = [r for r in rows if r["source_kind"] == "plugin"]
    assert len(plugin_rows) == 1
    assert plugin_rows[0]["runtime_name"] == "plug:tool"
    assert plugin_rows[0]["source_file"] == str(plugin_skill.absolute())
    assert plugin_rows[0]["active_state"] == "active"
    serialized = json.dumps(result, ensure_ascii=False)
    assert "TOP-SECRET" not in serialized and "provider_token" not in serialized
    assert str(cache_only) not in serialized and str(disabled / "skills" / "nope") not in serialized
    assert any(i["code"] == "codex_probe_invalid" for i in result["issues"])
    assert result["discovery"]["excluded_counts"]["invalid_declared_name"] == 2
    print("case_codex_fallback_is_conservative PASS")


def case_identity_and_determinism(tmp):
    p1 = _skill(Path(tmp) / "i-a" / "same", "same")
    p2 = _skill(Path(tmp) / "i-b" / "same", "same")
    base = []
    for p in (p2, p1):  # intentionally reversed input
        fact, _ = skillmd.scan_component(p, "skill")
        fact.update({
            "agent": "codex",
            "runtime_name": "same",
            "component_name": "same",
            "name": "same",
            "namespace": None,
            "scope": "user",
            "install_scope": "user",
            "source_kind": "standalone",
            "active_state": "active",
            "discovery_confidence": "runtime_probe",
            "discovery_method": "fixture",
            "plugin_id": None,
            "plugin_name": None,
            "marketplace": None,
            "plugin_version": None,
            "manifest_declared": None,
            "auditable": True,
            "accounting": {"listing": "confirmed", "trigger": "confirmed", "reason": "fixture"},
        })
        base.append(fact)
    first, first_issues = collect.finalize_skills(copy.deepcopy(base))
    second, second_issues = collect.finalize_skills(copy.deepcopy(base))
    assert first == second and not first_issues and not second_issues
    assert len(first) == 2 and len({r["instance_id"] for r in first}) == 2
    assert [r["source_file"] for r in first] == sorted(r["source_file"] for r in first)
    assert all(r["id"] == "codex::same" and r["logical_id"] == "codex::same" for r in first)
    assert all(r["conflict_group"] == "codex::same" for r in first)
    row = first[0]
    material = "\0".join([
        row["agent"], row["component_type"], row["runtime_name"], row["install_scope"],
        os.path.abspath(os.path.normpath(row["source_file"])), row["source_realpath"],
    ])
    expected = "codex::i::" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    assert row["instance_id"] == expected

    issues = [
        {"code": "z", "severity": "warning", "agent": "codex", "stage": "parse",
         "message": "z", "path": None, "safe_context": {}},
        {"code": "a", "severity": "error", "agent": "claude-code", "stage": "discovery",
         "message": "a", "path": "/tmp/a", "safe_context": {}},
    ]
    sorted_a = collect.sort_issues(copy.deepcopy(issues))
    sorted_b = collect.sort_issues(list(reversed(copy.deepcopy(issues))))
    assert sorted_a == sorted_b
    assert collect.issues_to_warnings(sorted_a) == collect.issues_to_warnings(sorted_b)
    print("case_identity_and_determinism PASS")


def case_claude_usage_strict(tmp):
    root = Path(tmp) / "claude-projects"
    source = Path(tmp) / "sources"
    skills = [
        _inventory_skill("claude-code", "plain", "cc-i-plain", _skill(source / "plain", "plain")),
        _inventory_skill("claude-code", "scope:命令/子", "cc-i-scoped", _skill(source / "scoped", "scoped")),
        _inventory_skill("claude-code", "a:dup", "cc-i-dup-a", _skill(source / "dup-a", "dup-a")),
        _inventory_skill("claude-code", "b:dup", "cc-i-dup-b", _skill(source / "dup-b", "dup-b")),
    ]
    resolver = usage.build_name_resolver(skills, "claude-code")

    def assistant(name, timestamp=RECENT, **extra):
        row = {
            "type": "assistant",
            "timestamp": timestamp,
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": name}}],
            },
        }
        row.update(extra)
        return row

    def user(command, timestamp=RECENT, **extra):
        row = {
            "type": "user",
            "timestamp": timestamp,
            "message": {"role": "user", "content": "<command-name>/%s</command-name>" % command},
        }
        row.update(extra)
        return row

    rows = [
        assistant("plain"),
        assistant("scope:命令/子"),
        user("scope:命令/子"),
        assistant("dup"),
        assistant("gone"),
        assistant("gone"),
        user("compact"),  # unknown slash is a built-in/noise and must be ignored
        assistant("plain", timestamp=None),
        assistant("plain", timestamp=OLD),
        user("plain", isCompactSummary=True),
        {"type": "prompt_snapshot", "timestamp": RECENT, "message": assistant("plain")["message"]},
        {"type": "skill_listing", "timestamp": RECENT, "message": assistant("plain")["message"]},
        {"type": "dynamic_skill", "timestamp": RECENT, "message": assistant("plain")["message"]},
        {"type": "invoked_skills", "timestamp": RECENT, "message": assistant("plain")["message"]},
        assistant("plain", attributionSkill="plain"),
        {"type": "assistant", "timestamp": RECENT,
         "message": {"role": "user", "content": assistant("plain")["message"]["content"]}},
        '{"type":"assistant","name":"Skill",BROKEN',
    ]
    _jsonl(root / "session.jsonl", rows)
    records, meta = usage.scan_claude_transcripts(
        30, resolver, roots=[root], now=NOW,
    )
    by_instance = {r["skill_instance_id"]: r for r in records if r["matched"]}
    assert by_instance["cc-i-plain"]["activations"] == 1
    assert by_instance["cc-i-scoped"]["activations"] == 2
    ambiguous = [r for r in records if r["match_status"] == "ambiguous"]
    assert len(ambiguous) == 1
    assert ambiguous[0]["activations"] == 1
    assert ambiguous[0]["candidate_instance_ids"] == ["cc-i-dup-a", "cc-i-dup-b"]
    unmatched = [r for r in records if r["match_status"] == "unmatched"]
    assert len(unmatched) == 1 and unmatched[0]["activations"] == 2
    assert unmatched[0]["source_ref"] == "gone" and unmatched[0]["source_ref_hash"]
    assert all(r["source_ref"] != "compact" for r in records)
    cov = meta["coverage"]
    assert cov["undated_events"] == 1
    assert cov["matched_activations"] == 3
    assert cov["unmatched_activations"] == 2
    assert cov["ambiguous_activations"] == 1
    assert cov["parse_errors"] == 1
    assert cov["direct_events"] == 8
    print("case_claude_usage_strict PASS")


def case_codex_usage_strict(tmp):
    root = Path(tmp) / "codex-sessions"
    src = Path(tmp) / "codex-sources"
    one_file = _skill(src / "one-literal", "one")
    two_file = _skill(src / "two", "two")
    real_one = Path(os.path.realpath(str(one_file)))
    alias_dir = Path(tmp) / "one-alias"
    alias_dir.symlink_to(one_file.parent, target_is_directory=True)
    skills = [
        _inventory_skill(
            "codex", "one", "cx-i-one", one_file,
            source_realpath=str(real_one), symlink_target=str(alias_dir),
        ),
        _inventory_skill("codex", "two", "cx-i-two", two_file),
    ]
    resolver = usage.build_path_resolver(skills, "codex")

    def fn(name, args, timestamp=RECENT, payload_type="function_call"):
        payload = {"type": payload_type, "name": name}
        if payload_type == "function_call":
            payload["arguments"] = json.dumps(args, ensure_ascii=False)
        else:
            payload["input"] = args
        return {"type": "response_item", "timestamp": timestamp, "payload": payload}

    unknown = str((Path(tmp) / "gone" / "SKILL.md").absolute())
    rows = [
        fn("exec_command", {"cmd": "cat '%s' && cat '%s'" % (one_file, real_one)}),
        fn("shell", {"command": "cat '%s' && cat %s" % (one_file, two_file)}),
        fn("exec", "cat '%s'" % (alias_dir / "SKILL.md"), payload_type="custom_tool_call"),
        fn("exec_command", {"cmd": "cat %s" % unknown}),
        fn("exec_command", {"cmd": "cat %s" % unknown}),
        fn("exec_command", {"cmd": "cat %s" % one_file}, timestamp=None),
        fn("exec_command", {"cmd": "cat %s" % one_file}, timestamp=OLD),
        {"type": "world_state", "timestamp": RECENT, "payload": fn("exec_command", {"cmd": "cat %s" % one_file})["payload"]},
        {"type": "session_meta", "timestamp": RECENT, "compacted": {"guardian_history": rows_placeholder(one_file)}},
        {"type": "response_item", "timestamp": RECENT, "payload": {"type": "function_call_output", "output": "cat %s" % one_file}},
        {"type": "event_msg", "timestamp": RECENT, "payload": fn("exec_command", {"cmd": "cat %s" % one_file})["payload"]},
        {"type": "message", "timestamp": RECENT, "payload": fn("exec_command", {"cmd": "cat %s" % one_file})["payload"]},
        {"type": "reasoning", "timestamp": RECENT, "payload": fn("exec_command", {"cmd": "cat %s" % one_file})["payload"]},
        {"type": "response_item", "timestamp": RECENT, "payload": {"type": "function_call", "name": "apply_patch", "arguments": json.dumps({"patch": "cat %s" % one_file})}},
    ]
    _jsonl(root / "rollout-fixture.jsonl", rows)
    records, meta = usage.scan_codex_rollouts(
        30, resolver, roots=[root], now=NOW,
    )
    by_instance = {r["skill_instance_id"]: r for r in records if r["matched"]}
    assert by_instance["cx-i-one"]["activations"] == 3, "同一 shell call 的同一实例只计一次"
    assert by_instance["cx-i-two"]["activations"] == 1
    unmatched = [r for r in records if r["match_status"] == "unmatched"]
    assert len(unmatched) == 1 and unmatched[0]["activations"] == 2
    assert unmatched[0]["source_ref"] == os.path.normpath(unknown)
    cov = meta["coverage"]
    assert cov["undated_events"] == 1
    assert cov["matched_activations"] == 4
    assert cov["unmatched_activations"] == 2
    assert cov["direct_events"] == 8
    print("case_codex_usage_strict PASS")


def rows_placeholder(one_file):
    """Nested historical call shaped like a real event; scanners must never recurse into it."""
    return [{
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "name": "exec_command",
            "arguments": json.dumps({"cmd": "cat %s" % one_file}),
        },
    }]


def case_window_validation(tmp):
    empty = Path(tmp) / "empty"
    empty.mkdir(parents=True, exist_ok=True)
    resolver = usage.build_name_resolver([], "claude-code")
    try:
        usage.scan_claude_transcripts(0, resolver, roots=[empty], now=NOW)
    except ValueError as exc:
        assert "positive" in str(exc).lower() or "正" in str(exc)
    else:
        raise AssertionError("window_days=0 必须拒绝")
    out = Path(tmp) / "should-not-exist"
    rc = collect.main(["--agents", "hermes", "--window-days", "0", "--out-dir", str(out)])
    assert rc == 2 and not out.exists()
    print("case_window_validation PASS")


def case_coverage_degrades_on_unreadable(tmp):
    # 自报 complete 但有读不出的文件/解析错误 → 必须降级 partial，不虚标覆盖面
    degraded = collect._normalize_coverage(
        {"coverage": {"status": "complete", "files_unreadable": 3, "parse_errors": 0}}, True)
    assert degraded["status"] == "partial"
    parse_bad = collect._normalize_coverage(
        {"coverage": {"status": "complete", "files_unreadable": 0, "parse_errors": "2"}}, True)
    assert parse_bad["status"] == "partial"
    clean = collect._normalize_coverage(
        {"coverage": {"status": "complete", "files_unreadable": 0, "parse_errors": 0}}, True)
    assert clean["status"] == "complete"
    # 非法计数当 0 处理：既不崩溃也不误降级
    junk = collect._normalize_coverage(
        {"coverage": {"status": "complete", "files_unreadable": "many", "parse_errors": None}}, True)
    assert junk["status"] == "complete"
    print("case_coverage_degrades_on_unreadable PASS")


def main():
    with tempfile.TemporaryDirectory(prefix="bulus-auditor-v2-fixture-") as tmp:
        case_skillmd_raw_facts(Path(tmp) / "skillmd")
        case_claude_discovery(Path(tmp) / "claude")
        case_claude_cli_failure_is_conservative(Path(tmp) / "claude-failure")
        case_codex_probe_discovery(Path(tmp) / "codex")
        case_codex_fallback_is_conservative(Path(tmp) / "codex-fallback")
        case_identity_and_determinism(Path(tmp) / "identity")
        case_claude_usage_strict(Path(tmp) / "claude-usage")
        case_codex_usage_strict(Path(tmp) / "codex-usage")
        case_window_validation(Path(tmp) / "window")
        case_coverage_degrades_on_unreadable(Path(tmp) / "coverage")
    print("ALL PASS — v0.2 discovery + usage fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
