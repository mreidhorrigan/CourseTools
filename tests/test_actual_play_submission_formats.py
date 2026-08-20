import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]

def test_actual_play_final_requires_mp4_odt_and_rubric_evidence_map():
    source = (ROOT / "course/content/assignments/211856-actual-play-project-final-submission.html").read_text()
    text = BeautifulSoup(source, "html.parser").get_text(" ", strip=True)
    assert "exactly two files" in text
    assert "Gameplay episode (MP4)" in text
    assert "Companion document (ODT)" in text
    assert "rubric evidence map" in text
    assert "exact timestamp or time range" in text
    config = json.loads("\n".join(
        line for line in (ROOT / "commands/configure-assignment-upload-formats.config.jsonc").read_text().splitlines()
        if not line.lstrip().startswith("//")
    ))
    assert config["allowed_extensions"] == ["mp4", "odt"]

def test_other_project_plans_offer_timestamped_formative_playtest_evidence():
    for relative in (
        "course/content/assignments/211860-digital-procedural-ecology-project-design-and-technical-plan.html",
        "course/content/assignments/211858-board-game-project-design-plan-and-draft-rulebook.html",
    ):
        text = BeautifulSoup((ROOT / relative).read_text(), "html.parser").get_text(" ", strip=True)
        assert "Optional formative playtest evidence" in text
        assert "short MP4 playtest" in text
        assert "timestamp important events" in text
