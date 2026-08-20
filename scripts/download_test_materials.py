#!/usr/bin/env python3
"""Download/copy blueprint materials into instructor-private testmaking storage."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (ROOT / "private/testmaking/materials").resolve()
USER_AGENT = "CanvasAutomationTestMaterials/1.0 (instructor course preparation)"


def safe_target(relative: str) -> Path:
    target = (PRIVATE_ROOT / relative).resolve()
    if target != PRIVATE_ROOT and PRIVATE_ROOT not in target.parents:
        raise ValueError(f"material destination escapes private storage: {relative}")
    return target


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def acquire(item: dict, session: requests.Session) -> dict:
    target = safe_target(item["destination"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if item.get("local_source"):
        source = Path(item["local_source"]).expanduser().resolve()
        data = source.read_bytes()
        media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        final_url = None
    elif item.get("url"):
        host = (urlparse(item["url"]).hostname or "").casefold()
        if host.startswith("canvas.") or ".instructure.com" in host:
            raise ValueError("authenticated Canvas URLs require an explicit local_source")
        response = session.get(item["url"], timeout=45, allow_redirects=True)
        response.raise_for_status()
        data = response.content
        media_type = response.headers.get("Content-Type", "application/octet-stream").split(";", 1)[0]
        final_url = response.url
    else:
        raise ValueError("material needs url or local_source")
    if target.suffix.casefold() == ".pdf" and media_type != "application/pdf":
        raise ValueError(f"expected PDF content, received {media_type}")
    target.write_bytes(data)
    return {"id": item["id"], "status": "stored", "path": str(target.relative_to(ROOT)),
            "bytes": len(data), "sha256": digest(data), "media_type": media_type,
            "final_url": final_url, "rights": item["rights"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", type=Path, default=ROOT / "private/testmaking/assessment-blueprint.json")
    parser.add_argument("--record", type=Path, default=ROOT / "private/testmaking/materials/download-record.json")
    args = parser.parse_args()
    blueprint = json.loads(args.blueprint.read_text(encoding="utf-8"))
    session = requests.Session(); session.headers.update({"User-Agent": USER_AGENT})
    records = []
    for item in blueprint["materials"]:
        if not item.get("testable"):
            records.append({"id": item["id"], "status": "not-testable",
                            "detail": "full content unavailable or deliberately outside assessment scope",
                            "rights": item["rights"]})
            continue
        try:
            records.append(acquire(item, session))
        except Exception as exc:
            records.append({"id": item["id"], "status": "failed", "detail": str(exc), "rights": item["rights"]})
    result = {"schema": "canvas-test-material-download/v1", "records": records,
              "stored": sum(r["status"] == "stored" for r in records),
              "failed": sum(r["status"] == "failed" for r in records),
              "not_testable": sum(r["status"] == "not-testable" for r in records)}
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
