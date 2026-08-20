#!/usr/bin/env python3
"""Move design documentation out of Start Here and synchronize one Canvas page."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from canvas_automation import jsonc
from canvas_automation.course_html import compile_fragment
from course_authoring import build_links, course_id
from sandbox_course_lifecycle import GuardedCanvas

TITLE = "Course Rationale and Design"
SLUG = "course-rationale-and-design"
SOURCE = "course/content/pages/course-rationale-and-design.html"
DESIGN_SECTION_IDS = ("course-rationale-design",)
STUDENT_SECTION_IDS = ("field-roadmap", "glossary")


def transform(start_html: str, syllabus_html: str, course_url: str) -> tuple[str, str, str]:
    start = BeautifulSoup(start_html, "html.parser")
    # Canvas renders the wiki-page title above the body, so the body begins at
    # heading level 2 and does not repeat the automatically displayed title.
    destination = BeautifulSoup('<div class="canvas-course"></div>', "html.parser")
    root = destination.div
    for section_id in DESIGN_SECTION_IDS:
        section = start.find("section", id=section_id)
        if section is None:
            raise ValueError(f"Start Here is missing section #{section_id}")
        root.append(section.extract())

    link = start.new_tag("a", href=f"{course_url}/pages/{SLUG}")
    link["data-api-endpoint"] = f"{course_url.replace('/courses/', '/api/v1/courses/')}/pages/{SLUG}"
    link["data-api-returntype"] = "Page"
    link.string = "public course rationale and workload design"
    paragraph = start.new_tag("p")
    paragraph.append("The ")
    paragraph.append(link)
    paragraph.append(" documents the course-development method and is available to interested readers.")
    start.div.append(paragraph)

    syllabus = BeautifulSoup(syllabus_html, "html.parser")
    rationale_link = syllabus.find("a", string=lambda value: value and "course rationale and design" in value.casefold())
    if rationale_link is None:
        raise ValueError("Syllabus course-rationale link was not found")
    rationale_link["href"] = f"{course_url}/pages/{SLUG}"
    rationale_link["data-api-endpoint"] = f"{course_url.replace('/courses/', '/api/v1/courses/')}/pages/{SLUG}"
    rationale_link["data-api-returntype"] = "Page"
    return str(start).strip() + "\n", str(destination).strip() + "\n", str(syllabus).strip() + "\n"


def restore_student_sections(start_html: str, design_html: str) -> tuple[str, str]:
    """Keep the timeline and terminology guides in required student orientation."""
    start = BeautifulSoup(start_html, "html.parser")
    design = BeautifulSoup(design_html, "html.parser")
    duplicate_title = design.find("h1", string=lambda value: value and value.strip() == TITLE)
    if duplicate_title is not None:
        duplicate_title.decompose()
    optional_link = start.find("a", href=lambda value: value and value.endswith(f"/pages/{SLUG}"))
    insertion_point = optional_link.find_parent("p") if optional_link else None
    for section_id in STUDENT_SECTION_IDS:
        section = design.find("section", id=section_id)
        if section is not None:
            if insertion_point:
                insertion_point.insert_before(section.extract())
            else:
                start.div.append(section.extract())
    ordered = start.find("ol")
    if ordered and not any("field roadmap" in li.get_text(" ", strip=True).casefold() for li in ordered.find_all("li")):
        item = start.new_tag("li")
        item.string = "Read the game studies field roadmap and terminology guides on this page."
        ordered.append(item)
    return str(start).strip() + "\n", str(design).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    config = jsonc.load_and_validate(ROOT / "course/course.config.jsonc")
    cid = course_id(config)
    expected = f"SEPARATE-DESIGN-PAGE-{cid}"
    if args.confirm != expected:
        raise ValueError(f"Apply requires --confirm {expected}")
    canvas = GuardedCanvas(args.server, cid)
    canvas.health()
    canvas.require_unpublished()

    start_path = ROOT / "course/content/pages/start-here.html"
    syllabus_path = ROOT / "course/content/syllabus.html"
    design_path = ROOT / SOURCE
    current_start = start_path.read_text(encoding="utf-8")
    current_syllabus = syllabus_path.read_text(encoding="utf-8")
    if all(f'id="{section_id}"' in current_start for section_id in DESIGN_SECTION_IDS):
        start_html, design_html, syllabus_html = transform(
            current_start, current_syllabus, config["course_url"].rstrip("/")
        )
    elif design_path.is_file():
        # Resume after page creation or another later step was interrupted.
        start_html, design_html, syllabus_html = (
            current_start, design_path.read_text(encoding="utf-8"), current_syllabus
        )
    else:
        raise ValueError("Design sections are absent from Start Here and no separated source exists")
    start_html, design_html = restore_student_sections(start_html, design_html)
    css = (ROOT / config["authoring"]["stylesheet"]).read_text(encoding="utf-8")
    compiled_design = compile_fragment(design_html, css)
    pages = canvas.raw("GET", f"/courses/{cid}/pages", params={"per_page": 100})
    existing = next((page for page in pages if page.get("url") == SLUG), None)
    payload = {"wiki_page": {"title": TITLE, "body": compiled_design, "published": True}}
    if existing:
        page = canvas.raw("PUT", f"/courses/{cid}/pages/{SLUG}", payload)
    else:
        page = canvas.raw("POST", f"/courses/{cid}/pages", payload)

    manifest_path = ROOT / config["authoring"]["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next((item for item in manifest["objects"] if item.get("slug") == SLUG), None)
    page_id = page.get("page_id") or page.get("id")
    if record is None:
        manifest["objects"].append({
            "canvas_id": page_id, "front_page": False, "kind": "page",
            "published": True, "slug": SLUG, "source": SOURCE, "title": TITLE,
        })
    else:
        record.update({"canvas_id": page_id, "published": True, "source": SOURCE, "title": TITLE})

    start_path.write_text(start_html, encoding="utf-8")
    design_path.write_text(design_html, encoding="utf-8")
    syllabus_path.write_text(syllabus_html, encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    modules = canvas.raw("GET", f"/courses/{cid}/modules", params={"per_page": 100})
    start_module = next(module for module in modules if module["name"] == "Start Here")
    items = canvas.raw("GET", f"/courses/{cid}/modules/{start_module['id']}/items", params={"per_page": 100})
    # The page stays published and syllabus-linked, but is not a required
    # Start Here module item because its audience is interested readers.
    for item in items:
        if item.get("title") == TITLE:
            canvas.raw("DELETE", f"/courses/{cid}/modules/{start_module['id']}/items/{item['id']}")

    links = build_links(ROOT, manifest, config)
    (ROOT / config["authoring"]["links_manifest"]).write_text(
        json.dumps(links, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"course_id": cid, "page_id": page_id, "slug": SLUG, "source": SOURCE}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
