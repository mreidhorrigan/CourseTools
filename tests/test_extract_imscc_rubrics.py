from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("extract_imscc_rubrics", ROOT / "scripts/extract_imscc_rubrics.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_extracts_editable_rubric_sources(tmp_path):
    package = tmp_path / "course.imscc"
    xml = b'''<rubrics><rubric><title>Example Rubric (Restored v1)</title><points_possible>2</points_possible><criteria><criterion><points>2</points><description>Specific evidence</description><ratings><rating><description>Strong</description><points>2</points></rating><rating><description>Missing</description><points>0</points></rating></ratings></criterion></criteria></rubric></rubrics>'''
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("course_settings/rubrics.xml", xml)
    paths = module.write_sources(package, tmp_path / "rubrics")
    rubric = json.loads(paths[0].read_text())
    assert paths[0].name == "example-rubric.json"
    assert rubric["title"] == "Example Rubric"
    assert rubric["criteria"][0]["ratings"][0] == {"description": "Strong", "points": 2.0}
