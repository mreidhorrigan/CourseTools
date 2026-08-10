"""Provider-aware external-link extraction and verification.

A successful web-page status is not proof that embedded media is playable.
YouTube and Vimeo links are therefore checked with their official oEmbed
endpoints. Results are deterministic once responses are supplied: callers may
run network requests concurrently but should sort records by URL for output.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

PROTECTED_CODES = {401, 403, 429}
USER_AGENT = "CanvasAutomationLinkQA/1.0 (+local course quality assurance)"


def extract_external_urls(html_bodies, exclude_hosts=()):
    excluded = {str(host).casefold() for host in exclude_hosts}
    urls = set()
    for body in html_bodies:
        for tag in BeautifulSoup(body or "", "html.parser").find_all("a", href=True):
            href = tag["href"].strip()
            host = (urlparse(href).hostname or "").casefold()
            if href.startswith(("http://", "https://")) and host not in excluded:
                urls.add(href)
    return sorted(urls)


def media_probe(url):
    """Return (endpoint, params) for a provider check, or (url, None)."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        video_id = parsed.path.strip("/") if host == "youtu.be" else parse_qs(parsed.query).get("v", [""])[0]
        if not video_id:
            raise ValueError("no specific YouTube video ID")
        return "https://www.youtube.com/oembed", {
            "url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"
        }
    if host == "vimeo.com" or host.endswith(".vimeo.com"):
        if not re.search(r"/\d+(?:$|[/?#])", parsed.path):
            raise ValueError("no specific Vimeo video ID")
        # The ordinary Vimeo page may return HTTP 200 for an unavailable-video
        # shell. Vimeo documents oEmbed as the availability/embedability probe.
        return "https://vimeo.com/api/oembed.json", {"url": url}
    return url, None


def classify_response(url, response):
    record = {
        "url": url,
        "status": "FAIL",
        "code": response.status_code,
        "final_url": response.url,
        "detail": "",
    }
    if response.status_code in PROTECTED_CODES:
        record["status"] = "PROTECTED"
        record["detail"] = "authentication, embedding policy, or rate limit prevents automated confirmation"
    elif response.status_code >= 400:
        record["detail"] = f"HTTP {response.status_code}"
    else:
        record["status"] = "OK"
    return record


def check_url(url, timeout=15, session=None, search_resolver_hosts=()):
    host = (urlparse(url).hostname or "").casefold()
    resolver_hosts = {str(item).casefold() for item in search_resolver_hosts}
    if host in resolver_hosts:
        return {
            "url": url, "status": "OUTTAKE", "code": None, "final_url": None,
            "detail": "library search/resolver result is not a stable, item-level access link; replace with a DOI, repository, author, or publisher URL",
        }
    try:
        endpoint, params = media_probe(url)
        requester = session or requests.Session()
        requester.headers.update({"User-Agent": USER_AGENT})
        response = requester.get(endpoint, params=params, timeout=timeout, allow_redirects=True)
        return classify_response(url, response)
    except Exception as exc:
        return {"url": url, "status": "FAIL", "code": None, "final_url": None, "detail": str(exc)}
