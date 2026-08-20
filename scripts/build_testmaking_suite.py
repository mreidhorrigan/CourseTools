#!/usr/bin/env python3
"""Build private Testmaker sources from a blueprint and concept specification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create")


def question(stem, answer, distractors, level, materials, target_id):
    if len(distractors) != 3 or len({answer, *distractors}) != 4:
        raise ValueError(f"invalid choices for {level}: {stem}")
    return {"stem": stem, "answer": answer, "distractors": distractors,
            "bloom": level, "materials": materials, "target": target_id}


def options(concepts, field, correct):
    return [item[field] for item in concepts if item is not correct]


def _sentence(value):
    return value.strip().rstrip(".?!")


def _feature_question(value):
    value = _sentence(value)
    if value.startswith("It "):
        return "Which concept " + value[3:] + "?"
    elif value.startswith("Its "):
        return "Which concept's " + value[4:] + "?"
    return "Which concept is characterized by " + value[0].lower() + value[1:] + "?"


def integrated_stems(level, concept):
    """Return two natural stems without exposing the generator's template vocabulary."""
    term = concept["term"]
    example = _sentence(concept["example"])
    variant = int(hashlib.sha256(f"stem-style-v1:{level}:{term}".encode()).hexdigest()[:8], 16) % 4
    if level == "Remember":
        return (f"Which definition best captures {term}?",
                f"What does {term} mean?")
    if level == "Understand":
        return (f"{example}. Which concept best accounts for this example?",
                _feature_question(concept["distinction"]))
    if level == "Apply":
        first = (
            f"A designer wants to work with {term}. Which action would put {term} into practice?",
            f"To apply {term}, which action should a design team take?",
            f"A team is using {term} to guide its work. Which action most directly applies {term}?",
            f"Which action would most effectively apply {term} during design?",
        )[variant]
        second = (
            f"{example}. Which response best analyzes this example through {term}?",
            f"Consider this situation: {example}. Which analytical response most effectively uses {term} to examine the situation?",
            f"{example}. How would an analysis grounded in {term} address this example?",
            f"The following example calls for analysis using {term}: {example}. What should that analysis examine?",
        )[variant]
        return first, second
    if level == "Analyze":
        return (
            (f"What distinguishes {term} from the related course concepts?",
             f"Which comparison most accurately isolates the defining feature of {term}?"),
            (f"How does {term} differ from related concepts?",
             f"Which statement identifies the analytical boundary around {term}?"),
            (f"What is the defining analytical feature of {term}?",
             f"Which distinction places {term} correctly among the course concepts?"),
            (f"An analysis invokes {term}. Which feature makes that classification precise?",
             f"Which comparison best differentiates {term} from neighboring ideas?"),
        )[variant]
    if level == "Evaluate":
        return (
            (f"A researcher is evaluating {term}. Which approach would produce the strongest judgment?",
             f"{example}. Which criterion offers the soundest evaluation of this case?"),
            (f"Which evidence would support the most defensible evaluation of {term}?",
             f"Consider this case: {example}. Which evaluative response is best supported?"),
            (f"What standard should guide a rigorous assessment of {term}?",
             f"{example}. How should this case be evaluated?"),
            (f"An evaluator makes a claim about {term}. Which method provides the strongest basis for it?",
             f"The evidence shows the following: {example}. Which judgment is most defensible?"),
        )[variant]
    return (
        (f"A project team wants to put {term} into practice. Which proposal does so most effectively?",
         f"Which project brief most effectively realizes {term}?"),
        (f"Which proposed project makes productive use of {term}?",
         f"A team is designing around {term}. Which plan translates {term} into workable form?"),
        (f"How could a new game or study operationalize {term}?",
         f"Which design specification turns {term} into a testable project?"),
        (f"A proposal claims to implement {term}. Which plan best supports that claim?",
         f"Which project design gives {term} the clearest practical expression?"),
    )[variant]


def generate_candidates(assessment, concepts):
    if len(concepts) != 4:
        raise ValueError(f"{assessment['key']} requires exactly four concept records")
    result = {level: [] for level in LEVELS}
    # Each tuple becomes one target-specific 1-of-2 pool. Across the ten pools,
    # the Bloom distribution remains 1/2/2/2/2/1.
    slots = [
        ("Remember", 0),
        ("Understand", 1), ("Understand", 2),
        ("Apply", 3), ("Apply", 0),
        ("Analyze", 1), ("Analyze", 2),
        ("Evaluate", 3), ("Evaluate", 0),
        ("Create", 1),
    ]
    level_counts = {level: 0 for level in LEVELS}
    for level, concept_index in slots:
        level_counts[level] += 1
        target_id = f"{assessment['key']}:{level.casefold()}-{level_counts[level]}"
        concept = concepts[concept_index]
        field = {"Remember": "definition", "Understand": "term", "Apply": "application",
                 "Analyze": "distinction", "Evaluate": "evaluation", "Create": "design"}[level]
        stems = integrated_stems(level, concept)
        for stem in stems:
            result[level].append(question(
                stem, concept[field], options(concepts, field, concept),
                level, concept["material_ids"], target_id))
    expected = {level: assessment["bloom_draws"][level] * 2 for level in LEVELS}
    actual = {level: len(items) for level, items in result.items()}
    if actual != expected:
        raise ValueError(f"{assessment['key']} candidate balance {actual} != {expected}")
    return result


def render_question(item, option=False):
    prefix = "[Option.] " if option else ""
    tags = [f"[Question.] {item['stem']}", f"[Correct.] {item['answer']}"]
    tags.extend(f"[Distractor.] {value}" for value in item["distractors"])
    tags.extend((f"[Bloom.] {item['bloom']}", f"[Material.] {', '.join(item['materials'])}",
                 f"[Target.] {item['target']}"))
    return prefix + " ".join(tags)


def render_quiz(assessment, candidates):
    blocks = []
    for level in LEVELS:
        values = candidates[level]
        for offset in range(0, len(values), 2):
            blocks.append("[Each version take 1 of the following options.]")
            blocks.extend(render_question(item, option=True) for item in values[offset:offset + 2])
    return "\n\n".join(blocks) + "\n"


def final_selection(candidate_sets, required_materials, count=10):
    all_candidates = [item for groups in candidate_sets.values() for values in groups.values() for item in values]
    ranked = sorted(all_candidates, key=lambda item: hashlib.sha256(
        f"final-selection-v2:{item['bloom']}:{item['target']}:{item['stem']}".encode()).hexdigest())
    selected = []
    level_counts = {level: 0 for level in LEVELS}
    needed = set(required_materials)

    def coverage(items):
        return {material for item in items for material in item["materials"]}

    # Cover every required source first while respecting the ten-per-level cap.
    while needed:
        candidates = [item for item in ranked if item not in selected
                      and level_counts[item["bloom"]] < count
                      and needed.intersection(item["materials"])]
        if not candidates:
            raise ValueError(f"no capacity to cover final-exam materials: {sorted(needed)}")
        candidate = max(candidates, key=lambda item: (
            len(needed.intersection(item["materials"])),
            -ranked.index(item),
        ))
        selected.append(candidate)
        level_counts[candidate["bloom"]] += 1
        needed -= set(candidate["materials"])

    # Fill every Bloom level deterministically, preferring unused targets.
    for level in LEVELS:
        while level_counts[level] < count:
            used_targets = {item["target"] for item in selected}
            candidate = next((item for item in ranked if item["bloom"] == level
                              and item not in selected and item["target"] not in used_targets), None)
            if candidate is None:
                candidate = next((item for item in ranked if item["bloom"] == level
                                  and item not in selected), None)
            if candidate is None:
                raise ValueError(f"not enough {level} candidates for final exam")
            selected.append(candidate)
            level_counts[level] += 1
    still_missing = set(required_materials) - coverage(selected)
    if still_missing:
        raise ValueError(f"final-exam coverage missing: {sorted(still_missing)}")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", type=Path, default=ROOT / "private/testmaking/assessment-blueprint.json")
    parser.add_argument("--concepts", type=Path, default=ROOT / "private/testmaking/question-concepts.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "private/testmaking/testmaking-manifest.json")
    args = parser.parse_args()
    blueprint = json.loads(args.blueprint.read_text(encoding="utf-8"))
    concept_spec = json.loads(args.concepts.read_text(encoding="utf-8"))
    previous = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.exists() else {}
    prior_entries = previous.get("assessments", previous.get("quizzes", []))
    live_ids = {item["key"]: item.get("canvas_quiz_id") for item in prior_entries}
    by_key = {item["key"]: item for item in blueprint["assessments"]}
    candidate_sets = {}
    entries = []
    for assessment in blueprint["assessments"]:
        if assessment["kind"] != "canvas-classic-quiz":
            continue
        candidates = generate_candidates(assessment, concept_spec[assessment["key"]])
        candidate_sets[assessment["key"]] = candidates
        target = ROOT / assessment["source"]; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_quiz(assessment, candidates), encoding="utf-8")
        entries.append({"key": assessment["key"], "title": assessment["title"],
                        "kind": assessment["kind"], "canvas_quiz_id": live_ids.get(assessment["key"]),
                        "source": assessment["source"], "expected_questions": assessment["question_count"],
                        "candidate_count": assessment["candidate_count"],
                        "pdf": {"title": assessment["title"], "versions": 3, "seed": "1"},
                        # Course-authoring owns prose and compiled inline styles. Testmaking
                        # owns assessment behavior, dates, question groups, and questions.
                        "canvas": {"time_limit": assessment["time_limit_minutes"], "allowed_attempts": 1,
                                   "shuffle_answers": True, "one_question_at_a_time": True,
                                   "show_correct_answers": False, "published": True,
                                   "unlock_at": assessment["unlock_at"], "due_at": assessment["lock_at"],
                                   "lock_at": assessment["lock_at"]}})
    final = by_key["final-exam"]
    final_questions = final_selection(candidate_sets, final["material_ids"])
    final_target = ROOT / final["source"]
    final_target.write_text("[Paragraph.] " + final["instructions"] + "\n\n" +
                            "\n\n".join(render_question(item) for item in final_questions) + "\n",
                            encoding="utf-8")
    entries.append({"key": final["key"], "title": final["title"], "kind": final["kind"],
                    "source": final["source"], "expected_questions": 60, "candidate_count": 60,
                    "pdf": {"title": final["title"] + " — 60 MCQs — 90 minutes", "versions": 3, "seed": "1"},
                    "canvas": None})
    manifest = {"schema": "canvas-testmaking-authoring/v2", "course_id": blueprint["course"]["canvas_course_id"],
                "requires_reinitialization": False, "source_format": "Testmaker Markdown",
                "assessments": entries}
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff = ROOT / "private/testmaking/llm-handoff/assessment-generation-spec.json"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    public_materials = [{key: item[key] for key in ("id", "week", "title", "url", "rights", "testable") if key in item}
                        for item in blueprint["materials"] if item.get("testable")]
    public_assessments = [{key: value for key, value in item.items()
                           if key not in {"source", "canvas_quiz_id"}}
                          for item in blueprint["assessments"]]
    handoff.write_text(json.dumps({"schema": "canvas-testmaking-llm-handoff/v1",
        "instructions": {"format": "Testmaker Markdown", "choices": "one correct answer and exactly three distinct plausible distractors", "bloom_levels": LEVELS,
                         "quiz_pooling": "ten target-specific Classic Quiz groups; draw one from each two-question group; group Bloom levels total 1/2/2/2/2/1",
                         "final_exam": "60 MCQs, 90 minutes, 1.5 minutes per question, ten questions at each Bloom level",
                         "grounding": "cite one or more supplied material IDs on every question; do not invent claims",
                         "construct_rule": "test the ideas, evidence, and reasoning taught in the course; do not test whether a method, source, phrase, or fact was assigned or belonged to the course",
                         "rewording_rule": "integrate scenarios grammatically, preserve the intellectual construct and answer key, avoid vague course-membership phrases, and run grammar and stem-style audits after rewriting"},
        "materials": public_materials, "assessments": public_assessments,
        "concepts": concept_spec}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"assessments": len(entries), "quiz_candidates": sum(sum(len(v) for v in groups.values()) for groups in candidate_sets.values()), "final_questions": len(final_questions), "manifest": str(args.manifest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
