"""Tests for the stored, guarded sandbox lifecycle driver."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "sandbox_course_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("sandbox_course_lifecycle", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_reset_requires_exact_course_specific_confirmation():
    canvas = MODULE.GuardedCanvas("http://127.0.0.1:5055", 12345)
    with pytest.raises(ValueError, match="RESET-COURSE-12345"):
        canvas.reset("RESET-COURSE-OTHER")


def test_lifecycle_script_parser_requires_course_and_subcommand():
    parser = MODULE.build_parser()
    args = parser.parse_args(["--course", "12345", "inventory"])
    assert args.course == 12345
    assert args.command == "inventory"


def test_cleanup_requires_exact_course_specific_confirmation():
    canvas = MODULE.GuardedCanvas("http://127.0.0.1:5055", 12345)
    with pytest.raises(ValueError, match="DELETE-CONTENT-12345"):
        canvas.cleanup({"course_id": 12345}, "DELETE-CONTENT-OTHER")


def test_cleanup_rejects_plan_for_another_course():
    canvas = MODULE.GuardedCanvas("http://127.0.0.1:5055", 12345)
    with pytest.raises(ValueError, match="does not match"):
        canvas.cleanup({"course_id": 67890}, "DELETE-CONTENT-12345")


def test_plan_identity_normalizes_identifiers_for_resume_checks():
    identity = MODULE.GuardedCanvas._plan_identity({
        "objects": {"pages": [{"identifier": "week-01"}], "modules": [{"identifier": 3}]}
    })
    assert identity == {"pages": ["week-01"], "modules": ["3"]}


def test_import_rejects_a_non_zip_before_contacting_server(tmp_path):
    bad = tmp_path / "bad.imscc"
    bad.write_text("not a zip", encoding="utf-8")
    canvas = MODULE.GuardedCanvas("http://127.0.0.1:5055", 12345)
    with pytest.raises(ValueError, match="not a readable IMSCC"):
        canvas.import_package(bad)


def test_parser_supports_resuming_a_migration():
    args = MODULE.build_parser().parse_args([
        "--course", "12345", "monitor-migration", "--migration-id", "34492",
        "--record", "result.json",
    ])
    assert args.migration_id == 34492
