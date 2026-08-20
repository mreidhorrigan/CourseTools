#!/usr/bin/env python3
"""Create an audited public excerpt from a private development chat transcript."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

BLOCKED_BLOCK_PATTERNS = (
    r"(?i)\b(?:api key|access token|bearer token|password|credential)\b",
    r"(?i)\b(?:answer key|correct answer|distractor|exam version|final exam(?:ination)?|midterm|question pool|private/testmaking)\b",
    r"(?i)\b(?:hidden instruction|canary term|font size 0|font-size\s*:\s*0)\b",
    r"(?i)\b(?:student data|medical information|accommodation information)\b",
)
INLINE_REDACTIONS = (
    (re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED CREDENTIAL]"),
    (re.compile(r"(?i)(?:Authorization\s*:\s*Bearer\s+)[A-Za-z0-9._-]+"), "Authorization: [REDACTED]"),
    (re.compile(r"(?m)^.*?/Users/.*$"), "[REDACTED LOCAL PATH REFERENCE]"),
    (re.compile(r"(?i)([?&](?:verifier|token|access_token|key)=)[^&\s)]+"), r"\1[REDACTED]"),
)


def terms(path: Path | None) -> list[str]:
    if path is None:
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def redact(source: str, denied_terms: list[str]) -> tuple[str, dict]:
    parts = re.split(r"(?m)(?=^## \d+\. )", source)
    header, blocks = parts[0], parts[1:]
    kept, omitted = [], []
    blocked = [re.compile(pattern) for pattern in BLOCKED_BLOCK_PATTERNS]
    denied = [re.compile(re.escape(term), re.I) for term in denied_terms]
    for block in blocks:
        reasons = [pattern.pattern for pattern in (*blocked, *denied) if pattern.search(block)]
        if reasons:
            title = block.splitlines()[0].strip()
            omitted.append({"block": title, "reason_count": len(reasons)})
            continue
        for pattern, replacement in INLINE_REDACTIONS:
            block = pattern.sub(replacement, block)
        kept.append(block.rstrip())
    notice = (
        "# Public development conversation excerpt\n\n"
        "> This public derivative contains visible user/assistant messages selected from a private development transcript. "
        "Messages concerning authentication secrets, private assessment content, security controls, personal data, or configured prohibited terms were omitted. "
        "Local filesystem paths and sensitive URL parameters were redacted. Omission does not imply that the remaining conversation is a complete procedural record.\n\n"
    )
    body = notice + "\n\n".join(kept).strip() + "\n"
    for pattern in denied:
        if pattern.search(body):
            raise RuntimeError("A configured prohibited term remained after redaction")
    for pattern in blocked:
        if pattern.search(body):
            raise RuntimeError("A safety-critical pattern remained after redaction")
    return body, {"input_blocks": len(blocks), "kept_blocks": len(kept), "omitted_blocks": len(omitted), "omissions": omitted}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--denylist", type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    result, audit = redact(source, terms(args.denylist))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    audit.update({
        "schema": "coursetools/public-chatlog-redaction/v1",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "output_sha256": hashlib.sha256(result.encode()).hexdigest(),
        "denylist_terms": len(terms(args.denylist)),
    })
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in audit.items() if key != "omissions"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
