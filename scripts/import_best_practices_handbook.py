#!/usr/bin/env python3
"""Import and adapt the complete Tooling Handbook for public distribution."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = PROJECT_ROOT / "docs" / "best-practices"
PUBLIC_SOURCE = "https://github.com/mreidhorrigan/best-practices-for-tool-development"
LOCAL_USER_ROOT_PATTERN = r"/" + r"Users/" + r"matthorrigan"

TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonc", ".command", ".sh", ".py"}
NAME_REPLACEMENTS = (
    ("REAPER_COMPOSITION_HOME", "CANVAS_AUTOMATION_HOME"),
    ("REAPER_COMPOSITION", "CANVAS_AUTOMATION"),
    ("GENERATIVE_DIFFUSION", "CANVAS_AUTOMATION"),
    ("MERGED_IMAGEPROCESSTOOL", "CANVAS_AUTOMATION"),
    ("VIDEO_PROCESSING", "CANVAS_AUTOMATION"),
    ("ABLETON_COMPOSITION", "CANVAS_AUTOMATION"),
    ("INKSCAPE_DEVELOPMENT", "CANVAS_AUTOMATION"),
    ("SOCI_MEDIA_API_EXPERIMENTS", "CANVAS_AUTOMATION"),
    ("SCANSION_MAKER", "CANVAS_AUTOMATION"),
    ("ableton-compose-mcp", "canvas-mcp"),
    ("ableton_compose", "canvas_automation"),
    ("ableton-compose", "canvas-mcp"),
    ("inkscape-mcp", "canvas-mcp"),
    ("INKS_WORKSPACE", "CANVAS_WORKSPACE"),
    ("INKS_INKSCAPE_BIN", "CANVAS_MCP_COMMAND"),
    ("INKS_TIMEOUT", "CANVAS_TIMEOUT"),
    ("INKS_MAX_FILE", "CANVAS_MAX_FILE"),
    ("GENDIFF", "Canvas Automation Toolkit"),
    ("gendiff", "Canvas Automation Toolkit"),
    ("REAPER", "Canvas Automation Toolkit"),
    ("Reaper", "Canvas Automation Toolkit"),
    ("reaper", "Canvas Automation Toolkit"),
    ("ABLETON", "Canvas Automation Toolkit"),
    ("Ableton", "Canvas"),
    ("ableton", "Canvas"),
    ("INKSCAPE", "Canvas Automation Toolkit"),
    ("Inkscape", "Canvas"),
    ("inkscape", "Canvas"),
    ("Claude Code's", "an AI CLI's"),
    ("Claude Code", "an AI CLI"),
    ("CLAUDE.md", "AGENTS.md"),
    (".claude/", ".agents/"),
    ("DOSSIER_TOOLS", "CANVAS_AUTOMATION"),
    ("DOSSIER", "Canvas Automation Toolkit"),
    ("Dossier", "course package"),
    ("dossier", "course package"),
    ("soci-media", "staged course workflow"),
    ("mvx", "companion tool"),
    ("studio-suite", "Canvas Automation Toolkit"),
    ("studio/jsonc.py", "src/canvas_automation/jsonc.py"),
    ("studio/config.py", "src/canvas_automation/config.py"),
    ("bin/studio", ".venv/bin/canvas-automation"),
    ("studio", "orchestrator"),
    ("AudioLDM", "an optional model"),
    ("audioldm", "optional-model"),
    ("Freesound", "an external asset service"),
    ("freesound", "external-service"),
    ("dense-collage", "course-package"),
)


def adapt_text(text: str, relative_path: str) -> str:
    """Remove machine-specific references and map examples to this toolkit."""
    text = re.sub(
        LOCAL_USER_ROOT_PATTERN + r"/CLAUDE_PROJECTS/[A-Za-z0-9_.-]+",
        "<toolkit-root>",
        text,
    )
    text = re.sub(
        LOCAL_USER_ROOT_PATTERN + r"/Documents/bio/storage/[A-Za-z0-9_./*-]+",
        "<toolkit-root>",
        text,
    )
    local_user_root = "/" + "Users" + "/" + "matthorrigan"
    text = text.replace(local_user_root + "/CLAUDE_PROJECTS", "<toolkit-root>")
    text = text.replace(local_user_root + "/Documents/bio/storage", "<toolkit-root>")
    text = text.replace(local_user_root + "/.local/bin", "<local-bin>")
    text = re.sub(r"/Users/[A-Za-z0-9._-]+", "<user-home>", text)
    text = text.replace("CLAUDE_PROJECTS/", "")
    text = text.replace("bio/storage/", "<toolkit-root>/archive/")
    text = text.replace(
        "[research/00-process-audit.md](research/00-process-audit.md)",
        "the source handbook's process audit",
    )
    for old, new in NAME_REPLACEMENTS:
        text = text.replace(old, new)

    if relative_path == "README.md":
        text = re.sub(
            r"- \[research/\]\(research/\):.*?\[research/00-process-audit\.md\]\(research/00-process-audit\.md\)\.\n",
            "",
            text,
            flags=re.S,
        )
        text = re.sub(
            r"## The exemplars\n.*\Z",
            """## CourseTools as the reference implementation

The Canvas Automation Toolkit applies the handbook throughout its public source tree:

| Practice | CourseTools implementation |
|---|---|
| Thin human launchers over a reusable engine | `commands/`, `src/canvas_automation/` |
| Reviewed configuration as an interface | documented `*.config.jsonc` and schemas |
| Deterministic output and provenance | IMSCC, test-form, manifest, SBOM, and release builders |
| Guarded external writes | one-course Canvas API guard and sandbox initialization |
| Optional agent integration | `skills/`, `mcp/`, and deterministic commands |
| Portable distribution | `setup-after-move.command`, `uv.lock`, platform notes, and stored tests |
""",
            text,
            flags=re.S,
        )

    banner = (
        "> **CourseTools edition.** This file is part of a complete public adaptation of Matt "
        "Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation "
        "Toolkit, and private machine paths and unavailable project references have been removed.\n\n"
    )
    if (
        Path(relative_path).suffix.lower() == ".md"
        and relative_path != "LICENSE.md"
        and not text.startswith("> **CourseTools edition.")
    ):
        text = banner + text
    return text.rstrip() + "\n"


def import_handbook(source: Path, destination: Path) -> list[str]:
    required = [source / "README.md", source / "checklist.md", source / "LICENSE.md"]
    if not all(path.is_file() for path in required):
        raise FileNotFoundError("Source must contain README.md, checklist.md, and LICENSE.md")

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    included: list[str] = []
    for path in sorted(source.rglob("*")):
        relative_parts = path.relative_to(source).parts
        if (
            not path.is_file()
            or any(part.startswith(".") for part in relative_parts)
            or (relative_parts and relative_parts[0] == "research")
        ):
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in TEXT_SUFFIXES or relative_parts[0] == "templates":
            target.write_text(adapt_text(path.read_text(encoding="utf-8"), relative.as_posix()), encoding="utf-8")
        else:
            shutil.copy2(path, target)
        included.append(relative.as_posix())

    provenance = destination / "COURSETOOLS-ADAPTATION.md"
    provenance.write_text(
        f"""# CourseTools handbook adaptation

This directory contains the complete published Tooling Handbook: its introduction, 15 chapters,
checklist, reusable templates, and license. Source-development research notes are omitted because
they document unrelated local projects rather than recipient-facing handbook instructions.

Source: [{PUBLIC_SOURCE}]({PUBLIC_SOURCE})  
Copyright © 2026 Matt Horrigan  
License: [CC BY-SA 4.0](LICENSE.md)

`scripts/import_best_practices_handbook.py` produced this edition. The adaptation maps examples
to the Canvas Automation Toolkit, replaces private absolute paths with portable placeholders,
and removes references that require access to unrelated private projects. The concise
CourseTools-specific operating guide remains at [`../BEST_PRACTICES_HANDBOOK.md`](../BEST_PRACTICES_HANDBOOK.md).
""",
        encoding="utf-8",
    )
    included.append("COURSETOOLS-ADAPTATION.md")
    return sorted(included)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to a checked-out Tooling Handbook")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    files = import_handbook(args.source.resolve(), args.destination.resolve())
    print(f"Imported {len(files)} files into {args.destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
