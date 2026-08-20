#!/usr/bin/env python3
"""Test whether rubrics separate exemplary existing games from broken work."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from canvas_automation import jsonc
from canvas_automation.util import fresh_out_dir, resolve_path
from mistral_assignment_qa import MistralClient, MistralQAError, complete_json


def read_case_text(root: Path, case: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if "dossier_file" in case:
        path = resolve_path(root, case["dossier_file"])
        return path.read_text(encoding="utf-8"), {
            "source": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
        }
    path = resolve_path(root, case["qa_results_file"])
    record = json.loads(path.read_text(encoding="utf-8"))
    trial_number = int(case["trial"])
    trial = next((item for item in record["trials"] if int(item["trial"]) == trial_number), None)
    if trial is None:
        raise MistralQAError(f"Trial {trial_number} is absent from {path}")
    return trial["submission"], {
        "source": str(path.relative_to(root)), "trial": trial_number,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "submission_sha256": hashlib.sha256(trial["submission"].encode()).hexdigest(),
    }


def select_rubric(rubric: dict[str, Any], descriptions: list[str] | None) -> dict[str, Any]:
    if descriptions is None:
        return rubric
    wanted = set(descriptions)
    criteria = [item for item in rubric["criteria"] if item["description"] in wanted]
    found = {item["description"] for item in criteria}
    if found != wanted:
        raise MistralQAError(f"Unknown portable criteria: {sorted(wanted - found)}")
    return {**rubric, "title": rubric["title"] + " — portable design criteria",
            "points_possible": sum(float(item["points"]) for item in criteria), "criteria": criteria}


def grade_messages(rubric: dict[str, Any], evidence: str, *, scope: str) -> list[dict[str, str]]:
    shape = {
        "overall_score": "number", "maximum_score": "number",
        "criterion_results": [{"criterion": "string", "score": "number", "evidence": "string", "reason": "string", "confidence": "low|medium|high"}],
        "missing_evidence": ["string"], "feedback": "string",
    }
    return [
        {"role": "system", "content": (
            "Act as a strict criterion-referenced grader. Score every supplied criterion only from the evidence dossier. "
            "Use only rating point values in the rubric. Do not reward reputation, infer absent evidence, or invent criteria. "
            "An exemplary published game can earn full marks when the dossier demonstrates a criterion. "
            "A broken or incomplete artifact must receive zero where evidence is absent or contradicts the criterion. Return one JSON object."
        )},
        {"role": "user", "content": f"Return JSON shaped like:\n{json.dumps(shape)}\n\nSCOPE\n{scope}\n\nRUBRIC\n{json.dumps(rubric)}\n\nEVIDENCE DOSSIER\n{evidence}"},
    ]


def percent(grade: dict[str, Any]) -> float:
    return round(100 * float(grade["overall_score"]) / float(grade["maximum_score"]), 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "commands/mistral-rubric-discrimination.config.jsonc")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = jsonc.load_and_validate(config_path)
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key and sys.stdin.isatty():
        api_key = getpass.getpass("Mistral API key (input hidden): ").strip()
    if not api_key:
        raise MistralQAError("MISTRAL_API_KEY is not set")
    client = MistralClient(api_key, api_url=config["api_url"], model=config["model"],
                           timeout_seconds=int(config["timeout_seconds"]))
    output = fresh_out_dir(resolve_path(ROOT, config["OUT_DIR"]), "rubric-endpoints")
    results = []
    for index, case in enumerate(config["cases"]):
        evidence, provenance = read_case_text(ROOT, case)
        rubric_path = resolve_path(ROOT, case["rubric_file"])
        rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
        result: dict[str, Any] = {"key": case["key"], "kind": case["kind"], "evidence": provenance,
                                  "rubric": str(rubric_path.relative_to(ROOT))}
        case_dir = output / case["key"]
        case_dir.mkdir()
        (case_dir / "evaluated-evidence.txt").write_text(evidence, encoding="utf-8")
        for offset, scope in enumerate(("full", "portable_design")):
            selected = select_rubric(rubric, None if scope == "full" else case["portable_criteria"])
            grade, metadata = complete_json(
                client, grade_messages(selected, evidence, scope=scope), stage=f"{case['key']} {scope}",
                seed=8400 + index * 20 + offset, temperature=0.0,
                max_tokens=int(config["analysis_max_tokens"]),
            )
            grade["percent"] = percent(grade)
            result[scope] = grade
            result.setdefault("api_metadata", {})[scope] = metadata
        results.append(result)
        print(f"{case['key']}: full {result['full']['percent']}%; portable {result['portable_design']['percent']}%", flush=True)
    summary = {
        "schema": "canvas-automation/rubric-discrimination/v1", "model": config["model"],
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(), "results": results,
        "interpretation": "Endpoint diagnostic only. Existing-game portable scores omit student-specific contribution criteria; model grades require human review.",
    }
    (output / "results.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
