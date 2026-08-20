#!/usr/bin/env python3
"""Validate a Testmaker source and write a machine-readable QA report."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canvas_automation.testmaker import parse_testmaker
from canvas_automation.test_quality import audit_quiz

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-questions", type=int)
    parser.add_argument("--assessment-ready", action="store_true", help="Require exactly three distractors, material IDs, and guaranteed coverage of all six Bloom levels")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = audit_quiz(parse_testmaker(args.input), args.expect_questions,
                        require_metadata=args.assessment_ready,
                        exact_distractors=3 if args.assessment_ready else None,
                        require_all_bloom=args.assessment_ready,
                        require_grammar=args.assessment_ready,
                        require_reference_resolution=args.assessment_ready); report["source"] = str(args.input)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True); args.json_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if report["errors"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
