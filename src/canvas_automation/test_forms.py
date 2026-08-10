"""Deterministic printable test forms from the same Testmaker source used by Canvas."""
from __future__ import annotations

import hashlib
import json
import random
from functools import partial
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab import rl_config
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.pdfgen.canvas import Canvas

from .testmaker import ParsedQuiz, Pool, Question, for_version, parse_testmaker

LABELS = "ABCDE"


def _seed(source: Path, label: str, seed: str) -> int:
    material = source.read_bytes() + b"\0" + label.encode() + b"\0" + seed.encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def select_questions(parsed: ParsedQuiz, label: str, rng: random.Random) -> list[Question]:
    selected = []
    for entry in for_version(parsed, label).items:
        if isinstance(entry, Pool):
            candidates = list(entry.questions); rng.shuffle(candidates)
            selected.extend(candidates if entry.scramble_all else candidates[:entry.take])
        else:
            selected.append(entry)
    return selected


def _option_order(question: Question, rng: random.Random):
    options = [(question.answer, True)] + [(value, False) for value in question.distractors]
    rng.shuffle(options)
    return options


def _pdf(path: Path, title: str, label: str, questions: list[Question], rng: random.Random, answer_key: bool):
    rl_config.invariant = 1
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("TestTitle", parent=styles["Title"], alignment=TA_CENTER, spaceAfter=12)
    body = styles["BodyText"]; body.spaceAfter = 5
    story = [Paragraph(title, heading), Paragraph(f"Version {label}", heading)]
    if not answer_key:
        story.extend([Paragraph("Name: ____________________________________", body), Spacer(1, 0.12 * inch)])
    for number, question in enumerate(questions, 1):
        if question.text_only:
            story.extend([Paragraph(question.stem, body), Spacer(1, 0.08 * inch)])
            continue
        story.append(Paragraph(f"<b>{number}.</b> {question.stem}", body))
        if question.distractors:
            options = _option_order(question, rng)
            for index, (value, correct) in enumerate(options):
                suffix = " <b>✓</b>" if answer_key and correct else ""
                story.append(Paragraph(f"{chr(65 + index)}. {value}{suffix}", body))
        else:
            story.extend([Spacer(1, 0.7 * inch), Paragraph("________________________________________________________________", body)])
        story.append(Spacer(1, 0.1 * inch))
    doc = SimpleDocTemplate(str(path), pagesize=letter, rightMargin=0.65*inch, leftMargin=0.65*inch, topMargin=0.6*inch, bottomMargin=0.6*inch, title=f"{title} Version {label}")
    doc.build(story, canvasmaker=partial(Canvas, invariant=1))


def build_forms(source: Path, output: Path, title: str, versions: int = 3, seed: str = "1") -> dict:
    if not 1 <= versions <= len(LABELS):
        raise ValueError("versions must be between 1 and 5")
    parsed = parse_testmaker(source); output.mkdir(parents=True, exist_ok=True)
    records = []
    for label in LABELS[:versions]:
        form_rng = random.Random(_seed(source, label, seed))
        questions = select_questions(parsed, label, form_rng)
        form = output / f"test-form-{label}.pdf"; key = output / f"answer-key-{label}.pdf"
        _pdf(form, title, label, questions, random.Random(_seed(source, label, seed)), False)
        _pdf(key, title + " Answer Key", label, questions, random.Random(_seed(source, label, seed)), True)
        records.append({"version": label, "question_count": sum(not q.text_only for q in questions), "test_form": form.name, "answer_key": key.name})
    manifest = {"schema_version": 1, "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "seed": seed, "title": title, "versions": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
