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
    payload, evidence = module.update_payload(source, live)
    assert payload["rubric_association_id"] == 7
    assert payload["rubric_association"]["association_id"] == 12
    assert payload["rubric"]["criteria"]["0"]["long_description"] == "Observable evidence"
    assert evidence == "rubric-association"


def test_update_payload_uses_exact_assignment_evidence_when_import_omits_association():
    source = {"title": "Plan", "criteria": [{"description": "Evidence", "points": 1, "ratings": []}]}
    live = {"id": 44, "title": "Plan", "associations": []}
    assignment = {"name": "Plan assignment", "rubric_settings": {"id": 44}, "use_rubric_for_grading": True}
    payload, evidence = module.update_payload(source, live, assignment)
    assert evidence == "assignment-rubric-settings"
    assert "rubric_association" not in payload
    assert payload["rubric"]["title"] == "Plan"


def test_update_payload_refuses_unconfirmed_missing_association():
    source = {"title": "Plan", "criteria": []}
    live = {"id": 44, "title": "Plan", "associations": []}
    try:
        module.update_payload(source, live, {"rubric_settings": {"id": 45}, "use_rubric_for_grading": True})
    except RuntimeError as error:
        assert "does not confirm" in str(error)
    else:
        raise AssertionError("unconfirmed association was accepted")


def test_bookmark_payload_preserves_course_bookmark_purpose():
    source = {"title": "Plan", "criteria": []}
    live = {"id": 44, "title": "Plan", "associations": [{"id": 9, "association_id": 77, "association_type": "Course", "purpose": "bookmark"}]}
    payload, evidence = module.bookmark_update_payload(source, live, 77)
    assert evidence == "course-bookmark-association"
    assert payload["rubric_association_id"] == 9
    assert payload["rubric_association"]["purpose"] == "bookmark"
    assert payload["rubric_association"]["use_for_grading"] is False


def test_normalized_criteria_treats_canvas_html_entities_as_text():
    source = [{"description": "Team's work", "long_description": "A & B", "points": 1, "ratings": []}]
    canvas = [{"description": "Team&#39;s work", "long_description": "A &amp; B", "points": 1, "ratings": []}]
    assert module.normalized_criteria(source) == module.normalized_criteria(canvas)
