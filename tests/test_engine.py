"""
Engine tests, run by verify.command. No network access anywhere in this
file: the Flask tests use its test client and a deliberately-unreachable
Canvas domain, never a live one.
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from canvas_automation import jsonc, util  # noqa: E402
from canvas_automation import cli  # noqa: E402
from canvas_automation.canvas_client import CanvasClient, build_rubric_criteria_hash  # noqa: E402
from canvas_automation.course_packet import build_gradebook_rows  # noqa: E402
from canvas_automation.testmaker import Pool, for_version, parse_testmaker, question_payload, versions_in  # noqa: E402
from canvas_automation.imscc import build_imscc  # noqa: E402
from canvas_automation.new_quizzes import new_quiz_item_payload  # noqa: E402
from canvas_automation.pdf_tools import html_to_flowables, merge_pdfs, render_assignment_pdf  # noqa: E402
from canvas_automation.payloads import (  # noqa: E402
    build_assignment_payload,
    build_discussion_payload,
    build_page_payload,
    build_rubric_payload,
)
from canvas_automation.server import canvas_hosts_match, create_app  # noqa: E402
from canvas_automation import server as server_module  # noqa: E402

COMMANDS = ROOT / "commands"
CONFIGS = sorted(COMMANDS.glob("*.config.jsonc"))


# --------------------------------------------------------------------------
# Testmaker tagged source -> Classic Canvas Quiz
# --------------------------------------------------------------------------

def test_testmaker_parser_maps_question_pool_and_written_question(tmp_path):
    source = tmp_path / "questions.md"
    source.write_text(
        "[Question.] MCQ stem [Correct.] yes [Distractor.] no\n\n"
        "[Question.] Essay stem\n\n"
        "[Each version take 1 of the following options.]\n\n"
        "[Option.] [Question.] Pool A [Answer.] key A\n\n"
        "[Option.] [Question.] Pool B [Answer.] key B\n",
        encoding="utf-8",
    )
    parsed = parse_testmaker(source)
    assert len(parsed.questions) == 4
    assert isinstance(parsed.items[-1], Pool)
    assert parsed.items[-1].take == 1
    assert len(parsed.items[-1].questions) == 2
    assert question_payload(parsed.items[0], name="Q1", mcq_points=1, written_points=5)["question"]["question_type"] == "multiple_choice_question"
    assert question_payload(parsed.items[1], name="Q2", mcq_points=1, written_points=5)["question"]["question_type"] == "essay_question"


def test_testmaker_parses_all_question_tags_in_one_paragraph(tmp_path):
    source = tmp_path / "one-paragraph.md"
    source.write_text(
        "[Question.] Which answer is correct?\n"
        "[Correct.] This one\n"
        "[Distractor.] Not this one\n"
        "[Distractor.] Nor this one\n",
        encoding="utf-8",
    )
    parsed = parse_testmaker(source)
    assert len(parsed.questions) == 1
    assert parsed.questions[0].stem == "Which answer is correct?"
    assert parsed.questions[0].answer == "This one"
    assert parsed.questions[0].distractors == ["Not this one", "Nor this one"]


def test_legacy_mcqer_import_remains_compatible(tmp_path):
    from canvas_automation.mcqer import parse_mcqer

    source = tmp_path / "legacy.md"
    source.write_text("[Question.] Legacy? [Correct.] Yes [Distractor.] No")
    assert parse_mcqer(source).questions[0].answer == "Yes"


def test_testmaker_parser_filters_version_specific_questions(tmp_path):
    source = tmp_path / "questions.txt"
    source.write_text(
        "[Question.] Shared\n\n"
        "[Only Version A.] [Question.] A only\n\n"
        "[Only Version B.] [Question.] B only", encoding="utf-8")
    parsed = parse_testmaker(source)
    assert versions_in(parsed) == ["A", "B"]
    assert [q.stem for q in for_version(parsed, "A").questions] == ["Shared", "A only"]
    assert [q.stem for q in for_version(parsed, "B").questions] == ["Shared", "B only"]


def test_testmaker_conversion_plan_is_deterministic(tmp_path):
    source = tmp_path / "questions.txt"
    source.write_text("[Question.] Stem [Answer.] right [Distractor.] wrong", encoding="utf-8")
    first = parse_testmaker(source)
    second = parse_testmaker(source)
    p1 = question_payload(first.questions[0], name="Q1", mcq_points=1, written_points=5)
    p2 = question_payload(second.questions[0], name="Q1", mcq_points=1, written_points=5)
    assert json.dumps(p1, sort_keys=True) == json.dumps(p2, sort_keys=True)


def test_canvas_client_preserves_new_quiz_api_prefix():
    client = CanvasClient("https://canvas.example", "secret")
    assert client._url("/api/quiz/v1/courses/7/quizzes") == (
        "https://canvas.example/api/quiz/v1/courses/7/quizzes"
    )
    assert client._url("/courses/7/quizzes") == (
        "https://canvas.example/api/v1/courses/7/quizzes"
    )


def test_assignment_command_has_no_quiz_only_image_dependency(tmp_path, monkeypatch):
    """Regression: image upload code once leaked into create-assignment."""
    config_path = tmp_path / "assignment.jsonc"
    config_path.write_text("{}", encoding="utf-8")
    config = {
        "course_id": 7,
        "assignment": {"name": "Stored test", "description": "Body"},
        "OUT_DIR": str(tmp_path / "out"),
    }

    class Response:
        status_code = 200
        content = b"{}"
        text = ""

        @staticmethod
        def json():
            return {"id": 9, "name": "Stored test", "html_url": "https://canvas/9"}

    monkeypatch.setattr(cli, "_load_config", lambda engine, path: (config, config_path))
    monkeypatch.setattr(cli, "_require_server", lambda base: {"canvas_base_url": "https://canvas"})
    monkeypatch.setattr(cli.requests, "post", lambda *args, **kwargs: Response())

    result = cli.cmd_create_assignment(
        SimpleNamespace(engine=str(tmp_path), config="unused", course_id=None)
    )
    assert result == 0
    assert list((tmp_path / "out").rglob("assignment.json"))


def test_imscc_builder_is_deterministic_and_complete(tmp_path):
    import zipfile
    spec = jsonc.load_jsonc(ROOT / "input/course-package.example.jsonc")
    outputs = []
    for n in (1, 2):
        work = tmp_path / f"work{n}"; work.mkdir(); out = tmp_path / f"course{n}.imscc"
        build_imscc(spec, ROOT, work, out); outputs.append(out.read_bytes())
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
            assert {"imsmanifest.xml", "course_settings/course_settings.xml",
                    "course_settings/module_meta.xml", "course_settings/rubrics.xml",
                    "wiki_content/welcome.html"} <= names
            rubrics = z.read("course_settings/rubrics.xml").decode()
            assert "Opening Reflection Rubric" in rubrics
            assignment_settings = z.read(next(x for x in names if x.endswith("/assignment_settings.xml"))).decode()
            assert "rubric_identifierref" in assignment_settings
            assert any("discussion" in x and x.endswith(".xml") for x in names)
            manifest=z.read("imsmanifest.xml").decode(); assert "imsdt_xmlv1p1" in manifest
    assert outputs[0] == outputs[1]


def test_new_quiz_choice_payload_is_deterministic():
    from canvas_automation.testmaker import Question
    q=Question("Stem",answer="Right",distractors=["Wrong"])
    a=new_quiz_item_payload(q,name="Q1",points=1,position=1)
    b=new_quiz_item_payload(q,name="Q1",points=1,position=1)
    assert a==b
    assert a["item"]["entry"]["interaction_type_slug"]=="choice"
    assert a["item"]["entry"]["scoring_algorithm"]=="Equivalence"


def test_question_payload_rewrites_image_tags():
    from canvas_automation.testmaker import Question
    payload=question_payload(Question("See [Image: diagram.png]",answer="Yes",distractors=["No"]),
        name="Q",mcq_points=1,written_points=5,image_urls={"diagram.png":"https://canvas.example/files/1/download"})
    assert '<img src="https://canvas.example/files/1/download"' in payload["question"]["question_text"]


# --------------------------------------------------------------------------
# jsonc parsing
# --------------------------------------------------------------------------

def test_strip_comments_preserves_urls_in_strings():
    text = '{"a": "http://example.com", "b": 1 // trailing comment\n}'
    assert jsonc.loads(text) == {"a": "http://example.com", "b": 1}


def test_strip_trailing_comma():
    text = '{"a": 1, "b": 2,}'
    assert jsonc.loads(text) == {"a": 1, "b": 2}


@pytest.mark.parametrize("config_path", CONFIGS, ids=lambda p: p.name)
def test_every_shipped_config_parses(config_path):
    data = jsonc.load_jsonc(config_path)
    assert isinstance(data, dict)


@pytest.mark.parametrize("config_path", CONFIGS, ids=lambda p: p.name)
def test_every_shipped_config_validates_against_its_schema(config_path):
    # Raises ConfigError on failure; a clean load_and_validate is the assertion.
    jsonc.load_and_validate(config_path)


def test_schema_validation_catches_a_bad_value():
    schema = {
        "type": "object",
        "required": ["course_id"],
        "properties": {"course_id": {"type": "integer", "minimum": 1}},
    }
    with pytest.raises(jsonc.ConfigError):
        jsonc.validate_config({"course_id": "not-a-number"}, schema)


def test_schema_validation_recurses_into_nested_objects():
    schema = {
        "type": "object",
        "properties": {
            "assignment": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            }
        },
    }
    with pytest.raises(jsonc.ConfigError):
        jsonc.validate_config({"assignment": {}}, schema)


# --------------------------------------------------------------------------
# The rubric criteria quirk (research/canvas-api-endpoints.md)
# --------------------------------------------------------------------------

def test_rubric_criteria_becomes_an_indexed_hash_not_an_array():
    criteria = [
        {"description": "A", "points": 10, "ratings": [{"description": "Good", "points": 10}]},
        {"description": "B", "points": 5, "ratings": [{"description": "Ok", "points": 5}]},
    ]
    result = build_rubric_criteria_hash(criteria)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"0", "1"}
    assert isinstance(result["0"]["ratings"], dict)
    assert set(result["0"]["ratings"].keys()) == {"0"}
    assert result["1"]["description"] == "B"


# --------------------------------------------------------------------------
# Payload builders + the determinism-of-request contract
# --------------------------------------------------------------------------

def test_assignment_payload_determinism():
    config = jsonc.load_jsonc(COMMANDS / "create-assignment.config.jsonc")
    first = build_assignment_payload(dict(config), ROOT)
    config_again = jsonc.load_jsonc(COMMANDS / "create-assignment.config.jsonc")
    second = build_assignment_payload(dict(config_again), ROOT)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_rubric_payload_determinism():
    config = jsonc.load_jsonc(COMMANDS / "create-rubric.config.jsonc")
    first = build_rubric_payload(config, ROOT)
    second = build_rubric_payload(jsonc.load_jsonc(COMMANDS / "create-rubric.config.jsonc"), ROOT)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_discussion_payload_determinism():
    config = jsonc.load_jsonc(COMMANDS / "create-discussion.config.jsonc")
    first = build_discussion_payload(dict(config), ROOT)
    second = build_discussion_payload(jsonc.load_jsonc(COMMANDS / "create-discussion.config.jsonc"), ROOT)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_page_payload_determinism():
    config = jsonc.load_jsonc(COMMANDS / "create-page.config.jsonc")
    first = build_page_payload(dict(config), ROOT)
    second = build_page_payload(jsonc.load_jsonc(COMMANDS / "create-page.config.jsonc"), ROOT)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_assignment_payload_reads_the_description_file():
    config = jsonc.load_jsonc(COMMANDS / "create-assignment.config.jsonc")
    payload = build_assignment_payload(dict(config), ROOT)
    assert "description_file" not in payload["assignment"]
    assert "Reflect on this" not in payload["assignment"]["description"]  # sanity: not a placeholder
    assert len(payload["assignment"]["description"]) > 0


# --------------------------------------------------------------------------
# util helpers
# --------------------------------------------------------------------------

def test_slugify_is_filesystem_safe():
    assert util.slugify("Week 3: Open Discussion!") == "week-3-open-discussion"
    assert util.slugify(None) == "untitled"


def test_fresh_out_dir_is_unique_and_never_reused(tmp_path):
    d1 = util.fresh_out_dir(tmp_path, slug="same-name")
    d2 = util.fresh_out_dir(tmp_path, slug="same-name")
    assert d1 != d2
    assert d1.exists() and d2.exists()


def test_write_provenance_shape(tmp_path):
    config_path = tmp_path / "x.config.jsonc"
    config_path.write_text("{}")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    path = util.write_provenance(
        out_dir, command="create-assignment", config_path=config_path,
        canvas_base_url="https://example.instructure.com", course_id=1,
        request_payload={"assignment": {"name": "x"}}, result={"type": "assignment", "id": 1},
    )
    record = json.loads(path.read_text())
    assert record["schema_version"] == "canvas.provenance/v1"
    assert record["config_sha256"]
    assert record["tool_versions"]["flask"]


# --------------------------------------------------------------------------
# Engine-root resolution (regression coverage for a real shipped bug: see
# research/02-engine-root-resolution.md). The bug was that ENGINE never
# reached the Python process and the sys.executable-based fallback broke
# on a symlinked venv interpreter, so output silently landed in $HOME.
# --------------------------------------------------------------------------

def test_find_engine_root_prefers_the_explicit_argument(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGINE", "/somewhere/else")
    assert util.find_engine_root(str(tmp_path)) == tmp_path


def test_find_engine_root_falls_back_to_the_environment_variable(monkeypatch, tmp_path):
    monkeypatch.delenv("ENGINE", raising=False)
    monkeypatch.setenv("ENGINE", str(tmp_path))
    assert util.find_engine_root(None) == tmp_path


def test_find_engine_root_falls_back_to_sys_prefix_when_nothing_else_is_set(monkeypatch, tmp_path):
    # Simulates exactly the failure mode that shipped: no --engine, no
    # ENGINE env var. sys.prefix (not sys.executable) must still resolve
    # correctly, since sys.prefix is not affected by .venv/bin/python
    # being a symlink to the system interpreter.
    monkeypatch.delenv("ENGINE", raising=False)
    fake_venv = tmp_path / ".venv"
    fake_venv.mkdir()
    monkeypatch.setattr(sys, "prefix", str(fake_venv))
    monkeypatch.setattr(sys, "base_prefix", "/usr")  # different from sys.prefix => "we are in a venv"
    assert util.find_engine_root(None) == tmp_path


def test_find_engine_root_last_resort_is_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("ENGINE", raising=False)
    monkeypatch.setattr(sys, "prefix", sys.base_prefix)  # pretend we're not in a venv at all
    monkeypatch.chdir(tmp_path)
    assert util.find_engine_root(None) == tmp_path


def test_resolve_out_base_uses_a_custom_out_dir_when_the_config_sets_one(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE", str(tmp_path))
    custom = tmp_path / "Desktop" / "my-exports"
    result = util.resolve_out_base(tmp_path, {"OUT_DIR": str(custom)}, "create-assignment")
    assert result == custom


def test_resolve_out_base_expands_engine_the_same_way_jsonc_py_does(tmp_path):
    result = util.resolve_out_base(tmp_path, {"OUT_DIR": "$ENGINE/out/create-assignment"}, "create-assignment")
    assert result == tmp_path / "out" / "create-assignment"


def test_resolve_out_base_defaults_to_engine_out_command_name_when_unset(tmp_path):
    result = util.resolve_out_base(tmp_path, {}, "create-assignment")
    assert result == tmp_path / "out" / "create-assignment"


def test_merge_pdfs_cli_writes_inside_the_engine_directory_not_cwd_or_home(tmp_path, monkeypatch):
    """
    An end-to-end regression test for the actual shipped bug: run the real
    installed CLI as a subprocess (not just call functions directly), from
    a working directory that is NOT the project, with no ENGINE env var
    set, exactly like a .command file invoked from Finder or an arbitrary
    shell. Only --engine (what commands/*.command now always passes)
    should determine where output lands.
    """
    canvas_automation_bin = ROOT / ".venv" / "bin" / "canvas-automation"
    if not canvas_automation_bin.is_file():
        pytest.skip("canvas-automation console script not built in this environment")

    fake_home = tmp_path / "not_the_project"
    fake_home.mkdir()
    p1 = tmp_path / "a.pdf"
    p2 = tmp_path / "b.pdf"
    from canvas_automation.pdf_tools import render_assignment_pdf
    render_assignment_pdf({"name": "A"}, p1)
    render_assignment_pdf({"name": "B"}, p2)

    engine_root = tmp_path / "real_engine"
    (engine_root / "commands").mkdir(parents=True)
    (engine_root / "commands" / "merge-pdfs.config.jsonc").write_text(
        '{"OUT_DIR": "$ENGINE/out/merge-pdfs", "output_name": "merged.pdf"}'
    )

    env = dict(os.environ)
    env.pop("ENGINE", None)  # the exact condition that broke: no ENGINE env var at all

    result = subprocess.run(
        [str(canvas_automation_bin), "merge-pdfs", "--engine", str(engine_root),
         "--config", "commands/merge-pdfs.config.jsonc", str(p1), str(p2)],
        cwd=str(fake_home),  # NOT the project directory
        env=env, capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert not (fake_home / "out").exists(), "output must not land next to cwd"
    assert (engine_root / "out" / "merge-pdfs").exists(), "output must land under the real engine root"



# --------------------------------------------------------------------------
# The Flask app: routes register, /health is clean, failures stay JSON
# --------------------------------------------------------------------------

def test_health_reports_status_and_never_the_token():
    app = create_app("fake-canvas-test.invalid", "super-secret-token")
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["canvas_base_url"] == "https://fake-canvas-test.invalid"
    assert "super-secret-token" not in json.dumps(body)


def test_health_reports_the_sandbox_course_guard():
    app = create_app("fake-canvas-test.invalid", "secret", allowed_course_id=77)
    body = app.test_client().get("/health").get_json()
    assert body["allowed_course_id"] == 77
    assert "secret" not in json.dumps(body)


def test_sandbox_url_hostname_must_match_canvas_api_hostname():
    assert canvas_hosts_match(
        "https://canvas.example.edu", "https://canvas.example.edu/courses/12345"
    )
    assert canvas_hosts_match(
        "canvas.example.edu", "https://canvas.example.edu/courses/12345/assignments"
    )
    assert not canvas_hosts_match(
        "https://canvas.example.edu", "https://other.instructure.com/courses/12345"
    )


@pytest.mark.parametrize("endpoint", [
    "/api/courses/88/assignments",
    "/api/courses/88/rubrics",
    "/api/courses/88/discussion_topics",
    "/api/courses/88/pages",
    "/api/courses/88/files",
    "/api/courses/88/content_migrations",
])
def test_sandbox_guard_blocks_dedicated_routes_before_canvas(endpoint):
    app = create_app("fake-canvas-test.invalid", "dummy", allowed_course_id=77)
    resp = app.test_client().post(endpoint, json={})
    assert resp.status_code == 403
    assert resp.get_json()["allowed_course_id"] == 77


def test_sandbox_guard_blocks_authenticated_download_for_wrong_course():
    app = create_app("fake-canvas-test.invalid", "dummy", allowed_course_id=77)
    resp = app.test_client().get("/api/courses/88/files/5/download")
    assert resp.status_code == 403
    assert resp.get_json()["allowed_course_id"] == 77


@pytest.mark.parametrize("path", [
    "/courses/88/quizzes",
    "/api/quiz/v1/courses/88/quizzes",
    "/api/quiz/v1/courses/88/quizzes/2/items",
])
def test_sandbox_guard_blocks_classic_and_new_quiz_raw_paths(path):
    app = create_app("fake-canvas-test.invalid", "dummy", allowed_course_id=77)
    resp = app.test_client().post(
        "/api/raw", json={"method": "POST", "path": path, "payload": {}}
    )
    assert resp.status_code == 403
    assert resp.get_json()["requested_course_id"] == 88


@pytest.mark.parametrize("path", [
    "/accounts/1/courses",
    "/users/2",
    "https://other.example/api/v1/accounts/1/courses",
])
def test_sandbox_guard_blocks_raw_mutations_without_a_course_path(path):
    app = create_app("fake-canvas-test.invalid", "dummy", allowed_course_id=77)
    resp = app.test_client().post(
        "/api/raw", json={"method": "POST", "path": path, "payload": {}}
    )
    assert resp.status_code == 403
    assert resp.get_json()["allowed_course_id"] == 77


def test_all_expected_routes_are_registered():
    app = create_app("fake-canvas-test.invalid", "dummy")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    for expected in (
        "/health",
        "/api/courses/<int:course_id>/assignments",
        "/api/courses/<int:course_id>/rubrics",
        "/api/courses/<int:course_id>/discussion_topics",
        "/api/courses/<int:course_id>/pages",
        "/api/courses/<int:course_id>/files",
        "/api/courses/<int:course_id>/files/<int:file_id>/download",
        "/api/courses/<int:course_id>/content_migrations",
        "/api/raw",
        "/shutdown",
    ):
        assert expected in rules


def test_shutdown_endpoint_calls_runner_callback_without_process_exit():
    app = create_app("fake-canvas-test.invalid", "dummy", allowed_course_id=77)
    stopped = threading.Event(); app.shutdown_callback = stopped.set
    response = app.test_client().post("/shutdown")
    assert response.status_code == 200
    assert stopped.wait(1)


def test_run_uses_waitress_and_drops_token_from_environment(monkeypatch):
    calls = []
    class FakeServer:
        def run(self): calls.append("run")
        def close(self): calls.append("close")
    monkeypatch.setenv("CANVAS_BASE_URL", "https://canvas.example")
    monkeypatch.setenv("CANVAS_API_TOKEN", "memory-only")
    monkeypatch.setattr(server_module.CanvasClient, "whoami", lambda self: {"name": "Tester"})
    monkeypatch.setattr("waitress.server.create_server", lambda app, **kwargs: (calls.append(kwargs) or FakeServer()))
    server_module.run("127.0.0.1", 5055, 77, "https://canvas.example/courses/77")
    assert calls[0] == {"host": "127.0.0.1", "port": 5055, "threads": 4, "clear_untrusted_proxy_headers": True}
    assert calls.count("run") == 1 and calls.count("close") >= 1
    assert "CANVAS_API_TOKEN" not in os.environ


def test_unreachable_canvas_still_returns_clean_json_not_a_crash():
    app = create_app("fake-canvas-test.invalid", "dummy")
    client = app.test_client()
    resp = client.post(
        "/api/courses/1/rubrics",
        json={
            "rubric": {"title": "t", "criteria": [{"description": "d", "points": 1}]},
            "rubric_association": {"association_type": "Course", "association_id": 1, "purpose": "bookmark"},
        },
    )
    assert resp.status_code == 500
    assert resp.is_json


# --------------------------------------------------------------------------
# Course URL parsing (export-course-packet's interactive prompt)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("given,expected", [
    ("https://yourschool.instructure.com/courses/12345", 12345),
    ("https://yourschool.instructure.com/courses/12345/assignments", 12345),
    ("https://yourschool.instructure.com/courses/12345/gradebook#tab-1", 12345),
    ("https://yourschool.instructure.com/courses/12345/", 12345),
    ("12345", 12345),
    ("  12345  ", 12345),
])
def test_parse_course_id_accepts_urls_and_bare_ids(given, expected):
    assert util.parse_course_id(given) == expected


def test_parse_course_id_rejects_garbage():
    with pytest.raises(ValueError):
        util.parse_course_id("https://yourschool.instructure.com/dashboard")


# --------------------------------------------------------------------------
# HTML -> PDF (export-course-packet's assignment rendering)
# --------------------------------------------------------------------------

def test_html_to_flowables_handles_common_tags_without_crashing():
    html = (
        "<h2>Heading</h2><p>Some <strong>bold</strong> and <em>italic</em> text "
        '<a href="https://example.com">a link</a>.</p>'
        "<ul><li>One</li><li>Two</li></ul>"
        "<table><tr><td>ignored</td></tr></table>"
    )
    flowables = html_to_flowables(html)
    assert len(flowables) > 0


def test_html_to_flowables_handles_empty_description():
    flowables = html_to_flowables(None)
    assert len(flowables) == 1


def test_render_assignment_pdf_produces_a_readable_pdf(tmp_path):
    from pypdf import PdfReader
    assignment = {
        "name": "Test Assignment",
        "due_at": "2026-09-15T23:59:00Z",
        "points_possible": 20,
        "description": "<p>Write about <strong>something</strong>.</p><ul><li>A</li><li>B</li></ul>",
    }
    out_path = tmp_path / "a.pdf"
    render_assignment_pdf(assignment, out_path)
    reader = PdfReader(str(out_path))
    assert len(reader.pages) >= 1
    text = reader.pages[0].extract_text()
    assert "Test Assignment" in text


# --------------------------------------------------------------------------
# PDF merging (shared by export-course-packet and merge-pdfs)
# --------------------------------------------------------------------------

def test_merge_pdfs_combines_page_counts(tmp_path):
    from pypdf import PdfReader
    p1, p2 = tmp_path / "one.pdf", tmp_path / "two.pdf"
    render_assignment_pdf({"name": "First"}, p1)
    render_assignment_pdf({"name": "Second", "description": "<p>" + "word " * 800 + "</p>"}, p2)  # forces >1 page

    out_path = tmp_path / "merged.pdf"
    page_count = merge_pdfs([p1, p2], out_path)

    expected = len(PdfReader(str(p1)).pages) + len(PdfReader(str(p2)).pages)
    assert page_count == expected
    assert len(PdfReader(str(out_path)).pages) == expected


def test_merge_pdfs_preserves_given_order(tmp_path):
    from pypdf import PdfReader
    first, second = tmp_path / "first.pdf", tmp_path / "second.pdf"
    render_assignment_pdf({"name": "AAAFIRST"}, first)
    render_assignment_pdf({"name": "ZZZSECOND"}, second)

    out_path = tmp_path / "merged.pdf"
    merge_pdfs([first, second], out_path)
    text = PdfReader(str(out_path)).pages[0].extract_text()
    assert "AAAFIRST" in text  # the first page of the merged file is the first input


# --------------------------------------------------------------------------
# Gradebook synthesis (no documented Canvas CSV-export endpoint; see
# research/canvas-api-endpoints.md)
# --------------------------------------------------------------------------

def test_build_gradebook_rows_shape():
    assignments = [
        {"id": 1, "name": "HW1", "points_possible": 10},
        {"id": 2, "name": "HW2", "points_possible": 20},
    ]
    enrollments = [
        {"user_id": 100, "user": {"sortable_name": "Doe, Jane"}, "grades": {"current_score": 90, "final_score": 88}},
        {"user_id": 101, "user": {"sortable_name": "Roe, Sam"}, "grades": {"current_score": 70, "final_score": 65}},
    ]
    submissions_by_student = {100: {1: 9, 2: 18}, 101: {1: 5}}  # Sam never submitted HW2

    rows = build_gradebook_rows(assignments, enrollments, submissions_by_student)

    assert rows[0] == ["Student", "Canvas User ID", "HW1 (10)", "HW2 (20)", "Current Score", "Final Score"]
    assert rows[1] == ["Doe, Jane", 100, 9, 18, 90, 88]
    assert rows[2] == ["Roe, Sam", 101, 5, "", 70, 65]  # missing submission -> blank, not zero


def test_build_gradebook_rows_falls_back_to_user_id_without_a_name():
    assignments = []
    enrollments = [{"user_id": 5, "grades": {}}]
    rows = build_gradebook_rows(assignments, enrollments, {})
    assert rows[1][0] == "User 5"


# --------------------------------------------------------------------------
# write_provenance without any Canvas fields (merge-pdfs has none)
# --------------------------------------------------------------------------

def test_write_provenance_without_canvas_fields(tmp_path):
    config_path = tmp_path / "x.config.jsonc"
    config_path.write_text("{}")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    path = util.write_provenance(
        out_dir, command="merge-pdfs", config_path=config_path,
        request_payload={"input_files": ["a.pdf", "b.pdf"]},
        result={"type": "merged_pdf", "page_count": 2},
    )
    record = json.loads(path.read_text())
    assert record["canvas_base_url"] is None
    assert record["course_id"] is None


# --------------------------------------------------------------------------
# Shell syntax
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "script",
    [
        *COMMANDS.glob("*.command"), *ROOT.glob("scripts/*.sh"),
        ROOT / "setup-after-move.command", ROOT / "verify.command",
    ],
    ids=lambda p: p.name,
)
def test_bash_syntax(script):
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_mcp_launcher_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(ROOT / "mcp" / "canvas-mcp-launcher")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_mcp_dependency_is_exactly_version_pinned():
    direct = [
        line.strip()
        for line in (ROOT / "mcp" / "requirements.in").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(direct) == 1
    name, separator, version = direct[0].partition("==")
    assert name == "canvas-mcp"
    assert separator == "=="
    assert version and all(part.isdigit() for part in version.split("."))
    lock = (ROOT / "mcp" / "requirements.lock").read_text()
    assert f"canvas-mcp=={version} \\" in lock
    assert "--hash=sha256:" in lock
    assert len([line for line in lock.splitlines() if "==" in line and not line.startswith("#")]) > 20
