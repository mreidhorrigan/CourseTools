#!/usr/bin/env python3
"""Check external links in HTML, an unpacked cartridge, or an IMSCC archive."""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from lxml import etree

from canvas_automation import jsonc
from canvas_automation.link_check import check_url, extract_external_urls


def safe_extract(archive, destination):
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if root != target and root not in target.parents:
            raise ValueError(f"archive member escapes destination: {member.filename}")
    archive.extractall(destination)


def collect_bodies(root):
    bodies = []
    for path in sorted(root.rglob("*.html")) + sorted(root.glob("g*.xml")):
        content = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".xml":
            try:
                bodies.extend(node.text or "" for node in etree.parse(str(path)).xpath("//*[local-name()='text']"))
                continue
            except etree.XMLSyntaxError:
                pass
        bodies.append(content)
    return bodies


def check_package(source, timeout=15, workers=12, search_resolver_hosts=()):
    if source.is_file() and source.suffix.lower() not in {".html", ".htm"}:
        with tempfile.TemporaryDirectory(prefix="imscc_links_") as temp:
            with zipfile.ZipFile(source) as archive:
                safe_extract(archive, Path(temp))
            urls = extract_external_urls(collect_bodies(Path(temp)))
    elif source.is_file():
        urls = extract_external_urls([source.read_text(encoding="utf-8", errors="replace")])
    else:
        urls = extract_external_urls(collect_bodies(source))
    found = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        future_map = {
            pool.submit(check_url, url, timeout, None, search_resolver_hosts): url for url in urls
        }
        for future in as_completed(future_map):
            found[future_map[future]] = future.result()
    return [found[url] for url in urls]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--outtakes-out", type=Path, help="Write links requiring replacement or manual resolution as JSON")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--config", type=Path, default=Path("course/course.config.jsonc"), help="Central course JSONC; defaults to course/course.config.jsonc")
    args = parser.parse_args()
    config = jsonc.load_and_validate(args.config) if args.config and args.config.exists() else {}
    resolver_hosts = config.get("search_resolver_hosts", [])
    if "institution" in config:
        resolver_hosts = config["institution"].get("library_resolver_hosts", [])
    results = check_package(
        args.source, args.timeout, args.workers, resolver_hosts
    )
    for record in results:
        line = f"{record['status']:9} {str(record['code'] or ''):4} {record['url']}"
        if record["final_url"] and record["final_url"] != record["url"]:
            line += f" -> {record['final_url']}"
        if record["detail"]:
            line += f" [{record['detail']}]"
        print(line)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    outtakes = [record for record in results if record["status"] == "OUTTAKE"]
    if args.outtakes_out:
        args.outtakes_out.parent.mkdir(parents=True, exist_ok=True)
        args.outtakes_out.write_text(json.dumps(outtakes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = [record for record in results if record["status"] in {"FAIL", "OUTTAKE"}]
    print(f"{'FAIL' if failures else 'PASS'}: {sum(r['status'] == 'FAIL' for r in results)} failed, {len(outtakes)} outtakes, {sum(r['status'] == 'PROTECTED' for r in results)} protected, {len(results)} checked.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
