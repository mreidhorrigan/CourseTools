import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_update_target", ROOT / "scripts/verify_update_target.py")
module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)

class FakeCanvas:
    workflow = "unpublished"
    def __init__(self, server, course_id): self.course_id = course_id
    def health(self): return {"allowed_course_id": self.course_id}
    def raw(self, method, path): return {"workflow_state": self.workflow}

def root_config(tmp_path, course_id=123):
    (tmp_path / "course").mkdir()
    (tmp_path / "course/course.config.jsonc").write_text(json.dumps({"course_url": f"https://canvas.example.edu/courses/{course_id}"}))

def test_guard_accepts_only_matching_unpublished_course(tmp_path, monkeypatch):
    root_config(tmp_path)
    monkeypatch.setattr(module, "GuardedCanvas", FakeCanvas)
    assert module.verify(tmp_path, "local")["status"] == "PASS"

def test_guard_rejects_published_course(tmp_path, monkeypatch):
    root_config(tmp_path)
    class Published(FakeCanvas): workflow = "available"
    monkeypatch.setattr(module, "GuardedCanvas", Published)
    with pytest.raises(RuntimeError, match="is published"):
        module.verify(tmp_path, "local")

def test_guard_rejects_server_for_different_course(tmp_path, monkeypatch):
    root_config(tmp_path)
    class Wrong(FakeCanvas):
        def health(self): return {"allowed_course_id": 999}
    monkeypatch.setattr(module, "GuardedCanvas", Wrong)
    with pytest.raises(RuntimeError, match="different course"):
        module.verify(tmp_path, "local")
