"""
Shared utilities for cli.py: finding the project root from wherever the
CLI was launched, resolving "<field>_file" references against /input,
creating fresh out/<command>/<timestamp>/ directories, and writing
provenance.json. All pure/deterministic except _fresh_out_dir (reads the
clock) and the filesystem writes; no network access lives here.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PROVENANCE_SCHEMA = "canvas.provenance/v1"
_COURSE_ID_RE = re.compile(r"/courses/(\d+)")


def parse_course_id(course_url_or_id: str) -> int:
    """
    Accepts a full Canvas course URL (anything after the id, like
    /assignments or a #fragment, is ignored) or a bare numeric course id,
    and returns the integer id. Raises ValueError with a message meant to
    be shown directly to whoever typed it in.
    """
    text = (course_url_or_id or "").strip()
    if text.isdigit():
        return int(text)
    match = _COURSE_ID_RE.search(text)
    if match:
        return int(match.group(1))
    raise ValueError(
        f"Could not find a course id in {course_url_or_id!r}. Paste the "
        "full course URL, e.g. https://yourschool.instructure.com/courses/12345, "
        "or just the numeric course id."
    )


def find_engine_root(explicit: "str | None" = None) -> Path:
    """
    The project root (the directory holding commands/, out/, input/, and
    .venv/), tried in order:

    1. `explicit` (the --engine flag every commands/*.command invocation
       passes). The most direct channel there is, so it wins outright.
    2. The ENGINE environment variable, for a direct, headless invocation
       that skips --engine (a script or agent driving the CLI straight).
    3. sys.prefix, if the interpreter is running inside a venv. This is
       set by Python itself at startup from .venv/pyvenv.cfg, which makes
       it reliable even though .venv/bin/python is usually a *symlink* to
       the system interpreter: resolving that symlink (as sys.executable
       would) walks straight out of the venv and gives the wrong answer.
       That was a real, shipped bug; see research/02-engine-root-resolution.md.
    4. The current working directory, as a last resort.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get("ENGINE")
    if env:
        return Path(env)
    if sys.prefix != sys.base_prefix:
        return Path(sys.prefix).parent
    return Path.cwd()


def resolve_out_base(engine: Path, config: dict, command_name: str) -> Path:
    """
    Where a command's output should live: OUT_DIR from the config if it is
    set (expanded via resolve_path, so $ENGINE/~/$HOME all work the same
    way they do for any other path in a config), else
    engine/out/<command_name> as the default every shipped config uses.
    """
    raw = config.get("OUT_DIR")
    if raw:
        return resolve_path(engine, raw)
    return engine / "out" / command_name


def resolve_path(engine: Path, value: str) -> Path:
    """
    A config-relative or absolute path, resolved against the engine root.

    $ENGINE is substituted directly from the already-resolved `engine`
    argument, not from os.environ. That matters: find_engine_root() can
    correctly resolve the engine root from --engine alone, with no ENGINE
    environment variable present at all, and path expansion inside a
    config value has to agree with that answer rather than silently
    falling back to an unset environment variable and leaving a literal
    "$ENGINE" in the path. ~ and $HOME still expand from the environment
    in the normal way, since HOME is reliably present there.
    """
    value = value.replace("$ENGINE", str(engine)).replace("${ENGINE}", str(engine))
    p = Path(os.path.expanduser(os.path.expandvars(value)))
    return p if p.is_absolute() else (engine / p).resolve()


def resolve_file_field(section: dict, field_name: str, engine: Path) -> dict:
    """
    If `section` has "<field_name>_file", read that file (resolved against
    the engine root, conventionally something under input/) into
    section[field_name], and drop the "_file" key. Leaves `section`
    unchanged if "<field_name>" was set directly, or if neither is set.
    """
    file_key = f"{field_name}_file"
    if file_key in section:
        file_path = resolve_path(engine, section.pop(file_key))
        if not file_path.exists():
            fail(f"{file_key} points to a file that does not exist: {file_path}")
        section[field_name] = file_path.read_text(encoding="utf-8")
    return section


def fail(message: str) -> "None":
    """Print a plain-language error and exit non-zero. launch() reports the exit code."""
    print(message, file=sys.stderr)
    sys.exit(1)


def slugify(text: "str | None", max_len: int = 40) -> str:
    if not text:
        return "untitled"
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "untitled")[:max_len]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fresh_out_dir(base_dir: Path, slug: "str | None" = None) -> Path:
    """
    A new, never-reused <base_dir>/<timestamp>[__<slug>]/ directory. Every
    run gets its own; nothing already there is ever touched. `base_dir` is
    normally resolve_out_base()'s return value, so a customized OUT_DIR in
    a config is honored rather than silently overridden by a hardcoded
    engine/out/<command> path.

    The timestamp alone is second-resolution, so two calls within the same
    second (plausible if a script drives this tool in a tight loop) would
    otherwise collide. On a collision this appends -2, -3, ... until it
    finds a name nobody's using, rather than trusting the clock alone.
    """
    stamp = utc_stamp()
    base_name = f"{stamp}__{slugify(slug)}" if slug else stamp
    candidate = base_dir / base_name
    n = 1
    while True:
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            n += 1
            candidate = base_dir / f"{base_name}-{n}"


def _dep_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def write_provenance(out_dir: Path, *, command: str, config_path: Path, request_payload: dict, result: dict,
                      canvas_base_url: "str | None" = None, course_id: "int | None" = None,
                      license_note: str = "User-authored content; not AI-generated.") -> Path:
    """
    A provenance.json beside the artifact(s) in out_dir, recording the
    recipe: which command and config produced this, against which Canvas
    course (if any; merge-pdfs has none), with what request, and what came
    back. This is the tool-level analogue of gendiff's model/seed/version
    provenance, adapted for an API integration: there is no seed, so the
    reproducible unit is the request (see tests/test_engine.py's
    payload-determinism checks), not the response, since Canvas assigns
    its own ids and timestamps.
    """
    record = {
        "schema_version": PROVENANCE_SCHEMA,
        "command": command,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "canvas_base_url": canvas_base_url,
        "course_id": course_id,
        "config_path": str(config_path),
        "config_sha256": hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
        "request_payload": request_payload,
        "result": result,
        "tool_versions": {
            "python": platform.python_version(),
            "flask": _dep_version("flask"),
            "requests": _dep_version("requests"),
        },
        "license_note": license_note,
    }
    out_path = out_dir / "provenance.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out_path
