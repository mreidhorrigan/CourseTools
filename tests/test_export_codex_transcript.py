from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("export_codex_transcript", ROOT / "scripts/export_codex_transcript.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def event(role, text, *, phase=None):
    payload = {"type": "message", "role": role, "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}]}
    if phase:
        payload["phase"] = phase
    return {"timestamp": "2026-01-01T00:00:00Z", "type": "response_item", "payload": payload}


def test_visible_export_excludes_control_roles_and_redacts_secrets(tmp_path):
    source = tmp_path / "rollout.jsonl"
    synthetic_secret = "sk-" + ("a" * 30)
    rows = [
        {"type": "session_meta", "payload": {"session_id": "session-1"}},
        event("developer", "hidden control text"),
        event("user", "<environment_context>hidden</environment_context>"),
        event("user", "Please build this."),
        event("assistant", f"Working with {synthetic_secret}.", phase="commentary"),
        {"type": "response_item", "payload": {"type": "function_call", "name": "secret_tool"}},
    ]
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    messages = module.visible_messages(source)
    assert [message["role"] for message in messages] == ["user", "assistant"]
    rendered = module.render(source, messages)
    assert "Please build this." in rendered
    assert "[REDACTED OPENAI-STYLE SECRET]" in rendered
    assert "hidden control text" not in rendered
    assert "environment_context" not in rendered
    assert "secret_tool" not in rendered
