#!/usr/bin/env python3
"""Upload one verified file to a guarded Canvas course and confirm visibility."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import requests

from sandbox_course_lifecycle import GuardedCanvas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--course", required=True, type=int)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--record", required=True, type=Path)
    args = parser.parse_args()
    content = args.file.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != args.sha256:
        raise ValueError(f"SHA-256 mismatch: expected {args.sha256}, found {digest}")
    canvas = GuardedCanvas(args.server, args.course)
    canvas.health()
    result = {"course_id": args.course, "filename": args.file.name, "folder": args.folder, "sha256": digest, "dry_run": not args.apply}
    if args.apply:
        expected = f"UPLOAD-FILE-{args.course}"
        if args.confirm != expected:
            raise ValueError(f"Apply requires --confirm {expected}")
        response = requests.post(
            f"{args.server}/api/courses/{args.course}/files",
            files={"file": (args.file.name, content, "application/zip")},
            data={"parent_folder_path": args.folder}, timeout=180,
        )
        response.raise_for_status()
        uploaded = response.json()
        file_id = uploaded["id"]
        metadata = canvas.raw("GET", f"/files/{file_id}")
        if isinstance(metadata, list):
            metadata = metadata[0]
        visible = not metadata.get("hidden", False) and not metadata.get("locked", False)
        if not visible:
            raise RuntimeError(f"Canvas uploaded file is not published/visible: {metadata}")
        download = requests.get(f"{args.server}/api/courses/{args.course}/files/{file_id}/download", timeout=180)
        download.raise_for_status()
        downloaded_digest = hashlib.sha256(download.content).hexdigest()
        if downloaded_digest != digest:
            raise RuntimeError("Canvas download does not match the verified local file")
        result.update({"dry_run": False, "file_id": file_id, "published": True, "download_sha256": downloaded_digest, "display_name": metadata.get("display_name")})
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
