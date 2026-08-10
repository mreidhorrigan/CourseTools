#!/usr/bin/env python3
"""Export, verify, apply, and package canonical Canvas course prose."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from canvas_automation import jsonc
from sandbox_course_lifecycle import GuardedCanvas

FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def semantic(text: str) -> str:
    soup = BeautifulSoup(text or "", "html.parser")
    for tag in soup.find_all(True):
        tag.attrs.pop("data-api-endpoint", None)
        tag.attrs.pop("data-api-returntype", None)
    return sha(str(soup))


def safe_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return value[:90] or "untitled"


def course_id(config: dict) -> int:
    match = re.search(r"/courses/([1-9][0-9]*)", config["course_url"])
    if not match:
        raise ValueError("course.config.jsonc has no numeric /courses/:id URL")
    return int(match.group(1))


def load_context(root: Path, server: str):
    config = jsonc.load_and_validate(root / "course/course.config.jsonc")
    cid = course_id(config)
    canvas = GuardedCanvas(server, cid)
    canvas.health()
    return config, cid, canvas


def write_source(root: Path, relative: str, body: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body or "", encoding="utf-8")


def object_record(kind, canvas_id, title, source, *, slug=None, published=None, front_page=None):
    record = {"kind": kind, "canvas_id": canvas_id, "title": title, "source": source}
    if slug is not None:
        record["slug"] = slug
    if published is not None:
        record["published"] = published
    if front_page is not None:
        record["front_page"] = front_page
    return record


def live_objects(canvas: GuardedCanvas, cid: int):
    course = canvas.raw("GET", f"/courses/{cid}", params={"include[]": "syllabus_body"})
    return course, {
        "page": canvas.raw("GET", f"/courses/{cid}/pages", params={"per_page": 100}),
        "assignment": canvas.raw("GET", f"/courses/{cid}/assignments", params={"per_page": 100}),
        "discussion": canvas.raw("GET", f"/courses/{cid}/discussion_topics", params={"per_page": 100}),
        "quiz": canvas.raw("GET", f"/courses/{cid}/quizzes", params={"per_page": 100}),
    }


def export_live(root: Path, server: str, initialize: bool) -> dict:
    config, cid, canvas = load_context(root, server)
    manifest_path = root / config["authoring"]["manifest"]
    old_sources = set()
    if manifest_path.exists():
        old_sources = {item["source"] for item in json.loads(manifest_path.read_text())["objects"]}
    if manifest_path.exists() and not initialize:
        raise ValueError("Authoring manifest already exists; export-live requires --initialize to replace its mapped sources")
    course, collections = live_objects(canvas, cid)
    if course.get("workflow_state") != "unpublished":
        raise RuntimeError("Refusing to initialize from a published course")
    objects = []
    syllabus = course.get("syllabus_body") or ""
    write_source(root, "course/content/syllabus.html", syllabus)
    objects.append(object_record("syllabus", cid, "Canvas Syllabus", "course/content/syllabus.html"))

    for page in sorted(collections["page"], key=lambda item: item["url"]):
        full = canvas.raw("GET", f"/courses/{cid}/pages/{page['url']}")
        section = "outtakes/pages" if full["title"].startswith("[OUTTAKE]") else "pages"
        source = f"course/content/{section}/{page['url']}.html"
        if full.get("front_page") and semantic(full.get("body") or "") == semantic(syllabus):
            source = "course/content/syllabus.html"
        else:
            write_source(root, source, full.get("body") or "")
        objects.append(object_record("page", full.get("page_id") or full.get("id"), full["title"], source, slug=full["url"], published=full.get("published"), front_page=full.get("front_page")))

    fields = {"assignment": ("name", "description"), "discussion": ("title", "message"), "quiz": ("title", "description")}
    for kind in ("assignment", "discussion", "quiz"):
        title_key, body_key = fields[kind]
        for item in sorted(collections[kind], key=lambda value: (value[title_key], value["id"])):
            if kind == "assignment" and set(item.get("submission_types") or []).intersection({"online_quiz", "discussion_topic"}):
                continue
            directory = {"assignment": "assignments", "discussion": "discussions", "quiz": "quizzes"}[kind]
            source = f"course/content/{directory}/{item['id']}-{safe_name(item[title_key])}.html"
            write_source(root, source, item.get(body_key) or "")
            objects.append(object_record(kind, item["id"], item[title_key], source, published=item.get("published")))

    manifest = {
        "schema": "canvas-course-authoring/v1", "course_id": cid, "course_url": config["course_url"],
        "requires_reinitialization": False,
        "course_name": course.get("name"), "course_code": course.get("course_code"),
        "source_policy": "Files named by source are authoritative; Canvas and IMSCC are generated targets.",
        "objects": objects,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    new_sources = {item["source"] for item in objects}
    content_root = (root / "course/content").resolve()
    for relative in sorted(old_sources - new_sources):
        stale = (root / relative).resolve()
        if content_root in stale.parents and stale.is_file():
            stale.unlink()
    links = build_links(root, manifest, config)
    links_path = root / config["authoring"]["links_manifest"]
    links_path.write_text(json.dumps(links, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"course_id": cid, "objects": len(objects), "unique_sources": len({item["source"] for item in objects}), "links": len(links["links"]), "manifest": str(manifest_path)}


def build_links(root: Path, manifest: dict, config: dict) -> dict:
    occurrences = defaultdict(list)
    for obj in manifest["objects"]:
        body = (root / obj["source"]).read_text(encoding="utf-8")
        for anchor in BeautifulSoup(body, "html.parser").find_all("a", href=True):
            href = anchor["href"].strip()
            occurrences[href].append({"kind": obj["kind"], "title": obj["title"], "source": obj["source"], "anchor_text": anchor.get_text(" ", strip=True)})
    canvas_host = config["institution"]["canvas_host"].casefold()
    institution_domains = tuple(item.casefold() for item in config["institution"]["policy_search_domains"])
    resolver_hosts = {item.casefold() for item in config["institution"]["library_resolver_hosts"]}
    links = []
    for href, uses in sorted(occurrences.items()):
        host = (urlparse(href).hostname or "").casefold()
        if href.startswith(("mailto:", "tel:")):
            category = "contact"
        elif href.startswith(("$", "/", "#")):
            category = "course-internal"
        elif host == canvas_host:
            category = "canvas-instance"
        elif host in resolver_hosts:
            category = "library-resolver"
        elif any(host == domain or host.endswith("." + domain) for domain in institution_domains):
            category = "institution"
        else:
            category = "external"
        action = {
            "contact": "confirm for target course",
            "course-internal": "verify after import or course copy",
            "canvas-instance": "replace or migration-enable for target course",
            "library-resolver": "replace with stable item-level or open-access URL",
            "institution": "AI/human review against current official policy",
            "external": "run provider-aware link QA and confirm intended work",
        }[category]
        links.append({"url": href, "category": category, "review_action": action, "occurrences": uses})
    return {"schema": "canvas-course-links/v1", "institution": config["institution"], "links": links}


def endpoint(obj, cid):
    if obj["kind"] == "syllabus": return "PUT", f"/courses/{cid}", "course", "syllabus_body"
    if obj["kind"] == "page": return "PUT", f"/courses/{cid}/pages/{obj['slug']}", "wiki_page", "body"
    if obj["kind"] == "assignment": return "PUT", f"/courses/{cid}/assignments/{obj['canvas_id']}", "assignment", "description"
    if obj["kind"] == "discussion": return "PUT", f"/courses/{cid}/discussion_topics/{obj['canvas_id']}", None, "message"
    if obj["kind"] == "quiz": return "PUT", f"/courses/{cid}/quizzes/{obj['canvas_id']}", "quiz", "description"
    raise ValueError(f"Unsupported kind: {obj['kind']}")


def current_body(canvas, cid, obj):
    if obj["kind"] == "syllabus":
        return (canvas.raw("GET", f"/courses/{cid}", params={"include[]": "syllabus_body"}).get("syllabus_body") or "")
    if obj["kind"] == "page": return canvas.raw("GET", f"/courses/{cid}/pages/{obj['slug']}").get("body") or ""
    path = {"assignment": "assignments", "discussion": "discussion_topics", "quiz": "quizzes"}[obj["kind"]]
    field = {"assignment": "description", "discussion": "message", "quiz": "description"}[obj["kind"]]
    return canvas.raw("GET", f"/courses/{cid}/{path}/{obj['canvas_id']}").get(field) or ""


def compare_or_apply(root, server, apply, confirm):
    config, cid, canvas = load_context(root, server)
    manifest = json.loads((root / config["authoring"]["manifest"]).read_text(encoding="utf-8"))
    if manifest.get("requires_reinitialization"):
        raise RuntimeError("Run export-live --initialize for this target before verification or apply")
    if manifest["course_id"] != cid:
        raise RuntimeError("Authoring manifest course_id does not match course.config.jsonc")
    if apply and confirm != f"SYNC-AUTHORING-{cid}":
        raise ValueError(f"Apply requires --confirm SYNC-AUTHORING-{cid}")
    if apply and canvas.raw("GET", f"/courses/{cid}").get("workflow_state") != "unpublished":
        raise RuntimeError("Refusing authoring synchronization because the target course is published")
    changes = []
    source_cache = {}
    for obj in manifest["objects"]:
        desired = source_cache.setdefault(obj["source"], (root / obj["source"]).read_text(encoding="utf-8"))
        live = current_body(canvas, cid, obj)
        if semantic(desired) == semantic(live):
            continue
        changes.append({"kind": obj["kind"], "title": obj["title"], "source": obj["source"], "before": semantic(live), "after": semantic(desired)})
        if apply:
            method, path, wrapper, field = endpoint(obj, cid)
            payload = {field: desired}
            if wrapper: payload = {wrapper: payload}
            canvas.raw(method, path, payload)
    expected_links = build_links(root, manifest, config)
    stored_links = json.loads((root / config["authoring"]["links_manifest"]).read_text(encoding="utf-8"))
    return {"course_id": cid, "status": "CURRENT" if not changes else ("APPLIED" if apply else "DRIFT"), "changed_objects": changes, "links_manifest_current": expected_links == stored_links}


def xml_title(data):
    try: tree = etree.fromstring(data)
    except etree.XMLSyntaxError: return ""
    titles = tree.xpath("//*[local-name()='title']/text()")
    return titles[0] if titles else ""


def replace_xml_description(data, body):
    tree = etree.fromstring(data)
    nodes = tree.xpath("/*/*[local-name()='description' or local-name()='message' or local-name()='text']")
    if not nodes: return data
    nodes[0].text = body
    return etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def rubric_title_key(value):
    value = re.sub(r"\s*\(Restored[^)]*\)\s*$", "", value or "", flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def replace_rubrics_xml(data, rubric_sources):
    """Preserve rubric resource IDs while replacing editable titles and criteria."""
    tree = etree.fromstring(data)
    by_title = {rubric_title_key(item["title"]): item for item in rubric_sources}
    updated = 0
    for rubric in tree.xpath("//*[local-name()='rubric']"):
        title_nodes = rubric.xpath("./*[local-name()='title']")
        if not title_nodes:
            continue
        source = by_title.get(rubric_title_key(title_nodes[0].text or ""))
        if not source:
            continue
        namespace = etree.QName(rubric).namespace
        qname = lambda name: f"{{{namespace}}}{name}" if namespace else name
        title_nodes[0].text = source["title"]
        points_nodes = rubric.xpath("./*[local-name()='points_possible']")
        if points_nodes:
            points_nodes[0].text = str(float(source["points_possible"]))
        criteria_nodes = rubric.xpath("./*[local-name()='criteria']")
        if not criteria_nodes:
            criteria_parent = etree.SubElement(rubric, qname("criteria"))
        else:
            criteria_parent = criteria_nodes[0]
            for child in list(criteria_parent):
                criteria_parent.remove(child)
        for index, criterion in enumerate(source["criteria"]):
            node = etree.SubElement(criteria_parent, qname("criterion"))
            stable = int(hashlib.sha256(f"{source['key']}:criterion:{index}".encode()).hexdigest()[:8], 16)
            etree.SubElement(node, qname("criterion_id")).text = f"_{stable}"
            etree.SubElement(node, qname("points")).text = str(float(criterion["points"]))
            etree.SubElement(node, qname("description")).text = criterion["description"]
            if criterion.get("long_description"):
                etree.SubElement(node, qname("long_description")).text = criterion["long_description"]
            ratings = etree.SubElement(node, qname("ratings"))
            for rating_index, rating in enumerate(criterion.get("ratings", [])):
                rating_node = etree.SubElement(ratings, qname("rating"))
                etree.SubElement(rating_node, qname("description")).text = rating["description"]
                etree.SubElement(rating_node, qname("points")).text = str(float(rating["points"]))
                etree.SubElement(rating_node, qname("criterion_id")).text = f"_{stable}"
                rating_stable = int(hashlib.sha256(f"{source['key']}:rating:{index}:{rating_index}".encode()).hexdigest()[:8], 16)
                etree.SubElement(rating_node, qname("id")).text = f"_{rating_stable}"
        updated += 1
    return etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True), updated


def build_imscc(root, output: Path | None):
    config = jsonc.load_and_validate(root / "course/course.config.jsonc")
    manifest = json.loads((root / config["authoring"]["manifest"]).read_text(encoding="utf-8"))
    if manifest.get("requires_reinitialization"):
        raise RuntimeError("Run export-live --initialize before building an IMSCC for this target")
    source = root / config["authoring"]["imscc_template"]
    if not source.is_file(): raise ValueError("Configure authoring.imscc_template before building")
    output = output or root / "out/course-authoring/course-from-authoring.imscc"
    output.parent.mkdir(parents=True, exist_ok=True)
    bodies = {obj["title"]: (root / obj["source"]).read_text(encoding="utf-8") for obj in manifest["objects"]}
    page_bodies = {obj.get("slug"): (root / obj["source"]).read_text(encoding="utf-8") for obj in manifest["objects"] if obj["kind"] == "page"}
    replacements = {}
    rubric_manifest_path = root / "course/rubric-manifest.json"
    rubric_sources = []
    if rubric_manifest_path.is_file():
        rubric_manifest = json.loads(rubric_manifest_path.read_text(encoding="utf-8"))
        rubric_sources = [json.loads((root / item["source"]).read_text(encoding="utf-8")) for item in rubric_manifest["rubrics"]]
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        if "course_settings/syllabus.html" in names: replacements["course_settings/syllabus.html"] = bodies["Canvas Syllabus"].encode()
        if rubric_sources and "course_settings/rubrics.xml" in names:
            replacement, _ = replace_rubrics_xml(archive.read("course_settings/rubrics.xml"), rubric_sources)
            replacements["course_settings/rubrics.xml"] = replacement
        for slug, body in page_bodies.items():
            name = f"wiki_content/{slug}.html"
            if name in names: replacements[name] = body.encode()
        for name in names:
            data = archive.read(name)
            if name.endswith("assignment_settings.xml"):
                title = xml_title(data)
                html_name = str(Path(name).parent / "assignment.html")
                if title in bodies and html_name in names: replacements[html_name] = bodies[title].encode()
            elif name.endswith("assessment_meta.xml"):
                title = xml_title(data)
                if title in bodies: replacements[name] = replace_xml_description(data, bodies[title])
            elif name.endswith(".xml"):
                title = xml_title(data)
                if title in bodies: replacements[name] = replace_xml_description(data, bodies[title])
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
            for name in sorted(names):
                info = zipfile.ZipInfo(name, FIXED_ZIP_TIME); info.external_attr = 0o100644 << 16
                target.writestr(info, replacements.get(name, archive.read(name)), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return {"output": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "updated_resources": len(replacements)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export-live"); export.add_argument("--initialize", action="store_true")
    verify = sub.add_parser("verify")
    apply_parser = sub.add_parser("apply"); apply_parser.add_argument("--confirm", required=True)
    build = sub.add_parser("build-imscc"); build.add_argument("--output", type=Path)
    links = sub.add_parser("refresh-links")
    args = parser.parse_args(); root = args.root.resolve()
    if args.command == "export-live": result = export_live(root, args.server, args.initialize)
    elif args.command == "verify": result = compare_or_apply(root, args.server, False, None)
    elif args.command == "apply": result = compare_or_apply(root, args.server, True, args.confirm)
    elif args.command == "build-imscc": result = build_imscc(root, args.output)
    else:
        config = jsonc.load_and_validate(root / "course/course.config.jsonc")
        manifest = json.loads((root / config["authoring"]["manifest"]).read_text())
        result = build_links(root, manifest, config)
        (root / config["authoring"]["links_manifest"]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
