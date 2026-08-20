#!/usr/bin/env python3
"""Audit Testmaker stems for duplicated or conspicuously templated prose."""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canvas_automation.testmaker import parse_testmaker
from canvas_automation.test_quality import stem_grammar_issues, stem_reference_issues

DISCOURAGED = (
    "For this case", "Which course concept", "Which feature most clearly",
    "Which evaluative standard", "Which judgment uses the strongest evidence",
    "Which design plan best operationalizes", "Which proposal best incorporates",
    "A designer is working with",
)
SEMANTIC_RISK_PHRASES = (
    "What should the designer do next?",
    "Which response is most appropriate?",
    "Which action best applies the assigned method?",
    "assigned method", "assigned material", "course method", "according to the course",
    "in this course", "course material", "from the course", "from the readings",
)


def audit(path: Path) -> dict:
    parsed = parse_testmaker(path)
    stems = [question.stem for question in parsed.questions]
    exact = collections.Counter(re.sub(r"\s+", " ", stem).strip().casefold() for stem in stems)
    duplicate_stems = sorted(stem for stem, count in exact.items() if count > 1)
    discouraged = [stem for stem in stems if stem.startswith(DISCOURAGED)]
    semantic_risks = [stem for stem in stems if any(phrase in stem for phrase in SEMANTIC_RISK_PHRASES)]
    prefixes = collections.Counter(" ".join(stem.split()[:5]).casefold() for stem in stems)
    repeated_prefixes = {prefix: count for prefix, count in sorted(prefixes.items()) if count >= 5}
    grammar = [{"stem": stem, "issues": [{"code": code, "detail": detail} for code, detail in stem_grammar_issues(stem)]}
               for stem in stems if stem_grammar_issues(stem)]
    references = [{"stem": stem, "issues": [{"code": code, "detail": detail} for code, detail in stem_reference_issues(stem)]}
                  for stem in stems if stem_reference_issues(stem)]
    return {
        "schema": "testmaker-stem-style/v1", "source": str(path), "question_count": len(stems),
        "status": "PASS" if not duplicate_stems and not discouraged and not semantic_risks and not grammar and not references else "FAIL",
        "duplicate_stems": duplicate_stems, "discouraged_template_stems": discouraged,
        "semantic_rewording_risks": semantic_risks,
        "grammar_errors": grammar,
        "reference_errors": references,
        "repeated_five_word_prefixes_for_review": repeated_prefixes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    reports = [audit(path) for path in args.inputs]
    result = {"status": "PASS" if all(item["status"] == "PASS" for item in reports) else "FAIL",
              "reports": reports}
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
