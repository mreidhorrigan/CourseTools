#!/usr/bin/env python3
"""Fail when institution- or course-specific markers leak into reusable code."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from canvas_automation import jsonc
from build_distribution import source_files


def audit(root: Path, config: dict, distribution_config: dict) -> dict:
    allowed_prefixes = tuple(config.get("course_content_prefixes", []))
    allowed_paths = set(config.get("course_content_test_paths", []))
    extensions = set(config["scan_extensions"])
    patterns = [(item["name"], re.compile(item["pattern"], re.I)) for item in config["markers"]]
    violations, config_review = [], []
    for rel, path in source_files(root, distribution_config.get("exclude_paths", [])):
        if path.suffix not in extensions or rel.startswith(allowed_prefixes) or rel in allowed_paths:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        is_config = rel.endswith(".config.jsonc")
        for number, line in enumerate(lines, 1):
            for name, pattern in patterns:
                if pattern.search(line):
                    finding = {"path": rel, "line": number, "marker": name}
                    (config_review if is_config else violations).append(finding)
    return {
        "portable": not violations,
        "violations": violations,
        "config_review": config_review,
        "reviewed_file_count": len(source_files(root, distribution_config.get("exclude_paths", []))),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=ROOT / "commands/portability-audit.config.jsonc")
    parser.add_argument("--distribution-config", type=Path, default=ROOT / "commands/build-distribution.config.jsonc")
    args = parser.parse_args()
    result = audit(args.root.resolve(), jsonc.load_and_validate(args.config), jsonc.load_and_validate(args.distribution_config))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["portable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
