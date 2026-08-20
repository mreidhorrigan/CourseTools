from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from canvas_automation import jsonc
from canvas_automation.testmaker import parse_testmaker

ROOT = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)
    return module


course_authoring = load_script("course_authoring")
initializer = load_script("initialize_toolkit")


def test_canonical_course_manifest_sources_and_links_are_current():
    config = jsonc.load_and_validate(ROOT / "course/course.config.jsonc")
    manifest = json.loads((ROOT / config["authoring"]["manifest"]).read_text())
    assert manifest["course_id"] == course_authoring.course_id(config)
    unique_sources = {item["source"] for item in manifest["objects"]}
    # Syllabus and syllabus-front-page intentionally share one source.
    assert len(manifest["objects"]) == len(unique_sources) + 1
    assert all((ROOT / item["source"]).is_file() for item in manifest["objects"])
    syllabus_sources = {item["source"] for item in manifest["objects"] if item["kind"] in {"syllabus", "page"} and item["title"] in {"Canvas Syllabus", "IAT 210 Course Syllabus"}}
    assert syllabus_sources == {"course/content/syllabus.html"}
    stored = json.loads((ROOT / config["authoring"]["links_manifest"]).read_text())
    assert course_authoring.build_links(ROOT, manifest, config) == stored


def test_canonical_testmaking_manifest_uses_parseable_markdown():
    sample = ROOT / "input/example-testmaker-quiz.md"
    assert sample.suffix == ".md"
    assert parse_testmaker(sample).questions
    private_manifest = ROOT / "private/testmaking/testmaking-manifest.json"
    if private_manifest.exists():
        manifest = json.loads(private_manifest.read_text())
        assert manifest["source_format"] == "Testmaker Markdown"
        for quiz in manifest.get("assessments", manifest.get("quizzes", [])):
            assert Path(quiz["source"]).suffix == ".md"
            assert parse_testmaker(ROOT / quiz["source"]).questions


def test_initializer_updates_one_central_target_and_command_ids(tmp_path):
    (tmp_path / "course").mkdir(); (tmp_path / "commands").mkdir()
    (tmp_path / "course/course.config.jsonc").write_text(json.dumps({"authoring": {"manifest": "course/course-manifest.json", "links_manifest": "course/links-manifest.json", "imscc_template": "template.imscc"}}))
    (tmp_path / "course/rubric-manifest.json").write_text(json.dumps({"course_id": 1, "rubrics": []}))
    (tmp_path / "commands/start-server.config.jsonc").write_text('{"course_id": 1, "sandbox_course_url": "https://old.example/courses/1"}')
    (tmp_path / "commands/create-page.config.jsonc").write_text('{"course_id": 1}')
    args = SimpleNamespace(course_url="https://canvas.example.edu/courses/987", institution_name="Example University", institution_homepage="https://example.edu/", policy_domain="example.edu", library_resolver_host="library.example.edu")
    result = initializer.initialize(tmp_path, args)
    assert result["course_id"] == 987
    assert jsonc.load_jsonc(tmp_path / "course/course.config.jsonc")["institution"]["library_resolver_hosts"] == ["library.example.edu"]
    assert '"course_id": 987' in (tmp_path / "commands/create-page.config.jsonc").read_text()
    assert "https://canvas.example.edu/courses/987" in (tmp_path / "commands/start-server.config.jsonc").read_text()
    assert json.loads((tmp_path / "course/rubric-manifest.json").read_text())["course_id"] == 987
    assert result["updated_course_manifests"] == ["course/rubric-manifest.json"]


def test_authoritative_sources_propagate_into_imscc(tmp_path):
    result = course_authoring.build_imscc(ROOT, tmp_path / "course.imscc")
    assert result["updated_resources"] >= 20
    with zipfile.ZipFile(result["output"]) as archive:
        compiled, _ = course_authoring.compiled_sources(
            ROOT,
            json.loads((ROOT / "course/course-manifest.json").read_text()),
            jsonc.load_and_validate(ROOT / "course/course.config.jsonc"),
        )
        assert archive.read("course_settings/syllabus.html").decode() == compiled["course/content/syllabus.html"]
        rubrics = archive.read("course_settings/rubrics.xml").decode()
        assert "Actual-Play Plan</title>" in rubrics
        assert "The plan states a testable question" in rubrics
        assert "Episode construction, listener orientation, and intelligibility" in rubrics
