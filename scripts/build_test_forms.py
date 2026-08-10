#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from canvas_automation.test_forms import build_forms


def main():
    parser = argparse.ArgumentParser(description="Build deterministic PDF test forms from a Testmaker source file.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--versions", type=int, default=3)
    parser.add_argument("--seed", default="1")
    args = parser.parse_args()
    build_forms(args.input, args.output, args.title, args.versions, args.seed)
    print(args.output / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
