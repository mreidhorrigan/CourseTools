#!/usr/bin/env python3
"""Identify an existing local Canvas Automation server before token entry."""
from __future__ import annotations

import argparse
import json
import socket
import sys
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class Probe(NamedTuple):
    state: str
    message: str


def probe(host: str, port: int, course_id: int, canvas_base_url: str, timeout: float = 1.0) -> Probe:
    try:
        connection = socket.create_connection((host, port), timeout=timeout)
        connection.close()
    except OSError:
        return Probe("available", f"No server is listening on {host}:{port}.")

    try:
        with urlopen(f"http://{host}:{port}/health", timeout=timeout) as response:
            body = json.load(response)
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return Probe(
            "occupied",
            f"Port {port} is already used by a process that is not a healthy Canvas Automation server ({exc}).",
        )

    actual_course = body.get("allowed_course_id")
    actual_base = str(body.get("canvas_base_url", "")).rstrip("/")
    if body.get("status") == "ok" and actual_course == course_id and actual_base == canvas_base_url.rstrip("/"):
        return Probe(
            "matching",
            f"Canvas Automation is already running on http://{host}:{port} and is guarded to course {course_id}.",
        )
    return Probe(
        "different",
        f"A Canvas Automation server is already running on port {port}, guarded to course {actual_course!r} at {actual_base or 'an unknown Canvas host'}.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--course-id", required=True, type=int)
    parser.add_argument("--canvas-base-url", required=True)
    args = parser.parse_args()
    result = probe(args.host, args.port, args.course_id, args.canvas_base_url)
    print(result.message)
    return {"matching": 0, "available": 3, "occupied": 4, "different": 5}[result.state]


if __name__ == "__main__":
    raise SystemExit(main())
