#!/usr/bin/env python3
"""Extract Canvas rubric XML from an IMSCC into editable JSON source files."""
from __future__ import annotations

import argparse
import json
import re
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


def slugify(value: str) -> str:
    value = re.sub(r"\s*\(Restored[^)]*\)\s*$", "", value, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def extract(package: Path) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="rubric_extract_") as temporary:
        with zipfile.ZipFile(package) as archive:
            try:
                data = archive.read("course_settings/rubrics.xml")
            except KeyError:
                raise ValueError("IMSCC has no course_settings/rubrics.xml") from None
        tree = etree.fromstring(data)
    rubrics = []
    for node in tree.xpath("//*[local-name()='rubric']"):
        text = lambda name: "".join(node.xpath(f"./*[local-name()='{name}']/text()"))
        title = text("title").strip()
        criteria = []
        for criterion in node.xpath("./*[local-name()='criteria']/*[local-name()='criterion']"):
            ctext = lambda name: "".join(criterion.xpath(f"./*[local-name()='{name}']/text()"))
            ratings = []
            for rating in criterion.xpath("./*[local-name()='ratings']/*[local-name()='rating']"):
                rtext = lambda name: "".join(rating.xpath(f"./*[local-name()='{name}']/text()"))
                ratings.append({"description": rtext("description").strip(), "points": float(rtext("points"))})
            criteria.append({"description": ctext("description").strip(), "points": float(ctext("points")), "ratings": ratings})
        rubrics.append({"schema": "canvas-automation/rubric-source/v1", "key": slugify(title),
                        "title": re.sub(r"\s*\(Restored[^)]*\)\s*$", "", title, flags=re.I),
                        "points_possible": float(text("points_possible")), "criteria": criteria})
    return sorted(rubrics, key=lambda item: item["key"])


def write_sources(package: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for rubric in extract(package):
        path = output_dir / f"{rubric['key']}.json"
        path.write_text(json.dumps(rubric, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    paths = write_sources(args.package.resolve(), args.output_dir.resolve())
    print(json.dumps({"rubrics": len(paths), "output_dir": str(args.output_dir.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
