from bs4 import BeautifulSoup

from canvas_automation.course_html import CourseHTMLCompileError, compile_fragment


CSS = ".canvas-course h2 { color: #b83b21; } .note { border: 1px solid #333; }"


def test_compiler_inlines_shared_css_and_preserves_semantic_classes():
    result = compile_fragment('<div class="canvas-course"><h2>Heading</h2><p class="note">Text</p></div>', CSS)
    soup = BeautifulSoup(result, "html.parser")
    assert "color:#b83b21" in soup.h2["style"].replace(" ", "")
    assert "border:1pxsolid#333" in soup.p["style"].replace(" ", "")
    assert soup.div["class"] == ["canvas-course"]
    assert soup.find("style") is None


def test_compiler_rejects_inline_styles_in_authoritative_source():
    try:
        compile_fragment('<p style="color:red">Text</p>', CSS)
    except CourseHTMLCompileError as error:
        assert "inline styles" in str(error)
    else:
        raise AssertionError("inline source style was accepted")


def test_compiler_does_not_fetch_stylesheets():
    try:
        compile_fragment('<link rel="stylesheet" href="https://example.invalid/x.css"><p>Text</p>', CSS)
    except CourseHTMLCompileError as error:
        assert "stylesheet" in str(error)
    else:
        raise AssertionError("external stylesheet was accepted")
