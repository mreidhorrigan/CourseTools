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
