from pathlib import Path

from canvas_automation.test_forms import build_forms
from canvas_automation import cli


def test_pdf_forms_are_reproducible_in_content_and_support_versions(tmp_path):
    source = tmp_path / "pool.md"
    source.write_text(
        "[Paragraph.] Directions marker\n\n"
        "[Question.] Shared? [Answer.] Yes [Distractor.] No\n\n"
        "[Only Version A.] [Question.] A? [Answer.] Yes [Distractor.] No\n\n"
        "[Only Version B.] [Question.] B? [Answer.] Yes [Distractor.] No\n\n"
        "[Each version take 1 of the following options.]\n\n"
        "[Option.] [Question.] P1? [Answer.] Yes [Distractor.] No\n\n"
        "[Option.] [Question.] P2? [Answer.] Yes [Distractor.] No\n",
        encoding="utf-8",
    )
    first = build_forms(source, tmp_path / "one", "Test", 2, "seed")
    second = build_forms(source, tmp_path / "two", "Test", 2, "seed")
    assert [v["question_count"] for v in first["versions"]] == [3, 3]
    assert first["backend"] == "original-mcqer-javascript"
    assert first["versions"] == second["versions"]
    for name in (
        "test-form-A.pdf", "answer-key-A.pdf", "test-form-B.pdf", "answer-key-B.pdf",
        "test-form-A.docx", "answer-key-A.docx", "test-form-B.docx", "answer-key-B.docx",
    ):
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()
    from pypdf import PdfReader
    for label in "AB":
        text = " ".join(page.extract_text() or "" for page in PdfReader(tmp_path / "one" / f"test-form-{label}.pdf").pages)
        assert text.count("Directions marker") == 1


def test_cli_uses_config_fresh_output_and_provenance(tmp_path):
    import json
    source = tmp_path / "quiz.md"
    source.write_text("[Question.] Stem [Answer.] Yes [Distractor.] No [Distractor.] Maybe [Distractor.] Never")
    config = tmp_path / "forms.config.jsonc"
    config.write_text(json.dumps({"OUT_DIR": str(tmp_path / "out"), "source_file": str(source), "title": "Stored Test", "versions": 1, "seed": "7"}))
    assert cli.main(["build-test-forms", "--engine", str(tmp_path), "--config", str(config)]) == 0
    output = next((tmp_path / "out").iterdir())
    assert all((output / name).is_file() for name in (
        "test-form-A.pdf", "answer-key-A.pdf", "test-form-A.docx", "answer-key-A.docx",
        "manifest.json", "provenance.json",
    ))


def test_pdf_keeps_each_mcq_stem_and_all_options_on_one_page(tmp_path):
    from pypdf import PdfReader

    source = tmp_path / "pagination.md"
    blocks = []
    for number in range(1, 15):
        padding = "This deliberately long sentence exercises deterministic pagination. "
        blocks.append(
            f"[Question.] STEMMARK{number} {padding} "
            f"[Answer.] OPT{number}A {padding} "
            f"[Distractor.] OPT{number}B {padding} "
            f"[Distractor.] OPT{number}C {padding} "
            f"[Distractor.] OPT{number}D {padding}"
        )
    source.write_text("\n\n".join(blocks), encoding="utf-8")
    output = tmp_path / "forms"
    build_forms(source, output, "Pagination Test", 1, "seed")
    pages = [page.extract_text() or "" for page in PdfReader(output / "test-form-A.pdf").pages]
    assert len(pages) > 1
    for number in range(1, 15):
        containing = [page for page in pages if f"STEMMARK{number} " in page]
        assert len(containing) == 1
        assert all(f"OPT{number}{letter} " in containing[0] for letter in "ABCD")
