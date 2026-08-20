from canvas_automation.testmaker import parse_testmaker
from canvas_automation.test_quality import audit_quiz

def test_quality_accepts_four_distinct_choices_and_count(tmp_path):
    source = tmp_path / "questions.md"
    source.write_text("[Question.] Stem\n[Answer.] Yes\n[Distractor.] No\n[Distractor.] Maybe\n[Distractor.] Never")
    parsed = parse_testmaker(source)
    report = audit_quiz(parsed, expected_questions=1)
    assert report["errors"] == 0 and report["generated_question_count"] == 1

def test_quality_finds_duplicate_short_options_and_wrong_count(tmp_path):
    source = tmp_path / "questions.md"
    source.write_text("[Question.] Stem\n[Answer.] Same\n[Distractor.] same\n[Distractor.] Other")
    parsed = parse_testmaker(source)
    report = audit_quiz(parsed, expected_questions=10)
    assert report["errors"] == 3
    assert {issue["code"] for issue in report["issues"]} == {"too-few-distractors", "duplicate-option", "question-count"}

def test_quality_counts_each_only_version_separately(tmp_path):
    source=tmp_path/"versions.md"; source.write_text("[Question.] Shared\n\n[Only Version A.] [Question.] A only\n\n[Only Version B.] [Question.] B only")
    report=audit_quiz(parse_testmaker(source),expected_questions=2)
    assert report["errors"]==0 and report["generated_question_counts"]=={"A":2,"B":2}


def test_assessment_ready_requires_and_guarantees_all_bloom_levels(tmp_path):
    source = tmp_path / "balanced.md"
    blocks = []
    for level in ("Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"):
        blocks.append("[Each version take 1 of the following options.]")
        for number in (1, 2):
            blocks.append(
                f"[Option.] [Question.] {level} {number}? [Correct.] A "
                f"[Distractor.] B [Distractor.] C [Distractor.] D "
                f"[Bloom.] {level} [Material.] W01-R1"
            )
    source.write_text("\n\n".join(blocks), encoding="utf-8")
    report = audit_quiz(parse_testmaker(source), expected_questions=6,
                        require_metadata=True, exact_distractors=3,
                        require_all_bloom=True)
    assert report["errors"] == 0


def test_grammar_gate_rejects_generator_fragment_join_and_double_punctuation(tmp_path):
    source = tmp_path / "awkward.md"
    source.write_text(
        "[Question.] For this case—Fans build maps—which action works.? "
        "[Correct.] A [Distractor.] B [Distractor.] C [Distractor.] D "
        "[Bloom.] Apply [Material.] W01-R1"
    )
    report = audit_quiz(parse_testmaker(source), require_grammar=True)
    assert {item["code"] for item in report["issues"]} == {
        "template-fragment-join", "double-terminal-punctuation"
    }


def test_reference_gate_requires_antecedents_within_each_question(tmp_path):
    source = tmp_path / "references.md"
    source.write_text(
        "[Question.] Which concept treats the recording as a constructed object? "
        "[Correct.] A [Distractor.] B [Distractor.] C [Distractor.] D\n\n"
        "[Question.] An actual-play recording includes deliberate edits. Which concept treats the recording as constructed? "
        "[Correct.] A [Distractor.] B [Distractor.] C [Distractor.] D"
    )
    report = audit_quiz(parse_testmaker(source), require_reference_resolution=True)
    errors = [item for item in report["issues"] if item["code"] == "unresolved-definite-reference"]
    assert len(errors) == 1 and errors[0]["location"] == "item 1"
