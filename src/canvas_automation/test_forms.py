"""Build deterministic printable forms with Testmaker's original MCQer renderer."""
from __future__ import annotations

import hashlib
import html
import json
import random
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ByteStringObject

from .testmaker import ParsedQuiz, Pool, Question, for_version, parse_testmaker

LABELS = "ABCDE"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RENDERER = PROJECT_ROOT / "vendor" / "testmaker-mcqer" / "mcqer.js"
RENDERER_PACKAGE = RENDERER.parent / "package.json"


def _seed(source: Path, label: str, seed: str) -> int:
    material = source.read_bytes() + b"\0" + label.encode() + b"\0" + seed.encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def select_questions(parsed: ParsedQuiz, label: str, rng: random.Random) -> list[Question]:
    selected = []
    for entry in for_version(parsed, label).items:
        if isinstance(entry, Pool):
            candidates = list(entry.questions)
            rng.shuffle(candidates)
            selected.extend(candidates if entry.scramble_all else candidates[:entry.take])
        else:
            selected.append(entry)
    return selected


def _question_markup(question: Question, label: str) -> str:
    prefix = f"[Only Version {label}.] "
    if question.text_only:
        value = prefix + "[Paragraph.] " + question.stem
    else:
        value = prefix + "[Question.] " + question.stem
        if question.answer is not None:
            value += " [Correct.] " + question.answer
        for distractor in question.distractors:
            value += " [Distractor.] " + distractor
    return f"<p>{html.escape(value)}</p>"


def _interchange_html(selections: dict[str, list[Question]]) -> str:
    paragraphs = ["<!doctype html>", '<html lang="en"><body>']
    for label, questions in selections.items():
        paragraphs.extend(_question_markup(question, label) for question in questions)
    paragraphs.append("</body></html>")
    return "\n".join(paragraphs) + "\n"


def _renderer_ready() -> None:
    if not RENDERER.is_file():
        raise RuntimeError(f"Testmaker renderer is missing: {RENDERER}")
    if not (RENDERER.parent / "node_modules").is_dir():
        raise RuntimeError(
            "Testmaker's JavaScript dependencies are not installed. Run "
            "`npm ci --omit=optional` in vendor/testmaker-mcqer or run the toolkit setup command."
        )


def _normalize_docx(path: Path) -> None:
    """Remove ZIP and core-property timestamps without changing document layout."""
    with zipfile.ZipFile(path) as source:
        members = [(info.filename, source.read(info.filename)) for info in source.infolist()]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for name, payload in sorted(members):
            if name == "docProps/core.xml":
                payload = re.sub(
                    rb"<dcterms:(created|modified)[^>]*>.*?</dcterms:\1>",
                    rb"<dcterms:\1 xsi:type=\"dcterms:W3CDTF\">2000-01-01T00:00:00Z</dcterms:\1>",
                    payload,
                )
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            target.writestr(info, payload)


def _normalize_pdf(path: Path) -> None:
    """Canonicalize renderer metadata and document IDs without changing layout."""
    reader = PdfReader(path)
    writer = PdfWriter(clone_from=reader)
    writer.metadata = {
        "/Producer": "CourseTools Testmaker",
        "/CreationDate": "D:20000101000000Z",
        "/ModDate": "D:20000101000000Z",
    }
    identifier = hashlib.sha256(b"coursetools-testmaker-pdf-v1" + path.name.encode()).digest()[:16]
    writer._ID = ArrayObject([ByteStringObject(identifier), ByteStringObject(identifier)])
    temporary = path.with_suffix(".normalized.pdf")
    with temporary.open("wb") as stream:
        writer.write(stream)
    temporary.replace(path)


def _normalized_pdf_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def audit_pdf_pagination(path: Path, questions: list[Question]) -> dict:
    """Fail when one generated MCQ's stem and choices do not share a page."""
    pages = [_normalized_pdf_text(page.extract_text()) for page in PdfReader(path).pages]
    checked = 0
    for question in questions:
        if question.text_only or not question.distractors:
            continue
        stem = _normalized_pdf_text(question.stem)
        stem_pages = [index for index, page in enumerate(pages) if stem in page]
        if len(stem_pages) != 1:
            raise RuntimeError(f"Could not locate one page for question stem in {path.name}: {stem[:80]}")
        page = pages[stem_pages[0]]
        missing = [value for value in [question.answer, *question.distractors]
                   if _normalized_pdf_text(value) not in page]
        if missing:
            raise RuntimeError(f"Question crosses a page boundary in {path.name}: {stem[:80]}")
        checked += 1
    return {"pages": len(pages), "mcq_blocks_checked": checked, "status": "PASS"}


def build_forms(source: Path, output: Path, title: str, versions: int = 3, seed: str = "1") -> dict:
    """Resolve pools in Python, then render through the original JavaScript MCQer."""
    source = Path(source)
    output = Path(output)
    if not 1 <= versions <= len(LABELS):
        raise ValueError("versions must be between 1 and 5")
    _renderer_ready()
    parsed = parse_testmaker(source)
    output.mkdir(parents=True, exist_ok=True)
    selections = {
        label: select_questions(parsed, label, random.Random(_seed(source, label, seed)))
        for label in LABELS[:versions]
    }
    renderer_seed = hashlib.sha256(source.read_bytes() + b"\0" + seed.encode()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="coursetools-testmaker-") as temporary:
        work = Path(temporary)
        interchange = work / "resolved.html"
        interchange.write_text(_interchange_html(selections), encoding="utf-8")
        raw = work / "rendered"
        command = [
            "node", str(RENDERER), "--input", str(interchange), "--output", str(raw),
            "--versions", str(versions), "--seed", renderer_seed,
            "--font-size", "11", "--margin-size", "36",
        ]
        result = subprocess.run(command, cwd=RENDERER.parent, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f"Testmaker JavaScript renderer failed:\n{result.stderr or result.stdout}")

        records = []
        for label, questions in selections.items():
            names = {}
            for kind, raw_kind in (("test_form", "testForm"), ("answer_key", "answerKey")):
                for suffix in ("pdf", "docx"):
                    source_file = raw / f"resolved_{raw_kind}_{label}.{suffix}"
                    destination = output / f"{kind.replace('_', '-')}-{label}.{suffix}"
                    if not source_file.is_file():
                        raise RuntimeError(f"Testmaker did not produce expected file: {source_file.name}")
                    shutil.copyfile(source_file, destination)
                    if suffix == "docx":
                        _normalize_docx(destination)
                    else:
                        _normalize_pdf(destination)
                    names[f"{kind}_{suffix}"] = destination.name
            pagination = {
                "test_form": audit_pdf_pagination(output / names["test_form_pdf"], questions),
                "answer_key": audit_pdf_pagination(output / names["answer_key_pdf"], questions),
            }
            records.append({
                "version": label,
                "question_count": sum(not question.text_only for question in questions),
                "test_form": names["test_form_pdf"],
                "answer_key": names["answer_key_pdf"],
                "test_form_docx": names["test_form_docx"],
                "answer_key_docx": names["answer_key_docx"],
                "pagination": pagination,
            })

    manifest = {
        "schema_version": 2,
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "seed": seed,
        "title": title,
        "backend": "original-mcqer-javascript",
        "renderer": str(RENDERER.relative_to(PROJECT_ROOT)),
        "renderer_sha256": hashlib.sha256(RENDERER.read_bytes()).hexdigest(),
        "versions": records,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
