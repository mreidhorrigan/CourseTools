#!/usr/bin/env python3
"""Apply configuration-driven links and information blocks to a Canvas syllabus page."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from canvas_automation import jsonc
from sandbox_course_lifecycle import GuardedCanvas


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def semantic_digest(text: str) -> str:
    soup = BeautifulSoup(text or "", "html.parser")
    for tag in soup.find_all(True):
        tag.attrs.pop("data-api-endpoint", None)
        tag.attrs.pop("data-api-returntype", None)
    return digest(str(soup))


def section_paragraph(soup: BeautifulSoup, heading: str, levels: list[str]):
    node = next((tag for tag in soup.find_all(levels) if tag.get_text(" ", strip=True) == heading), None)
    if not node:
        raise ValueError(f"Missing configured syllabus heading: {heading}")
    paragraph = node.find_next_sibling("p")
    if not paragraph:
        raise ValueError(f"Missing paragraph after configured syllabus heading: {heading}")
    return paragraph


def link_phrase(soup: BeautifulSoup, container, phrase: str, url: str) -> None:
    if container.find("a", href=url):
        return
    for text in container.find_all(string=True):
        value = str(text)
        if phrase not in value:
            continue
        before, after = value.split(phrase, 1)
        if before:
            text.insert_before(NavigableString(before))
        anchor = soup.new_tag("a", href=url)
        anchor.string = phrase
        text.insert_before(anchor)
        if after:
            text.insert_before(NavigableString(after))
        text.extract()
        return
    raise ValueError(f"Could not find configured anchor phrase: {phrase}")


def transform(body: str, config: dict) -> str:
    soup = BeautifulSoup(body, "html.parser")
    for replacement in config.get("text_replacements", []):
        old, new = replacement["old"], replacement["new"]
        exact = replacement.get("exact", False)
        matches = [
            node for node in soup.find_all(string=True)
            if (str(node).strip() == old if exact else old in str(node))
        ]
        if not matches and old not in soup.get_text(" ", strip=True):
            continue
        for node in matches:
            node.replace_with(new if exact else str(node).replace(old, new))
    for removal in config.get("removals", []):
        for node in list(soup.select(removal["selector"])):
            contains = removal.get("contains")
            if contains is None or contains in node.get_text(" ", strip=True):
                node.decompose()
    for insertion in config.get("insertions", []):
        if soup.find(id=insertion["marker_id"]):
            continue
        target = soup.select_one(insertion["after_selector"])
        if not target:
            raise ValueError(f"Insertion selector matched nothing: {insertion['after_selector']}")
        fragment = BeautifulSoup(insertion["html"], "html.parser")
        nodes = [node for node in fragment.contents if str(node).strip()]
        if len(nodes) != 1:
            raise ValueError(f"Insertion {insertion['marker_id']} must contain one top-level HTML node")
        target.insert_after(nodes[0])

    for replacement in config.get("content_replacements", []):
        container = soup.select_one(replacement["container_selector"])
        if not container:
            raise ValueError(f"Content container matched nothing: {replacement['container_selector']}")
        start = container.select_one(replacement["start_after_selector"])
        stop = container.select_one(replacement["stop_before_selector"])
        if not start or not stop:
            raise ValueError("Configured content-replacement boundaries were not found")
        cursor = start.next_sibling
        while cursor and cursor is not stop:
            following = cursor.next_sibling
            cursor.extract()
            cursor = following
        fragment = BeautifulSoup(replacement["html"], "html.parser")
        for node in [node for node in fragment.contents if str(node).strip()]:
            stop.insert_before(node)

    for rule in config.get("heading_styles", []):
        for heading in soup.select(rule["selector"]):
            declarations = {}
            for source in (heading.get("style", ""), rule["style"]):
                for declaration in source.split(";"):
                    if ":" in declaration:
                        name, value = declaration.split(":", 1)
                        declarations[name.strip().lower()] = value.strip()
            heading["style"] = "; ".join(f"{name}: {value}" for name, value in declarations.items()) + ";"

    for rule in config.get("paragraph_rules", []):
        paragraph = section_paragraph(soup, rule["heading"], rule.get("heading_levels", ["h3"]))
        for link in rule.get("links", []):
            link_phrase(soup, paragraph, link["phrase"], link["url"])
        for addition in rule.get("append", []):
            if addition["marker"] not in paragraph.get_text(" ", strip=True):
                paragraph.append(BeautifulSoup(" " + addition["html"], "html.parser"))
    return str(soup)


def desired_present(body: str, config: dict) -> bool:
    soup = BeautifulSoup(body, "html.parser")
    hrefs = {anchor.get("href") for anchor in soup.find_all("a", href=True)}
    text = soup.get_text(" ", strip=True)
    checks = config.get("verification", {})
    styles_present = all(
        all(rule["style"].strip().rstrip(";") in tag.get("style", "") for tag in soup.select(rule["selector"]))
        and bool(soup.select(rule["selector"]))
        for rule in config.get("heading_styles", [])
    )
    text_nodes = [str(node).strip() for node in soup.find_all(string=True)]
    replacements_present = all(
        (item["old"] not in text_nodes if item.get("exact", False) else item["old"] not in text)
        and item["new"] in text
        for item in config.get("text_replacements", [])
    )
    return (
        set(checks.get("required_hrefs", [])) <= hrefs
        and all(soup.find(id=marker) is not None for marker in checks.get("required_ids", []))
        and all(fragment in text for fragment in checks.get("required_text", []))
        and all(fragment not in text for fragment in checks.get("forbidden_text", []))
        and styles_present
        and replacements_present
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--course", required=True, type=int)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--record", required=True, type=Path)
    args = parser.parse_args()
    config = jsonc.load_and_validate(args.config)
    canvas = GuardedCanvas(args.server, args.course)
    canvas.health()
    page_slug = config["page_slug"]
    page = canvas.raw("GET", f"/courses/{args.course}/pages/{page_slug}")
    updated = transform(page["body"], config)
    page_current = desired_present(page["body"], config)
    sync_course_syllabus = config.get("sync_course_syllabus", False)
    course = canvas.raw(
        "GET", f"/courses/{args.course}", params={"include[]": "syllabus_body"}
    ) if sync_course_syllabus else {}
    course_body = course.get("syllabus_body") or ""
    course_current = (
        desired_present(course_body, config)
        and semantic_digest(course_body) == semantic_digest(updated)
    ) if sync_course_syllabus else True
    changed = not page_current or not course_current
    result = {
        "course_id": args.course,
        "page_slug": page_slug,
        "dry_run": not args.apply,
        "changed": changed,
        "before_sha256": digest(page["body"]),
        "after_sha256": digest(updated),
        "after_semantic_sha256": semantic_digest(updated),
        "config": str(args.config),
        "wiki_page_current": page_current,
        "course_syllabus_current": course_current,
    }
    if args.apply and changed:
        expected = f"{config['confirmation_prefix']}-{args.course}"
        if args.confirm != expected:
            raise ValueError(f"Apply requires --confirm {expected}")
        if not page_current:
            saved = canvas.raw(
                "PUT", f"/courses/{args.course}/pages/{page_slug}",
                {"wiki_page": {
                    "body": updated,
                    "front_page": config.get("front_page", False),
                    "published": config.get("published", False),
                }},
            )
            result["saved_page_id"] = saved.get("page_id")
        if sync_course_syllabus and not course_current:
            canvas.raw(
                "PUT", f"/courses/{args.course}",
                {"course": {"syllabus_body": updated}},
            )
            result["course_syllabus_updated"] = True
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
