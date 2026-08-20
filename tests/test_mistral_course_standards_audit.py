import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mistral_course_standards_audit", ROOT / "scripts/mistral_course_standards_audit.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_course_audit_builds_three_bounded_packets_without_secrets():
    packets = MODULE.build_packets(ROOT)
    assert set(packets) == {
        "orientation_content_and_weekly_design",
        "assessment_alignment_and_feedback",
        "structure_navigation_and_workload",
    }
    assert all(value.strip() for value in packets.values())
    assert all(len(value) < 115_000 for value in packets.values())
    assert all("MISTRAL_API_KEY" not in value for value in packets.values())


def test_standards_profile_has_authoritative_sources_and_scope_limit():
    text = (ROOT / "research/standards/course-audit-standards.md").read_text(encoding="utf-8")
    for source in ("qualitymatters.org", "oscqr.suny.edu", "w3.org/TR/WCAG22", "udlguidelines.cast.org"):
        assert source in text
    assert "does not confer certification" in text
