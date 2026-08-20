#!/usr/bin/env python3
"""Audit private assessment coverage, downloads, Testmaker sources, and outputs."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canvas_automation.testmaker import Pool, parse_testmaker
from canvas_automation.test_quality import audit_quiz


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", type=Path, default=ROOT / "private/testmaking/assessment-blueprint.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "private/testmaking/testmaking-manifest.json")
    parser.add_argument("--record", type=Path, default=ROOT / "private/testmaking/audit-report.json")
    args = parser.parse_args()
    blueprint = json.loads(args.blueprint.read_text(encoding="utf-8"))
    if blueprint.get("schema") != "canvas-testmaking-blueprint/v1":
        raise ValueError("unsupported assessment blueprint schema")
    if not isinstance(blueprint.get("materials"), list) or not isinstance(blueprint.get("assessments"), list):
        raise ValueError("blueprint needs materials and assessments arrays")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = {item["key"]: item for item in manifest["assessments"]}
    downloads = json.loads((ROOT / "private/testmaking/materials/download-record.json").read_text(encoding="utf-8"))
    stored = {item["id"] for item in downloads["records"] if item["status"] == "stored"}
    errors = []; reports = []
    for assessment in blueprint["assessments"]:
        entry = entries.get(assessment["key"])
        if not entry:
            errors.append(f"missing manifest entry: {assessment['key']}"); continue
        parsed = parse_testmaker(ROOT / assessment["source"])
        quality = audit_quiz(parsed, assessment["question_count"], require_metadata=True,
                             exact_distractors=3, require_all_bloom=True)
        cited = {material for item in parsed.questions for material in item.material_ids}
        expected = set(assessment["material_ids"])
        if cited != expected:
            errors.append(f"{assessment['key']} material coverage differs: missing={sorted(expected-cited)} extra={sorted(cited-expected)}")
        if not expected <= stored:
            errors.append(f"{assessment['key']} cites unstored materials: {sorted(expected-stored)}")
        if len(parsed.questions) != assessment["candidate_count"]:
            errors.append(f"{assessment['key']} candidate count differs")
        if quality["errors"]:
            errors.append(f"{assessment['key']} quality errors: {quality['issues']}")
        if assessment["kind"] == "canvas-classic-quiz":
            pools = [item for item in parsed.items if isinstance(item, Pool)]
            if len(pools) != 10 or any(item.take != 1 or len(item.questions) != 2 for item in pools):
                errors.append(f"{assessment['key']} must have ten target-specific 1-of-2 pools")
            targets = []
            for pool in pools:
                pool_targets = {question.target_id for question in pool.questions}
                if None in pool_targets or len(pool_targets) != 1:
                    errors.append(f"{assessment['key']} has a pool without one shared [Target.] identifier")
                targets.extend(pool_targets)
            if len(targets) != len(set(targets)):
                errors.append(f"{assessment['key']} repeats a learning target across pools")
            start = datetime.fromisoformat(assessment["unlock_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(assessment["lock_at"].replace("Z", "+00:00"))
            if (end-start).total_seconds() != 86400:
                errors.append(f"{assessment['key']} window is not exactly 24 hours")
            if sum(assessment["bloom_draws"].values()) != 10:
                errors.append(f"{assessment['key']} Bloom draws do not total 10")
        else:
            if assessment.get("time_limit_minutes") != 90 or assessment["question_count"] != 60:
                errors.append("final exam must contain 60 MCQs in 90 minutes")
            if "1.5 minutes per question" not in assessment.get("instructions", ""):
                errors.append("final exam instructions omit 1.5 minutes per question")
        output_manifest = ROOT / "out/testmaking-authoring" / assessment["key"] / "manifest.json"
        if output_manifest.is_file():
            built = json.loads(output_manifest.read_text(encoding="utf-8"))
            if any(item["question_count"] != assessment["question_count"] for item in built["versions"]):
                errors.append(f"{assessment['key']} printable form count differs")
        reports.append({"key": assessment["key"], "candidate_count": len(parsed.questions),
                        "generated_count": quality.get("generated_question_count"),
                        "materials": sorted(cited), "quality_errors": quality["errors"]})
    handoff = (ROOT / "private/testmaking/llm-handoff/assessment-generation-spec.json").read_text(encoding="utf-8")
    if "/Users/" in handoff or "[Correct.]" in handoff or "answer-key" in handoff:
        errors.append("LLM handoff contains a local path or current answer-key material")
    result = {"schema": "canvas-assessment-suite-audit/v1", "status": "PASS" if not errors else "FAIL",
              "errors": errors, "assessments": reports,
              "download_summary": {key: downloads[key] for key in ("stored", "failed", "not_testable")}}
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
