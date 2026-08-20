#!/usr/bin/env python3
"""Apply the reviewed 24-hour quiz windows and final-exam duration copy."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    ROOT / "course/content/syllabus.html",
    ROOT / "course/content/assignments/207282-in-person-final-examination.html",
    ROOT / "examples/iat210/syllabus-links.config.jsonc",
    ROOT / "examples/iat210/prepare_course_starter.py",
] + sorted((ROOT / "course/content/quizzes").glob("*-practice-quiz-*.html"))
REPLACEMENTS = {
    "Sep 22, 09:00–23:59": "Sep 22, 00:00–24:00",
    "Oct 6, 09:00–23:59": "Oct 6, 00:00–24:00",
    "Oct 20, 09:00–23:59": "Oct 20, 00:00–24:00",
    "Nov 3, 09:00–23:59": "Nov 3, 00:00–24:00",
    "Nov 10, 09:00–23:59": "Nov 10, 00:00–24:00",
    "Nov 24, 09:00–23:59": "Nov 24, 00:00–24:00",
    "Dec 7, 09:00–23:59": "Dec 7, 00:00–24:00",
    "Quiz availability uses Pacific time: Quiz 1 is available Sep 22, 00:00–24:00": "Each quiz has one 24-hour Pacific-time window: Quiz 1 Sep 22, 00:00–24:00",
    "Quiz availability uses Pacific time: Each quiz has one 24-hour Pacific-time window:": "Each quiz has one 24-hour Pacific-time window:",
    "60 multiple-choice questions; 90 minutes (1.5 minutes per question); 60 multiple-choice questions; 90 minutes (1.5 minutes per question);": "60 multiple-choice questions; 90 minutes (1.5 minutes per question);",
    "It contains 60 multiple-choice questions and lasts 90 minutes, allowing an average of 1.5 minutes per question. It contains 60 multiple-choice questions and lasts 90 minutes, allowing an average of 1.5 minutes per question.": "It contains 60 multiple-choice questions and lasts 90 minutes, allowing an average of 1.5 minutes per question.",
    "The final approved pool may randomly draw 10 questions so students receive different subsets.": "Canvas draws a Bloom-balanced set of 10 questions from 20 candidates so students receive different subsets.",
    "<p><strong>Instructor status:</strong> keep unpublished until the approved Testmaker pool contains at least 10 reading-specific questions.</p>": "",
}


def main() -> int:
    changed = 0
    for path in FILES:
        before = path.read_text(encoding="utf-8")
        after = before
        for old, new in REPLACEMENTS.items():
            after = after.replace(old, new)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed += 1
    print(f"Assessment-window copy current; changed {changed} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
