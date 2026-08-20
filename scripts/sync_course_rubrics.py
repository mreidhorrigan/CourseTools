#!/usr/bin/env python3
"""Plan or apply guarded synchronization of authoritative local rubric JSON."""
from __future__ import annotations

import argparse
import html
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
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    # A one-time terminology migration renamed the designed artifact from
    # "procedural ecology" to "procedural ecosystem." Treat the earlier live
    # title as the same rubric so the guarded synchronizer can rename it.
    return normalized.replace("procedural ecology", "procedural ecosystem")


def normalized_criteria(criteria: list[dict]) -> list[dict]:
    clean = lambda value: html.unescape(str(value or ""))
    result = []
    for criterion in criteria or []:
        result.append({
            "description": clean(criterion.get("description", "")),
            "long_description": clean(criterion.get("long_description", "")),
            "points": float(criterion.get("points", 0)),
            "ratings": [
                {"description": clean(rating.get("description", "")), "points": float(rating.get("points", 0))}
                for rating in criterion.get("ratings", [])
            ],
        })
    return result


def update_payload(source: dict, live: dict, assignment: dict | None = None) -> tuple[dict, str]:
    associations = live.get("associations") or []
    grading = next((item for item in associations if item.get("purpose") == "grading"), None)
    payload = {
        "rubric": {
            "title": source["title"],
            "free_form_criterion_comments": bool(source.get("free_form_criterion_comments", False)),
            "criteria": build_rubric_criteria_hash(source["criteria"]),
        },
    }
    if grading:
        payload["rubric_association_id"] = grading["id"]
        payload["rubric_association"] = {
            "association_id": grading["association_id"],
            "association_type": grading["association_type"],
            "use_for_grading": True,
            "purpose": "grading",
        }
        return payload, "rubric-association"
    settings = (assignment or {}).get("rubric_settings") or {}
    if settings.get("id") != live.get("id") or not (assignment or {}).get("use_rubric_for_grading"):
        raise RuntimeError(
            f"Rubric {live.get('title')!r} has no grading association and the exact assignment "
            "does not confirm that it uses this rubric for grading; refusing update"
        )
    # Some restored/imported rubrics omit associations from Canvas's rubric
    # detail response even though the assignment explicitly identifies and
    # grades with the rubric. Updating only rubric fields preserves that
    # association; post-update verification checks it again.
    return payload, "assignment-rubric-settings"


def bookmark_update_payload(source: dict, live: dict, course_id: int) -> tuple[dict, str]:
    bookmark = next((item for item in live.get("associations") or []
                     if item.get("purpose") == "bookmark"
                     and item.get("association_type") == "Course"
                     and item.get("association_id") == course_id), None)
    if not bookmark:
        raise RuntimeError(f"Rubric {live.get('title')!r} has no verified course bookmark association")
    return {
        "rubric_association_id": bookmark["id"],
        "rubric": {
            "title": source["title"],
            "free_form_criterion_comments": bool(source.get("free_form_criterion_comments", False)),
            "criteria": build_rubric_criteria_hash(source["criteria"]),
        },
        "rubric_association": {
            "association_id": course_id, "association_type": "Course",
            "use_for_grading": False, "purpose": "bookmark",
        },
    }, "course-bookmark-association"


def verify_rubric_source(source: dict, rubric: dict) -> None:
    if normalized_title(rubric.get("title", "")) != normalized_title(source["title"]):
        raise RuntimeError(f"rubric title verification failed for {source['title']!r}")
    if normalized_criteria(source["criteria"]) != normalized_criteria(rubric.get("data") or []):
        raise RuntimeError(f"rubric criteria verification failed for {source['title']!r}")


def verify_update(source: dict, rubric: dict, assignment: dict) -> None:
    verify_rubric_source(source, rubric)
    if (assignment.get("rubric_settings") or {}).get("id") != rubric.get("id"):
        raise RuntimeError(f"assignment association verification failed for {source['title']!r}")
    if not assignment.get("use_rubric_for_grading"):
        raise RuntimeError(f"assignment grading verification failed for {source['title']!r}")


def load_target(root: Path) -> tuple[int, dict]:
    config = jsonc.load_and_validate(root / "course/course.config.jsonc")
    match = re.search(r"/courses/([1-9][0-9]*)", config["course_url"])
    if not match:
        raise ValueError("course URL has no numeric course ID")
    course_id = int(match.group(1))
    manifest = json.loads((root / "course/rubric-manifest.json").read_text(encoding="utf-8"))
    if manifest["course_id"] != course_id:
        raise RuntimeError("rubric manifest does not match course configuration")
    return course_id, manifest


def audit_associations(root: Path, server: str) -> dict:
    course_id, manifest = load_target(root)
    canvas = GuardedCanvas(server, course_id)
    canvas.health()
    listed = canvas.raw("GET", f"/courses/{course_id}/rubrics", params={"per_page": 100})
    by_title = {normalized_title(item.get("title", "")): item for item in listed}
    assignments = canvas.raw("GET", f"/courses/{course_id}/assignments", params={"per_page": 100})
    assignments_by_title = {item.get("name"): item for item in assignments}
    records = []
    for entry in manifest["rubrics"]:
        source = json.loads((root / entry["source"]).read_text(encoding="utf-8"))
        listed_rubric = by_title.get(normalized_title(source["title"]))
        assignment = assignments_by_title.get(entry["assignment_title"])
        if not listed_rubric or not assignment:
            records.append({"title": source["title"], "assignment_title": entry["assignment_title"],
                            "rubric_found": bool(listed_rubric), "assignment_found": bool(assignment)})
            continue
        rubric = canvas.raw("GET", f"/courses/{course_id}/rubrics/{listed_rubric['id']}",
                            params={"include[]": ["associations", "assessments"]})
        settings = assignment.get("rubric_settings") or {}
        assigned_rubric = None
        if settings.get("id") == rubric.get("id"):
            assigned_rubric = rubric
        records.append({
            "title": source["title"], "rubric_id": rubric["id"],
            "live_title": rubric.get("title"), "assignment_title": entry["assignment_title"],
            "assignment_id": assignment["id"], "assignment_rubric_id": settings.get("id"),
            "use_rubric_for_grading": bool(assignment.get("use_rubric_for_grading")),
            "associations": [{key: item.get(key) for key in ("id", "association_id", "association_type", "purpose", "use_for_grading")}
                             for item in rubric.get("associations") or []],
            "assessment_count": len(rubric.get("assessments") or []),
            "assigned_rubric": None if not assigned_rubric else {
                "id": assigned_rubric.get("id"), "title": assigned_rubric.get("title"),
                "associations": [{key: item.get(key) for key in ("id", "association_id", "association_type", "purpose", "use_for_grading")}
                                 for item in assigned_rubric.get("associations") or []],
                "assessment_count": len(assigned_rubric.get("assessments") or []),
            },
            "assigned_rubric_state": "current" if assigned_rubric else "stale-or-different-id",
        })
    return {"course_id": course_id, "mode": "audit", "rubrics": records}


def audit_content(root: Path, server: str) -> dict:
    course_id, manifest = load_target(root)
    canvas = GuardedCanvas(server, course_id)
    canvas.health()
    listed = canvas.raw("GET", f"/courses/{course_id}/rubrics", params={"per_page": 100})
    by_title = {normalized_title(item.get("title", "")): item for item in listed}
    records = []
    for entry in manifest["rubrics"]:
        source = json.loads((root / entry["source"]).read_text(encoding="utf-8"))
        listed_rubric = by_title.get(normalized_title(source["title"]))
        if not listed_rubric:
            records.append({"title": source["title"], "status": "missing"})
            continue
        live = canvas.raw("GET", f"/courses/{course_id}/rubrics/{listed_rubric['id']}",
                          params={"include[]": ["associations", "assessments"]})
        expected, actual = normalized_criteria(source["criteria"]), normalized_criteria(live.get("data") or [])
        records.append({"title": source["title"], "rubric_id": live["id"],
                        "status": "current" if expected == actual else "different",
                        "expected": expected if expected != actual else None,
                        "actual": actual if expected != actual else None})
    return {"course_id": course_id, "mode": "diff", "rubrics": records}


def synchronize(root: Path, server: str, apply: bool, confirm: str | None) -> dict:
    course_id, manifest = load_target(root)
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
    assignments = canvas.raw("GET", f"/courses/{course_id}/assignments", params={"per_page": 100})
    assignments_by_title = {item.get("name"): item for item in assignments}
    changes = []
    for entry in manifest["rubrics"]:
        source = json.loads((root / entry["source"]).read_text(encoding="utf-8"))
        listed_rubric = by_title.get(normalized_title(source["title"]))
        if not listed_rubric:
            raise RuntimeError(f"live rubric not found for {source['title']!r}; synchronization never guesses or creates")
        assignment = assignments_by_title.get(entry["assignment_title"])
        if not assignment:
            raise RuntimeError(f"live assignment not found for {entry['assignment_title']!r}; synchronization never guesses")
        assigned_id = (assignment.get("rubric_settings") or {}).get("id")
        if not assigned_id:
            raise RuntimeError(f"assignment {entry['assignment_title']!r} has no rubric; refusing to guess")
        assigned_title = (assignment.get("rubric_settings") or {}).get("title", "")
        if not assigned_title:
            raise RuntimeError(f"assignment {entry['assignment_title']!r} has no rubric title; refusing repair")
        bookmark_rubric = canvas.raw("GET", f"/courses/{course_id}/rubrics/{listed_rubric['id']}",
                                     params={"include[]": ["associations", "assessments"]})
        if bookmark_rubric.get("assessments"):
            raise RuntimeError(f"rubric {source['title']!r} already has assessments; refusing structural update")
        needs_association_repair = assigned_id != bookmark_rubric["id"]
        if needs_association_repair:
            association_change = {
                "rubric_id": bookmark_rubric["id"], "rubric_role": "grading-association",
                "title": source["title"], "source": entry["source"],
                "assignment_title": entry["assignment_title"], "assignment_id": assignment["id"],
                "stale_rubric_id": assigned_id, "stale_rubric_title": assigned_title,
                "association_evidence": "authoritative manifest assignment mapping and exact restored rubric title",
                "status": "planned",
            }
            changes.append(association_change)
            if apply:
                canvas.raw("POST", f"/courses/{course_id}/rubric_associations", {
                    "rubric_association": {
                        "rubric_id": bookmark_rubric["id"], "association_type": "Assignment",
                        "association_id": assignment["id"], "purpose": "grading", "use_for_grading": True,
                    }
                })
                assignment = canvas.raw("GET", f"/courses/{course_id}/assignments/{assignment['id']}")
                if (assignment.get("rubric_settings") or {}).get("id") != bookmark_rubric["id"]:
                    raise RuntimeError(f"rubric association repair failed for {entry['assignment_title']!r}")
                if not assignment.get("use_rubric_for_grading"):
                    raise RuntimeError(f"grading flag repair failed for {entry['assignment_title']!r}")
                association_change["status"] = "applied"
                bookmark_rubric = canvas.raw("GET", f"/courses/{course_id}/rubrics/{bookmark_rubric['id']}",
                                             params={"include[]": ["associations", "assessments"]})
        different = source["title"] != re.sub(r"\s*\(Restored[^)]*\)\s*$", "", bookmark_rubric.get("title", ""), flags=re.I)
        different = different or normalized_criteria(source["criteria"]) != normalized_criteria(bookmark_rubric.get("data") or [])
        if not different:
            if apply and needs_association_repair:
                verify_update(source, bookmark_rubric, assignment)
            continue
        if apply:
            payload, association_evidence = update_payload(source, bookmark_rubric, assignment)
        elif needs_association_repair:
            payload, association_evidence = {}, "after planned assignment reassociation"
        else:
            payload, association_evidence = update_payload(source, bookmark_rubric, assignment)
        change = {"rubric_id": bookmark_rubric["id"], "rubric_role": "grading-and-bookmark",
                  "title": source["title"], "source": entry["source"],
                  "assignment_title": entry["assignment_title"],
                  "association_evidence": association_evidence, "status": "planned"}
        changes.append(change)
        if apply:
            canvas.raw("PUT", f"/courses/{course_id}/rubrics/{bookmark_rubric['id']}", payload)
            verified_rubric = canvas.raw("GET", f"/courses/{course_id}/rubrics/{bookmark_rubric['id']}",
                                         params={"include[]": ["associations", "assessments"]})
            verified_assignment = canvas.raw("GET", f"/courses/{course_id}/assignments/{assignment['id']}")
            verify_update(source, verified_rubric, verified_assignment)
            # A grading-association update can cause Canvas to omit its
            # redundant course-bookmark association from the detail response.
            # The assignment ID, rubric ID, grading flag, title, and criteria
            # have all been verified above; do not fail after a successful and
            # fully verified update merely because that bookmark is absent.
            change["status"] = "applied"
    return {"course_id": course_id, "mode": "apply" if apply else "plan", "changed_rubrics": changes,
            "status": "CURRENT" if not changes else ("APPLIED" if apply else "DRIFT")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit")
    sub.add_parser("diff")
    sub.add_parser("plan")
    apply_parser = sub.add_parser("apply"); apply_parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.command == "audit":
        result = audit_associations(args.root.resolve(), args.server)
    elif args.command == "diff":
        result = audit_content(args.root.resolve(), args.server)
    else:
        result = synchronize(args.root.resolve(), args.server, args.command == "apply", getattr(args, "confirm", None))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
