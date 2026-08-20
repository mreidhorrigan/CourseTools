"""Parse Testmaker's tagged .txt/.md/.docx format and build Canvas quiz requests."""
from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


class TestmakerFormatError(ValueError):
    """The source cannot be converted safely into one Canvas quiz."""


@dataclass
class Question:
    stem: str
    answer: str | None = None
    distractors: list[str] = field(default_factory=list)
    text_only: bool = False
    only_version: str | None = None
    bloom_level: str | None = None
    material_ids: list[str] = field(default_factory=list)
    target_id: str | None = None


@dataclass
class Pool:
    take: int
    questions: list[Question]
    scramble_all: bool = False


@dataclass
class ParsedQuiz:
    items: list[Question | Pool]
    warnings: list[str] = field(default_factory=list)
    assets: dict[str, bytes] = field(default_factory=dict)

    @property
    def questions(self) -> list[Question]:
        result: list[Question] = []
        for item in self.items:
            candidates = item.questions if isinstance(item, Pool) else [item]
            result.extend(q for q in candidates if not q.text_only)
        return result


_CONTENT_TAG = re.compile(r"(\[Question\.\]|\[Answer\.\]|\[Correct\.\]|\[Distractor\.\]|\[Bloom\.\]|\[Material\.\]|\[Target\.\])", re.I)
_POOL = re.compile(r"^\[Each version take (\d+) of the following options?\.\]$", re.I)
_SCRAMBLE = re.compile(r"^\[Scramble the order of the following options?\.\]$", re.I)
_ONLY_VERSION = re.compile(r"^\[Only Version ([A-E])\.\]", re.I)
_OPTION = re.compile(r"^\[Option\.\]\s*", re.I)


def _clean_block(block: str) -> str:
    text = re.sub(r"\s*\n\s*", " ", block).strip()
    text = re.sub(r"^\s*(?:#{1,6}\s+|>\s+|[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*|__([^_]+)__|`([^`]+)`", lambda m: next(g for g in m.groups() if g is not None), text)
    return text.strip()


def _text_paragraphs(text: str) -> list[str]:
    return [clean for block in re.split(r"\n[ \t]*\n+", text.replace("\r\n", "\n").replace("\r", "\n")) if (clean := _clean_block(block))]


def _docx_paragraphs(path: Path) -> tuple[list[str], dict[str, bytes]]:
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
            relroot = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
            rels={x.attrib["Id"]:x.attrib["Target"] for x in relroot}
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise TestmakerFormatError(f"Could not read DOCX {path.name}: {exc}") from exc
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []; assets={}; relns="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    for para in root.findall(".//w:body/w:p", ns):
        parts = []
        for node in para.iter():
            if node.tag.endswith("}t") and node.text:
                parts.append(node.text)
            elif node.tag.endswith("}tab"):
                parts.append("\t")
            elif node.tag.endswith("}br"):
                parts.append("\n")
            elif node.tag.endswith("}blip") and node.attrib.get(f"{{{relns}}}embed"):
                target=rels.get(node.attrib[f"{{{relns}}}embed"]); name=Path(target or "image").name
                if target:
                    with zipfile.ZipFile(path) as archive: assets[name]=archive.read("word/"+target)
                    parts.append(f" [Image: {name}] ")
        if cleaned := _clean_block("".join(parts)):
            paragraphs.append(cleaned)
    return paragraphs,assets


def read_paragraphs(path: Path) -> tuple[list[str], dict[str, bytes]]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_paragraphs(path)
    if suffix in {".txt", ".md", ".markdown"}:
        return _text_paragraphs(path.read_text(encoding="utf-8-sig")),{}
    raise TestmakerFormatError("Questions file must be .docx, .md, .markdown, or .txt.")


def _parse_question(text: str, source_number: int) -> Question:
    only_version = None
    if match := _ONLY_VERSION.match(text):
        only_version = match.group(1).upper()
        text = text[match.end():].strip()
    parts = _CONTENT_TAG.split(text)
    current = None
    stem = None
    answer = None
    distractors: list[str] = []
    bloom_level = None
    material_ids: list[str] = []
    target_id = None
    for part in parts:
        normalized = part.lower()
        if normalized == "[question.]": current = "q"; continue
        if normalized in {"[answer.]", "[correct.]"}: current = "a"; continue
        if normalized == "[distractor.]": current = "d"; continue
        if normalized == "[bloom.]": current = "b"; continue
        if normalized == "[material.]": current = "m"; continue
        if normalized == "[target.]": current = "t"; continue
        value = part.strip()
        if not value:
            continue
        if current == "q": stem = value
        elif current == "a": answer = value
        elif current == "d": distractors.append(value)
        elif current == "b": bloom_level = value
        elif current == "m": material_ids.extend(item.strip() for item in value.split(",") if item.strip())
        elif current == "t": target_id = value
    if not stem:
        raise TestmakerFormatError(f"Question paragraph {source_number} has no [Question.] text.")
    if distractors and not answer:
        raise TestmakerFormatError(f"Question paragraph {source_number} has distractors but no [Answer.] or [Correct.].")
    return Question(stem=stem, answer=answer, distractors=distractors,
                    only_version=only_version, bloom_level=bloom_level,
                    material_ids=material_ids, target_id=target_id)


def parse_testmaker(path: Path) -> ParsedQuiz:
    paragraphs,assets = read_paragraphs(path)
    items: list[Question | Pool] = []
    warnings: list[str] = []
    i = 0
    while i < len(paragraphs):
        text = paragraphs[i].strip()
        if text == "[Version X]":
            i += 1; continue
        pool_match = _POOL.match(text)
        scramble_match = _SCRAMBLE.match(text)
        if pool_match or scramble_match:
            questions: list[Question] = []
            i += 1
            while i < len(paragraphs) and _OPTION.match(paragraphs[i]):
                candidate = _OPTION.sub("", paragraphs[i], count=1)
                questions.append(_parse_question(candidate, i + 1))
                i += 1
            if not questions:
                raise TestmakerFormatError(f"Pool near paragraph {i + 1} has no [Option.] questions.")
            take = int(pool_match.group(1)) if pool_match else len(questions)
            if take > len(questions):
                raise TestmakerFormatError(f"Pool asks Canvas to take {take}, but contains only {len(questions)} questions.")
            items.append(Pool(take=take, questions=questions, scramble_all=bool(scramble_match)))
            continue
        if _OPTION.match(text):
            raise TestmakerFormatError(f"Stray [Option.] at paragraph {i + 1}; it must immediately follow a pool header.")
        if "[Page break.]" in text:
            warnings.append("[Page break.] was ignored; Canvas controls quiz pagination with one_question_at_a_time.")
            text = text.replace("[Page break.]", " ").strip()
        if re.match(r"^\[(Paragraph|Not a question)\.\]", text, re.I):
            warnings.append("Scenario [Paragraph.] content was converted to a zero-point text-only quiz item.")
            scenario = re.sub(r"^\[(Paragraph|Not a question)\.\]\s*", "", text, flags=re.I)
            only_version = None
            if match := _ONLY_VERSION.match(text):
                only_version = match.group(1).upper()
                text = text[match.end():].strip()
            items.append(Question(stem=scenario, text_only=True, only_version=only_version))
        elif "[Question.]" in text:
            items.append(_parse_question(text, i + 1))
        i += 1
    if not items or not any(q.stem for q in (x for x in items if isinstance(x, Question))):
        if not any(isinstance(x, Pool) for x in items):
            raise TestmakerFormatError("No valid [Question.] paragraphs found.")
    return ParsedQuiz(items=items, warnings=list(dict.fromkeys(warnings)),assets=assets)


def versions_in(parsed: ParsedQuiz) -> list[str]:
    """Sorted explicit version labels used by the source."""
    return sorted({q.only_version for q in parsed.questions if q.only_version})


def for_version(parsed: ParsedQuiz, version: str) -> ParsedQuiz:
    """Keep shared questions plus those tagged for one fixed paper version."""
    label = version.upper()
    items: list[Question | Pool] = []
    for item in parsed.items:
        if isinstance(item, Pool):
            questions = [q for q in item.questions if q.only_version in (None, label)]
            if questions:
                take = min(item.take, len(questions))
                items.append(Pool(take=take, questions=questions, scramble_all=item.scramble_all))
        elif item.only_version in (None, label):
            items.append(item)
    return ParsedQuiz(items=items, warnings=list(parsed.warnings),assets=dict(parsed.assets))


def question_payload(question: Question, *, name: str, mcq_points: float, written_points: float,
                     group_id: int | None = None, image_urls: dict[str,str] | None = None) -> dict:
    def rich(text):
        chunks=[]; pos=0
        for m in re.finditer(r"\[Image:\s*([^\]]+)\]",text,re.I):
            chunks.append(html.escape(text[pos:m.start()])); name=m.group(1).strip(); url=(image_urls or {}).get(name)
            chunks.append(f'<img src="{html.escape(url)}" alt="Question image: {html.escape(name)}">' if url else f'[Image: {html.escape(name)}]'); pos=m.end()
        chunks.append(html.escape(text[pos:])); return "".join(chunks)
    escaped_stem = f"<p>{rich(question.stem)}</p>"
    if question.distractors:
        answers = [{"answer_text": question.answer, "answer_html": rich(question.answer), "answer_weight": 100}]
        answers.extend({"answer_text": text, "answer_html": rich(text), "answer_weight": 0} for text in question.distractors)
        body = {"question_name": name, "question_text": escaped_stem,
                "question_type": "multiple_choice_question", "points_possible": mcq_points,
                "answers": answers}
    elif question.text_only:
        body = {"question_name": name, "question_text": escaped_stem,
                "question_type": "text_only_question", "points_possible": 0}
    else:
        body = {"question_name": name, "question_text": escaped_stem,
                "question_type": "essay_question", "points_possible": written_points}
    if group_id is not None:
        body["quiz_group_id"] = group_id
    return {"question": body}
