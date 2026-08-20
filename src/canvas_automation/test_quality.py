"""Deterministic structural and editorial QA for Testmaker question sources."""
from __future__ import annotations

from collections import Counter
import re

from .testmaker import ParsedQuiz, Pool, Question, for_version, versions_in

BLOOM_LEVELS = ("remember", "understand", "apply", "analyze", "evaluate", "create")


def stem_grammar_issues(stem: str) -> list[tuple[str, str]]:
    """Return deterministic errors for grammar defects common to generated stems."""
    issues = []
    if not stem.endswith("?"):
        issues.append(("stem-terminal-punctuation", "question stem must end with a question mark"))
    if re.search(r"[.?!]\?$", stem):
        issues.append(("double-terminal-punctuation", "question stem has duplicated terminal punctuation"))
    if re.match(r"^For this case[—:-]\s*[A-Z]", stem):
        issues.append(("template-fragment-join", "rewrite the capitalized scenario as integrated prose"))
    if re.match(r"^Which course concept (?:best explains this example|is identified by this feature):", stem):
        issues.append(("template-fragment-join", "integrate the example or feature into a grammatical question"))
    if stem and not stem[0].isupper():
        issues.append(("stem-capitalization", "question stem must begin with a capital letter"))
    if re.search(r"\s{2,}", stem):
        issues.append(("stem-whitespace", "question stem contains repeated whitespace"))
    return issues


_REFERENCE_TARGETS = ("recording", "method", "concept", "system", "mechanism", "artifact")


def stem_reference_issues(stem: str) -> list[tuple[str, str]]:
    """Flag conservative cases whose referent is absent from the same stem."""
    issues = []
    if re.match(r"^(?:It|Its|They|Their|This|That|These|Those|Here|There)\b", stem):
        issues.append(("unresolved-opening-reference", "stem begins with a pronoun or indexical whose referent is absent"))
    lowered = stem.casefold()
    for phrase in ("this concept", "that concept", "presented here", "described above", "the former", "the latter"):
        if phrase in lowered:
            issues.append(("unresolved-indexical", f"replace `{phrase}` with its explicit referent"))
    for noun in _REFERENCE_TARGETS:
        for match in re.finditer(rf"\bthe {noun}\b", lowered):
            earlier = lowered[:match.start()]
            if not re.search(rf"\b(?:a|an|this|that|each|one|named|specific) {noun}\b|\b{noun}s?\b", earlier):
                issues.append(("unresolved-definite-reference", f"define `{noun}` before referring to `the {noun}`"))
                break
    return issues


def audit_question(question: Question, location: str, *, require_metadata=False,
                   exact_distractors: int | None = None, require_grammar=False,
                   require_reference_resolution=False) -> list[dict]:
    issues = []
    if question.text_only:
        return issues
    if require_grammar:
        issues.extend({"severity": "error", "location": location, "code": code, "detail": detail}
                      for code, detail in stem_grammar_issues(question.stem))
    if require_reference_resolution:
        issues.extend({"severity": "error", "location": location, "code": code, "detail": detail}
                      for code, detail in stem_reference_issues(question.stem))
    normalized = [(value or "").strip().casefold() for value in [question.answer, *question.distractors]]
    if question.distractors and len(question.distractors) < 3:
        issues.append({"severity": "error", "location": location, "code": "too-few-distractors", "detail": "multiple-choice questions require at least three distractors"})
    if exact_distractors is not None and len(question.distractors) != exact_distractors:
        issues.append({"severity": "error", "location": location, "code": "distractor-count", "detail": f"question has {len(question.distractors)} distractors; expected exactly {exact_distractors}"})
    if require_metadata and (question.bloom_level or "").casefold() not in BLOOM_LEVELS:
        issues.append({"severity": "error", "location": location, "code": "bloom-level", "detail": "question needs one Bloom level: " + ", ".join(BLOOM_LEVELS)})
    if require_metadata and not question.material_ids:
        issues.append({"severity": "error", "location": location, "code": "material-coverage", "detail": "question needs at least one [Material.] identifier"})
    if any(value and count > 1 for value, count in Counter(normalized).items()):
        issues.append({"severity": "error", "location": location, "code": "duplicate-option", "detail": "answer choices must be distinct"})
    if question.distractors:
        answer_length = len(question.answer.split())
        lengths = [len(value.split()) for value in question.distractors]
        if lengths and answer_length >= 8 and answer_length > max(lengths) * 2:
            issues.append({"severity": "warning", "location": location, "code": "answer-length-tell", "detail": "the correct answer is substantially longer than every distractor"})
    return issues


def audit_quiz(parsed: ParsedQuiz, expected_questions: int | None = None, *,
               require_metadata=False, exact_distractors: int | None = None,
               require_all_bloom=False, require_grammar=False,
               require_reference_resolution=False) -> dict:
    issues = []
    for index, entry in enumerate(parsed.items, 1):
        questions = entry.questions if isinstance(entry, Pool) else [entry]
        for q_index, question in enumerate(questions, 1):
            location = f"item {index}.{q_index}" if isinstance(entry, Pool) else f"item {index}"
            issues.extend(audit_question(question, location, require_metadata=require_metadata,
                                         exact_distractors=exact_distractors,
                                         require_grammar=require_grammar,
                                         require_reference_resolution=require_reference_resolution))
        if isinstance(entry, Pool) and entry.take > len(entry.questions):
            issues.append({"severity": "error", "location": f"item {index}", "code": "pool-too-small", "detail": f"pool takes {entry.take} from only {len(entry.questions)} questions"})
    labels = versions_in(parsed) or [None]
    counts = {}
    for label in labels:
        selected = for_version(parsed, label) if label else parsed
        count = sum(item.take if isinstance(item, Pool) and not item.scramble_all else len(item.questions) if isinstance(item, Pool) else 0 if item.text_only else 1 for item in selected.items)
        counts[label or "shared"] = count
        if expected_questions is not None and count != expected_questions:
            location = f"version {label}" if label else "quiz"
            issues.append({"severity": "error", "location": location, "code": "question-count", "detail": f"generated form has {count} questions; expected {expected_questions}"})
        if require_all_bloom:
            guaranteed = set()
            for item in selected.items:
                if isinstance(item, Pool):
                    levels = {(q.bloom_level or "").casefold() for q in item.questions}
                    if item.take and len(levels) == 1:
                        guaranteed.update(levels)
                elif not item.text_only:
                    guaranteed.add((item.bloom_level or "").casefold())
            missing = [level for level in BLOOM_LEVELS if level not in guaranteed]
            if missing:
                issues.append({"severity": "error", "location": f"version {label}" if label else "quiz", "code": "bloom-coverage", "detail": "generated form does not guarantee: " + ", ".join(missing)})
    result = {"generated_question_counts": counts, "errors": sum(i["severity"] == "error" for i in issues), "warnings": sum(i["severity"] == "warning" for i in issues), "issues": issues}
    if len(set(counts.values())) == 1: result["generated_question_count"] = next(iter(counts.values()))
    return result
