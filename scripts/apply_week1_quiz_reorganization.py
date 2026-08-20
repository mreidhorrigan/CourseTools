#!/usr/bin/env python3
"""Move Practice Quiz 1 to Week 1 and rename Week 2 in the guarded course."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from configure_iat210_course import QUIZ_WINDOWS
from sandbox_course_lifecycle import GuardedCanvas

WEEK2_PAGE_SLUG = "week-2-historiography-gender-slash-race-and-game-culture-2"
WEEK2_PAGE_TITLE = "Week 2: Historiography, representation, and game culture"
WEEK2_MODULE_NAME = "Week 2 - Historiography, representation, and game culture"

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--course", required=True, type=int)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args(); canvas = GuardedCanvas(args.server, args.course); canvas.health()
    if args.apply:
        if args.confirm != f"MOVE-QUIZ1-WEEK1-{args.course}":
            raise RuntimeError(f"Apply requires --confirm MOVE-QUIZ1-WEEK1-{args.course}")
        canvas.require_unpublished()
    modules = canvas.raw("GET", f"/courses/{args.course}/modules", params={"per_page": 100})
    week1 = next(item for item in modules if item["name"].startswith("Week 1 -"))
    week2 = next(item for item in modules if item["name"].startswith("Week 2 -"))
    quizzes = canvas.raw("GET", f"/courses/{args.course}/quizzes", params={"per_page": 100})
    quiz = next(item for item in quizzes if item["title"] == "Practice Quiz 1")
    all_items = []
    for module in modules:
        for item in canvas.raw("GET", f"/courses/{args.course}/modules/{module['id']}/items", params={"per_page": 100}):
            all_items.append((module, item))
    quiz_items = [(module, item) for module, item in all_items if item["title"] == "Practice Quiz 1"]
    current = (len(quiz_items) == 1 and quiz_items[0][0]["id"] == week1["id"]
               and quiz.get("unlock_at") == QUIZ_WINDOWS[0][0] and quiz.get("lock_at") == QUIZ_WINDOWS[0][1]
               and week2["name"] == WEEK2_MODULE_NAME)
    if args.apply and not current:
        canvas.raw("PUT", f"/courses/{args.course}/pages/{WEEK2_PAGE_SLUG}", {"wiki_page": {"title": WEEK2_PAGE_TITLE}})
        canvas.raw("PUT", f"/courses/{args.course}/modules/{week2['id']}", {"module": {"name": WEEK2_MODULE_NAME}})
        for module, item in quiz_items:
            canvas.raw("DELETE", f"/courses/{args.course}/modules/{module['id']}/items/{item['id']}")
        week1_items = canvas.raw("GET", f"/courses/{args.course}/modules/{week1['id']}/items", params={"per_page": 100})
        canvas.raw("POST", f"/courses/{args.course}/modules/{week1['id']}/items", {"module_item": {
            "type": "Quiz", "title": "Practice Quiz 1", "content_id": quiz["id"],
            "position": len(week1_items) + 1,
        }})
        opens, closes = QUIZ_WINDOWS[0]
        quiz = canvas.raw("PUT", f"/courses/{args.course}/quizzes/{quiz['id']}", {"quiz": {
            "unlock_at": opens, "due_at": closes, "lock_at": closes,
            "time_limit": 10, "allowed_attempts": 1, "published": True,
        }})
        current = True
    print(json.dumps({"course_id": args.course, "quiz": "Practice Quiz 1",
                      "window": QUIZ_WINDOWS[0], "week2_title": WEEK2_PAGE_TITLE,
                      "status": "CURRENT" if current else "DRIFT"}, indent=2))
    return 0 if (not args.apply or current) else 1

if __name__ == "__main__":
    raise SystemExit(main())
