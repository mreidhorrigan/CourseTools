from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_running_server", ROOT / "scripts/check_running_server.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class Connection:
    def close(self):
        pass


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def install_health(monkeypatch, body):
    monkeypatch.setattr(module.socket, "create_connection", lambda *_args, **_kwargs: Connection())
    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: Response(json.dumps(body).encode()))


def test_probe_recognizes_matching_guard(monkeypatch):
    install_health(monkeypatch, {
        "status": "ok", "allowed_course_id": 12345, "canvas_base_url": "https://canvas.example.edu",
    })
    result = module.probe("127.0.0.1", 5055, 12345, "https://canvas.example.edu")
    assert result.state == "matching"
    assert "already running" in result.message


def test_probe_rejects_different_course_guard(monkeypatch):
    install_health(monkeypatch, {
        "status": "ok", "allowed_course_id": 67890, "canvas_base_url": "https://canvas.example.edu",
    })
    result = module.probe("127.0.0.1", 5055, 12345, "https://canvas.example.edu")
    assert result.state == "different"
    assert "67890" in result.message


def test_probe_distinguishes_available_port(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise ConnectionRefusedError

    monkeypatch.setattr(module.socket, "create_connection", unavailable)
    assert module.probe("127.0.0.1", 5055, 12345, "https://canvas.example.edu").state == "available"


def test_probe_distinguishes_unrelated_listener(monkeypatch):
    monkeypatch.setattr(module.socket, "create_connection", lambda *_args, **_kwargs: Connection())

    def invalid(*_args, **_kwargs):
        raise module.URLError("not HTTP")

    monkeypatch.setattr(module, "urlopen", invalid)
    assert module.probe("127.0.0.1", 5055, 12345, "https://canvas.example.edu").state == "occupied"
