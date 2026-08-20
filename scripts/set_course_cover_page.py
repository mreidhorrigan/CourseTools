#!/usr/bin/env python3
"""Create a basic Canvas cover page and make it the guarded course home page."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from canvas_automation import jsonc
from canvas_automation.course_html import compile_fragment
from course_authoring import build_links, course_id
from sandbox_course_lifecycle import GuardedCanvas

TITLE = "IAT 210 Course Home"
SLUG = "iat-210-course-home"
SOURCE = "course/content/pages/course-home.html"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    config = jsonc.load_and_validate(ROOT / "course/course.config.jsonc")
    cid = course_id(config)
    expected = f"SET-COURSE-HOME-{cid}"
    if args.confirm != expected:
        raise ValueError(f"Apply requires --confirm {expected}")
    canvas = GuardedCanvas(args.server, cid)
    canvas.health(); canvas.require_unpublished()
    source = (ROOT / SOURCE).read_text(encoding="utf-8")
    css = (ROOT / config["authoring"]["stylesheet"]).read_text(encoding="utf-8")
    body = compile_fragment(source, css)
    pages = canvas.raw("GET", f"/courses/{cid}/pages", params={"per_page": 100})
    existing = next((page for page in pages if page.get("url") == SLUG or page.get("title") == TITLE), None)
    payload = {"wiki_page": {"title": TITLE, "body": body, "published": True, "front_page": True}}
    if existing:
        page = canvas.raw("PUT", f"/courses/{cid}/pages/{SLUG}", payload)
    else:
        page = canvas.raw("POST", f"/courses/{cid}/pages", payload)
    canvas.raw("PUT", f"/courses/{cid}", {"course": {"default_view": "wiki"}})

    manifest_path = ROOT / config["authoring"]["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["objects"]:
        if item.get("kind") == "page":
            item["front_page"] = item.get("slug") == SLUG
    record = next((item for item in manifest["objects"]
                   if item.get("slug") == SLUG or item.get("source") == SOURCE), None)
    page_id = page.get("page_id") or page.get("id")
    live_slug = page.get("url") or SLUG
    values = {"canvas_id": page_id, "front_page": True, "kind": "page", "published": True,
              "slug": live_slug, "source": SOURCE, "title": TITLE}
    if record is None:
        manifest["objects"].append(values)
    else:
        record.update(values)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    links = build_links(ROOT, manifest, config)
    (ROOT / config["authoring"]["links_manifest"]).write_text(
        json.dumps(links, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"course_id": cid, "page_id": page_id, "slug": live_slug, "front_page": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
