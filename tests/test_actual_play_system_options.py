from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PLAN=next((ROOT/"course/content/assignments").glob("*-actual-play-project-session-plan-and-rulebook.html"))
FINAL=next((ROOT/"course/content/assignments").glob("*-actual-play-project-final-submission.html"))

URLS={
 "https://www.dndbeyond.com/srd",
 "https://cairnrpg.com/barebones/rules/barebones-character-creation/",
 "https://fate-srd.com/fate-accelerated",
 "https://www.basicfantasy.org/",
 "https://tomkinpress.com/collections/downloads-for-ironsworn-starforged/products/ironsworn-starforged-playkit",
 "https://bladesinthedark.com/downloads",
}

def test_actual_play_plan_has_all_approved_existing_systems():
    text=PLAN.read_text(encoding="utf-8")
    assert all(url in text for url in URLS)
    assert "improvised television episode" in text
    assert "licence or explicit permission" in text

def test_final_requires_system_provenance_and_distinguishes_extensions():
    text=FINAL.read_text(encoding="utf-8")
    assert "selected system" in text
    assert "published procedures and team extensions" in text
    assert "version, source link, and licence or permission basis" in text
