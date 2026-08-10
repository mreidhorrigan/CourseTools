from __future__ import annotations

import importlib.util
from pathlib import Path

from canvas_automation import jsonc

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("audit_portability", ROOT / "scripts/audit_portability.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_distribution_source_has_no_specific_values_in_reusable_code():
    config = jsonc.load_and_validate(ROOT / "commands/portability-audit.config.jsonc")
    distribution = jsonc.load_and_validate(ROOT / "commands/build-distribution.config.jsonc")
    result = module.audit(ROOT, config, distribution)
    assert result["violations"] == []
    assert any(item["path"] == "commands/start-server.config.jsonc" for item in result["config_review"])


def test_audit_detects_a_specific_value_in_code(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/leak.py").write_text('HOST = "canvas.example.edu"\n')
    config = {
        "scan_extensions": [".py"],
        "course_content_prefixes": [],
        "course_content_test_paths": [],
        "markers": [{"name": "host", "pattern": "canvas\\.example\\.edu"}],
    }
    result = module.audit(tmp_path, config, {"exclude_paths": []})
    assert result["portable"] is False
    assert result["violations"] == [{"path": "scripts/leak.py", "line": 1, "marker": "host"}]
