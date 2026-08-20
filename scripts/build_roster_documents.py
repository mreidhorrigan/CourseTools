#!/usr/bin/env python3
"""Build DOC_TOOLS-format seating charts and nameplates from a private roster run."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canvas_automation import jsonc


def newest_private_run(root: Path) -> Path:
    candidates = sorted((root / "out/private-roster").glob("*__course-*"), reverse=True)
    if not candidates:
        raise ValueError("No private roster run found; run pull-canvas-roster.command first")
    return candidates[0]


def count_data_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def count_seats(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(value.strip().upper() == "X" for row in csv.reader(handle) for value in row)


def node_environment(root: Path, seed: int) -> dict[str, str]:
    environment = dict(os.environ)
    environment["NODE_PATH"] = str(root / "vendor/testmaker-mcqer/node_modules")
    environment["SEATPLANNER_SEED"] = str(seed)
    return environment


def run_command(command: list[str], environment: dict[str, str]) -> None:
    result = subprocess.run(command, text=True, capture_output=True, env=environment)
    if result.returncode:
        # DOC_TOOLS errors contain paths or aggregate diagnostics, never roster rows.
        raise RuntimeError((result.stderr or result.stdout or "Document renderer failed").strip())


def build(run_dir: Path, config: dict, root: Path) -> dict:
    required = [run_dir / "nameplates.csv", run_dir / "seatplanner-source.csv"]
    if any(not path.is_file() for path in required):
        raise ValueError("Roster run predates document adapters; pull the Canvas roster again")
    output = run_dir / "documents"; output.mkdir(mode=0o700, exist_ok=True); os.chmod(output, 0o700)
    environment = node_environment(root, int(config.get("seed", 210)))
    summary = {"student_count": count_data_rows(required[0]), "nameplates": None, "seating_chart": None}
    if config.get("nameplates", {}).get("enabled", True):
        # Preserve the proven browser renderer byte-for-byte. The private
        # workspace keeps its roster adapter beside the original HTML, which
        # the user opens and prints to PDF after reviewing parsed first names.
        source = root / "vendor/doctools-seatplanner"
        workspace = output / "nameplates-workspace"
        (workspace / "brand").mkdir(parents=True, mode=0o700, exist_ok=True)
        shutil.copy2(source / "Nameplates.html", workspace / "Nameplates.html")
        shutil.copy2(source / "brand/brand.css", workspace / "brand/brand.css")
        shutil.copy2(required[0], workspace / "nameplates.csv")
        instructions = (
            "Open Nameplates.html, choose nameplates.csv, review every parsed "
            "first name, and use Print nameplates to save the PDF. Keep this "
            "entire directory private because nameplates.csv contains student data.\n"
        )
        (workspace / "START-HERE.txt").write_text(instructions, encoding="utf-8")
        for path in workspace.rglob("*"):
            if path.is_file(): os.chmod(path, 0o600)
        summary["nameplates"] = "nameplates-workspace/Nameplates.html"
    seating = config.get("seating_chart", {})
    if seating.get("enabled", False):
        layout_value = seating.get("layout")
        if not layout_value:
            raise ValueError("Set seating_chart.layout to a reviewed room-layout CSV")
        layout = Path(str(layout_value).replace("$ENGINE", str(root))).expanduser().resolve()
        if not layout.is_file(): raise ValueError(f"Room layout does not exist: {layout}")
        seats, students = count_seats(layout), summary["student_count"]
        if seating.get("require_all_students_fit", True) and seats < students:
            raise ValueError(f"Room layout has {seats} seats for {students} students; refusing partial chart")
        command = ["node", "--require", str(root / "vendor/doctools-seatplanner/seed-random.cjs"),
                   str(root / "vendor/doctools-seatplanner/seatplanner.js"), "--students", str(required[1]),
                   "--layout", str(layout), "--output", str(output)]
        if seating.get("rank", False): command.append("--rank")
        run_command(command, environment)
        for path in output.iterdir():
            if path.is_file(): os.chmod(path, 0o600)
        summary["seating_chart"] = {"layout_seats": seats, "source": layout.name}
    (output / "document-summary.json").write_text(json.dumps({**summary, "contains_student_data": True}, indent=2)+"\n", encoding="utf-8")
    os.chmod(output / "document-summary.json", 0o600)
    return {**summary, "output": str(output), "contains_student_data": True}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("run_dir",nargs="?",type=Path)
    parser.add_argument("--config",type=Path,default=ROOT/"commands/build-roster-documents.config.jsonc")
    args=parser.parse_args()
    try: summary=build((args.run_dir.resolve() if args.run_dir else newest_private_run(ROOT)),jsonc.load_and_validate(args.config.resolve()),ROOT)
    except Exception as error: print(f"Error: {error}",file=sys.stderr);return 1
    print(json.dumps(summary,indent=2));return 0


if __name__=="__main__": raise SystemExit(main())
