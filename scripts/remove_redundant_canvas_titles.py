#!/usr/bin/env python3
"""Remove in-body H1 titles that Canvas renders separately for the item type."""
from __future__ import annotations
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTOMATIC_TITLE_KINDS = {"page", "assignment", "discussion"}

def normalized(value: str) -> str:
    value = re.sub(r"^\[OUTTAKE\]\s*", "", value, flags=re.I)
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

def main() -> int:
    manifest = json.loads((ROOT / "course/course-manifest.json").read_text(encoding="utf-8"))
    changed = []
    seen = set()
    for item in manifest["objects"]:
        if item["kind"] not in AUTOMATIC_TITLE_KINDS or item["source"] in seen:
            continue
        seen.add(item["source"])
        path = ROOT / item["source"]
        source = path.read_text(encoding="utf-8")
        match = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, flags=re.I | re.S)
        if not match or normalized(match.group(1)) != normalized(item["title"]):
            continue
        updated = source[:match.start()] + source[match.end():]
        path.write_text(updated, encoding="utf-8")
        changed.append(item["source"])
    print(json.dumps({"automatic_title_kinds": sorted(AUTOMATIC_TITLE_KINDS),
                      "changed_sources": changed}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
