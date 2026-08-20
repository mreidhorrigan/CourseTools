#!/usr/bin/env python3
"""Restrict instructor-only assessment trees to the current local account."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ((ROOT / "private/testmaking").resolve(),
           (ROOT / "out/testmaking-authoring").resolve(),
           (ROOT / "out/build-test-forms").resolve())


def secure_tree(root: Path) -> tuple[int, int]:
    target = root.resolve()
    if target not in ALLOWED:
        raise ValueError(f"refusing unapproved assessment tree: {target}")
    if not target.exists():
        return 0, 0
    directories = files = 0
    for path in [target, *sorted(target.rglob("*"))]:
        if path.is_symlink():
            raise ValueError(f"refusing symbolic link in assessment tree: {path}")
        if path.is_dir():
            os.chmod(path, 0o700); directories += 1
        elif path.is_file():
            os.chmod(path, 0o600); files += 1
    return directories, files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-output", action="store_true")
    args = parser.parse_args()
    targets = ALLOWED if args.include_output else ALLOWED[:1]
    counts = [secure_tree(path) for path in targets]
    print(f"Secured {sum(x for x, _ in counts)} directories and {sum(y for _, y in counts)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
