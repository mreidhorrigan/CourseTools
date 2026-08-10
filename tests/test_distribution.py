from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "scripts/build_distribution.py"
spec = importlib.util.spec_from_file_location("build_distribution", path)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_sanitization_replaces_live_course_target():
    data = b'{"course_id": 4066, "sandbox_course_url": "https://canvas.private.test/courses/4066"}'
    clean = module.sanitize("commands/test.config.jsonc", data).decode()
    assert '"course_id": 12345' in clean
    assert "canvas.example.edu/courses/12345" in clean
    assert "canvas.private.test" not in clean


def test_distribution_is_deterministic_sanitized_and_has_index(tmp_path):
    exclusions = module.jsonc.load_and_validate(ROOT / "commands/build-distribution.config.jsonc")["exclude_paths"]
    config = {"OUT_DIR": str(tmp_path / "one"), "archive_name": "toolkit.zip", "exclude_paths": exclusions}
    first, first_hash = module.build(ROOT, config)
    config["OUT_DIR"] = str(tmp_path / "two")
    second, second_hash = module.build(ROOT, config)
    assert first_hash == second_hash
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    with zipfile.ZipFile(first) as archive:
        names = set(archive.namelist())
        assert {"index.html", "AGENTS.md", "README.md", "PUBLIC_REPOSITORY.md", "LICENSE", "LICENSES.md", "sbom.json", "DISTRIBUTION-MANIFEST.json", "DISTRIBUTION-SAFETY.json"} <= names
        assert json.loads(archive.read("DISTRIBUTION-SAFETY.json"))["status"] == "PASS"
        assert "docs/TESTMAKING.md" in names
        assert "scripts/build_test_forms.py" in names
        assert "scripts/validate_question_pool.py" in names
        assert "commands/build-test-forms.command" in names
        assert "commands/build-test-forms.config.jsonc" in names
        assert "commands/build-test-forms.schema.json" in names
        assert "assets/favicon-slime.svg" in names
        assert "assets/slime-widget.js" in names
        assert "docs/BEST_PRACTICES_HANDBOOK.md" in names
        assert "course/AUTHORING.md" in names
        assert "course/course-manifest.json" in names
        assert json.loads(archive.read("course/rubric-manifest.json"))["course_id"] == 12345
        assert "course/PENDING-LIVE-UPDATE.md" not in names
        assert "commands/initialize-testmaking.command" in names
        assert "commands/test-assignment-rubric.command" in names
        assert "commands/test-assignment-rubric.config.jsonc" in names
        assert "docs/ASSIGNMENT_RUBRIC_QA.md" in names
        assert "scripts/mistral_assignment_qa.py" in names
        assert "skills/configure-canvas-course/SKILL.md" in names
        assert "commands/initialize.command" in names
        distributed_course = json.loads(archive.read("course/course-manifest.json"))
        assert distributed_course["requires_reinitialization"] is True
        assert {item["canvas_id"] for item in distributed_course["objects"]} == {0}
        assert not any(name.startswith("private/") for name in names)
        assert not any(name.startswith("course/testmaking/") for name in names)
        starter_name = "examples/iat210/IAT210-Fall2026-example-course-starter-v2.0.imscc"
        notice_name = "examples/iat210/README.md"
        assert starter_name in names and notice_name in names
        assert "examples/iat210/prepare_course_starter.py" in names
        assert "scripts/configure_iat210_course.py" not in names
        assert archive.read("index.html") == (ROOT / "index.html").read_bytes()
        index = archive.read("index.html").decode()
        assert "Upload this file first:" in index
        assert index.index("AI in a web chat") < index.index("First run on Mac for command-line operation")
        assert "what installing the local command-line toolkit adds" in index
        assert "IMSCC import path" in index and "optional MCP integration" in index
        assert "Layered quality assurance" in index
        assert "Course-specific values" in index
        assert "commands/portability-audit.config.jsonc" in index
        assert "course/course.config.jsonc" in index
        assert "private/" in index and "out/" in index
        assert "docs/BEST_PRACTICES_HANDBOOK.md" in index
        assert "The adapted handbook explains how to structure projects" in index
        assert "This toolkit’s Testmaker tool turns one editable test source" in index
        assert 'href="docs/TESTMAKING.md"' in index
        assert 'href="docs/TESTMAKER_AUTHORING.md"' in index
        assert 'href="docs/ASSIGNMENT_RUBRIC_QA.md"' in index
        assert 'src="assets/slime-widget.js"' in index
        assert "macOS-first" not in index and "QA is a stack" not in index
        handbook = archive.read("docs/BEST_PRACTICES_HANDBOOK.md").decode()
        assert "CC BY-SA 4.0" in handbook
        assert "REAPER" not in handbook and "ABLETON" not in handbook
        assert "/Users/" not in handbook and "CLAUDE_PROJECTS" not in handbook
        starter_bytes = archive.read(starter_name)
        notice = archive.read(notice_name).decode()
        assert hashlib.sha256(starter_bytes).hexdigest() in notice
        assert "not a production course" in notice
        assert "M. Horrigan" in notice and "CC BY 4.0" in notice
        with zipfile.ZipFile(io.BytesIO(starter_bytes)) as starter:
            starter_names = set(starter.namelist())
            manifest = starter.read("imsmanifest.xml").decode()
            syllabus = starter.read("wiki_content/iat-210-course-syllabus.html").decode()
            assert {f"Practice Quiz {number}" for number in range(1, 8)} <= set(module.re.findall(r"Practice Quiz \d+", manifest))
            assert "Practice Quiz 8" not in manifest and "Practice Quiz 9" not in manifest
            assert not any("outtake-week-" in name for name in starter_names)
            assert not any(name.endswith("I9_GAME_03_TRAMMELL.pdf") for name in starter_names)
            assert "M. Horrigan" in syllabus and "remote Wednesdays, 12:00–13:00" in syllabus
            assert syllabus.index("IAT 210 studies the history") < syllabus.index("The three project rounds")
            assert "fabricate sources or playtests" not in syllabus and "fabricate sources" in syllabus
            assert "Report persistent team problems" in syllabus
            assert "To receive a nonzero grade for this course's three major projects" in syllabus
            assert "Quiz 7 Dec 7, 09:00–23:59" in syllabus
            assert "font-family: OpenDyslexic" in syllabus or "font-family:OpenDyslexic" in syllabus
            quiz_metadata = [starter.read(name).decode() for name in starter_names if name.endswith("assessment_meta.xml")]
            quiz_metadata = [text for text in quiz_metadata if "Practice Quiz " in text]
            assert len(quiz_metadata) == 7
            assert all("<unlock_at>" in text and "<lock_at>" in text and "<all_day>false</all_day>" in text for text in quiz_metadata)
            assert "Centre for Accessible Learning" in syllabus and "SIAT recommended grading scale" in syllabus
            assert "academic-integrity reporting procedures" in syllabus
        assert not any(name.startswith((".git/", ".venv/", "out/", "input/imscc/IAT210_")) for name in names)
        assert "canvas.sfu.ca" not in archive.read("commands/start-server.config.jsonc").decode()
        assert "input/.DS_Store" not in names
        assert "input/imscc/README.md" not in names
        assert json.loads(archive.read("DISTRIBUTION-MANIFEST.json"))["sanitized"] is True


def test_distribution_publishes_one_stable_release_and_prunes_snapshots(tmp_path):
    project = tmp_path / "project"
    build_root = project / "out" / "distribution"
    old = build_root / "20260101T000000Z__canvas-automation-distribution"
    current = build_root / "20260102T000000Z__canvas-automation-distribution"
    old.mkdir(parents=True)
    current.mkdir()
    archive = current / "canvas-automation-toolkit.zip"
    provenance = current / "provenance.json"
    archive.write_bytes(b"release bytes")
    provenance.write_text('{"status":"PASS"}\n')

    published = module.publish_release(
        project,
        archive,
        provenance,
        {
            "release_dir": "$ENGINE/release",
            "retained_timestamped_builds": 0,
        },
    )

    assert published == project / "release" / "canvas-automation-toolkit.zip"
    assert published.read_bytes() == b"release bytes"
    assert (project / "release" / "provenance.json").is_file()
    assert not list(build_root.iterdir())


def test_sbom_covers_locked_packages_and_optional_mcp():
    bom = module.build_sbom(ROOT)
    assert bom["bomFormat"] == "CycloneDX"
    assert any(item["name"] == "canvas-mcp" and item["scope"] == "optional" for item in bom["components"])
    locked_names = {
        match.group(1).lower().replace("_", "-")
        for line in (ROOT / "mcp/requirements.lock").read_text().splitlines()
        if (match := module.re.match(r"^([A-Za-z0-9_.-]+)==", line))
    }
    sbom_names = {item["name"] for item in bom["components"] if item.get("group") == "canvas-mcp-environment"}
    assert sbom_names == locked_names


def test_distribution_safety_rejects_private_assessment_material(tmp_path):
    private = tmp_path / "private/testmaking/questions"
    private.mkdir(parents=True)
    (private / "exam.md").write_text("[Question.] Secret [Answer.] Key")
    try:
        module.audit_distribution_safety(tmp_path)
    except RuntimeError as error:
        assert "private/testmaking/questions/exam.md" in str(error)
    else:
        raise AssertionError("private assessment material passed the distribution safety audit")


def test_distribution_safety_rejects_provider_keys_and_student_exports(tmp_path):
    key_name = "MISTRAL" + "_API_KEY"
    (tmp_path / "settings.txt").write_text(f'{key_name}="abcdefghijklmnop123456"\n')
    try:
        module.audit_distribution_safety(tmp_path)
    except RuntimeError as error:
        assert "assigned Canvas or Mistral credential" in str(error)
    else:
        raise AssertionError("assigned provider key passed the distribution safety audit")
    (tmp_path / "settings.txt").unlink()
    (tmp_path / "grades.csv").write_text("student_id,grade\n1,100\n")
    try:
        module.audit_distribution_safety(tmp_path)
    except RuntimeError as error:
        assert "prohibited path or credential-file name" in str(error)
    else:
        raise AssertionError("student grade export passed the distribution safety audit")
