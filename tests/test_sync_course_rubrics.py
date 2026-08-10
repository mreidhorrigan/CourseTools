from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("sync_course_rubrics", ROOT / "scripts/sync_course_rubrics.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_restored_suffix_does_not_break_title_matching():
    assert module.normalized_title("Actual-Play Plan (Restored v1.9)") == module.normalized_title("Actual-Play Plan")


def test_update_payload_preserves_grading_association_and_long_descriptions():
    source = {"title": "Plan", "criteria": [{"description": "Evidence", "long_description": "Observable evidence", "points": 1, "ratings": [{"description": "Yes", "points": 1}]}]}
    live = {"title": "Plan", "associations": [{"id": 7, "association_id": 12, "association_type": "Assignment", "purpose": "grading"}]}
    payload = module.update_payload(source, live)
    assert payload["rubric_association_id"] == 7
    assert payload["rubric_association"]["association_id"] == 12
    assert payload["rubric"]["criteria"]["0"]["long_description"] == "Observable evidence"
