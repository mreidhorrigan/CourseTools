from __future__ import annotations

from types import SimpleNamespace
import importlib.util
import io
import zipfile
from pathlib import Path

from canvas_automation.link_check import check_url, extract_external_urls, media_probe

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_external_links_script", ROOT / "scripts/check_external_links.py")
script = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(script)


class FakeSession:
    def __init__(self, status, final="https://example.test/final"):
        self.headers = {}
        self.status = status
        self.final = final
        self.calls = []

    def get(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        return SimpleNamespace(status_code=self.status, url=self.final)


def test_external_url_extraction_is_unique_and_sorted():
    assert extract_external_urls(['<a href="https://b.test">b</a><a href="/local">l</a>', '<a href="https://a.test">a</a>']) == [
        "https://a.test", "https://b.test"
    ]


def test_external_url_extraction_excludes_authenticated_canvas_host():
    bodies = [
        '<a href="https://canvas.example/courses/1/assignments/2">internal</a>'
        '<a href="https://example.org">external</a>'
    ]
    assert extract_external_urls(bodies, exclude_hosts=["canvas.example"]) == [
        "https://example.org"
    ]


def test_vimeo_uses_oembed_not_false_positive_page_status():
    endpoint, params = media_probe("https://vimeo.com/175727157")
    assert endpoint == "https://vimeo.com/api/oembed.json"
    assert params == {"url": "https://vimeo.com/175727157"}
    session = FakeSession(404)
    result = check_url("https://vimeo.com/175727157", session=session)
    assert result["status"] == "FAIL"
    assert session.calls[0][0] == endpoint


def test_provider_restriction_is_not_reported_as_verified():
    result = check_url("https://vimeo.com/123456", session=FakeSession(403))
    assert result["status"] == "PROTECTED"


def test_generic_success_is_ok_and_missing_video_id_fails():
    assert check_url("https://example.test", session=FakeSession(200))["status"] == "OK"
    assert check_url("https://vimeo.com/channels/staffpicks", session=FakeSession(200))["status"] == "FAIL"


def test_doi_uses_crossref_metadata_without_claiming_full_text_access():
    endpoint, params = media_probe("https://doi.org/10.1234/example.value")
    assert endpoint == "https://api.crossref.org/works/10.1234%2Fexample.value"
    assert params is None
    session = FakeSession(200)
    result = check_url("https://doi.org/10.1234/example.value", session=session)
    assert result["status"] == "METADATA"
    assert "full-text access" in result["detail"]
    assert session.calls[0][0] == endpoint


def test_sfu_library_search_is_an_outtake_without_false_network_success():
    session = FakeSession(200)
    result = check_url(
        "https://library.example.edu/search?q=example",
        session=session,
        search_resolver_hosts=["library.example.edu"],
    )
    assert result["status"] == "OUTTAKE"
    assert "not a stable" in result["detail"]
    assert session.calls == []


def test_archive_extraction_rejects_path_traversal(tmp_path):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("../escape.html", "bad")
    data.seek(0)
    with zipfile.ZipFile(data) as archive:
        try:
            script.safe_extract(archive, tmp_path)
        except ValueError as exc:
            assert "escapes destination" in str(exc)
        else:
            raise AssertionError("unsafe archive member was accepted")
