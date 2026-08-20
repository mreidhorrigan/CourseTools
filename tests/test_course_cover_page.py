from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def test_cover_page_links_to_canvas_syllabus_route():
    soup = BeautifulSoup((ROOT / "course/content/pages/course-home.html").read_text(), "html.parser")
    links = {anchor.get_text(" ", strip=True): anchor.get("href") for anchor in soup.find_all("a")}
    assert links["Read the course syllabus"].endswith("/assignments/syllabus")
