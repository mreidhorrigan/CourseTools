#!/usr/bin/env python3
"""_jsonc.py — load a JSONC config and emit shell `KEY=value` lines for `eval`.

JSONC = JSON plus // and /* */ comments and trailing commas, so a config can document itself
(see 04-config-files-jsonc.md). The stripper is STRING-AWARE: a // inside a quoted value (a
path, an http:// URL) is preserved; only real comments and trailing commas are removed. The
cleaned text is parsed by the stdlib json module, so values follow normal JSON rules.

Each top-level scalar key prints as  KEY=<shell-quoted value> . Strings expand ~ , $HOME and
$ENGINE . Non-scalar values (objects, arrays) are skipped (flat config only).

VALIDATION (fail fast, fail readably). If a sibling JSON Schema exists, the config is checked
against it BEFORE any KEY=value line is printed. The schema is found from an explicit (possibly
commented-out) "$schema" path, or by deriving "<stem>.schema.json" from the config name. It is
plain JSON (no external dependency needed); this checks top-level required keys, type, enum, and
minimum/maximum. On any problem it prints  __CONFIG_ERROR__='...the offending key...'  and exits
non-zero, so the launcher reports it instead of running with a bad value. See 04-config-files-jsonc.md.

Usage:  eval "$(python _jsonc.py path/to/thing.config.jsonc)"
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path


def strip_jsonc(s: str) -> str:
    """Remove // and /* */ comments and trailing commas, respecting JSON strings."""
    out: list[str] = []
    i, n = 0, len(s)
    in_str = False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:        # keep an escaped char as-is
                out.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":     # line comment
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":     # block comment
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if c in "}]":                                       # drop a trailing comma before a closer
            j = len(out) - 1
            while j >= 0 and out[j] in " \t\r\n":
                j -= 1
            if j >= 0 and out[j] == ",":
                del out[j]
            out.append(c)
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def expand(v: str) -> str:
    return os.path.expanduser(os.path.expandvars(v))


def fail(msg: str) -> int:
    print("__CONFIG_ERROR__=" + shlex.quote(msg))
    return 1


def find_schema(config_path: Path, raw_text: str) -> Path | None:
    """Locate a sibling schema: an explicit (even commented-out) "$schema", else <stem>.schema.json."""
    m = re.search(r'"\$schema"\s*:\s*"([^"]+)"', raw_text)
    if m:
        cand = (config_path.parent / m.group(1)).resolve()
        if cand.is_file():
            return cand
    base = config_path.name
    for suffix in (".config.jsonc", ".config.json", ".jsonc", ".json"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    cand = config_path.with_name(base + ".schema.json")
    return cand if cand.is_file() else None


_TYPE_OK = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def validate(data: dict, schema: dict) -> str | None:
    """Minimal, dependency-free check of top-level scalars. Returns an error string or None."""
    for key in schema.get("required", []):
        if key not in data:
            return f"missing required key '{key}' in config"
    props = schema.get("properties", {})
    for key, spec in props.items():
        if key not in data:
            continue
        val = data[key]
        t = spec.get("type")
        types = t if isinstance(t, list) else [t] if t else []
        if types and not any(_TYPE_OK.get(tt, lambda v: True)(val) for tt in types):
            return f"key '{key}' must be {' or '.join(types)}, got {type(val).__name__}"
        if "enum" in spec and val not in spec["enum"]:
            return f"key '{key}' must be one of {spec['enum']}, got {val!r}"
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            if "minimum" in spec and val < spec["minimum"]:
                return f"key '{key}' must be >= {spec['minimum']}, got {val}"
            if "maximum" in spec and val > spec["maximum"]:
                return f"key '{key}' must be <= {spec['maximum']}, got {val}"
    return None


def main() -> int:
    if len(sys.argv) != 2:
        return fail("usage: _jsonc.py <config.jsonc>")
    p = Path(sys.argv[1])
    try:
        raw = p.read_text()
    except FileNotFoundError:
        return fail("config not found: " + str(p))
    try:
        data = json.loads(strip_jsonc(raw))
    except json.JSONDecodeError as e:
        return fail("bad config " + p.name + ": " + str(e))
    if not isinstance(data, dict):
        return fail("config root must be a JSON object")

    schema_path = find_schema(p, raw)
    if schema_path is not None:
        try:
            schema = json.loads(schema_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            return fail("bad schema " + schema_path.name + ": " + str(e))
        err = validate(data, schema)
        if err:
            return fail(err + "  (see " + schema_path.name + ")")

    for k, val in data.items():
        if k.startswith("$"):           # e.g. a "$schema" editor hint — ignore at runtime
            continue
        if isinstance(val, bool):
            val = "1" if val else ""
        elif isinstance(val, (int, float)):
            val = str(val)
        elif isinstance(val, str):
            val = expand(val)
        else:
            continue                     # skip objects / arrays (flat config only)
        print(k + "=" + shlex.quote(val))
    return 0


if __name__ == "__main__":
    sys.exit(main())
