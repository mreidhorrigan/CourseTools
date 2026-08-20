"""Pure transformations for private Canvas roster and gradebook exports."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import random
from typing import Any


def canonical_students(enrollments: list[dict[str, Any]], sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize active student enrollments without discarding SIS identifiers."""
    section_names = {item.get("id"): item.get("name", "") for item in sections}
    by_user: dict[int, dict[str, Any]] = {}
    for enrollment in enrollments:
        if enrollment.get("type") not in {None, "StudentEnrollment"}:
            continue
        user = enrollment.get("user") or {}
        user_id = enrollment.get("user_id") or user.get("id")
        if user_id is None:
            continue
        current = by_user.setdefault(user_id, {
            "canvas_user_id": user_id,
            "sis_user_id": user.get("sis_user_id") or enrollment.get("sis_user_id") or "",
            "display_name": user.get("short_name") or user.get("name") or "",
            "full_name": user.get("name") or "",
            "sortable_name": user.get("sortable_name") or user.get("name") or "",
            "login_id": user.get("login_id") or "",
            "avatar_url": user.get("avatar_url") or "",
            "sections": [],
            "current_score": (enrollment.get("grades") or {}).get("current_score"),
            "final_score": (enrollment.get("grades") or {}).get("final_score"),
            "current_grade": (enrollment.get("grades") or {}).get("current_grade"),
            "final_grade": (enrollment.get("grades") or {}).get("final_grade"),
        })
        section_name = section_names.get(enrollment.get("course_section_id"), "")
        if section_name and section_name not in current["sections"]:
            current["sections"].append(section_name)
    for student in by_user.values():
        student["sections"].sort(key=str.casefold)
    return sorted(by_user.values(), key=lambda item: (item["sortable_name"].casefold(), item["canvas_user_id"]))


def assignment_gradebook(students: list[dict[str, Any]], assignments: list[dict[str, Any]],
                         submissions: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    assignments = sorted(assignments, key=lambda item: (item.get("position", 10**9), item.get("id", 0)))
    scores: dict[tuple[int, int], Any] = {}
    for group in submissions:
        user_id = group.get("user_id")
        for submission in group.get("submissions", []):
            scores[(user_id, submission.get("assignment_id"))] = submission.get("score")
    headers = ["Student", "SIS User ID", "Canvas User ID", "Section"]
    headers += [f"{item.get('name', 'Assignment')} ({item.get('points_possible', '')})" for item in assignments]
    headers += ["Current Score", "Final Score", "Current Grade", "Final Grade"]
    rows = []
    for student in students:
        row = [student["sortable_name"], student["sis_user_id"], student["canvas_user_id"],
               "; ".join(student["sections"])]
        row += [scores.get((student["canvas_user_id"], assignment.get("id")), "") for assignment in assignments]
        row += [student["current_score"], student["final_score"], student["current_grade"], student["final_grade"]]
        rows.append(row)
    return headers, rows


def seat_labels(count: int, columns: int) -> list[str]:
    if columns < 1 or columns > 26:
        raise ValueError("seating.columns must be between 1 and 26")
    return [f"{chr(65 + index % columns)}{index // columns + 1}" for index in range(count)]


def seating_rows(students: list[dict[str, Any]], config: dict[str, Any]) -> list[list[Any]]:
    ordered = list(students)
    mode = config.get("order", "alphabetical")
    if mode == "random":
        random.Random(int(config.get("random_seed", 210))).shuffle(ordered)
    elif mode != "alphabetical":
        raise ValueError("seating.order must be alphabetical or random")
    labels = seat_labels(len(ordered), int(config.get("columns", 6)))
    return [[label, item["display_name"], item["sis_user_id"], "; ".join(item["sections"])]
            for label, item in zip(labels, ordered)]


def write_table(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)


def write_exports(output: Path, course: dict[str, Any], students: list[dict[str, Any]],
                  assignments: list[dict[str, Any]], submissions: list[dict[str, Any]],
                  config: dict[str, Any]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    canonical = {"schema": "canvas-automation/private-roster/v1",
                 "course": {key: course.get(key) for key in ("id", "name", "course_code", "workflow_state")},
                 "students": students}
    (output / "canonical-roster.json").write_text(json.dumps(canonical, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    roster_headers = ["Sortable Name", "Display Name", "Full Name", "SIS User ID", "Canvas User ID",
                      "Login ID", "Section", "Avatar URL", "Current Score", "Final Score", "Current Grade", "Final Grade"]
    roster_rows = [[item["sortable_name"], item["display_name"], item["full_name"], item["sis_user_id"],
                    item["canvas_user_id"], item["login_id"], "; ".join(item["sections"]), item["avatar_url"],
                    item["current_score"], item["final_score"], item["current_grade"], item["final_grade"]]
                   for item in students]
    write_table(output / "canonical-roster.csv", roster_headers, roster_rows)
    grade_headers, grade_rows = assignment_gradebook(students, assignments, submissions)
    write_table(output / "gradebook.csv", grade_headers, grade_rows)
    write_table(output / "nameplates.csv", ["Name", "Section"],
                [[item["display_name"], "; ".join(item["sections"])] for item in students])
    # Exact adapter expected by DOC_TOOLS Seat Planner's Canvas detector.
    write_table(output / "seatplanner-source.csv",
                ["Student", "SIS Login ID", "Notes", "Unposted Current Score"],
                [[item["sortable_name"], item["login_id"], "", item["current_score"]]
                 for item in students])
    write_table(output / "seating-plan.csv", ["Seat", "Display Name", "SIS User ID", "Section"],
                seating_rows(students, config.get("seating", {})))
    summary = {
        "schema": "canvas-automation/private-roster-export/v1", "course_id": course.get("id"),
        "student_count": len(students), "assignment_count": len(assignments),
        "files": ["canonical-roster.json", "canonical-roster.csv", "gradebook.csv", "nameplates.csv",
                  "seatplanner-source.csv", "seating-plan.csv"],
        "contains_student_data": True,
        "handling": "Private educational record: excluded from Git and public distributions.",
    }
    (output / "export-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for path in output.iterdir():
        if path.is_file():
            os.chmod(path, 0o600)
    return summary
