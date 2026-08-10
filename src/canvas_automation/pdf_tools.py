"""
PDF creation and merging for the engine.

Two distinct needs, two distinct libraries, matching the pdf skill's own
guidance: reportlab to CREATE new PDF content (one page-set per
assignment), pypdf to MERGE already-existing PDF files (a structural
operation, not a generative one). Both are plain functions with no
Flask/CLI dependency, so they are usable from export-course-packet and
merge-pdfs alike, and from anything else built on this engine later.
"""
import json
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("AssignmentTitle", parent=_STYLES["Title"], fontSize=18, spaceAfter=6)
_META_STYLE = ParagraphStyle("AssignmentMeta", parent=_STYLES["Normal"], textColor="#555555", spaceAfter=14)
_BODY_STYLE = _STYLES["Normal"]
_HEADING_STYLES = {1: _STYLES["Heading1"], 2: _STYLES["Heading2"], 3: _STYLES["Heading3"]}

# reportlab's Paragraph markup understands only a small, specific subset of
# tags (b, i, u, br, a, font, super, sub, ...); anything else has to be
# converted or dropped before it reaches a Paragraph. This is the mapping
# for the common inline tags Canvas's rich text editor actually produces.
_INLINE_TAG_MAP = {"strong": "b", "b": "b", "em": "i", "i": "i", "u": "u"}


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_html(node) -> str:
    """Render an HTML node's inline content as reportlab Paragraph markup."""
    if isinstance(node, NavigableString):
        return _escape(str(node))
    parts = []
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(_escape(str(child)))
            continue
        name = getattr(child, "name", None)
        if name == "br":
            parts.append("<br/>")
        elif name == "a" and child.get("href"):
            parts.append(f'<a href="{_escape(child["href"])}" color="blue">{_inline_html(child)}</a>')
        elif name in _INLINE_TAG_MAP:
            tag = _INLINE_TAG_MAP[name]
            parts.append(f"<{tag}>{_inline_html(child)}</{tag}>")
        else:
            parts.append(_inline_html(child))
    return "".join(parts)


def html_to_flowables(html: "str | None") -> list:
    """
    A deliberately modest HTML -> reportlab flowables converter. Paragraphs,
    headings, ordered/unordered lists, and bold/italic/underline/link text
    survive; tables, images, and embedded media are noted and skipped
    rather than crashing the render, since a packet missing one embedded
    image is far more useful than a packet that fails to build at all.
    """
    if not html or not html.strip():
        return [Paragraph("(no description)", _BODY_STYLE)]

    soup = BeautifulSoup(html, "html.parser")
    flowables = []

    def walk(node):
        for child in getattr(node, "children", []):
            name = getattr(child, "name", None)
            if name is None:
                text = str(child).strip()
                if text:
                    flowables.append(Paragraph(_escape(text), _BODY_STYLE))
            elif name in ("p", "div"):
                text = _inline_html(child).strip()
                if text:
                    flowables.append(Paragraph(text, _BODY_STYLE))
                    flowables.append(Spacer(1, 6))
                else:
                    walk(child)
            elif name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = min(int(name[1]), 3)
                flowables.append(Paragraph(_inline_html(child), _HEADING_STYLES[level]))
                flowables.append(Spacer(1, 6))
            elif name in ("ul", "ol"):
                items = [
                    ListItem(Paragraph(_inline_html(li), _BODY_STYLE))
                    for li in child.find_all("li", recursive=False)
                ]
                if items:
                    flowables.append(ListFlowable(items, bulletType="bullet" if name == "ul" else "1"))
                    flowables.append(Spacer(1, 6))
            elif name == "table":
                flowables.append(Paragraph("[table omitted; see the original in Canvas]", _META_STYLE))
            elif name in ("script", "style"):
                continue
            else:
                walk(child)

    walk(soup)
    return flowables or [Paragraph("(no description)", _BODY_STYLE)]


def render_assignment_pdf(assignment: dict, out_path: Path) -> None:
    """Render one assignment (title, due date, points, description) to its own PDF."""
    doc = SimpleDocTemplate(
        str(out_path), pagesize=LETTER,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
    )
    story = [Paragraph(_escape(assignment.get("name") or "Untitled assignment"), _TITLE_STYLE)]

    meta_bits = []
    if assignment.get("due_at"):
        meta_bits.append(f"Due {assignment['due_at']}")
    if assignment.get("points_possible") is not None:
        meta_bits.append(f"{assignment['points_possible']} points")
    if meta_bits:
        story.append(Paragraph(_escape(" | ".join(meta_bits)), _META_STYLE))

    story.extend(html_to_flowables(assignment.get("description")))
    doc.build(story)


def merge_pdfs(paths: "list[Path]", out_path: Path) -> int:
    """
    Concatenate existing PDFs, in the given order, into a single PDF.
    Returns the total page count written. Uses the pdf skill's documented
    pypdf merge pattern (PdfReader per file, add_page per page) rather
    than a newer convenience method, for maximum compatibility.
    """
    writer = PdfWriter()
    page_count = 0
    for p in paths:
        reader = PdfReader(str(p))
        for page in reader.pages:
            writer.add_page(page)
            page_count += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)
    return page_count
