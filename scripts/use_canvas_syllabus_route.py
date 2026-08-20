#!/usr/bin/env python3
"""Replace course wiki-page syllabus links with Canvas's canonical Syllabus route."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canvas_automation import jsonc

def main() -> int:
    config = jsonc.load_and_validate(ROOT / "course/course.config.jsonc")
    course_url = config["course_url"].rstrip("/")
    match = re.search(r"/courses/([1-9][0-9]*)$", course_url)
    if not match:
        raise RuntimeError("Configured course URL does not end with a numeric course ID")
    course_id = match.group(1)
    api_prefix = re.escape(f"{course_url.rsplit('/courses/', 1)[0]}/api/v1/courses/{course_id}/pages/iat-210-course-syllabus")
    page_url = f"{course_url}/pages/iat-210-course-syllabus"
    syllabus_url = f"{course_url}/assignments/syllabus"
    changed = []
    for path in sorted((ROOT / "course/content").rglob("*.html")):
        before = path.read_text(encoding="utf-8")
        after = re.sub(
            rf' data-api-endpoint="{api_prefix}(?:%23[^"]*)?" data-api-returntype="Page"',
            "",
            before,
        )
        after = after.replace(page_url, syllabus_url)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed.append(path.relative_to(ROOT).as_posix())
    print(json.dumps({"course_id": int(course_id), "canonical_syllabus_url": syllabus_url,
                      "changed_files": changed}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
