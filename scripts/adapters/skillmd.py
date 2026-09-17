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
            files.append(os.path.relpath(fp, str(root)))  # B1：原为相对 sub 的裸文件名，导致 measure 拼路径全部 FileNotFoundError
            try:
                total += len(read_text(fp))
            except OSError:
                pass
    return sorted(files), total


def scan_skill_dir(path, agent, scope):
    """扫描一个 skill 目录，返回 (契约 skills[] 单条 dict, warnings 列表)。100% 只读。"""
    p = Path(path)
    entry = {
        "id": "%s::%s" % (agent, p.name),
        "agent": agent,
        "name": p.name,
        "path": str(p),
        "symlink_target": os.path.realpath(str(p)) if os.path.islink(str(p)) else None,
        "scope": scope,
        "description": "",
        "has_skill_md": False,
        "body_chars": 0,
        "body_lines": 0,
        "ref_files": [],
        "ref_total_chars": 0,
        "scripts_files": [],
        "frontmatter_keys": [],
    }
    warns = []
    sm = p / "SKILL.md"
    if sm.is_file():
        entry["has_skill_md"] = True
        try:
            meta, body, keys = parse_frontmatter(read_text(sm))
            entry["description"] = str(meta.get("description", "")).strip()
            entry["body_chars"] = len(body)
            entry["body_lines"] = len(body.splitlines())
            entry["frontmatter_keys"] = keys
        except SkillMDParseError as e:
            # 官方口径：frontmatter 坏 = 字段全丢且零警告、name 回退目录名——审计层必须显性标出
            warns.append("%s: frontmatter 坏（%s），官方会静默丢弃字段" % (entry["id"], e))
        except OSError as e:
            warns.append("%s: SKILL.md 读不了（%s），仅计文件层" % (entry["id"], e))
    entry["ref_files"], entry["ref_total_chars"] = _dir_stats(p / "references", p)  # B1：基准改 skill 根
    entry["scripts_files"], _ = _dir_stats(p / "scripts", p)
    return entry, warns
