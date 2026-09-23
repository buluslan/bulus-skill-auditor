#!/usr/bin/env python3
"""Create a shareable copy of audit output with local paths redacted."""

import argparse
import json
import ntpath
import os
import posixpath
import re
import shutil
import sys
import tempfile
from pathlib import Path


PATH_KEYS = {
    "path",
    "raw_path",
    "realpath",
    "source_file",
    "source_realpath",
    "source_ref",
    "raw_result_path",
    "symlink_target",
    "skill_roots",
    "installpath",
    "install_path",
}

_FILE_EXTENSIONS = (
    "csv|json|jsonl|log|md|markdown|toml|txt|yaml|yml|xml|html|htm|py|sh"
)

# 机器本地根：/tmp、/var、/etc 及其 macOS realpath 形态 /private/tmp、/private/var、/private/etc
# （canonical TMPDIR 拼写是 /var/folders/…，含稳定 per-user 标识，必须覆盖裸 /var 形态）
_POSIX_LOCAL_ROOTS = r"(?:(?:private/)?(?:tmp|var|etc))"

# 分隔符类同时容忍 JSON 转义后的双反斜杠（文本兜底路径里的 C:\\Users\\…）
_WIN_SEP = r"[\\\\/]+"
_WIN_SEG = r"[^\\\\/\s`\"'<>]"

# Extension-aware patterns run first so paths containing spaces can be kept useful
# without exposing their local prefix. The shorter patterns then cover directories
# and extensionless files that contain no whitespace.
# POSIX 模式的前瞻否定：只挡字母数字（允许 file: / scp host: 等冒号前缀后的本地路径；
# URL 里若真出现 /Users/<name> 段也会被脱敏——对隐私工具而言过度脱敏比泄漏安全）
_POSIX_LOOKBEHIND = r"(?<![\w])"

_POSIX_WITH_EXTENSION_RE = re.compile(
    _POSIX_LOOKBEHIND
    + r"(?P<path>/(?:Users|home)/[^/\s`\"'<>]+/[^`\"'<>\r\n]*?\."
    + r"(?:%s))" % _FILE_EXTENSIONS,
    re.IGNORECASE,
)
_POSIX_LOCAL_WITH_EXTENSION_RE = re.compile(
    _POSIX_LOOKBEHIND
    + r"(?P<path>/%s/[^/\s`\"'<>]+(?:/[^\s`\"'<>\r\n]*?)?\.(?:%s))"
    % (_POSIX_LOCAL_ROOTS, _FILE_EXTENSIONS),
    re.IGNORECASE,
)
_ROOT_WITH_EXTENSION_RE = re.compile(
    r"(?<![:\w])(?P<path>/root/[^`\"'<>\r\n]*?\.(?:%s))" % _FILE_EXTENSIONS,
    re.IGNORECASE,
)
# 任意盘符（C:…/D:…），要求至少一级目录，避免吞掉句中零散的 "X:"；
# 分隔符用 _WIN_SEP 同时覆盖 C:\ C:/ 与 JSON 转义的 C:\\
_WINDOWS_WITH_EXTENSION_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<path>[A-Za-z]:%(sep)s(?:%(seg)s+%(sep)s)+[^`\"'<>\r\n]*?\.(?:%(ext)s))"
    % {"sep": _WIN_SEP, "seg": _WIN_SEG, "ext": _FILE_EXTENSIONS},
    re.IGNORECASE,
)
# UNC：\\server\share\…（含 JSON 转义的 \\\\server\\share\\…）
_UNC_WITH_EXTENSION_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<path>\\\\%(seg)s+%(sep)s%(seg)s+(?:%(sep)s[^`\"'<>\r\n]*?)?\.(?:%(ext)s))"
    % {"sep": _WIN_SEP, "seg": _WIN_SEG, "ext": _FILE_EXTENSIONS},
    re.IGNORECASE,
)
_POSIX_PATH_RE = re.compile(
    _POSIX_LOOKBEHIND + r"(?P<path>/(?:Users|home)/[^/\s`\"'<>]+(?:/[^\s`\"'<>]*)*)"
)
_POSIX_LOCAL_PATH_RE = re.compile(
    _POSIX_LOOKBEHIND + r"(?P<path>/%s/[^/\s`\"'<>]+(?:/[^\s`\"'<>]*)*)" % _POSIX_LOCAL_ROOTS
)
_ROOT_PATH_RE = re.compile(r"(?<![:\w])(?P<path>/root(?:/[^\s`\"'<>]*)?)")
_WINDOWS_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<path>[A-Za-z]:%(sep)s(?:%(seg)s+%(sep)s)+[^\s`\"'<>]*)"
    % {"sep": _WIN_SEP, "seg": _WIN_SEG},
    re.IGNORECASE,
)
_UNC_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<path>\\\\%(seg)s+%(sep)s%(seg)s+(?:%(sep)s[^\s`\"'<>]*)*)"
    % {"sep": _WIN_SEP, "seg": _WIN_SEG},
    re.IGNORECASE,
)
_BACKTICK_PATH_RE = re.compile(
    r"`(?P<path>"
    r"(?:/(?:Users|home)/[^/`]+(?:/[^`]*)?|/root(?:/[^`]*)?|/%s/[^/`]+(?:/[^`]*)?|"
    r"[A-Za-z]:[\\\\/]+[^`]+|\\\\[^`]+)"
    r")`" % _POSIX_LOCAL_ROOTS,
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION = ".,;:)]}"


def _is_windows_absolute(value):
    return bool(re.match(r"^[A-Za-z]:[\\/]", value)) or ntpath.isabs(value)


def _is_absolute_path(value):
    return isinstance(value, str) and (
        os.path.isabs(value) or _is_windows_absolute(value)
    )


def _basename(value):
    stripped = value.rstrip("/\\")
    if not stripped:
        return ""
    if _is_windows_absolute(value):
        return ntpath.basename(stripped)
    return posixpath.basename(stripped)


# 裸用户家目录形态：末段就是用户名本身，保留 basename = 泄漏用户名，整体替换
_BARE_HOME_RE = re.compile(
    r"^(?:/(?:Users|home)/[^/]+|[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/]+)$",
    re.IGNORECASE,
)


def redact_path(value):
    """Redact a complete absolute path while retaining only its basename."""
    if not isinstance(value, str) or not _is_absolute_path(value):
        return value
    if _BARE_HOME_RE.match(value.rstrip("/\\")):
        return "<local-path>"
    name = _basename(value)
    return "<local-path>/%s" % name if name else "<local-path>"


def _replace_path_match(match):
    value = match.group("path")
    trailing = ""
    while value and value[-1] in _TRAILING_PUNCTUATION:
        trailing = value[-1] + trailing
        value = value[:-1]
    return redact_path(value) + trailing


def _replace_backtick_match(match):
    return "`%s`" % redact_path(match.group("path"))


def redact_text(value):
    """Redact embedded macOS, Linux, and Windows user paths in text."""
    if not isinstance(value, str):
        return value
    redacted = _BACKTICK_PATH_RE.sub(_replace_backtick_match, value)
    for pattern in (
        _POSIX_WITH_EXTENSION_RE,
        _POSIX_LOCAL_WITH_EXTENSION_RE,
        _ROOT_WITH_EXTENSION_RE,
        _WINDOWS_WITH_EXTENSION_RE,
        _UNC_WITH_EXTENSION_RE,
        _POSIX_PATH_RE,
        _POSIX_LOCAL_PATH_RE,
        _ROOT_PATH_RE,
        _WINDOWS_PATH_RE,
        _UNC_PATH_RE,
    ):
        redacted = pattern.sub(_replace_path_match, redacted)
    return redacted


def _is_path_key(key):
    if not isinstance(key, str):
        return False
    normalized = key.replace("-", "_").lower()
    return normalized in PATH_KEYS


_MAX_REDACT_DEPTH = 100  # 深嵌套 JSON 防递归崩溃；超深的子树整体替换为占位符（宁可丢内容不泄漏）


def redact(value, key=None, _depth=0):
    """Return a redacted copy of a JSON-compatible value."""
    if isinstance(value, dict):
        if _depth >= _MAX_REDACT_DEPTH:
            return "<deep-nested-value-redacted>"
        return {
            item_key: redact(item, item_key, _depth + 1)
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        if _depth >= _MAX_REDACT_DEPTH:
            return "<deep-nested-value-redacted>"
        return [redact(item, key, _depth + 1) for item in value]
    if isinstance(value, str):
        if _is_path_key(key):
            path_value = redact_path(value)
            if path_value != value:
                return path_value
        return redact_text(value)
    return value


def _write_json_copy(source, target):
    try:
        with source.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, RecursionError):
        # 坏 JSON 或超深嵌套（json 解析器自身递归爆栈）→ 退回文本正则脱敏，永不因单文件中断
        _write_text_copy(source, target)
        return
    try:
        with target.open("w", encoding="utf-8") as handle:
            json.dump(redact(payload), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except RecursionError:
        _write_text_copy(source, target)


def _write_text_copy(source, target):
    try:
        content = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("无法安全脱敏二进制文件: %s" % source) from exc
    target.write_text(redact_text(content), encoding="utf-8")


def _write_jsonl_copy(source, target):
    """JSONL 逐行结构化脱敏：JSON 转义过的 Windows 双反斜杠路径只有解析后才能稳定命中；
    解析失败的行退回文本正则兜底，永不因坏行中断。"""
    try:
        content = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("无法安全脱敏二进制文件: %s" % source) from exc
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            lines.append(redact_text(line))
            continue
        lines.append(json.dumps(redact(payload), ensure_ascii=False))
    target.write_text("\n".join(lines) + ("\n" if content.endswith("\n") else ""),
                      encoding="utf-8")


def _transform_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    if suffix == ".json":
        _write_json_copy(source, target)
    elif suffix == ".jsonl":
        _write_jsonl_copy(source, target)
    else:
        _write_text_copy(source, target)
    shutil.copymode(str(source), str(target))


def _resolved_for_compare(value):
    return os.path.normcase(os.path.realpath(os.path.abspath(str(value))))


def _same_path(left, right):
    return _resolved_for_compare(left) == _resolved_for_compare(right)


def _is_within(candidate, directory):
    candidate_abs = _resolved_for_compare(candidate)
    directory_abs = _resolved_for_compare(directory)
    try:
        return os.path.commonpath([candidate_abs, directory_abs]) == directory_abs
    except ValueError:
        return False


def create_share_copy(source, output):
    """Create a redacted file or directory copy without changing the source."""
    source = Path(source).expanduser()
    output = Path(output).expanduser()
    if not source.exists():
        raise ValueError("输入不存在: %s" % source)
    if source.is_symlink():
        raise ValueError("输入不能是符号链接: %s" % source)
    if _same_path(source, output):
        raise ValueError("输出必须与输入不同，原始产物不会被原地修改")

    if source.is_file():
        output.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".%s." % output.name,
            suffix=".tmp",
            dir=str(output.parent),
        )
        os.close(file_descriptor)
        temporary = Path(temporary_name)
        try:
            _transform_file(source, temporary)
            os.replace(str(temporary), str(output))
        finally:
            if temporary.exists():
                temporary.unlink()
        return output

    if not source.is_dir():
        raise ValueError("输入必须是普通文件或目录: %s" % source)
    if _is_within(output, source):
        raise ValueError("目录副本必须写到输入目录之外")
    if output.exists():
        raise ValueError("输出目录已存在，请换一个新的分享副本目录: %s" % output)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".%s." % output.name, dir=str(output.parent))
    )
    try:
        for item in sorted(source.rglob("*"), key=lambda path: str(path)):
            relative = item.relative_to(source)
            destination = temporary / relative
            if item.is_symlink():
                raise ValueError("分享副本不跟随符号链接: %s" % item)
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif item.is_file():
                _transform_file(item, destination)
            else:
                raise ValueError("不支持的文件类型: %s" % item)
        os.replace(str(temporary), str(output))
    finally:
        if temporary.exists():
            shutil.rmtree(str(temporary))
    return output


def build_parser():
    parser = argparse.ArgumentParser(
        description="生成不修改原件的脱敏分享副本；支持单个 JSON/Markdown 文件或整个输出目录"
    )
    parser.add_argument("input", help="输入文件或输出目录")
    parser.add_argument("--out", required=True, help="分享副本文件或目录")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = create_share_copy(args.input, args.out)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(output.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
