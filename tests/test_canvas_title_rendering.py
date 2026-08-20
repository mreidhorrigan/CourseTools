import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTOMATIC_TITLE_KINDS = {"page", "assignment", "discussion"}

def normalized(value):
    value = re.sub(r"^\[OUTTAKE\]\s*", "", value, flags=re.I)
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

def test_canvas_automatic_title_types_do_not_repeat_their_title_as_first_h1():
    manifest = json.loads((ROOT / "course/course-manifest.json").read_text())
    checked = set()
    for item in manifest["objects"]:
        if item["kind"] not in AUTOMATIC_TITLE_KINDS or item["source"] in checked:
            continue
        checked.add(item["source"])
        source = (ROOT / item["source"]).read_text()
        match = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, flags=re.I | re.S)
        assert not match or normalized(match.group(1)) != normalized(item["title"]), item["source"]
