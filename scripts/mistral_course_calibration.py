#!/usr/bin/env python3
"""Run auditable Mistral student/grader trials across authoritative course assessments."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from canvas_automation.util import fresh_out_dir
from mistral_assignment_qa import MistralClient, MistralQAError, run


PROFILES = [
    "Severely incomplete attempt: misunderstand the task, omit several central deliverables, and provide little assessable evidence.",
    "Limited novice: address the visible topic but use vague generalities, incomplete evidence, and weak execution.",
    "Developing student: satisfy basic requirements unevenly; include plausible work with important gaps and limited integration.",
    "Borderline competent student: complete most requirements, but make hurried choices, shallow analysis, and a few consequential errors.",
    "Competent student: meet the stated requirements with clear, workable evidence and ordinary undergraduate quality; avoid exceptional polish.",
    "Strong student: make thoughtful, well-supported decisions, integrate course concepts, and submit coherent work with minor limitations.",
    "Very strong student: demonstrate precise reasoning, effective iteration, and convincing evidence across nearly all criteria.",
    "Excellent student: produce unusually coherent, well-tested, well-documented work that exceeds ordinary expectations without adding irrelevant material.",
    "Exceptional student: produce original, rigorous, highly usable work with compelling evidence, careful limitations, and virtually no material weakness.",
]


def assignment_sources(root: Path) -> dict[str, str]:
    manifest = json.loads((root / "course/course-manifest.json").read_text(encoding="utf-8"))
    return {
        item["title"]: item["source"]
        for item in manifest["objects"]
        if item["kind"] in {"assignment", "discussion"}
    }


def normalized_score(grade: dict) -> float | None:
    score, maximum = grade.get("overall_score"), grade.get("maximum_score")
    if isinstance(score, (int, float)) and isinstance(maximum, (int, float)) and maximum > 0:
        return round(100 * float(score) / float(maximum), 2)
    return None


def report_markdown(summary: dict) -> str:
    lines = [
        "# Mistral course-assessment calibration", "",
        f"- Model: `{summary['model']}`",
        f"- Assessments: {summary['assessment_count']}",
        f"- Scored simulations: {summary['distribution']['count']}",
        f"- Mean: {summary['distribution']['mean']}",
        f"- Median: {summary['distribution']['median']}",
        "- Interpretation: diagnostic model simulations; never student grades or a mandated curve.", "",
        "## Assessment results", "",
        "| Assessment | Trials | Mean | Median | Range | Output |", "|---|---:|---:|---:|---:|---|",
    ]
    for item in summary["assessments"]:
        values = item["scores_percent"]
        value_range = f"{min(values):.1f}–{max(values):.1f}" if values else "n/a"
        lines.append(
            f"| {item['title']} | {len(values)} | {item['mean']} | {item['median']} | {value_range} | `{item['output']}` |"
        )
    lines.extend([
        "", "## Review rule", "",
        "Inspect recurring instruction ambiguities, rubric mismatches, and score compression. Revise only when a finding is supported by the source and the intended learning outcome. A target centre near 75% is a design diagnostic; criterion-referenced evidence determines actual grades.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--match", action="append", default=[], help="Run titles containing this text; repeatable")
    parser.add_argument("--trials", type=int, default=9)
    parser.add_argument("--model", default="mistral-small-latest")
    args = parser.parse_args()
    root = args.root.resolve()
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key and sys.stdin.isatty():
        api_key = getpass.getpass("Mistral API key (input hidden): ").strip()
    if not api_key:
        raise MistralQAError("MISTRAL_API_KEY is not set")

    sources = assignment_sources(root)
    rubric_manifest = json.loads((root / "course/rubric-manifest.json").read_text(encoding="utf-8"))
    selected = []
    for item in rubric_manifest["rubrics"]:
        title = item["assignment_title"]
        if args.match and not any(value.casefold() in title.casefold() for value in args.match):
            continue
        if title not in sources:
            raise ValueError(f"No authoritative assignment source for {title!r}")
        selected.append((title, sources[title], item["source"]))
    if not selected:
        raise ValueError("No assessments matched")

    output = fresh_out_dir(root / "out/course-development/mistral-calibration", "course-assessments")
    configs = output / "configs"
    configs.mkdir()
    client = MistralClient(
        api_key,
        api_url="https://api.mistral.ai/v1/chat/completions",
        model=args.model,
        timeout_seconds=180,
        retry_attempts=5,
        retry_base_seconds=5,
    )
    assessments = []
    all_scores = []
    for index, (title, instructions, rubric) in enumerate(selected):
        config = {
            "OUT_DIR": str(output / "assessment-runs"),
            "instructions_file": str(root / instructions),
            "rubric_file": str(root / rubric),
            "context_files": [],
            "expected_requirements": [],
            "student_profiles": PROFILES,
            "trials": args.trials,
            "seed": 2100 + index * 100,
            "model": args.model,
            "api_url": "https://api.mistral.ai/v1/chat/completions",
            "student_temperature": 0.45,
            "grader_temperature": 0.05,
            "student_max_tokens": 2600,
            "analysis_max_tokens": 2200,
            "max_input_chars": 60000,
            "timeout_seconds": 180,
            "retry_attempts": 5,
            "retry_base_seconds": 5,
        }
        config_path = configs / f"{index + 1:02d}.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"[{index + 1}/{len(selected)}] {title}", flush=True)
        run_output = run(root, config_path, client)
        result = json.loads((run_output / "qa-results.json").read_text(encoding="utf-8"))
        scores = [score for trial in result["trials"] if (score := normalized_score(trial["grade"])) is not None]
        all_scores.extend(scores)
        assessments.append({
            "title": title,
            "instructions": instructions,
            "rubric": rubric,
            "output": str(run_output.relative_to(output)),
            "scores_percent": scores,
            "mean": round(statistics.mean(scores), 2) if scores else None,
            "median": round(statistics.median(scores), 2) if scores else None,
        })
    distribution = {
        "count": len(all_scores),
        "mean": round(statistics.mean(all_scores), 2) if all_scores else None,
        "median": round(statistics.median(all_scores), 2) if all_scores else None,
        "minimum": min(all_scores) if all_scores else None,
        "maximum": max(all_scores) if all_scores else None,
        "a_plus_95_or_higher": sum(score >= 95 for score in all_scores),
        "f_below_50": sum(score < 50 for score in all_scores),
    }
    summary = {
        "schema": "canvas-automation/mistral-course-calibration/v1",
        "model": args.model,
        "assessment_count": len(assessments),
        "profiles": PROFILES,
        "distribution": distribution,
        "assessments": assessments,
        "limitations": [
            "Simulations test assessment boundaries and do not predict actual students.",
            "Actual grading remains criterion-referenced; no score or letter-grade quota is imposed.",
            "Mistral may lack the capability to create or evaluate complete playable artifacts.",
        ],
    }
    (output / "course-calibration.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "course-calibration.md").write_text(report_markdown(summary), encoding="utf-8")
    print(json.dumps({"output": str(output), "distribution": distribution}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
