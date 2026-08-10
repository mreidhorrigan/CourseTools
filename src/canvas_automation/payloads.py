"""
Pure functions that turn a loaded config into the exact JSON payload the
server (and so Canvas) will receive. No network access and no filesystem
writes happen here (resolve_file_field does read from /input, since the
config's content lives there, but that read is deterministic). Kept
separate from cli.py so tests/test_engine.py can assert the same config
produces byte-identical output twice: the honest, tool-controllable
version of the handbook's determinism contract for a live-API tool. See
research/canvas-api-endpoints.md for why Canvas's own response cannot be
held to that same standard.
"""
from pathlib import Path

from .util import resolve_file_field


def build_assignment_payload(config: dict, engine: Path) -> dict:
    assignment = resolve_file_field(dict(config["assignment"]), "description", engine)
    return {"assignment": assignment}


def build_rubric_payload(config: dict, engine: Path) -> dict:
    payload = {"rubric": dict(config["rubric"])}
    if config.get("rubric_association"):
        payload["rubric_association"] = config["rubric_association"]
    return payload


def build_discussion_payload(config: dict, engine: Path) -> dict:
    # Discussion Topics takes flat top-level fields; everything except the
    # bookkeeping keys goes straight through.
    topic = {k: v for k, v in config.items() if k not in ("course_id", "OUT_DIR")}
    return resolve_file_field(topic, "message", engine)


def build_page_payload(config: dict, engine: Path) -> dict:
    page = resolve_file_field(dict(config["page"]), "body", engine)
    return {"page": page}
