#!/usr/bin/env python3
"""Make the Start Here syllabus module item open Canvas's canonical Syllabus view."""
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

MODULE_TITLE = "Start Here"
ITEM_TITLE = "IAT 210 Course Syllabus"

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    config = jsonc.load_and_validate(ROOT / "course/course.config.jsonc")
    match = re.search(r"/courses/([1-9][0-9]*)", config["course_url"])
    if not match:
        raise RuntimeError("Configured course URL has no numeric course ID")
    course_id = int(match.group(1)); target = config["course_url"].rstrip("/") + "/assignments/syllabus"
    canvas = GuardedCanvas(args.server, course_id); canvas.health()
    modules = canvas.raw("GET", f"/courses/{course_id}/modules", params={"per_page": 100})
    module = next(item for item in modules if item["name"] == MODULE_TITLE)
    items = canvas.raw("GET", f"/courses/{course_id}/modules/{module['id']}/items", params={"per_page": 100})
    item = next(item for item in items if item["title"] == ITEM_TITLE)
    current = item.get("type") == "ExternalUrl" and item.get("external_url") == target
    if args.apply and not current:
        if args.confirm != f"SET-SYLLABUS-LINK-{course_id}":
            raise RuntimeError(f"Apply requires --confirm SET-SYLLABUS-LINK-{course_id}")
        canvas.require_unpublished()
        position = item.get("position", 1)
        canvas.raw("DELETE", f"/courses/{course_id}/modules/{module['id']}/items/{item['id']}")
        item = canvas.raw("POST", f"/courses/{course_id}/modules/{module['id']}/items", {"module_item": {
            "type": "ExternalUrl", "title": ITEM_TITLE, "external_url": target,
            "new_tab": False, "position": position,
        }})
        current = item.get("type") == "ExternalUrl" and item.get("external_url") == target
    print(json.dumps({"course_id": course_id, "module": MODULE_TITLE, "title": ITEM_TITLE,
                      "type": item.get("type"), "url": item.get("external_url"),
                      "status": "CURRENT" if current else "DRIFT"}, indent=2))
    return 0 if (not args.apply or current) else 1

if __name__ == "__main__":
    raise SystemExit(main())
