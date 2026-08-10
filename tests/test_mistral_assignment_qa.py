from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/mistral_assignment_qa.py"
spec = importlib.util.spec_from_file_location("mistral_assignment_qa", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class FakeClient:
    model = "test-mistral"

    def complete(self, messages, *, seed, temperature, max_tokens, json_mode=False):
        system = messages[0]["content"]
        if not json_mode:
            return "A simulated submission with a claim, two observations, and a limitation.", {"seed": seed}
        if "Grade only" in system:
            return json.dumps({
                "overall_score": 8, "maximum_score": 10,
                "criterion_results": [], "missing_evidence": [],
                "grading_ambiguities": ["Citation format is undefined."], "feedback": "Clarify citation form.",
            }), {"seed": seed}
        return json.dumps({
            "instruction_ambiguities": [], "rubric_ambiguities": [],
            "instruction_rubric_mismatches": [], "plausible_but_unintended_choices": [],
            "requirements_not_observed": [], "grade_reproducibility": "medium",
            "priority_actions": ["Define the required citation form."],
        }), {"seed": seed}


def test_run_creates_local_diagnostic_report_without_key(tmp_path):
    instructions = tmp_path / "assignment.md"
    rubric = tmp_path / "rubric.md"
    instructions.write_text("Write 100 words and cite one observation.")
    rubric.write_text("Clarity: 5 points. Evidence: 5 points.")
    config_path = tmp_path / "qa.config.jsonc"
    config_path.write_text(json.dumps({
        "OUT_DIR": str(tmp_path / "out"),
        "instructions_file": str(instructions), "rubric_file": str(rubric),
        "context_files": [], "expected_requirements": ["Write 100 words."],
        "student_profiles": ["Literal reader"], "trials": 2, "seed": 4,
        "model": "test-mistral", "api_url": "https://example.invalid/v1/chat/completions",
        "student_temperature": 0.5, "grader_temperature": 0.1,
        "student_max_tokens": 256, "analysis_max_tokens": 256,
        "max_input_chars": 5000, "timeout_seconds": 30,
    }))

    output = module.run(tmp_path, config_path, FakeClient())

    record = json.loads((output / "qa-results.json").read_text())
    provenance = json.loads((output / "provenance.json").read_text())
    assert len(record["trials"]) == 2
    assert record["trials"][0]["grade"]["overall_score"] == 8
    assert "Define the required citation form" in (output / "qa-report.md").read_text()
    assert provenance["api_key_stored"] is False
    assert "secret" not in json.dumps(provenance).lower()


def test_json_result_rejects_unstructured_output():
    try:
        module.json_result("not JSON", "grading")
    except module.MistralQAError as error:
        assert "invalid JSON" in str(error)
    else:
        raise AssertionError("unstructured output was accepted")


def test_read_source_enforces_input_limit(tmp_path):
    source = tmp_path / "large.md"
    source.write_text("x" * 20)
    try:
        module.read_source(tmp_path, str(source), "source", 10)
    except module.MistralQAError as error:
        assert "configured maximum" in str(error)
    else:
        raise AssertionError("oversized input was accepted")


def test_client_retries_rate_limit_without_exposing_key(monkeypatch):
    class Response:
        def __init__(self, status):
            self.status_code = status
            self.headers = {}

        def raise_for_status(self):
            if self.status_code >= 400:
                error = module.requests.HTTPError("limited")
                error.response = self
                raise error

        def json(self):
            return {"id": "ok", "model": "test", "choices": [{"message": {"content": "done"}}]}

    responses = iter([Response(429), Response(200)])
    sleeps = []
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    client = module.MistralClient("private-value", api_url="https://example.invalid", model="test",
                                  timeout_seconds=10, retry_attempts=2, retry_base_seconds=1)
    content, _ = client.complete([{"role": "user", "content": "test"}], seed=1,
                                 temperature=0, max_tokens=128)
    assert content == "done"
    assert sleeps == [1]


def test_student_prompt_requires_gradeable_binary_dossier():
    messages = module.student_messages("Submit a ZIP.", "", "Literal reader")
    assert "textual submission dossier" in messages[0]["content"]
    assert "Do not invent a download link" in messages[0]["content"]
