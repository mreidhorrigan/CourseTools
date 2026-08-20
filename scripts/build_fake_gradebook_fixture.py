#!/usr/bin/env python3
"""Build wholly synthetic Canvas-gradebook fixtures for safe public testing."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


HEADERS = [
    "Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Notes",
    "Participation (1001)", "Project (1002)", "Final Examination (1003)",
    "Coursework Current Score", "Coursework Unposted Current Score",
    "Coursework Final Score", "Coursework Unposted Final Score",
    "Final Examination Current Score", "Final Examination Unposted Current Score",
    "Final Examination Final Score", "Final Examination Unposted Final Score",
    "Current Score", "Unposted Current Score", "Final Score", "Unposted Final Score",
    "Current Grade", "Unposted Current Grade", "Final Grade", "Unposted Final Grade",
]

SYNTHETIC_STUDENTS = [
    # Names, identifiers, and scores are invented and do not derive from a real gradebook.
    ("Example, Ada", "fake-canvas-001", "900000001", "example_a", "97.4"),
    ("Example, Benoit", "fake-canvas-002", "900000002", "example_b", "94.5"),
    ("Example, Chandra", "fake-canvas-003", "900000003", "example_c", "89.5"),
    ("Example, Diego", "fake-canvas-004", "900000004", "example_d", "84.5"),
    ("Example, Esme", "fake-canvas-005", "900000005", "example_e", "79.49"),
    ("Example, Farah", "fake-canvas-006", "900000006", "example_f", "74.5"),
    ("Example, Gabriel", "fake-canvas-007", "900000007", "example_g", "69.5"),
    ("Example, Hana", "fake-canvas-008", "900000008", "example_h", "64.5"),
    ("Example, Idris", "fake-canvas-009", "900000009", "example_i", "59.5"),
    ("Example, Jun", "fake-canvas-010", "900000010", "example_j", "54.5"),
    ("Example, Kira", "fake-canvas-011", "900000011", "example_k", "49.5"),
    ("Example, Luis", "fake-canvas-012", "900000012", "example_l", "32.2"),
]


def row_for_student(student: tuple[str, str, str, str, str], index: int) -> dict[str, str]:
    name, canvas_id, sis_id, login, final_score = student
    section = "DEMO101 D100 and DEMO101 D100 Synthetic Section" if index in {3, 8} else "DEMO101 D100"
    score = float(final_score)
    coursework = round(min(100.0, max(0.0, score + (2 if index % 2 else -2))), 2)
    exam = round(min(100.0, max(0.0, score + (-4 if index % 2 else 4))), 2)
    return {
        "Student": name, "ID": canvas_id, "SIS User ID": sis_id,
        "SIS Login ID": login, "Section": section, "Notes": "synthetic fixture",
        "Participation (1001)": str(round(coursework / 10, 2)),
        "Project (1002)": str(round(coursework * 0.6, 2)),
        "Final Examination (1003)": str(round(exam * 0.3, 2)),
        "Coursework Current Score": str(coursework), "Coursework Unposted Current Score": str(coursework),
        "Coursework Final Score": str(coursework), "Coursework Unposted Final Score": str(coursework),
        "Final Examination Current Score": str(exam), "Final Examination Unposted Current Score": str(exam),
        "Final Examination Final Score": str(exam), "Final Examination Unposted Final Score": str(exam),
        "Current Score": final_score, "Unposted Current Score": final_score,
        "Final Score": final_score, "Unposted Final Score": final_score,
        "Current Grade": "(synthetic; recalculate)", "Unposted Current Grade": "(synthetic; recalculate)",
        "Final Grade": "(synthetic; recalculate)", "Unposted Final Grade": "(synthetic; recalculate)",
    }


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, lineterminator="\n")
        writer.writeheader()
        writer.writerow({})
        points = {"Student": "    Points Possible", "Participation (1001)": "10",
                  "Project (1002)": "60", "Final Examination (1003)": "30"}
        for column in HEADERS:
            if column.endswith("Score"):
                points[column] = "(read only)"
            elif column.endswith("Grade"):
                points[column] = "(read only)"
        writer.writerow(points)
        for index, student in enumerate(SYNTHETIC_STUDENTS, 1):
            writer.writerow(row_for_student(student, index))
        writer.writerow({"Student": "Student, Test", "ID": "fake-canvas-test",
                         "Section": "DEMO101 D100", "Notes": "synthetic Canvas test student"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "tests/fixtures/gradebooks/canvas-gradebook-synthetic.csv")
    args = parser.parse_args()
    build(args.output.resolve())
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
