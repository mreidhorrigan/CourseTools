#!/usr/bin/env python3
"""One-time, prose-preserving migration from legacy inline styles to semantic classes."""
from __future__ import annotations

import argparse
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]

CLASS_BY_STYLE = {
    "border:1px solid #94bad2;background:#f4faff;padding:9px 12px;margin:0 0 14px;line-height:1.7": "course-navigation",
    "border:1px solid #94bad2;background:#f4faff;padding:10px 12px;margin:0 0 16px;line-height:1.7": "course-navigation",
    "border:1px solid #85bfe5;background:#f4faff;padding:12px 14px;margin:1rem 0": "information-note",
    "border:1px solid #85bfe5;background:#f4faff;padding:10px 12px": "information-note",
    "border-left:5px solid #b64024;background:#faf6f3;padding:11px 14px;margin:1rem 0": "emphasis-note",
    "background:#f8fbfd;": "alternate-row",
}


def normalized(style: str) -> str:
    return "".join(style.split()).rstrip(";") + (";" if style.rstrip().endswith(";") else "")


def add_class(tag, value: str) -> None:
    tag["class"] = list(dict.fromkeys([*(tag.get("class") or []), value]))


def transform(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    roots = [tag for tag in soup.contents if getattr(tag, "name", None)]
    if len(roots) == 1 and roots[0].name == "div":
        container = roots[0]
        add_class(container, "canvas-course")
    else:
        container = soup.new_tag("div")
        container["class"] = ["canvas-course"]
        for child in list(soup.contents):
            container.append(child.extract())
        soup.append(container)

    for tag in soup.find_all(style=True):
        style = normalized(tag["style"])
        compact = style.replace(" ", "")
        mapped = CLASS_BY_STYLE.get(compact)
        if mapped:
            add_class(tag, mapped)
        if tag.name == "td" and "text-align:center" in compact:
            add_class(tag, "centered-cell")
        if tag.name == "th":
            for width in (6, 12, 19, 20, 43, 48):
                if f"width:{width}%" in compact:
                    add_class(tag, f"column-{width}")
        del tag["style"]
    return str(soup).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed = []
    for path in sorted((args.root / "course/content").rglob("*.html")):
        before = path.read_text(encoding="utf-8")
        after = transform(before)
        if before != after:
            changed.append(path.relative_to(args.root).as_posix())
            if args.apply:
                path.write_text(after, encoding="utf-8")
    print({"mode": "apply" if args.apply else "plan", "changed": changed, "count": len(changed)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
