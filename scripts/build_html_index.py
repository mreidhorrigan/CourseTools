#!/usr/bin/env python3
"""Deterministically render the collaborator HTML guide at the project root."""
from __future__ import annotations
import argparse
from pathlib import Path
from build_distribution import render_index

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--root",type=Path,default=ROOT); parser.add_argument("--output",type=Path)
    args=parser.parse_args(); root=args.root.resolve(); output=(args.output or root/"INDEX.html").resolve()
    output.write_text(render_index(root),encoding="utf-8"); print(output); return 0
if __name__=="__main__": raise SystemExit(main())
