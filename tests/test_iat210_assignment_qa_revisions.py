from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent


def rubric(name):
    return json.loads((ROOT / "course/content/rubrics" / name).read_text())


def test_actual_play_rubric_totals_and_descriptors_are_complete():
    for name, total in (("actual-play-plan.json", 6), ("actual-play-final.json", 12)):
        data = rubric(name)
        assert sum(item["points"] for item in data["criteria"]) == total == data["points_possible"]
        assert all(item.get("long_description") for item in data["criteria"])
        assert all(item["ratings"][0]["points"] == item["points"] for item in data["criteria"])
        assert all(item["ratings"][-1]["points"] == 0 for item in data["criteria"])


def test_actual_play_assignment_pages_contain_gradeable_requirements():
    assignments = ROOT / "course/content/assignments"
    plan_path = next(assignments.glob("*-actual-play-project-session-plan-and-rulebook.html"))
    final_path = next(assignments.glob("*-actual-play-project-final-submission.html"))
    plan = BeautifulSoup(plan_path.read_text(), "html.parser").get_text(" ", strip=True)
    final = BeautifulSoup(final_path.read_text(), "html.parser").get_text(" ", strip=True)
    for phrase in ("one PDF", "consequential", "primary and backup recording", "testable question", "AI appendix"):
        assert phrase in plan
    for phrase in ("exactly two files", "MP4", "ODT", "10–15 minute", "rubric evidence map", "Consent and permissions record", "before/after", "Individual contribution and analysis", "AI appendix"):
        assert phrase in final


def test_rubric_manifest_maps_all_nine_sources():
    manifest = json.loads((ROOT / "course/rubric-manifest.json").read_text())
    assert len(manifest["rubrics"]) == 9
    assert all((ROOT / item["source"]).is_file() for item in manifest["rubrics"])
