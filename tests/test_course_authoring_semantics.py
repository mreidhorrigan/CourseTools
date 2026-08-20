import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "course_authoring", ROOT / "scripts/course_authoring.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_semantic_comparison_ignores_comments_discarded_by_canvas():
    marked = "<p>Before</p><!-- generated:section:start --><p>After</p>"
    canvas_saved = "<p>Before</p><p>After</p>"
    assert MODULE.semantic(marked) == MODULE.semantic(canvas_saved)


def test_semantic_comparison_still_detects_visible_changes():
    assert MODULE.semantic("<p>Before</p>") != MODULE.semantic("<p>After</p>")


def test_semantic_comparison_ignores_compiled_inline_style_serialization():
    first = '<h2 class="section" style="color:#b83b21; margin:1rem">Heading</h2>'
    second = '<h2 class="section" style="margin: 1rem; color: rgb(184,59,33)">Heading</h2>'
    assert MODULE.semantic(first) == MODULE.semantic(second)


def test_semantic_comparison_ignores_outer_serialization_whitespace():
    assert MODULE.semantic("<p>Text</p>\n") == MODULE.semantic("<p>Text</p>")


def test_semantic_comparison_ignores_canvas_file_verifier_parameter():
    stable = '<a href="https://canvas.example/courses/12/files/34/download">File</a>'
    live = '<a href="https://canvas.example/courses/12/files/34/download?verifier=rotating-value">File</a>'
    assert MODULE.semantic(stable) == MODULE.semantic(live)


def test_exported_canvas_html_is_decompiled_before_becoming_source(tmp_path):
    MODULE.write_source(
        tmp_path,
        "course/content/page.html",
        '<div class="canvas-course"><h2 style="color:#b83b21">Heading</h2></div>',
    )
    saved = (tmp_path / "course/content/page.html").read_text(encoding="utf-8")
    assert "style=" not in saved
    assert "canvas-course" in saved
    assert "Heading" in saved
