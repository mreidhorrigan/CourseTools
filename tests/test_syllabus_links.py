from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("update_syllabus_links", ROOT / "scripts/update_syllabus_links.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


CONFIG = {
    "text_replacements": [{"old": "Example syllabus", "new": "Sample syllabus"}],
    "heading_styles": [{"selector": "section > h2", "style": "color: #b83b21"}],
    "removals": [{"selector": ".obsolete", "contains": "Remove this"}],
    "insertions": [{
        "marker_id": "contact-details",
        "after_selector": "h1",
        "html": '<section aria-labelledby="contact-details"><h2 id="contact-details">Contact</h2><p><a href="mailto:teacher@example.edu">Email the instructor</a></p></section>',
    }],
    "content_replacements": [{
        "container_selector": "#description",
        "start_after_selector": "h2",
        "stop_before_selector": "h3",
        "html": "<p>Integrated catalog description.</p><p>Project sequence description.</p>",
    }],
    "paragraph_rules": [{
        "heading": "Accessibility",
        "links": [{"phrase": "accessibility office", "url": "https://example.edu/accessibility"}],
        "append": [{"marker": "Policy details", "html": 'Policy details are in the <a href="https://example.edu/policy">institutional policy</a>.'}],
    }],
    "verification": {
        "required_hrefs": ["mailto:teacher@example.edu", "https://example.edu/accessibility", "https://example.edu/policy"],
        "required_ids": ["contact-details"],
        "required_text": ["Sample syllabus", "Email the instructor", "Policy details", "Integrated catalog description", "Project sequence description"],
        "forbidden_text": ["obsolete@example.edu"],
    },
}


def fixture() -> str:
    return "<html><body><h1>Example syllabus</h1><p class='obsolete'>Remove this metadata.</p><section id='description'><h2>Description</h2><p>Old description.</p><h3>Details</h3></section><h3>Accessibility</h3><p>Contact the accessibility office.</p></body></html>"


def test_transform_is_configuration_driven_and_idempotent():
    first = module.transform(fixture(), CONFIG)
    second = module.transform(first, CONFIG)
    assert first == second
    assert module.desired_present(first, CONFIG)
    assert not module.desired_present(fixture(), CONFIG)
    soup = BeautifulSoup(first, "html.parser")
    assert soup.find(id="contact-details")
    assert "color: #b83b21" in soup.find(id="contact-details").get("style", "")
    assert soup.find("a", string="accessibility office")["href"] == "https://example.edu/accessibility"
    assert not soup.select_one(".obsolete")
    assert "Old description" not in first
    assert first.index("Integrated catalog description") < first.index("Project sequence description") < first.index("Details")


def test_missing_configured_heading_fails_clearly():
    bad = {**CONFIG, "paragraph_rules": [{"heading": "Missing section"}]}
    try:
        module.transform(fixture(), bad)
    except ValueError as error:
        assert "Missing configured syllabus heading" in str(error)
    else:
        raise AssertionError("Expected a missing-heading error")


def test_semantic_digest_ignores_canvas_api_link_metadata():
    plain = '<p><a href="/pages/help">Help</a></p>'
    canvas = '<p><a data-api-endpoint="/api/v1/courses/1/pages/help" data-api-returntype="Page" href="/pages/help">Help</a></p>'
    assert module.semantic_digest(plain) == module.semantic_digest(canvas)
