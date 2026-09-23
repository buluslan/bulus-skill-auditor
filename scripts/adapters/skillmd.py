#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKILL.md 共享解析 + skill 目录统计（claude-code/codex/hermes 的 SKILL.md 同构，agentskills.io 开放标准）。

只读。健壮性针对同类工具公开反馈里一半的坑：
块标量(>-/|/|-)、plain 多行 description、CRLF、成对引号、'---' 不闭合、Tab 缩进。

frontmatter "坏" 的检测口径（S1 官方结论）：frontmatter 坏 = 官方字段全丢且零警告、name 回退目录名。
本解析器对结构性破坏（未闭合 / Tab 缩进 / 非法顶层行 / 重复键）raise SkillMDParseError，
调用方记 warning「官方会静默丢弃字段」，该 skill 仍保留文件层条目，不崩。
"""
import os
import re
from pathlib import Path

MAX_READ = 5 * 1024 * 1024  # 单文件读取上限（防异常大文件拖垮扫描）

_KEY_RE = re.compile(r"^([ \t]*)([A-Za-z0-9_.\-]+):(.*)$")
_BLOCK_INDICATORS = (">", "|", ">-", "|-", ">+", "|+")


class SkillMDParseError(Exception):
    """frontmatter 结构性损坏（官方会静默丢弃全部字段）。"""


def read_text(path):
    """读文本（utf-8 宽容模式，封顶 MAX_READ）。只读。"""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read(MAX_READ)


def _indent_len(s):
    return len(s) - len(s.lstrip(" \t"))


def _strip_quotes(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        inner = v[1:-1]
        if v[0] == "'":
            return inner.replace("''", "'")
        return _unescape(inner)
    return v


def _unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] in ('n', 't', '\\', '"'):
            out.append({"n": "\n", "t": "\t"}.get(s[i + 1], s[i + 1]))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _take_block(lines, i, key_indent):
    """收集块标量的缩进内容行，返回 (block, 新 i)。"""
    block = []
    n = len(lines)
    while i < n:
        ln = lines[i]
        if ln.strip() == "":
            block.append("")
            i += 1
            continue
        if _indent_len(ln) > key_indent:
            block.append(ln)
            i += 1
            continue
        break
    while block and block[-1] == "":
        block.pop()
    return block, i


def _render_block(block, indicator):
    """按指示符渲染块标量；'>' 折叠成单字符串（契约要求），'|' 保留换行。"""
    if not block:
        return ""
    ind = min(_indent_len(l) for l in block if l.strip())
    ded = [l[ind:] if l.strip() else "" for l in block]
    if indicator.startswith(">"):
        pieces = []
        for ln in ded:
            if not ln:
                pieces.append("\n")
            else:
                if pieces and not pieces[-1].endswith("\n"):
                    pieces.append(" ")
                pieces.append(ln)
        s = "".join(pieces)
    else:
        s = "\n".join(ded)
    return s.strip()


def parse_frontmatter(text):
    """解析 frontmatter，返回 (meta: dict[str,str], body: str, keys: list[str])。

    无 frontmatter → ({}, 原文, [])，不算坏。结构性损坏 → raise SkillMDParseError。
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text, []
    meta, keys, bad = {}, [], None
    i, n = 1, len(lines)
    while i < n:
        raw = lines[i]
        stripped = raw.strip()
        if stripped in ("---", "..."):
            if bad:
                raise SkillMDParseError(bad)
            return meta, "\n".join(lines[i + 1:]), keys
        if raw.startswith("\t"):
            if bad is None:
                bad = "第 %d 行使用 Tab 缩进（YAML 禁止）" % (i + 1)
            i += 1
            continue
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        m = _KEY_RE.match(raw)
        if not m:
            if raw[0] in (" ", "-"):  # 列表项/续行：挂在上一键，不记键名
                i += 1
                continue
            if bad is None:
                bad = "第 %d 行不是合法键值：%r" % (i + 1, stripped[:40])
            i += 1
            continue
        key_indent, key, rest = len(m.group(1)), m.group(2), m.group(3).strip()
        if key in meta and bad is None:
            bad = "键 %r 重复出现（严格 YAML 视为错误）" % key
        i += 1
        if rest in _BLOCK_INDICATORS:
            block, i = _take_block(lines, i, key_indent)
            meta[key] = _render_block(block, rest)
            keys.append(key)
            continue
        # plain 标量 + 缩进续行（多行 description 的常见形态）
        parts = [rest] if rest else []
        while i < n:
            nxt = lines[i]
            ns = nxt.strip()
            if ns in ("---", "..."):
                break
            if not ns:
                i += 1
                continue
            if nxt.startswith("\t"):  # Tab 缩进 YAML 禁止——交回外层统一判坏
                if bad is None:
                    bad = "第 %d 行使用 Tab 缩进（YAML 禁止）" % (i + 1)
                break
            if _indent_len(nxt) > key_indent:
                parts.append(ns)
                i += 1
                continue
            break
        meta[key] = _strip_quotes(" ".join(p for p in parts if p))
        keys.append(key)
    raise SkillMDParseError("frontmatter 未闭合（缺少结尾 '---'）")


def _dir_stats(sub, root):
    """统计子目录（references/ 或 scripts/）：(相对路径列表, 总字符数)。跳过隐藏文件。

    路径相对 skill 根 root 产出（带 references/、scripts/ 前缀），
    与 CONTRACT.md skills[] 的 ref_files/scripts_files 形态一致。
    """
    if not sub.is_dir():
        return [], 0
    files, total = [], 0
    for dirpath, dirnames, filenames in os.walk(str(sub)):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if fn.startswith("."):
                continue
            fp = os.path.join(dirpath, fn)
            # 路径相对 skill 根产出（带 references/、scripts/ 前缀），与数据契约的形态一致
            files.append(os.path.relpath(fp, str(root)))
            try:
                total += len(read_text(fp))
            except OSError:
                pass
    return sorted(files), total


def _component_root(source_file, component_type):
    """Return the content root without assigning any runtime identity."""
    source = Path(source_file)
    if component_type == "skill" and source.name == "SKILL.md":
        return source.parent
    return source.parent


def scan_component(source_file, component_type):
    """Read one explicitly discovered component and return content facts only.

    Discovery adapters own runtime names, scopes, plugin identity, and active state.  This
    parser deliberately knows none of those concepts.  ``source_file`` is kept lexical
    while ``source_realpath`` records the physical target so collect can build a stable
    instance identity later.
    """
    if component_type not in ("skill", "command", "agent"):
        raise ValueError("unsupported component_type: %s" % component_type)
    source = Path(os.path.abspath(os.path.normpath(str(source_file))))
    root = _component_root(source, component_type)
    source_realpath = os.path.realpath(str(source))
    root_realpath = os.path.realpath(str(root))
    fact = {
        "component_type": component_type,
        "declared_name": None,
        "directory_name": root.name,
        "path": str(root),
        "realpath": root_realpath,
        "source_file": str(source),
        "source_realpath": source_realpath,
        "symlink_target": root_realpath if str(root) != root_realpath else None,
        "description": "",
        "has_skill_md": component_type == "skill" and source.is_file(),
        "body_chars": 0,
        "body_lines": 0,
        "ref_files": [],
        "ref_total_chars": 0,
        "scripts_files": [],
        "frontmatter_keys": [],
        "source_format": "skill-md" if component_type == "skill" else "markdown",
    }
    issues = []
    if not source.is_file():
        issues.append({
            "code": "component_source_missing",
            "message": "component source file is not readable",
            "path": str(source),
            "safe_context": {"component_type": component_type},
        })
        return fact, issues
    try:
        text = read_text(source)
        meta, body, keys = parse_frontmatter(text)
        declared = meta.get("name")
        fact["declared_name"] = str(declared).strip() if declared is not None and str(declared).strip() else None
        fact["description"] = str(meta.get("description", "")).strip()
        fact["body_chars"] = len(body)
        fact["body_lines"] = len(body.splitlines())
        fact["frontmatter_keys"] = keys
    except SkillMDParseError as exc:
        # Claude/Codex drop malformed frontmatter fields; keep the file-level facts.
        fact["body_chars"] = len(text)
        fact["body_lines"] = len(text.splitlines())
        issues.append({
            "code": "frontmatter_invalid",
            "message": "frontmatter is structurally invalid; declared fields were ignored",
            "path": str(source),
            "safe_context": {"detail": str(exc)[:200]},
        })
    except OSError as exc:
        fact["has_skill_md"] = False
        issues.append({
            "code": "component_read_failed",
            "message": "component source file could not be read",
            "path": str(source),
            "safe_context": {"error_type": type(exc).__name__},
        })
        return fact, issues

    if component_type == "skill":
        fact["ref_files"], fact["ref_total_chars"] = _dir_stats(root / "references", root)
        fact["scripts_files"], _ = _dir_stats(root / "scripts", root)
    return fact, issues


def scan_skill_dir(path, agent=None, scope=None):
    """Backward-compatible directory entry point.

    ``agent`` and ``scope`` remain accepted for v1 callers, but identity and active-state
    decisions intentionally stay in the discovery adapter/collector.
    """
    fact, issues = scan_component(Path(path) / "SKILL.md", "skill")
    warnings = ["%s (%s)" % (item["message"], item.get("path") or "unknown") for item in issues]
    return fact, warnings
