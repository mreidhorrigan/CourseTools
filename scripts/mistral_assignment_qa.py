#!/usr/bin/env python3
"""Use Mistral as a boundary tester for assignment instructions and rubrics."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from canvas_automation import jsonc
from canvas_automation.util import fresh_out_dir, resolve_out_base, resolve_path


class MistralQAError(RuntimeError):
    """A safe, user-facing error from assignment QA."""


def read_source(root: Path, value: str, label: str, max_chars: int) -> tuple[Path, str]:
    path = resolve_path(root, value)
    if not path.is_file():
        raise MistralQAError(f"{label} does not exist: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise MistralQAError(f"{label} is empty: {path}")
    if len(text) > max_chars:
        raise MistralQAError(
            f"{label} has {len(text):,} characters; configured maximum is {max_chars:,}. "
            "Reduce the source or raise max_input_chars deliberately."
        )
    return path, text


class MistralClient:
    def __init__(self, api_key: str, *, api_url: str, model: str, timeout_seconds: int,
                 retry_attempts: int = 5, retry_base_seconds: float = 5):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.retry_base_seconds = retry_base_seconds

    def complete(self, messages: list[dict[str, str]], *, seed: int, temperature: float,
                 max_tokens: int, json_mode: bool = False) -> tuple[str, dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "random_seed": seed,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = None
            for attempt in range(self.retry_attempts):
                response = requests.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                if response.status_code not in {429, 500, 502, 503, 504} or attempt + 1 >= self.retry_attempts:
                    break
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = self.retry_base_seconds * (2 ** attempt)
                delay = min(max(delay, self.retry_base_seconds), 45)
                print(f"Mistral returned HTTP {response.status_code}; retrying in {delay:g} seconds ({attempt + 2}/{self.retry_attempts})…", file=sys.stderr)
                time.sleep(delay)
            assert response is not None
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            if not isinstance(content, str) or not content.strip():
                raise MistralQAError("Mistral returned no text content.")
            return content.strip(), {"id": body.get("id"), "model": body.get("model"), "usage": body.get("usage", {})}
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else "unknown"
            raise MistralQAError(f"Mistral API request failed with HTTP {status}. Check the key, model, and quota.") from None
        except (requests.RequestException, KeyError, ValueError, TypeError) as error:
            raise MistralQAError(f"Mistral API request failed: {type(error).__name__}: {error}") from None


def json_result(text: str, stage: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise MistralQAError(f"Mistral returned invalid JSON during {stage}: {error}") from None
    if not isinstance(value, dict):
        raise MistralQAError(f"Mistral returned a non-object JSON value during {stage}.")
    return value


def complete_json(client: MistralClient, messages: list[dict[str, str]], *, stage: str,
                  seed: int, temperature: float, max_tokens: int,
                  repair_attempts: int = 2) -> tuple[dict[str, Any], dict[str, Any]]:
    """Request JSON and retry malformed/truncated responses with an explicit repair prompt."""
    attempts: list[dict[str, Any]] = []
    current_messages = messages
    for attempt in range(repair_attempts + 1):
        raw, metadata = client.complete(
            current_messages, seed=seed + attempt, temperature=temperature,
            max_tokens=max_tokens, json_mode=True,
        )
        attempts.append({"attempt": attempt + 1, "raw_response": raw, "api_metadata": metadata})
        try:
            value = json_result(raw, stage)
            return value, {"successful_attempt": attempt + 1, "attempts": attempts}
        except MistralQAError:
            if attempt >= repair_attempts:
                raise MistralQAError(
                    f"Mistral returned invalid JSON during {stage} after {attempt + 1} attempts. "
                    "Raw responses remain available in the API caller's diagnostic context."
                ) from None
            current_messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "The preceding response was incomplete or invalid JSON. Return the same result "
                    "as one complete, valid JSON object. Be concise enough to finish within the token limit."
                )},
            ]
    raise AssertionError("unreachable")


def student_messages(instructions: str, context: str, profile: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": (
            "Act as a student completing an assignment. The supplied STUDENT PROFILE is binding and controls the submission's completeness, reasoning, evidence, and execution. "
            "Do not compensate for a weak profile, silently repair its omissions, or produce excellent work unless the profile explicitly calls for it. "
            "Use only the supplied assignment instructions and context. "
            "Do not ask questions, consult a rubric, invent hidden requirements, or explain your process. Produce the submission itself. "
            "When a submission normally contains a ZIP, media, website, PDF, or other binary artifact, return a textual submission dossier: "
            "list every file and reproduce or concretely describe enough of each file's contents for a grader to assess it. "
            "Do not invent a download link, sandbox path, inaccessible attachment, or claim that a file was uploaded."
        )},
        {"role": "user", "content": f"STUDENT PROFILE\n{profile}\n\nASSIGNMENT INSTRUCTIONS\n{instructions}\n\nCONTEXT\n{context or '(none supplied)'}"},
    ]


def grading_messages(instructions: str, rubric: str, submission: str) -> list[dict[str, str]]:
    shape = {
        "overall_score": "number or null", "maximum_score": "number or null",
        "criterion_results": [{"criterion": "string", "score": "number or null", "evidence": "string", "reason": "string", "confidence": "low|medium|high"}],
        "missing_evidence": ["string"], "grading_ambiguities": ["string"], "feedback": "string",
    }
    return [
        {"role": "system", "content": "Grade only from the supplied rubric and submission. Do not invent criteria. Return one JSON object exactly in the requested shape."},
        {"role": "user", "content": f"Return JSON shaped like:\n{json.dumps(shape)}\n\nASSIGNMENT INSTRUCTIONS\n{instructions}\n\nRUBRIC\n{rubric}\n\nSUBMISSION\n{submission}"},
    ]


def audit_messages(instructions: str, rubric: str, expected: list[str], submission: str,
                   grade: dict[str, Any]) -> list[dict[str, str]]:
    shape = {
        "instruction_ambiguities": [{"issue": "string", "evidence": "string", "suggested_revision": "string"}],
        "rubric_ambiguities": [{"issue": "string", "evidence": "string", "suggested_revision": "string"}],
        "instruction_rubric_mismatches": [{"issue": "string", "location": "string", "suggested_revision": "string"}],
        "plausible_but_unintended_choices": ["string"], "requirements_not_observed": ["string"],
        "grade_reproducibility": "low|medium|high", "priority_actions": ["string"],
    }
    return [
        {"role": "system", "content": (
            "Audit assignment specificity. Treat a plausible misunderstanding by a literal student or an unsupported grading judgment as evidence of a possible design gap. "
            "Do not rewrite the whole assignment. Return one JSON object exactly in the requested shape."
        )},
        {"role": "user", "content": f"Return JSON shaped like:\n{json.dumps(shape)}\n\nEXPECTED REQUIREMENTS\n{json.dumps(expected)}\n\nINSTRUCTIONS\n{instructions}\n\nRUBRIC\n{rubric}\n\nSIMULATED SUBMISSION\n{submission}\n\nSIMULATED GRADE\n{json.dumps(grade)}"},
    ]


def render_report(record: dict[str, Any]) -> str:
    lines = [
        "# Assignment and rubric boundary-test report", "",
        f"- Model: `{record['model']}`", f"- Trials: {len(record['trials'])}",
        "- Interpretation: findings identify material for human review; model output is not an authoritative grade.", "",
    ]
    for trial in record["trials"]:
        lines.extend([f"## Trial {trial['trial']}", "", "### Simulated submission", "", trial["submission"], "", "### Simulated grading", "", "```json", json.dumps(trial["grade"], indent=2, ensure_ascii=False), "```", "", "### Specificity audit", "", "```json", json.dumps(trial["audit"], indent=2, ensure_ascii=False), "```", ""])
    lines.extend(["## Review guidance", "", "Prioritize issues that recur across trials. Confirm each issue against the authoritative assignment and rubric. Revise source prose, rerun the harness, and retain reports only in approved local storage.", ""])
    return "\n".join(lines)


def run(root: Path, config_path: Path, client: MistralClient) -> Path:
    config = jsonc.load_and_validate(config_path)
    max_chars = int(config.get("max_input_chars", 60_000))
    instruction_path, instructions = read_source(root, config["instructions_file"], "instructions_file", max_chars)
    rubric_path, rubric = read_source(root, config["rubric_file"], "rubric_file", max_chars)
    context_parts = []
    context_paths = []
    for item in config.get("context_files", []):
        path, content = read_source(root, item, "context file", max_chars)
        context_paths.append(path)
        context_parts.append(f"SOURCE: {path.name}\n{content}")
    context = "\n\n".join(context_parts)
    complete_instructions = instructions
    if context:
        complete_instructions += "\n\nASSIGNMENT CONTEXT AND LINKED POLICIES\n" + context
    trials = []
    profiles = config["student_profiles"]
    base_seed = int(config.get("seed", 210))
    for index in range(int(config["trials"])):
        profile = profiles[index % len(profiles)]
        submission, student_meta = client.complete(
            student_messages(instructions, context, profile), seed=base_seed + index * 10,
            temperature=float(config["student_temperature"]), max_tokens=int(config["student_max_tokens"]),
        )
        grade, grade_meta = complete_json(
            client, grading_messages(complete_instructions, rubric, submission), stage="grading",
            seed=base_seed + index * 10 + 1,
            temperature=float(config["grader_temperature"]), max_tokens=int(config["analysis_max_tokens"]),
        )
        audit, audit_meta = complete_json(
            client, audit_messages(complete_instructions, rubric, config.get("expected_requirements", []), submission, grade),
            stage="specificity audit",
            seed=base_seed + index * 10 + 2, temperature=float(config["grader_temperature"]),
            max_tokens=int(config["analysis_max_tokens"]),
        )
        trials.append({"trial": index + 1, "student_profile": profile, "submission": submission,
                       "grade": grade, "audit": audit,
                       "api_metadata": {"student": student_meta, "grader": grade_meta, "auditor": audit_meta}})
    record = {
        "schema": "canvas-automation/assignment-rubric-qa/v1", "model": client.model,
        "source_sha256": {
            "instructions": hashlib.sha256(instruction_path.read_bytes()).hexdigest(),
            "rubric": hashlib.sha256(rubric_path.read_bytes()).hexdigest(),
            **{f"context:{path.name}": hashlib.sha256(path.read_bytes()).hexdigest() for path in context_paths},
        },
        "expected_requirements": config.get("expected_requirements", []), "trials": trials,
        "limitations": ["Model simulations are diagnostic examples, not predictions of individual students.", "Simulated grades require human review and must not be used as student grades.", "Repeated or cross-model testing is needed before treating a non-finding as evidence of clarity."],
    }
    out_dir = fresh_out_dir(resolve_out_base(root, config, "assignment-rubric-qa"), instruction_path.stem)
    (out_dir / "qa-results.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "qa-report.md").write_text(render_report(record), encoding="utf-8")
    provenance = {"schema": "canvas.provenance/v1", "command": "test-assignment-rubric", "model": client.model,
                  "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(), "source_sha256": record["source_sha256"],
                  "api_key_stored": False, "result": {"trials": len(trials), "report": "qa-report.md"}}
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=Path("commands/test-assignment-rubric.config.jsonc"))
    args = parser.parse_args()
    root, config_path = args.root.resolve(), args.config.resolve()
    try:
        config = jsonc.load_and_validate(config_path)
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key and sys.stdin.isatty():
            api_key = getpass.getpass("Mistral API key (input hidden): ").strip()
        if not api_key:
            raise MistralQAError("MISTRAL_API_KEY is not set. Run the macOS command to enter it privately, or set it only for this process.")
        client = MistralClient(
            api_key, api_url=config["api_url"], model=config["model"],
            timeout_seconds=int(config["timeout_seconds"]),
            retry_attempts=int(config.get("retry_attempts", 5)),
            retry_base_seconds=float(config.get("retry_base_seconds", 5)),
        )
        output = run(root, config_path, client)
        print(json.dumps({"output": str(output), "model": client.model}, indent=2))
        return 0
    except (MistralQAError, jsonc.ConfigError) as error:
        print(f"Assignment QA failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
