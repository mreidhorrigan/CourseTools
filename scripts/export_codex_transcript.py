#!/usr/bin/env python3
"""Export visible user/assistant messages from a Codex rollout JSONL file."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


SECRET_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED OPENAI-STYLE SECRET]"),
    (re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)[A-Za-z0-9._-]{16,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(Canvas API token\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
)


def redact(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def block_text(block: dict) -> str | None:
    kind = block.get("type")
    if kind in {"input_text", "output_text", "text"}:
        return block.get("text", "")
    if kind in {"input_image", "image"}:
        name = block.get("name") or block.get("path") or "image"
        return f"[Attached image: {name}]"
    return None


def visible_messages(source: Path) -> list[dict]:
    messages = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on line {number}: {error}") from error
        if event.get("type") != "response_item":
            continue
        payload = event.get("payload", {})
        if payload.get("type") != "message" or payload.get("role") not in {"user", "assistant"}:
            continue
        parts = [part for block in payload.get("content", []) if (part := block_text(block)) is not None]
        text = redact("\n\n".join(parts).strip())
        if not text or text.startswith("<environment_context>"):
            continue
        messages.append({
            "timestamp": event.get("timestamp"),
            "role": payload["role"],
            "phase": payload.get("phase"),
            "text": text,
        })
    return messages


def render(source: Path, messages: list[dict]) -> str:
    session_id = None
    first = source.read_text(encoding="utf-8").splitlines()[0]
    try:
        session_id = json.loads(first).get("payload", {}).get("session_id")
    except (json.JSONDecodeError, IndexError):
        pass
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    lines = [
        "# Canvas Automation development conversation",
        "",
        "> Point-in-time export of the visible conversation between the user and Codex. ",
        "> System/developer instructions, hidden reasoning, tool calls, and raw tool outputs are excluded. ",
        "> Credential-shaped strings are redacted automatically. Local paths and public course URLs are retained because they document the workflow.",
        "",
        f"- Session: `{session_id or 'unknown'}`",
        f"- Source SHA-256: `{source_hash}`",
        f"- Visible messages: {len(messages)}",
        "",
    ]
    for index, message in enumerate(messages, 1):
        label = "User" if message["role"] == "user" else "Assistant"
        if message.get("phase") == "commentary":
            label += " — progress update"
        stamp = message.get("timestamp") or "timestamp unavailable"
        lines.extend([f"## {index}. {label}", "", f"*{stamp}*", "", message["text"], ""])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Codex rollout JSONL")
    parser.add_argument("output", type=Path, help="Private Markdown output path")
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    messages = visible_messages(source)
    if not messages:
        raise RuntimeError("No visible user/assistant messages found")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(source, messages), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "messages": len(messages),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
