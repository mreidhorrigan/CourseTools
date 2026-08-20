#!/usr/bin/env python3
"""Rename the designed artifact from procedural ecology to procedural ecosystem."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from canvas_automation import jsonc
from course_authoring import build_links, course_id
from sandbox_course_lifecycle import GuardedCanvas

PROJECT_REPLACEMENTS = (
    ("Digital Procedural-Ecology", "Digital Procedural-Ecosystem"),
    ("Digital game design: procedural ecology", "Digital game design: procedural ecosystem"),
    ("browser-playable procedural ecology", "browser-playable procedural ecosystem"),
)
ECOSYSTEM_PATHS = (
    "course/content/assignments/211860-digital-procedural-ecology-project-design-and-technical-plan.html",
    "course/content/assignments/211861-digital-procedural-ecology-project-final-submission.html",
    "course/content/discussions/259659-digital-procedural-ecology-project-ideation-discussion.html",
    "course/content/rubrics/digital-procedural-ecology-ideation.json",
    "course/content/rubrics/digital-procedural-ecology-plan.json",
    "course/content/rubrics/digital-procedural-ecology-final.json",
    "course/research/idn-videogame-design-option.md",
    "course/research/rubric-benchmarks/evolution-of-trust.md",
    "commands/mistral-rubric-discrimination.config.jsonc",
)
PROJECT_PATHS = (
    "course/content/syllabus.html", "course/content/pages/course-rationale-and-design.html",
    "course/course-manifest.json", "course/rubric-manifest.json",
    "commands/build-course-dossier.config.jsonc", "scripts/configure_iat210_course.py",
    "scripts/update_iat210_syllabus_454.py", "scripts/verify_iat210_454.py",
    "tests/test_iat210_syllabus_454.py", "examples/iat210/syllabus-links.config.jsonc",
)


def replace_file(path: Path, replacements: tuple[tuple[str, str], ...]) -> bool:
    before = path.read_text(encoding="utf-8")
    after = before
    for old, new in replacements:
        after = after.replace(old, new)
    if after != before:
        path.write_text(after, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    config = jsonc.load_and_validate(ROOT / "course/course.config.jsonc")
    cid = course_id(config); expected = f"RENAME-PROCEDURAL-ECOSYSTEM-{cid}"
    if args.confirm != expected:
        raise ValueError(f"Apply requires --confirm {expected}")
    canvas = GuardedCanvas(args.server, cid); canvas.health(); canvas.require_unpublished()
    changed = []
    for relative in PROJECT_PATHS:
        if replace_file(ROOT / relative, PROJECT_REPLACEMENTS): changed.append(relative)
    artifact_replacements = PROJECT_REPLACEMENTS + (
        ("procedural ecology", "procedural ecosystem"),
        ("Procedural ecology", "Procedural ecosystem"),
        ("interacting ecology", "interacting ecosystem"),
        ("loop or ecology", "loop or ecosystem"),
    )
    for relative in ECOSYSTEM_PATHS:
        if replace_file(ROOT / relative, artifact_replacements): changed.append(relative)

    canvas.raw("PUT", f"/courses/{cid}/assignments/211860", {"assignment": {"name": "Digital Procedural-Ecosystem Project: Design and Technical Plan"}})
    canvas.raw("PUT", f"/courses/{cid}/assignments/211861", {"assignment": {"name": "Digital Procedural-Ecosystem Project: Final Submission"}})
    canvas.raw("PUT", f"/courses/{cid}/discussion_topics/259659", {"title": "Digital Procedural-Ecosystem Project: Ideation Discussion"})
    # The linked graded-discussion assignment may retain its own display name.
    assignments = canvas.raw("GET", f"/courses/{cid}/assignments", params={"per_page": 100})
    for assignment in assignments:
        if assignment.get("name") == "Digital Procedural-Ecology Project: Ideation Discussion":
            canvas.raw("PUT", f"/courses/{cid}/assignments/{assignment['id']}", {"assignment": {"name": "Digital Procedural-Ecosystem Project: Ideation Discussion"}})

    manifest = json.loads((ROOT / config["authoring"]["manifest"]).read_text(encoding="utf-8"))
    links = build_links(ROOT, manifest, config)
    (ROOT / config["authoring"]["links_manifest"]).write_text(json.dumps(links, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"course_id": cid, "changed_files": sorted(set(changed))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
