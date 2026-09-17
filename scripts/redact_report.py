#!/usr/bin/env python3
"""Create a shareable JSON copy with local filesystem paths redacted."""

import argparse
import json
import os
from pathlib import Path


PATH_KEYS = {"path", "raw_path", "symlink_target", "skill_roots"}


def redact_path(value):
    if not isinstance(value, str) or not os.path.isabs(value):
        return value
    name = Path(value).name
    return "<local-path>/%s" % name if name else "<local-path>"


def redact(value, key=None):
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    if key in PATH_KEYS:
        return redact_path(value)
    return value


def main():
    parser = argparse.ArgumentParser(description="脱敏 JSON 报告中的本机绝对路径")
    parser.add_argument("input", help="输入 JSON 文件")
    parser.add_argument("--out", required=True, help="脱敏副本输出路径")
    args = parser.parse_args()
    with open(args.input, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    output = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(redact(payload), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(output)


if __name__ == "__main__":
    main()
