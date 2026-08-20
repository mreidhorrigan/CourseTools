import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("convert_canvas_gradebook", ROOT / "scripts/convert_canvas_gradebook.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def config(tmp_path: Path) -> Path:
    path = tmp_path / "config.jsonc"
    path.write_text(json.dumps({
        "input_columns": {"student_id": "SIS User ID", "percentage": "Final Score", "section": "Section"},
        "course": {"subject": None, "catalog_number": None, "section": None},
        "grade_scale": [
            {"minimum": 95, "grade": "A+"}, {"minimum": 90, "grade": "A"},
            {"minimum": 85, "grade": "A-"}, {"minimum": 80, "grade": "B+"},
            {"minimum": 75, "grade": "B"}, {"minimum": 70, "grade": "B-"},
            {"minimum": 65, "grade": "C+"}, {"minimum": 60, "grade": "C"},
            {"minimum": 55, "grade": "C-"}, {"minimum": 50, "grade": "D"},
            {"minimum": 0, "grade": "F"},
        ],
        "missing_percentage": "error", "output_formats": ["csv", "txt"],
    }))
    return path


def test_half_up_rounding_changes_94_5_to_a_plus():
    scale = MODULE.validate_scale([{"minimum": 95, "grade": "A+"}, {"minimum": 0, "grade": "F"}])
    assert MODULE.half_up_whole("94.5") == 95
    assert MODULE.letter_grade(MODULE.half_up_whole("94.5"), scale) == "A+"
    assert MODULE.half_up_whole("94.49") == 94


def test_conversion_skips_canvas_metadata_and_writes_exact_shape(tmp_path):
    source = tmp_path / "grades.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Student", "ID", "SIS User ID", "Section", "Final Score"])
        writer.writeheader()
        writer.writerow({"Student": "Points Possible", "Final Score": "(read only)"})
        writer.writerow({"Student": "One", "ID": "canvas-1", "SIS User ID": "003010000", "Section": "IAT206W D100", "Final Score": "94.5"})
        writer.writerow({"Student": "Two", "ID": "canvas-2", "SIS User ID": "003010001", "Section": "IAT206W D100 and IAT206W D100 Media Across Cultures", "Final Score": "74.5"})
        writer.writerow({"Student": "Test Student", "ID": "canvas-test", "Section": "IAT206W D100", "Final Score": ""})
    output = tmp_path / "out"
    record = MODULE.run(source, config(tmp_path), output)
    csv_path = output / "grades-grade-submission.csv"
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    assert rows == [
        ["IAT", "206W", "D100", "003010000", "A+"],
        ["IAT", "206W", "D100", "003010001", "B"],
    ]
    with (output / "grades-grade-submission.txt").open(newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle, delimiter="\t")) == rows
    provenance = json.loads((output / "grades-grade-submission-conversion-record.json").read_text())
    assert provenance["student_identifiers_in_record"] is False
    assert record["counts"]["converted"] == 2


def test_omitted_output_directory_writes_beside_input(tmp_path):
    source = tmp_path / "runtime-input.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["SIS User ID", "Final Score", "Section"])
        writer.writeheader()
        writer.writerow({"SIS User ID": "900000001", "Final Score": "94.5", "Section": "DEMO101 D100"})
    record = MODULE.run(source, config(tmp_path))
    assert source.exists()
    assert (tmp_path / "runtime-input-grade-submission.csv").exists()
    assert (tmp_path / "runtime-input-grade-submission.txt").exists()
    assert (tmp_path / "runtime-input-grade-submission-conversion-record.json").exists()
    assert record["input_filename"] == source.name


def test_default_config_produces_only_sfu_accepted_headerless_csv(tmp_path):
    source = tmp_path / "default.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["SIS User ID", "Final Score", "Section"])
        writer.writeheader()
        writer.writerow({"SIS User ID": "009000001", "Final Score": "94.5", "Section": "DEMO101 D100"})
    record = MODULE.run(source, ROOT / "commands/convert-gradebook.config.jsonc", tmp_path / "default-out")
    assert record["outputs"] == ["default-grade-submission.csv"]
    with (tmp_path / "default-out/default-grade-submission.csv").open(newline="", encoding="utf-8-sig") as handle:
        assert list(csv.reader(handle)) == [["DEMO", "101", "D100", "009000001", "A+"]]
    assert not (tmp_path / "default-out/default-grade-submission.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert record["output_validation"]["default-grade-submission.csv"]["header_absent"] is True


def test_runtime_validator_rejects_headers_and_slashes(tmp_path):
    headed = tmp_path / "headed.csv"
    headed.write_text("Subject,Catalog Nbr,Section,Student ID,Grade\n", encoding="utf-8")
    try:
        MODULE.validate_upload_file(headed, 1, {"A+"})
    except MODULE.GradebookConversionError as error:
        assert "headings" in str(error)
    else:
        raise AssertionError("Header row was accepted")
    bad = tmp_path / "slash.csv"
    bad.write_text("DEMO,101,D/100,900000001,A+\n", encoding="utf-8")
    try:
        MODULE.validate_upload_file(bad, 1, {"A+"})
    except MODULE.GradebookConversionError as error:
        assert "slash" in str(error)
    else:
        raise AssertionError("Prohibited slash was accepted")


def test_identified_student_without_percentage_stops_conversion(tmp_path):
    row = {"SIS User ID": "301", "Final Score": "", "Section": "IAT206W D100"}
    cfg = json.loads(config(tmp_path).read_text())
    try:
        MODULE.convert_rows([row], cfg)
    except MODULE.GradebookConversionError as error:
        assert "Missing Final Score" in str(error)
    else:
        raise AssertionError("Missing student grade was silently omitted")


def test_committed_synthetic_fixture_is_reproducible_and_convertible(tmp_path):
    fixture = ROOT / "tests/fixtures/gradebooks/canvas-gradebook-synthetic.csv"
    rebuilt = tmp_path / "rebuilt.csv"
    MODULE_FIXTURE = ROOT / "scripts/build_fake_gradebook_fixture.py"
    fixture_spec = importlib.util.spec_from_file_location("build_fake_gradebook_fixture", MODULE_FIXTURE)
    fixture_module = importlib.util.module_from_spec(fixture_spec)
    assert fixture_spec.loader
    fixture_spec.loader.exec_module(fixture_module)
    fixture_module.build(rebuilt)
    assert rebuilt.read_bytes() == fixture.read_bytes()
    record = MODULE.run(fixture, config(tmp_path), tmp_path / "converted")
    assert record["counts"]["converted"] == 12
    assert "Example," in fixture.read_text(encoding="utf-8-sig")
    assert "synthetic fixture" in fixture.read_text(encoding="utf-8-sig")
