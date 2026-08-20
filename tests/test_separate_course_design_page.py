import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("separate_design", ROOT / "scripts/separate_course_design_page.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_transform_moves_design_sections_and_retargets_syllabus_link():
    start = '<div><h1>Start</h1><section id="course-rationale-design">R</section><section id="field-roadmap">F</section><section id="glossary">G</section></div>'
    syllabus = '<div><a href="old">course rationale and design explanation</a></div>'
    new_start, design, new_syllabus = MODULE.transform(start, syllabus, "https://canvas.example/courses/12")
    assert 'id="course-rationale-design"' not in new_start
    assert "workload design" in new_start
    assert all(f'id="{section_id}"' in design for section_id in MODULE.DESIGN_SECTION_IDS)
    assert "<h1" not in design
    assert "/courses/12/pages/course-rationale-and-design" in new_syllabus


def test_student_timeline_and_glossary_are_restored_to_start_here():
    start = '<div><h1>Start</h1><ol><li>Read syllabus</li></ol><p><a href="https://x/pages/course-rationale-and-design">public course rationale</a></p></div>'
    design = '<div><section id="course-rationale-design">R</section><section id="field-roadmap">F</section><section id="glossary">G</section></div>'
    new_start, new_design = MODULE.restore_student_sections(start, design)
    assert 'id="field-roadmap"' in new_start and 'id="glossary"' in new_start
    assert "Read the game studies field roadmap" in new_start
    assert 'id="field-roadmap"' not in new_design and 'id="glossary"' not in new_design
    assert "<h1" not in new_design
