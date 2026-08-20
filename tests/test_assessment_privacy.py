from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_private_assessment_sources_and_outputs_are_git_ignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "private/testmaking/*" in ignore
    assert "!private/testmaking/README.md" in ignore
    assert "out/" in ignore


def test_distribution_builder_has_private_assessment_guards():
    source = (ROOT / "scripts/build_distribution.py").read_text(encoding="utf-8")
    assert '"private/"' in source
    assert '"out/testmaking-authoring/"' in source
    assert "PRIVATE_ASSESSMENT_PREFIXES" in source
