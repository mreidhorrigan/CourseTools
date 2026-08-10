#!/usr/bin/env python3
"""Plan or apply guarded synchronization of authoritative local rubric JSON."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from canvas_automation import jsonc
from canvas_automation.canvas_client import build_rubric_criteria_hash
from sandbox_course_lifecycle import GuardedCanvas


def normalized_title(value: str) -> str:
    value = re.sub(r"\s*\(Restored[^)]*\)\s*$", "", value or "", flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def normalized_criteria(criteria: list[dict]) -> list[dict]:
    result = []
    for criterion in criteria or []:
        result.append({
            "description": criterion.get("description", ""),
            "long_description": criterion.get("long_description", "") or "",
            "points": float(criterion.get("points", 0)),
            "ratings": [
                {"description": rating.get("description", ""), "points": float(rating.get("points", 0))}
                for rating in criterion.get("ratings", [])
            ],
        })
    return result


def update_payload(source: dict, live: dict) -> dict:
    associations = live.get("associations") or []
    grading = next((item for item in associations if item.get("purpose") == "grading"), None)
    if not grading:
        raise RuntimeError(f"Rubric {live.get('title')!r} has no grading association; refusing update")
    return {
        "rubric_association_id": grading["id"],
        "rubric": {
            "title": source["title"],
            "free_form_criterion_comments": bool(source.get("free_form_criterion_comments", False)),
            "criteria": build_rubric_criteria_hash(source["criteria"]),
        },
        "rubric_association": {
            "association_id": grading["association_id"],
            "association_type": grading["association_type"],
            "use_for_grading": True,
            "purpose": "grading",
        },
    }


def synchronize(root: Path, server: str, apply: bool, confirm: str | None) -> dict:
    config = jsonc.load_and_validate(root / "course/course.config.jsonc")
    match = re.search(r"/courses/([1-9][0-9]*)", config["course_url"])
    if not match:
        raise ValueError("course URL has no numeric course ID")
    course_id = int(match.group(1))
    manifest = json.loads((root / "course/rubric-manifest.json").read_text(encoding="utf-8"))
    if manifest["course_id"] != course_id:
        raise RuntimeError("rubric manifest does not match course configuration")
    canvas = GuardedCanvas(server, course_id)
    canvas.health()
    course = canvas.raw("GET", f"/courses/{course_id}")
    if apply:
        if confirm != f"SYNC-RUBRICS-{course_id}":
            raise ValueError(f"apply requires --confirm SYNC-RUBRICS-{course_id}")
        if course.get("workflow_state") != "unpublished":
            raise RuntimeError("refusing rubric synchronization because the target course is published")
    listed = canvas.raw("GET", f"/courses/{course_id}/rubrics", params={"per_page": 100})
    by_title = {normalized_title(item.get("title", "")): item for item in listed}
    changes = []
    for entry in manifest["rubrics"]:
        source = json.loads((root / entry["source"]).read_text(encoding="utf-8"))
        listed_rubric = by_title.get(normalized_title(source["title"]))
        if not listed_rubric:
            raise RuntimeError(f"live rubric not found for {source['title']!r}; synchronization never guesses or creates")
        live = canvas.raw("GET", f"/courses/{course_id}/rubrics/{listed_rubric['id']}",
                          params={"include[]": ["associations", "assessments"]})
        different = source["title"] != re.sub(r"\s*\(Restored[^)]*\)\s*$", "", live.get("title", ""), flags=re.I)
        different = different or normalized_criteria(source["criteria"]) != normalized_criteria(live.get("data") or [])
        if not different:
            continue
        change = {"rubric_id": live["id"], "title": source["title"], "source": entry["source"],
                  "assignment_title": entry["assignment_title"], "status": "planned"}
        changes.append(change)
        if apply:
            if live.get("assessments"):
                raise RuntimeError(f"rubric {source['title']!r} already has assessments; refusing structural update")
            canvas.raw("PUT", f"/courses/{course_id}/rubrics/{live['id']}", update_payload(source, live))
            change["status"] = "applied"
    return {"course_id": course_id, "mode": "apply" if apply else "plan", "changed_rubrics": changes,
            "status": "CURRENT" if not changes else ("APPLIED" if apply else "DRIFT")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    apply_parser = sub.add_parser("apply"); apply_parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    result = synchronize(args.root.resolve(), args.server, args.command == "apply", getattr(args, "confirm", None))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
