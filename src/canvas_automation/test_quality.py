"""Deterministic structural and editorial QA for Testmaker question sources."""
from __future__ import annotations

from collections import Counter

from .testmaker import ParsedQuiz, Pool, Question, for_version, versions_in


def audit_question(question: Question, location: str) -> list[dict]:
    issues = []
    if question.text_only:
        return issues
    normalized = [(value or "").strip().casefold() for value in [question.answer, *question.distractors]]
    if question.distractors and len(question.distractors) < 3:
        issues.append({"severity": "error", "location": location, "code": "too-few-distractors", "detail": "multiple-choice questions require at least three distractors"})
    if any(value and count > 1 for value, count in Counter(normalized).items()):
        issues.append({"severity": "error", "location": location, "code": "duplicate-option", "detail": "answer choices must be distinct"})
    if question.distractors:
        answer_length = len(question.answer.split())
        lengths = [len(value.split()) for value in question.distractors]
        if lengths and answer_length >= 8 and answer_length > max(lengths) * 2:
            issues.append({"severity": "warning", "location": location, "code": "answer-length-tell", "detail": "the correct answer is substantially longer than every distractor"})
    return issues


def audit_quiz(parsed: ParsedQuiz, expected_questions: int | None = None) -> dict:
    issues = []
    for index, entry in enumerate(parsed.items, 1):
        questions = entry.questions if isinstance(entry, Pool) else [entry]
        for q_index, question in enumerate(questions, 1):
            location = f"item {index}.{q_index}" if isinstance(entry, Pool) else f"item {index}"
            issues.extend(audit_question(question, location))
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
    result = {"generated_question_counts": counts, "errors": sum(i["severity"] == "error" for i in issues), "warnings": sum(i["severity"] == "warning" for i in issues), "issues": issues}
    if len(set(counts.values())) == 1: result["generated_question_count"] = next(iter(counts.values()))
    return result
