import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("redactor", ROOT / "scripts/redact_public_chatlog.py")
MODULE = importlib.util.module_from_spec(SPEC); assert SPEC.loader; SPEC.loader.exec_module(MODULE)


def test_redactor_omits_sensitive_blocks_and_redacts_paths():
    private_path = "/" + "Users/person/project/file"
    source = f"# Private\n\n## 1. User\n\nPublic method at {private_path}.\n\n## 2. User\n\nHere is an API key.\n\n## 3. Assistant\n\nForbiddenWord appears.\n"
    result, audit = MODULE.redact(source, ["ForbiddenWord"])
    assert "[REDACTED LOCAL PATH REFERENCE]" in result
    assert "API key" not in result and "ForbiddenWord" not in result
    assert audit["kept_blocks"] == 1 and audit["omitted_blocks"] == 2
