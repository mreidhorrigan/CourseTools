#!/usr/bin/env python3
"""Verify that a local guard targets the configured, unpublished Canvas course."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from canvas_automation import jsonc
from sandbox_course_lifecycle import GuardedCanvas

def configured_course_id(root: Path) -> int:
    config = jsonc.load_and_validate(root / "course/course.config.jsonc")
    match = re.search(r"/courses/([1-9][0-9]*)", config["course_url"])
    if not match:
        raise RuntimeError("The configured course URL has no numeric course ID")
    return int(match.group(1))

def verify(root: Path, server: str) -> dict:
    course_id = configured_course_id(root)
    canvas = GuardedCanvas(server, course_id)
    health = canvas.health()
    if int(health.get("allowed_course_id", 0)) != course_id:
        raise RuntimeError("The running server is guarded to a different course")
    course = canvas.raw("GET", f"/courses/{course_id}")
    if course.get("workflow_state") != "unpublished":
        raise RuntimeError(f"Refusing update: Canvas course {course_id} is published")
    return {"status": "PASS", "course_id": course_id, "workflow_state": "unpublished",
            "guarded_course_id": health["allowed_course_id"]}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve(), args.server), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
