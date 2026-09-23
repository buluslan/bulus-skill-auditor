#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapter registry and shared, policy-free safety helpers.

Agent-specific activation rules live in their adapter modules.  In particular, this
module never walks plugin caches or infers that a directory is active.
"""
import json
import os
import subprocess
from pathlib import Path

_CLI_CACHE = {}
_SEVERITIES = ("info", "warning", "error")
_STAGES = ("discovery", "parse", "usage", "eval", "report")
_SAFE_CONTEXT_KEYS = {
    "component_type", "count", "error_type", "field", "plugin_id", "reason",
    "returncode", "root_id", "timeout_seconds", "version",
}


def normalize_lexical_path(path):
    """Return a stable absolute lexical path without resolving symlinks."""
    return os.path.abspath(os.path.normpath(str(path)))


def path_is_within(path, root):
    """Lexically contain ``path`` in ``root`` (Python 3.9 compatible)."""
    try:
        return os.path.commonpath([normalize_lexical_path(path), normalize_lexical_path(root)]) == normalize_lexical_path(root)
    except (TypeError, ValueError):
        return False


def make_issue(code, severity, agent, stage, message, path=None, safe_context=None):
    """Build a deterministic diagnostic without copying untrusted CLI/config text."""
    if severity not in _SEVERITIES:
        raise ValueError("invalid issue severity: %s" % severity)
    if stage not in _STAGES:
        raise ValueError("invalid issue stage: %s" % stage)
    context = {}
    for key, value in sorted((safe_context or {}).items()):
        if key not in _SAFE_CONTEXT_KEYS:
            continue
        if value is None or isinstance(value, (bool, int, float)):
            context[key] = value
        elif isinstance(value, str):
            context[key] = value[:200]
    return {
        "code": str(code),
        "severity": severity,
        "agent": agent,
        "stage": stage,
        "message": str(message),
        "path": normalize_lexical_path(path) if path else None,
        "safe_context": context,
    }


def issue_sort_key(issue):
    severity_rank = {"error": 0, "warning": 1, "info": 2}
    return (
        severity_rank.get(issue.get("severity"), 9),
        str(issue.get("agent") or ""),
        str(issue.get("stage") or ""),
        str(issue.get("code") or ""),
        str(issue.get("path") or ""),
        str(issue.get("message") or ""),
        json.dumps(issue.get("safe_context") or {}, ensure_ascii=False, sort_keys=True),
    )


def run_cli_json(command, agent, stage, timeout=5):
    """Run a read-only management CLI once and decode one JSON value safely.

    The process cache prevents repeated calls while discovering multiple components.
    Diagnostics intentionally contain no stdout/stderr or environment/config values.
    """
    key = (tuple(command), int(timeout))
    if key in _CLI_CACHE:
        cached = _CLI_CACHE[key]
        return {
            "ok": cached["ok"],
            "data": cached["data"],
            "returncode": cached["returncode"],
            "issue": dict(cached["issue"]) if cached.get("issue") else None,
        }
    try:
        proc = subprocess.run(
            list(command), capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        result = {
            "ok": False,
            "data": None,
            "returncode": None,
            "issue": make_issue(
                "management_cli_timeout", "warning", agent, stage,
                "management CLI timed out; discovery used a conservative fallback",
                safe_context={"timeout_seconds": timeout},
            ),
        }
    except (OSError, ValueError) as exc:
        result = {
            "ok": False,
            "data": None,
            "returncode": None,
            "issue": make_issue(
                "management_cli_unavailable", "warning", agent, stage,
                "management CLI could not be started; discovery used a conservative fallback",
                safe_context={"error_type": type(exc).__name__},
            ),
        }
    else:
        if proc.returncode != 0:
            result = {
                "ok": False,
                "data": None,
                "returncode": proc.returncode,
                "issue": make_issue(
                    "management_cli_nonzero", "warning", agent, stage,
                    "management CLI exited non-zero; discovery used a conservative fallback",
                    safe_context={"returncode": proc.returncode},
                ),
            }
        else:
            try:
                data = json.loads(proc.stdout)
            except (TypeError, ValueError):
                result = {
                    "ok": False,
                    "data": None,
                    "returncode": proc.returncode,
                    "issue": make_issue(
                        "management_cli_bad_json", "warning", agent, stage,
                        "management CLI returned invalid JSON; discovery used a conservative fallback",
                    ),
                }
            else:
                if not isinstance(data, (dict, list)):
                    result = {
                        "ok": False,
                        "data": None,
                        "returncode": proc.returncode,
                        "issue": make_issue(
                            "management_cli_bad_json", "warning", agent, stage,
                            "management CLI returned an unsupported JSON shape; discovery used a conservative fallback",
                        ),
                    }
                else:
                    result = {"ok": True, "data": data, "returncode": proc.returncode, "issue": None}
    _CLI_CACHE[key] = result
    return {
        "ok": result["ok"],
        "data": result["data"],
        "returncode": result["returncode"],
        "issue": dict(result["issue"]) if result.get("issue") else None,
    }


def reset_cli_cache():
    """Clear process-local management CLI cache (primarily for deterministic tests)."""
    _CLI_CACHE.clear()


# Imports follow helper definitions to avoid partial-initialization cycles.
from . import claude_code, codex, hermes  # noqa: F401,E402

REGISTRY = {
    "claude-code": claude_code,
    "codex": codex,
    "hermes": hermes,
}
ALL_AGENTS = ["claude-code", "codex", "hermes"]


def get_adapters(names):
    return [(name, REGISTRY[name]) for name in names]
