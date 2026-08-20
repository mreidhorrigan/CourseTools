#!/usr/bin/env python3
"""Audit authoritative course sources with Mistral against cited standards."""
from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from canvas_automation.util import fresh_out_dir
from mistral_assignment_qa import MistralClient, MistralQAError, complete_json


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.parts.append(f" [link: {href}] ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape("".join(self.parts))
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n\s*\n+", "\n", value)
        return value.strip()


def html_text(path: Path) -> str:
    parser = VisibleText()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.text()


def source_block(root: Path, relative: str) -> str:
    path = root / relative
    body = html_text(path) if path.suffix.lower() in {".html", ".htm"} else path.read_text(encoding="utf-8")
    return f"SOURCE: {relative}\n{body.strip()}"


def build_packets(root: Path) -> dict[str, str]:
    manifest = json.loads((root / "course/course-manifest.json").read_text(encoding="utf-8"))
    active = [o for o in manifest["objects"] if o.get("published", True) and "/outtakes/" not in o["source"]]
    page_sources = sorted({o["source"] for o in active if o["kind"] in {"syllabus", "page", "quiz"}})
    assessment_sources = sorted({o["source"] for o in active if o["kind"] in {"assignment", "discussion"}})
    rubrics = json.loads((root / "course/rubric-manifest.json").read_text(encoding="utf-8"))["rubrics"]
    rubric_sources = sorted({r["source"] for r in rubrics})
    structure = {
        "course": {k: manifest.get(k) for k in ("course_code", "course_name")},
        "active_objects": [{k: o.get(k) for k in ("kind", "title", "source", "published")} for o in active],
        "module_order_source": [
            {k: o.get(k) for k in ("kind", "title", "position")}
            for o in active
        ],
        "workload_configuration": (root / "course/reading-workload.config.jsonc").read_text(encoding="utf-8"),
    }
    return {
        "orientation_content_and_weekly_design": "\n\n".join(source_block(root, p) for p in page_sources),
        "assessment_alignment_and_feedback": "\n\n".join(source_block(root, p) for p in assessment_sources + rubric_sources),
        "structure_navigation_and_workload": json.dumps(structure, indent=2, ensure_ascii=False),
    }


def audit_messages(standards: str, packet_name: str, packet: str) -> list[dict[str, str]]:
    shape = {
        "packet": packet_name,
        "strengths": [{"standard": "string", "evidence": "source path plus heading or short phrase", "finding": "string"}],
        "findings": [{
            "id": "short stable identifier", "priority": "high|medium|low",
            "standard": "framework and area", "status": "demonstrated|not_evidenced|needs_human_test",
            "evidence": ["source path plus heading or short phrase"], "student_impact": "string",
            "recommendation": "small practical correction", "target_source": "path or unknown",
        }],
        "uncertainties": ["string"],
    }
    return [
        {"role": "system", "content": (
            "You are a rigorous external reviewer of an online university course. Apply only the supplied "
            "standards profile. Audit only what the packet demonstrates. A missing item may be marked "
            "not_evidenced; never convert absence from this packet into a demonstrated defect. Cite local "
            "source paths and headings or short phrases. Prioritize useful, specific findings over generic "
            "commentary. Do not claim certification, legal compliance, or inaccessible Canvas state. Return JSON only."
        )},
        {"role": "user", "content": (
            f"Return one JSON object shaped like:\n{json.dumps(shape)}\n\n"
            f"STANDARDS PROFILE\n{standards}\n\nCOURSE PACKET: {packet_name}\n{packet}"
        )},
    ]


def synthesis_messages(standards: str, audits: list[dict[str, Any]]) -> list[dict[str, str]]:
    shape = {
        "executive_assessment": "string",
        "priority_findings": [{"rank": 1, "finding_ids": ["string"], "finding": "string", "why_useful": "string", "recommended_action": "string"}],
        "verified_strengths_to_preserve": ["string"],
        "standards_coverage_limits": ["string"],
        "recommended_human_checks": ["string"],
    }
    return [
        {"role": "system", "content": (
            "Synthesize independent course-packet audits. Merge duplicates and retain evidence distinctions. "
            "Rank no more than ten material, actionable findings. Do not introduce a finding absent from the "
            "packet audits. Explicitly state where browser, assistive-technology, policy, or instructor judgment "
            "is still required. Return JSON only."
        )},
        {"role": "user", "content": f"Return JSON shaped like:\n{json.dumps(shape)}\n\nSTANDARDS PROFILE\n{standards}\n\nPACKET AUDITS\n{json.dumps(audits, ensure_ascii=False)}"},
    ]


def markdown_report(record: dict[str, Any]) -> str:
    synthesis = record["synthesis"]
    lines = [
        "# Mistral standards audit of the authored course", "",
        f"- Requested model alias: `{record['requested_model']}`",
        f"- API-returned model identifier(s): {', '.join(f'`{x}`' for x in record['returned_model_identifiers'])}",
        f"- Standards profile: `{record['standards_source']}`",
        "- Status: diagnostic model review; findings require human verification.", "",
        "## Executive assessment", "", synthesis.get("executive_assessment", ""), "",
        "## Priority findings", "",
    ]
    for item in synthesis.get("priority_findings", []):
        lines.extend([
            f"### {item.get('rank', '?')}. {item.get('finding', '')}", "",
            f"Why useful: {item.get('why_useful', '')}", "",
            f"Recommended action: {item.get('recommended_action', '')}", "",
            f"Source finding IDs: {', '.join(item.get('finding_ids', []))}", "",
        ])
    lines.extend(["## Strengths to preserve", ""])
    lines.extend(f"- {x}" for x in synthesis.get("verified_strengths_to_preserve", []))
    lines.extend(["", "## Required human checks", ""])
    lines.extend(f"- {x}" for x in synthesis.get("recommended_human_checks", []))
    lines.extend(["", "## Coverage limits", ""])
    lines.extend(f"- {x}" for x in synthesis.get("standards_coverage_limits", []))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--standards", type=Path, default=ROOT / "research/standards/course-audit-standards.md")
    parser.add_argument("--model", default="mistral-small-latest")
    parser.add_argument("--max-packet-chars", type=int, default=115_000)
    args = parser.parse_args()
    root, standards_path = args.root.resolve(), args.standards.resolve()
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        raise MistralQAError("MISTRAL_API_KEY is not set")
    standards = standards_path.read_text(encoding="utf-8")
    packets = build_packets(root)
    oversized = {name: len(value) for name, value in packets.items() if len(value) > args.max_packet_chars}
    if oversized:
        raise MistralQAError(f"Course audit packet exceeds --max-packet-chars: {oversized}")
    output = fresh_out_dir(root / "out/course-development/mistral-course-standards-audit", "course-audit")
    (output / "packets").mkdir()
    client = MistralClient(api_key, api_url="https://api.mistral.ai/v1/chat/completions", model=args.model,
                           timeout_seconds=240, retry_attempts=5, retry_base_seconds=5)
    audits, call_records = [], []
    for index, (name, packet) in enumerate(packets.items(), 1):
        (output / "packets" / f"{name}.txt").write_text(packet + "\n", encoding="utf-8")
        print(f"[{index}/{len(packets) + 1}] Auditing {name} ({len(packet):,} characters)", flush=True)
        value, meta = complete_json(client, audit_messages(standards, name, packet), stage=name,
                                    seed=21000 + index, temperature=0.05, max_tokens=6000)
        audits.append(value)
        call_records.append({"stage": name, **meta})
    print(f"[{len(packets) + 1}/{len(packets) + 1}] Synthesizing findings", flush=True)
    synthesis, meta = complete_json(client, synthesis_messages(standards, audits), stage="synthesis",
                                    seed=21999, temperature=0.05, max_tokens=5000)
    call_records.append({"stage": "synthesis", **meta})
    returned = sorted({
        attempt.get("api_metadata", {}).get("model")
        for call in call_records for attempt in call.get("attempts", [])
        if attempt.get("api_metadata", {}).get("model")
    })
    record = {
        "schema": "canvas-automation/mistral-course-standards-audit/v1",
        "requested_model": args.model, "returned_model_identifiers": returned,
        "standards_source": str(standards_path.relative_to(root)),
        "standards_sha256": hashlib.sha256(standards.encode()).hexdigest(),
        "packet_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in packets.items()},
        "packet_audits": audits, "synthesis": synthesis, "api_calls": call_records,
    }
    (output / "audit-results.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "audit-report.md").write_text(markdown_report(record), encoding="utf-8")
    print(json.dumps({"output": str(output), "returned_model_identifiers": returned}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
