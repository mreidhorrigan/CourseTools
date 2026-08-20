#!/usr/bin/env python3
"""Prepare a distributable IAT 210 course starter from a current Canvas export."""
from __future__ import annotations

import argparse
import hashlib
import re
import tempfile
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup
from lxml import etree

FIXED_TIME = (2026, 1, 1, 0, 0, 0)
TITLE = "IAT 210 Example Course Starter"
CODE = "IAT210-EXAMPLE-STARTER"
TRAMMELL_URL = "https://www.gamejournal.it/wp-content/uploads/2021/01/I9_GAME_03_TRAMMELL.pdf"
WARNING = (
    "Example course starter generated with AI under the direction of M. Horrigan. "
    "This is not a production course. Review every item before adapting it for teaching."
)
SYLLABUS_COPYEDITS = {
    "fabricate sources or playtests": "fabricate sources",
    "When competing ideas cannot be": "When two competing ideas cannot be",
    "The grade does not reward theatrical skill or professional equipment. It rewards": "The grade rewards",
    "Report sustained team problems": "Report persistent team problems",
    "Each student must schedule and attend one synchronous video interview with the instructor or a teaching assistant during the final month of the course.":
        "To receive a nonzero grade for this course's three major projects, each student must schedule and attend one synchronous video interview with the instructor or a teaching assistant during the final month of the course.",
}
SYLLABUS_EXACT_COPYEDITS = {
    "Actual-play ideation; Quiz 1": "Actual-play ideation; Quiz 1 (Sep 22, 00:00–24:00)",
    "Actual-play final; Quiz 2": "Actual-play final; Quiz 2 (Oct 6, 00:00–24:00)",
    "Digital ideation; Quiz 3": "Digital ideation; Quiz 3 (Oct 20, 00:00–24:00)",
    "Quiz 4": "Quiz 4 (Nov 3, 00:00–24:00)",
    "Digital final; Quiz 5": "Digital final; Quiz 5 (Nov 10, 00:00–24:00)",
    "Board-game plan; Quiz 6; interviews": "Board-game plan; Quiz 6 (Nov 24, 00:00–24:00); interviews",
    "Board-game final; Quiz 7; exam review; interviews complete":
        "Board-game final; Quiz 7 (Dec 7, 00:00–24:00); exam review; interviews complete",
}
QUIZ_WINDOWS = {
    1: ("2026-09-22T07:00:00", "2026-09-23T07:00:00", "2026-09-22"),
    2: ("2026-10-06T07:00:00", "2026-10-07T07:00:00", "2026-10-06"),
    3: ("2026-10-20T07:00:00", "2026-10-21T07:00:00", "2026-10-20"),
    4: ("2026-11-03T08:00:00", "2026-11-04T08:00:00", "2026-11-03"),
    5: ("2026-11-10T08:00:00", "2026-11-11T08:00:00", "2026-11-10"),
    6: ("2026-11-24T08:00:00", "2026-11-25T08:00:00", "2026-11-24"),
    7: ("2026-12-07T08:00:00", "2026-12-08T08:00:00", "2026-12-07"),
}
QUIZ_AVAILABILITY_TEXT = (
    "Each quiz has one 24-hour Pacific-time window: Quiz 1 Sep 22, 00:00–24:00; "
    "Quiz 2 Oct 6, 00:00–24:00; Quiz 3 Oct 20, 00:00–24:00; Quiz 4 Nov 3, "
    "00:00–24:00; Quiz 5 Nov 10, 00:00–24:00; Quiz 6 Nov 24, 00:00–24:00; "
    "and Quiz 7 Dec 7, 00:00–24:00."
)


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if root != target and root not in target.parents:
            raise ValueError(f"Unsafe IMSCC member: {member.filename}")
    archive.extractall(destination)


def local_name(node) -> str:
    return etree.QName(node).localname


def rewrite_manifest(path: Path) -> None:
    tree = etree.parse(str(path))
    for resource in list(tree.xpath("//*[local-name()='resource']")):
        href = resource.get("href", "")
        if "outtake-week-" in href or "I9_GAME_03_TRAMMELL.pdf" in href:
            resource.getparent().remove(resource)
    title_strings = tree.xpath("//*[local-name()='lom']/*[local-name()='general']/*[local-name()='title']/*[local-name()='string']")
    if title_strings:
        title_strings[0].text = TITLE
    path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def rewrite_course_metadata(path: Path, *, context: bool = False) -> None:
    tree = etree.parse(str(path))
    values = {"course_name": TITLE, "title": TITLE, "course_code": CODE}
    if context:
        values["root_account_name"] = "Example Canvas installation"
    for node in tree.iter():
        name = local_name(node)
        if name in values:
            node.text = values[name]
    path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def rewrite_html(path: Path, add_warning: bool = False) -> None:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    for heading in soup.find_all(["h1", "h2", "h3"]):
        stack = "font-family:OpenDyslexic,'Atkinson Hyperlegible','Avenir Next','Trebuchet MS',Arial,sans-serif"
        style = heading.get("style", "")
        heading["style"] = re.sub(r"font-family:[^;]+", stack, style) if "font-family:" in style else f"{stack};{style}"
    for node in list(soup.find_all(string=True)):
        revised = str(node)
        if revised.strip() in SYLLABUS_EXACT_COPYEDITS:
            revised = SYLLABUS_EXACT_COPYEDITS[revised.strip()]
        for old, new in SYLLABUS_COPYEDITS.items():
            revised = revised.replace(old, new)
        if revised != str(node):
            node.replace_with(revised)
    history = next((p for p in soup.find_all("p") if p.get_text(" ", strip=True).startswith("IAT 210 studies")), None)
    projects = next((p for p in soup.find_all("p") if p.get_text(" ", strip=True).startswith("The three project rounds")), None)
    if history and projects and list(soup.descendants).index(projects) < list(soup.descendants).index(history):
        history.extract()
        projects.insert_before(history)
    quiz_heading = next((h for h in soup.find_all(["h2", "h3"]) if h.get_text(" ", strip=True) == "Practice quizzes and final examination"), None)
    if quiz_heading and QUIZ_AVAILABILITY_TEXT not in soup.get_text(" ", strip=True):
        paragraph = quiz_heading.find_next_sibling("p")
        if paragraph:
            paragraph.append(" " + QUIZ_AVAILABILITY_TEXT)
    for tag in soup.find_all(True):
        tag.attrs.pop("data-api-endpoint", None)
        tag.attrs.pop("data-api-returntype", None)
    for anchor in soup.find_all("a", href=True):
        if "I9_GAME_03_TRAMMELL.pdf" in anchor["href"]:
            anchor["href"] = TRAMMELL_URL
            parent = anchor.find_parent("li")
            if parent:
                span = parent.find("span")
                if span:
                    span.string = "Open-access publisher-hosted PDF."
    if add_warning and WARNING not in soup.get_text(" ", strip=True):
        aside = soup.new_tag("aside")
        aside["role"] = "note"
        strong = soup.new_tag("strong")
        strong.string = "Example course starter: "
        aside.append(strong)
        aside.append(WARNING)
        container = soup.body or soup
        container.insert(0, aside)
    path.write_text(str(soup), encoding="utf-8")


def rewrite_quiz_window(path: Path) -> None:
    tree = etree.parse(str(path))
    title = next((node.text or "" for node in tree.xpath("//*[local-name()='title']")), "")
    match = re.fullmatch(r"Practice Quiz ([1-7])", title)
    if not match:
        return
    unlock_at, closes_at, local_date = QUIZ_WINDOWS[int(match.group(1))]
    for node in tree.xpath("/*[local-name()='quiz']/*[local-name()='due_at'] | //*[local-name()='assignment']/*[local-name()='due_at'] | //*[local-name()='assignment']/*[local-name()='lock_at']"):
        node.text = closes_at
    for node in tree.xpath("//*[local-name()='assignment']/*[local-name()='unlock_at']"):
        node.text = unlock_at
    for node in tree.xpath("//*[local-name()='assignment']/*[local-name()='all_day_date']"):
        node.text = local_date
    for node in tree.xpath("//*[local-name()='assignment']/*[local-name()='all_day']"):
        node.text = "false"
    path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def rename_testmaker_in_text(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("MCQer", "Testmaker").replace("MCQER", "TESTMAKER")
    # Assignment and discussion descriptions are HTML escaped inside XML. The
    # ordinary HTML pass cannot see their attributes, so remove live-instance
    # API metadata in both literal and escaped forms here as well.
    text = re.sub(r"\sdata-api-endpoint=(?:\"[^\"]*\"|'[^']*')", "", text)
    text = re.sub(r"\sdata-api-returntype=(?:\"[^\"]*\"|'[^']*')", "", text)
    text = re.sub(r"\sdata-api-endpoint=&quot;.*?&quot;", "", text)
    text = re.sub(r"\sdata-api-returntype=&quot;.*?&quot;", "", text)
    path.write_text(text, encoding="utf-8")


def validate(root: Path) -> None:
    manifest = (root / "imsmanifest.xml").read_text(encoding="utf-8")
    quizzes = sorted(set(re.findall(r"Practice Quiz (\d+)", manifest)))
    if quizzes != [str(number) for number in range(1, 8)]:
        raise ValueError(f"Expected exactly Practice Quizzes 1–7; found {quizzes}")
    all_names = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]
    if any("outtake-week-" in name for name in all_names):
        raise ValueError("Outtake pages remain in the course starter")
    if any(name.endswith("I9_GAME_03_TRAMMELL.pdf") for name in all_names):
        raise ValueError("The third-party Trammell PDF remains embedded")
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in root.rglob("*") if path.is_file()
    )
    if "canvas.sfu.ca/api/v1/courses/4066" in combined:
        raise ValueError("Instance-specific Canvas API attributes remain")
    if "MCQer" in combined or "MCQER" in combined:
        raise ValueError("Legacy Testmaker name remains in the course starter")
    if WARNING not in combined or TITLE not in combined:
        raise ValueError("The course starter label is missing")


def build(source: Path, output: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="iat210_starter_") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(source) as archive:
            safe_extract(archive, root)
        for path in list((root / "wiki_content").glob("outtake-week-*.html")):
            path.unlink()
        pdf = root / "web_resources/course readings/I9_GAME_03_TRAMMELL.pdf"
        if pdf.exists():
            pdf.unlink()
        rewrite_manifest(root / "imsmanifest.xml")
        rewrite_course_metadata(root / "course_settings/course_settings.xml")
        context = root / "course_settings/context.xml"
        if context.is_file():
            rewrite_course_metadata(context, context=True)
        for html in root.rglob("*.html"):
            rewrite_html(html, html.name in {"start-here.html", "iat-210-course-syllabus.html", "syllabus.html"})
        for metadata in root.rglob("assessment_meta.xml"):
            rewrite_quiz_window(metadata)
        for text_path in [*root.rglob("*.xml"), *root.rglob("*.html")]:
            rename_testmaker_in_text(text_path)
        validate(root)
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = zipfile.ZipInfo(path.relative_to(root).as_posix(), FIXED_TIME)
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(build(args.source, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
