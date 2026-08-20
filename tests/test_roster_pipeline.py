import csv
import hashlib
import importlib.util
import json
import stat
from pathlib import Path

from canvas_automation.roster_pipeline import (
    assignment_gradebook, canonical_students, seat_labels, seating_rows, write_exports,
)


def fixtures():
    sections = [{"id": 10, "name": "DEMO101 D100"}, {"id": 11, "name": "DEMO101 D200"}]
    enrollments = [
        {"type": "StudentEnrollment", "user_id": 2, "course_section_id": 10,
         "user": {"id": 2, "name": "Ada Example", "short_name": "Ada", "sortable_name": "Example, Ada",
                  "sis_user_id": "900000002", "login_id": "ada", "avatar_url": "https://example.invalid/a.png"},
         "grades": {"current_score": 94.5, "final_score": 90, "current_grade": "A+", "final_grade": "A"}},
        {"type": "StudentEnrollment", "user_id": 1, "course_section_id": 11,
         "user": {"id": 1, "name": "Benoit Example", "short_name": "Benoit", "sortable_name": "Example, Benoit",
                  "sis_user_id": "900000001"}, "grades": {}},
    ]
    return sections, enrollments


def test_canonical_roster_is_sorted_and_preserves_preferred_display_name():
    sections, enrollments = fixtures()
    students = canonical_students(enrollments, sections)
    assert [item["display_name"] for item in students] == ["Ada", "Benoit"]
    assert students[0]["sections"] == ["DEMO101 D100"]
    assert students[0]["sis_user_id"] == "900000002"


def test_gradebook_and_private_derivatives_have_stable_shapes(tmp_path):
    sections, enrollments = fixtures()
    students = canonical_students(enrollments, sections)
    assignments = [{"id": 20, "name": "Project", "points_possible": 10, "position": 1}]
    submissions = [{"user_id": 2, "submissions": [{"assignment_id": 20, "score": 9}]}]
    headers, rows = assignment_gradebook(students, assignments, submissions)
    assert "Project (10)" in headers
    assert rows[0][headers.index("Project (10)")] == 9
    summary = write_exports(tmp_path, {"id": 17063, "name": "Demo"}, students, assignments, submissions,
                            {"seating": {"columns": 2, "order": "alphabetical"}})
    assert summary["contains_student_data"] is True
    assert set(summary["files"]) == {p.name for p in tmp_path.iterdir() if p.name != "export-summary.json"}
    with (tmp_path / "nameplates.csv").open(newline="", encoding="utf-8") as handle:
        nameplates = list(csv.reader(handle))
    assert nameplates[0] == ["Name", "Section"]
    assert nameplates[1] == ["Ada", "DEMO101 D100"]
    with (tmp_path / "seatplanner-source.csv").open(newline="", encoding="utf-8") as handle:
        seatplanner = list(csv.reader(handle))
    assert seatplanner[0] == ["Student", "SIS Login ID", "Notes", "Unposted Current Score"]
    assert seatplanner[1][0] == "Example, Ada"
    assert json.loads((tmp_path / "canonical-roster.json").read_text())["students"][0]["display_name"] == "Ada"
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in tmp_path.iterdir())


def test_seating_can_be_reproducibly_randomized():
    sections, enrollments = fixtures()
    students = canonical_students(enrollments, sections)
    assert seat_labels(7, 3) == ["A1", "B1", "C1", "A2", "B2", "C2", "A3"]
    first = seating_rows(students, {"columns": 2, "order": "random", "random_seed": 4})
    assert first == seating_rows(students, {"columns": 2, "order": "random", "random_seed": 4})


def test_private_canvas_reader_is_get_only():
    script = Path(__file__).resolve().parents[1] / "scripts/pull_canvas_roster.py"
    spec = importlib.util.spec_from_file_location("pull_canvas_roster", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    reader = module.PrivateCanvasReader("http://127.0.0.1:5055", 17063)
    try:
        reader.raw("POST", "/courses/17063/enrollments")
    except ValueError as error:
        assert "GET requests only" in str(error)
    else:
        raise AssertionError("Private reader accepted a mutation")


def test_original_nameplate_renderer_is_staged_without_format_changes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = root / "vendor/doctools-seatplanner/Nameplates.html"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "55ea90775691d1b70318fd3bc6b691c2c1e3b2e1c780d52e11b0dbb005587e51"
    )
    run_dir = tmp_path / "private-run"
    run_dir.mkdir()
    (run_dir / "nameplates.csv").write_text("Name,Section\nAda,DEMO101 D100\n", encoding="utf-8")
    (run_dir / "seatplanner-source.csv").write_text(
        "Student,SIS Login ID,Notes,Unposted Current Score\nExample Ada,ada,,95\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location(
        "build_roster_documents", root / "scripts/build_roster_documents.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    summary = module.build(
        run_dir,
        {"seed": 210, "nameplates": {"enabled": True}, "seating_chart": {"enabled": False}},
        root,
    )
    staged = run_dir / "documents/nameplates-workspace/Nameplates.html"
    assert staged.read_bytes() == source.read_bytes()
    assert summary["nameplates"] == "nameplates-workspace/Nameplates.html"
    assert stat.S_IMODE(staged.stat().st_mode) == 0o600
