#!/usr/bin/env python3
"""_pipeline.py — read pipeline.json and report a profile's step status.

Helper for the stepwise driver (pipeline.command); not run directly by users. The 'done_if'
globs are evaluated relative to the profile folder (profiles/<name>/), so a step is 'done' once
its expected output exists. staged course workflow specialises this as a study under studies/<name>/.
See 13-staged-pipelines-and-shared-config.md.

  _pipeline.py list <profile_home>          -> tab rows:  n \\t step \\t status \\t desc   (status: done|next|todo)
  _pipeline.py resolve <profile_home> <sel> -> the step stem for sel (n | name | "next"); "GATED " prefix if gated
  _pipeline.py optional                     -> tab rows:  step \\t gated|optional \\t desc
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = json.loads((HERE / "pipeline.json").read_text())


def status(profile_home: str):
    ph = Path(profile_home)
    rows, took_next = [], False
    for s in PIPE["pipeline"]:
        done = bool(glob.glob(str(ph / s["done_if"])))
        if done:
            st = "done"
        elif not took_next:
            st, took_next = "next", True
        else:
            st = "todo"
        rows.append((s["n"], s["step"], st, s.get("desc", "")))
    return rows


def gated(step: str) -> bool:
    return any(s["step"] == step and s.get("gated") for s in PIPE.get("optional", []))


def resolve(profile_home: str, sel: str):
    if sel == "next":
        for _n, step, st, _desc in status(profile_home):
            if st == "next":
                return step
        return None
    if sel.isdigit():
        for s in PIPE["pipeline"]:
            if s["n"] == int(sel):
                return s["step"]
    names = [s["step"] for s in PIPE["pipeline"]] + [s["step"] for s in PIPE.get("optional", [])]
    return sel if sel in names else None


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: _pipeline.py list|resolve|optional [...]", file=sys.stderr)
        return 2
    cmd = args[0]
    if cmd == "list" and len(args) >= 2:
        for n, step, st, desc in status(args[1]):
            print(f"{n}\t{step}\t{st}\t{desc}")
        return 0
    if cmd == "resolve" and len(args) >= 3:
        step = resolve(args[1], args[2])
        if not step:
            return 1
        print(("GATED " if gated(step) else "") + step)
        return 0
    if cmd == "optional":
        for s in PIPE.get("optional", []):
            print(f"{s['step']}\t{'gated' if s.get('gated') else 'optional'}\t{s.get('desc', '')}")
        return 0
    print("usage: _pipeline.py list|resolve|optional [...]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
