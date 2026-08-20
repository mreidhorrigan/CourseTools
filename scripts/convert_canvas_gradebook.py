#!/usr/bin/env python3
"""Convert a Canvas gradebook export to a five-column grade-submission file."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from canvas_automation import jsonc


OUTPUT_COLUMNS = ["Subject", "Catalog Nbr", "Section", "Student ID", "Grade"]
COURSE_RE = re.compile(r"\b([A-Za-z]{2,})\s*([0-9]{2,4}[A-Za-z]?)\s+([A-Za-z][0-9A-Za-z-]*)\b")


class GradebookConversionError(ValueError):
    """A safe configuration or input error."""


def half_up_whole(value: str) -> int:
    cleaned = value.strip().removesuffix("%").strip()
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        raise GradebookConversionError(f"Percentage is not numeric: {value!r}") from None
    if not number.is_finite():
        raise GradebookConversionError(f"Percentage is not finite: {value!r}")
    return int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def validate_scale(scale: list[dict[str, Any]]) -> list[tuple[int, str]]:
    if not isinstance(scale, list) or not scale:
        raise GradebookConversionError("grade_scale must be a non-empty list")
    result: list[tuple[int, str]] = []
    for entry in scale:
        try:
            minimum, grade = int(entry["minimum"]), str(entry["grade"]).strip()
        except (KeyError, TypeError, ValueError):
            raise GradebookConversionError("Each grade_scale entry needs an integer minimum and a grade") from None
        if not grade:
            raise GradebookConversionError("A grade_scale grade cannot be blank")
        result.append((minimum, grade))
    if result != sorted(result, reverse=True):
        raise GradebookConversionError("grade_scale minimums must be strictly descending")
    if len({minimum for minimum, _ in result}) != len(result):
        raise GradebookConversionError("grade_scale minimums must be unique")
    if result[-1][0] > 0:
        raise GradebookConversionError("grade_scale must include a minimum of 0 or lower")
    return result


def letter_grade(rounded_percentage: int, scale: list[tuple[int, str]]) -> str:
    for minimum, grade in scale:
        if rounded_percentage >= minimum:
            return grade
    raise GradebookConversionError(f"Rounded percentage {rounded_percentage} is below the configured scale")


def parse_course(section_value: str, config: dict[str, Any]) -> tuple[str, str, str]:
    match = COURSE_RE.search(section_value)
    inferred = match.groups() if match else ("", "", "")
    values = (
        str(config.get("subject") or inferred[0]).strip().upper(),
        str(config.get("catalog_number") or inferred[1]).strip().upper(),
        str(config.get("section") or inferred[2]).strip().upper(),
    )
    if not all(values):
        raise GradebookConversionError(
            f"Could not infer Subject, Catalog Nbr, and Section from {section_value!r}; set course fields in the config"
        )
    return values


def convert_rows(rows: list[dict[str, str]], config: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, int]]:
    columns = config["input_columns"]
    id_column = columns["student_id"]
    percentage_column = columns["percentage"]
    section_column = columns["section"]
    scale = validate_scale(config["grade_scale"])
    result: list[dict[str, str]] = []
    skipped_missing_id = skipped_metadata = 0
    seen_ids: set[str] = set()
    for source_row_number, row in enumerate(rows, start=2):
        student_id = (row.get(id_column) or "").strip()
        percentage = (row.get(percentage_column) or "").strip()
        if not student_id:
            if percentage and percentage.casefold() not in {"(read only)", "read only"}:
                skipped_missing_id += 1
            else:
                skipped_metadata += 1
            continue
        if student_id in seen_ids:
            raise GradebookConversionError(f"Duplicate {id_column} on source row {source_row_number}")
        if not percentage or percentage.casefold() in {"(read only)", "read only"}:
            behavior = config.get("missing_percentage", "error")
            if behavior == "skip":
                continue
            raise GradebookConversionError(f"Missing {percentage_column} for an identified student on source row {source_row_number}")
        rounded = half_up_whole(percentage)
        subject, catalog, section = parse_course((row.get(section_column) or "").strip(), config["course"])
        result.append({
            "Subject": subject, "Catalog Nbr": catalog, "Section": section,
            "Student ID": student_id, "Grade": letter_grade(rounded, scale),
        })
        seen_ids.add(student_id)
    if not result:
        raise GradebookConversionError("No student rows were converted")
    return result, {"converted": len(result), "skipped_metadata_or_blank": skipped_metadata,
                    "skipped_nonstudent_without_id": skipped_missing_id}


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    # No UTF-8 BOM: with no header row, a BOM would become part of the first
    # record's Subject value in parsers that do not strip it.
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows([row[column] for column in OUTPUT_COLUMNS] for row in rows)


def write_txt(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerows([row[column] for column in OUTPUT_COLUMNS] for row in rows)


def validate_upload_file(path: Path, expected_rows: int, valid_grades: set[str],
                         require_numeric_student_id: bool = True) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise GradebookConversionError("Generated upload file has an unexpected UTF-8 byte-order mark")
    delimiter = "\t" if path.suffix.casefold() == ".txt" else ","
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter=delimiter))
    if len(rows) != expected_rows:
        raise GradebookConversionError(f"Generated upload has {len(rows)} rows; expected {expected_rows}")
    if rows and rows[0] == OUTPUT_COLUMNS:
        raise GradebookConversionError("Generated upload incorrectly contains column headings")
    for index, row in enumerate(rows, 1):
        if len(row) != 5 or any(not value.strip() for value in row):
            raise GradebookConversionError(f"Generated upload row {index} does not contain five nonblank fields")
        if require_numeric_student_id and not row[3].isdigit():
            raise GradebookConversionError(f"Generated upload row {index} has a nonnumeric Student ID")
        if row[4] not in valid_grades:
            raise GradebookConversionError(f"Generated upload row {index} has a grade outside the configured scale")
        if any("/" in value for value in row):
            raise GradebookConversionError(f"Generated upload row {index} contains a prohibited slash character")
    return {"header_absent": True, "columns_per_row": 5, "rows": len(rows),
            "no_utf8_bom": True, "no_slash_characters": True,
            "student_ids_numeric": require_numeric_student_id}


def run(input_path: Path, config_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    config = jsonc.load_and_validate(config_path)
    if input_path.suffix.casefold() != ".csv":
        raise GradebookConversionError("Input must be a Canvas CSV gradebook export")
    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        required = set(config["input_columns"].values())
        missing = sorted(required - set(headers))
        if missing:
            raise GradebookConversionError(f"Input is missing configured columns: {', '.join(missing)}")
        rows, counts = convert_rows(list(reader), config)
    output_dir = output_dir or input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", input_path.stem).strip("-") + "-grade-submission"
    formats = config.get("output_formats", ["csv"])
    outputs: list[str] = []
    if "csv" in formats:
        path = output_dir / f"{stem}.csv"
        write_csv(path, rows)
        outputs.append(str(path))
    if "txt" in formats:
        path = output_dir / f"{stem}.txt"
        write_txt(path, rows)
        outputs.append(str(path))
    unknown = set(formats) - {"csv", "txt"}
    if unknown or not outputs:
        raise GradebookConversionError(f"Unsupported or empty output_formats: {formats}")
    valid_grades = {grade for _, grade in validate_scale(config["grade_scale"])}
    validations = {
        Path(value).name: validate_upload_file(
            Path(value), len(rows), valid_grades,
            bool(config.get("require_numeric_student_id", True)),
        ) for value in outputs
    }
    record = {
        "schema": "canvas-automation/grade-submission-conversion/v1",
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "input_filename": input_path.name,
        "config_filename": config_path.name,
        "rounding": "nearest whole percentage, halves away from zero (ROUND_HALF_UP)",
        "counts": counts,
        "outputs": [Path(value).name for value in outputs],
        "student_identifiers_in_record": False,
        "output_validation": validations,
    }
    record_name = f"{stem}-conversion-record.json"
    record["conversion_record"] = record_name
    (output_dir / record_name).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Canvas gradebook CSV export")
    parser.add_argument("--config", type=Path, default=ROOT / "commands/convert-gradebook.config.jsonc")
    parser.add_argument(
        "--output", type=Path,
        help="Output directory; defaults to the input CSV's directory",
    )
    args = parser.parse_args()
    try:
        record = run(
            args.input.resolve(), args.config.resolve(),
            args.output.resolve() if args.output else None,
        )
    except (OSError, GradebookConversionError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
