"""JSONC loading and schema validation for the engine.

commands/_jsonc.py (copied from the tooling handbook's templates/, unmodified)
handles the shell side: it turns FLAT top-level scalars into `KEY=value` lines
for `eval`, and does a shallow, top-level-only schema check. That is by
design; see 04-config-files-jsonc.md.

Canvas's own API is nested (an assignment's fields, a rubric's criteria and
their ratings), so the configs here have to be nested too. This module is
the deep half: it parses the FULL structure (not just top-level scalars) and
validates it against the same sibling `*.schema.json` the shell layer uses,
recursing into "object" and "array" schemas where the shell-side validator
does not. Both layers read the same schema file; this one just looks
further into it.

The comment/trailing-comma stripper is copied from the same string-aware
algorithm as commands/_jsonc.py, so the two never disagree about what a
comment is.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas, respecting JSON strings."""
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if c in "}]":
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


def loads(text: str) -> Any:
    """Parse a jsonc string into Python data."""
    return json.loads(strip_jsonc(text))


def load_jsonc(path: "str | Path") -> Any:
    """Parse a jsonc file into Python data."""
    return loads(Path(path).read_text(encoding="utf-8"))


class ConfigError(Exception):
    """A config failed schema validation. Message is meant to be read by a human."""


_TYPE_OK = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}
# NOTE: commands/_jsonc.py (copied verbatim from the handbook) has the same
# table without "null", and defaults an unrecognised type name to "always
# passes" rather than "always fails". That is its shallow, top-level-only
# pre-check; this module is the deep one and is worth getting exactly
# right, so the "null" case is explicit here instead of relying on the
# same permissive fallback.


def _validate_node(value: Any, schema: dict, path: str) -> None:
    """Raise ConfigError on the first mismatch. Recurses into object/array schemas."""
    t = schema.get("type")
    types = t if isinstance(t, list) else [t] if t else []
    if types and not any(_TYPE_OK.get(tt, lambda v: True)(value) for tt in types):
        raise ConfigError(f"'{path}' must be {' or '.join(types)}, got {type(value).__name__}")

    if "enum" in schema and value not in schema["enum"]:
        raise ConfigError(f"'{path}' must be one of {schema['enum']}, got {value!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ConfigError(f"'{path}' must be >= {schema['minimum']}, got {value}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ConfigError(f"'{path}' must be <= {schema['maximum']}, got {value}")

    if isinstance(value, dict) and "properties" in schema:
        for key in schema.get("required", []):
            if key not in value:
                raise ConfigError(f"missing required key '{path}.{key}'")
        for key, sub_schema in schema["properties"].items():
            if key in value:
                _validate_node(value[key], sub_schema, f"{path}.{key}")

    if isinstance(value, list) and "items" in schema:
        for idx, item in enumerate(value):
            _validate_node(item, schema["items"], f"{path}[{idx}]")


def validate_config(data: dict, schema: dict) -> None:
    """
    Validate a full (possibly nested) config against a JSON Schema. Raises
    ConfigError with a human-readable message on the first problem found;
    returns None on success. This is the recursive counterpart to
    commands/_jsonc.py's shallow, top-level-only `validate()`.
    """
    for key in schema.get("required", []):
        if key not in data:
            raise ConfigError(f"missing required key '{key}'")
    for key, sub_schema in schema.get("properties", {}).items():
        if key in data:
            _validate_node(data[key], sub_schema, key)


def find_schema(config_path: "str | Path") -> "Path | None":
    """<stem>.config.jsonc -> <stem>.schema.json, sitting next to it. None if absent."""
    config_path = Path(config_path)
    base = config_path.name
    for suffix in (".config.jsonc", ".config.json", ".jsonc", ".json"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    candidate = config_path.with_name(base + ".schema.json")
    return candidate if candidate.is_file() else None


def load_and_validate(config_path: "str | Path") -> dict:
    """
    Load a jsonc config and, if a sibling schema.json exists, validate the
    FULL nested structure against it. Raises ConfigError on a bad config
    (the CLI turns this into a plain-language exit, matching the
    __CONFIG_ERROR__ contract commands/_jsonc.py uses on the shell side).
    """
    data = load_jsonc(config_path)
    if not isinstance(data, dict):
        raise ConfigError("config root must be a JSON object")
    schema_path = find_schema(config_path)
    if schema_path is not None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate_config(data, schema)
    return data
