#!/usr/bin/env python3
"""Pull a guarded Canvas course roster/gradebook and build private derivatives."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from canvas_automation import jsonc
from canvas_automation.roster_pipeline import canonical_students, write_exports
from canvas_automation.util import fresh_out_dir


class PrivateCanvasReader:
    """Read-only local-server client that never prints Canvas response bodies."""

    def __init__(self, server: str, course_id: int):
        self.server = server.rstrip("/")
        self.course_id = course_id

    def health(self) -> dict:
        response = requests.get(f"{self.server}/health", timeout=10)
        if response.status_code >= 400:
            raise RuntimeError(f"Local server health check failed with HTTP {response.status_code}")
        value = response.json()
        if value.get("allowed_course_id") != self.course_id:
            raise RuntimeError(
                f"Local server is guarded to course {value.get('allowed_course_id')}, not {self.course_id}"
            )
        return value

    def raw(self, method: str, path: str, params=None):
        if method != "GET":
            raise ValueError("PrivateCanvasReader permits GET requests only")
        response = requests.post(
            f"{self.server}/api/raw",
            json={"method": "GET", "path": path, "params": params or {}}, timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Canvas read failed with HTTP {response.status_code} at {path}")
        return response.json() if response.content else None


def configured_course_id(root: Path) -> int:
    config = jsonc.load_and_validate(root / "course/course.config.jsonc")
    match = re.search(r"/courses/([1-9][0-9]*)", config["course_url"])
    if not match:
        raise ValueError("course/course.config.jsonc needs a numeric Canvas course URL")
    return int(match.group(1))


def fetch(canvas: PrivateCanvasReader, course_id: int, config: dict) -> tuple[dict, list, list, list]:
    course = canvas.raw("GET", f"/courses/{course_id}")
    sections = canvas.raw("GET", f"/courses/{course_id}/sections", params={"per_page": 100})
    enrollment_params = {"type[]": "StudentEnrollment", "state[]": "active", "per_page": 100}
    if config.get("include_avatar_urls", False):
        enrollment_params["include[]"] = "avatar_url"
    enrollments = canvas.raw("GET", f"/courses/{course_id}/enrollments", params=enrollment_params)
    students = canonical_students(enrollments, sections)
    assignments = []
    submissions = []
    if config.get("include_assignment_scores", True):
        assignments = canvas.raw("GET", f"/courses/{course_id}/assignments", params={"per_page": 100})
        if config.get("only_published_assignments", True):
            assignments = [item for item in assignments if item.get("published")]
        ids = [item["id"] for item in assignments]
        if ids and students:
            submissions = canvas.raw("GET", f"/courses/{course_id}/students/submissions", params={
                "student_ids[]": "all", "assignment_ids[]": ids, "grouped": "true", "per_page": 100,
            })
    return course, students, assignments, submissions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--course", type=int, help="Must match the central configured course and server guard")
    parser.add_argument("--config", type=Path, default=ROOT / "commands/pull-canvas-roster.config.jsonc")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    expected = configured_course_id(root)
    course_id = args.course or expected
    if course_id != expected:
        print(f"Error: requested course {course_id} differs from centrally configured course {expected}", file=sys.stderr)
        return 1
    config = jsonc.load_and_validate(args.config.resolve())
    canvas = PrivateCanvasReader(args.server, course_id)
    try:
        canvas.health()
        course, students, assignments, submissions = fetch(canvas, course_id, config)
        output = args.output.resolve() if args.output else fresh_out_dir(root / "out/private-roster", f"course-{course_id}")
        summary = write_exports(output, course, students, assignments, submissions, config)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({**summary, "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
