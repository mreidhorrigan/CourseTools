"""Compile semantic course HTML and shared CSS into Canvas-safe inline HTML."""
from __future__ import annotations

import hashlib
from pathlib import Path

from bs4 import BeautifulSoup
from premailer import Premailer


class CourseHTMLCompileError(ValueError):
    """The authoring source or compiled result violates the Canvas HTML contract."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_source(html: str, *, allow_inline_styles: bool = False) -> None:
    soup = BeautifulSoup(html or "", "html.parser")
    if soup.find("style") or soup.find("link", rel=lambda value: value and "stylesheet" in value):
        raise CourseHTMLCompileError("Course source must not contain <style> or stylesheet <link> elements")
    if not allow_inline_styles:
        styled = soup.find_all(style=True)
        if styled:
            names = ", ".join(tag.name for tag in styled[:5])
            raise CourseHTMLCompileError(f"Course source contains inline styles on: {names}")


def compile_fragment(html: str, css: str, *, allow_source_inline_styles: bool = False) -> str:
    """Apply a CSS cascade and return only the compiled body fragment."""
    validate_source(html, allow_inline_styles=allow_source_inline_styles)
    document = f"<!doctype html><html><head></head><body>{html}</body></html>"
    compiled = Premailer(
        html=document,
        css_text=css,
        allow_network=False,
        allow_loading_external_files=False,
        disable_link_rewrites=True,
        preserve_internal_links=True,
        keep_style_tags=False,
        remove_classes=False,
        strip_important=True,
        disable_basic_attributes=["align", "bgcolor", "height", "width"],
    ).transform()
    soup = BeautifulSoup(compiled, "html.parser")
    if soup.find("style") or soup.find("link", rel=lambda value: value and "stylesheet" in value):
        raise CourseHTMLCompileError("CSS compiler left a stylesheet in the Canvas result")
    body = soup.body
    if body is None:
        raise CourseHTMLCompileError("CSS compiler returned no body")
    result = "".join(str(child) for child in body.contents).strip()
    if not result:
        raise CourseHTMLCompileError("CSS compiler returned an empty fragment")
    return result + "\n"


def compile_file(source: Path, stylesheet: Path) -> str:
    return compile_fragment(source.read_text(encoding="utf-8"), stylesheet.read_text(encoding="utf-8"))
