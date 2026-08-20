import json
from pathlib import Path

from bs4 import BeautifulSoup
from canvas_automation import jsonc


ROOT = Path(__file__).resolve().parents[1]


def test_syllabus_links_every_manifest_quiz_and_final_exam_assignment():
    manifest = json.loads((ROOT / "course/course-manifest.json").read_text())
    config = jsonc.load_and_validate(ROOT / "course/course.config.jsonc")
    course_url = config["course_url"].rstrip("/")
    soup = BeautifulSoup((ROOT / "course/content/syllabus.html").read_text(), "html.parser")
    links = {link.get("href"): link.get_text(" ", strip=True) for link in soup.find_all("a", href=True)}

    quizzes = [item for item in manifest["objects"] if item["kind"] == "quiz"]
    assert len(quizzes) == 7
    for quiz in quizzes:
        href = f"{course_url}/quizzes/{quiz['canvas_id']}"
        assert links.get(href) == quiz["title"]

    exams = [item for item in manifest["objects"]
             if item["kind"] == "assignment" and "final-examination" in item["source"]]
    assert len(exams) == 1
    exam_href = f"{course_url}/assignments/{exams[0]['canvas_id']}"
    assert exam_href in links
    assert "number of questions, time allowance" in soup.get_text(" ", strip=True)
    assert "10-minute limit" in soup.get_text(" ", strip=True)
    assert "one attempt" in soup.get_text(" ", strip=True)
