#!/usr/bin/env python3
"""Apply configured upload formats to one guarded, unpublished-course assignment."""
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
    course = jsonc.load_and_validate(root / "course/course.config.jsonc")
    match = re.search(r"/courses/([1-9][0-9]*)", course["course_url"])
    if not match:
        raise ValueError("Configured Canvas course URL has no numeric course ID")
    return int(match.group(1))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "commands/configure-assignment-upload-formats.config.jsonc")
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    config = jsonc.load_and_validate(args.config)
    course_id = configured_course_id(ROOT)
    if config["course_id"] != course_id:
        raise RuntimeError("Upload-format config does not match the central course configuration")
    canvas = GuardedCanvas(args.server, course_id)
    canvas.health()
    assignment = canvas.raw("GET", f"/courses/{course_id}/assignments/{config['assignment_id']}")
    if assignment.get("name") != config["expected_title"]:
        raise RuntimeError("Assignment title does not match the configured safety precondition")
    before = {key: assignment.get(key) or [] for key in ("submission_types", "allowed_extensions")}
    desired = {key: config[key] for key in ("submission_types", "allowed_extensions")}
    if args.apply:
        if args.confirm != f"SET-UPLOAD-FORMATS-{course_id}-{config['assignment_id']}":
            raise RuntimeError("Apply confirmation is missing or incorrect")
        canvas.require_unpublished()
        assignment = canvas.raw("PUT", f"/courses/{course_id}/assignments/{config['assignment_id']}", {"assignment": desired})
    after = {key: assignment.get(key) or [] for key in ("submission_types", "allowed_extensions")}
    print(json.dumps({"course_id": course_id, "assignment_id": config["assignment_id"],
                      "title": assignment["name"], "before": before, "desired": desired,
                      "after": after, "status": "CURRENT" if after == desired else "DRIFT"}, indent=2))
    return 0 if (not args.apply or after == desired) else 1

if __name__ == "__main__":
    raise SystemExit(main())
