from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts")); spec=spec_from_file_location("syllabus454",ROOT/"scripts/update_iat210_syllabus_454.py"); module=module_from_spec(spec); spec.loader.exec_module(module)

HTML="""<p>Assessment dates and weights remain unchanged pending an explicit project-calendar decision.</p><h2>Assessment</h2><table><tr><th>Assessment</th><th>Weight</th><th>Instructions and dates</th></tr><tr><td>Actual-play podcast and tabletop roleplay</td><td>21%</td><td>Sep</td></tr><tr><td>Board-game design</td><td>21%</td><td>Oct 20; Oct 27; Nov 10</td></tr><tr><td>Digital game design: procedural ecology</td><td>21%</td><td>Nov 17; Nov 24; Dec 7</td></tr><tr><td>Practice quizzes</td><td>7%</td><td>Nine quizzes; best seven scores count</td></tr></table><h3>Practice quizzes and final examination</h3><p>The nine online quizzes are open-book formative assessment. The best seven scores count.</p><h2>Project Design and Deliverables</h2><h3 id="actual-play-project">Actual</h3><p>A</p><h3 id="board-game-project">Board</h3><p>B</p><h3 id="digital-project">Digital</h3><p>D</p><h3 id="ai-policy">AI</h3><p>X</p><h2>Weekly Schedule</h2><table><tr><th>Week</th><th>Milestone</th></tr>""" + "".join(f"<tr><td>{i}</td><td>Old {i}</td></tr>" for i in range(1,14)) + "</table>"

def test_transform_is_idempotent_and_aligns_sequence_and_quizzes():
    first=module.transform(HTML); second=module.transform(first); assert first==second
    soup=BeautifulSoup(first,"html.parser"); text=soup.get_text(" ",strip=True)
    assert "4-5-4 sequence" in text and "10 questions" in text and "best seven" not in text.casefold()
    headings=[h.get("id") for h in soup.find_all("h3")]
    assert headings.index("digital-project") < headings.index("board-game-project")
    rows=[[x.get_text(" ",strip=True) for x in r.find_all(["th","td"])] for r in soup.find_all("table")[0].find_all("tr")]
    assert [r[0] for r in rows][1:4]==["Actual-play podcast and tabletop roleplay","Digital game design: procedural ecology","Board-game design"]
