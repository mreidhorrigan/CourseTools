import importlib.util
from pathlib import Path
from canvas_automation import jsonc

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("dossier",ROOT/"scripts/build_course_dossier.py")
MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)

def test_dossier_config_sources_are_public_course_content():
    config=jsonc.load_and_validate(ROOT/"commands/build-course-dossier.config.jsonc")
    assert len(config["documents"]) >= 12
    for record in config["documents"]:
        assert record["source"].startswith("course/content/")
        assert MOD.selected_html(record).strip()

def test_design_page_excludes_required_student_timeline():
    config=jsonc.load_and_validate(ROOT/"commands/build-course-dossier.config.jsonc")
    rationale=next(x for x in config["documents"] if x["title"]=="Course Rationale and Design")
    body=MOD.selected_html(rationale)
    assert "Wake Forest University Workload Estimator" in body
    assert "field-roadmap" not in body
    assert "Complete the technology and availability check" not in body
