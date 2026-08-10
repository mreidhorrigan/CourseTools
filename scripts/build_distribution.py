#!/usr/bin/env python3
"""Build a deterministic, sanitized Canvas Automation distribution ZIP."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import tomllib
import zipfile
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from canvas_automation import jsonc
from canvas_automation.util import fresh_out_dir, resolve_out_base

FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
TOP_FILES = {
    ".gitignore", "AGENTS.md", "CHATGPT_CANVAS_COURSE_AUTHORING_GUIDE.md", "INDEX.html", "LICENSE",
    "LICENSES.md", "PUBLIC_REPOSITORY.md", "README.md", "TODO.md", "pyproject.toml", "uv.lock",
    "setup-after-move.command", "verify.command",
}
INCLUDE_DIRS = {"assets", "commands", "course", "docs", "examples", "mcp", "research", "skills", "src", "scripts", "templates", "tests"}
PRIVATE_ASSESSMENT_PREFIXES = ("private/", "out/testmaking-authoring/", "out/build-test-forms/")
LICENSES = {
    "beautifulsoup4": "MIT", "blinker": "MIT", "canvas-automation": "MIT",
    "certifi": "MPL-2.0", "charset-normalizer": "MIT", "click": "BSD-3-Clause",
    "colorama": "BSD-3-Clause", "et-xmlfile": "MIT", "exceptiongroup": "MIT",
    "flask": "BSD-3-Clause", "idna": "BSD-3-Clause", "importlib-metadata": "Apache-2.0",
    "iniconfig": "MIT", "itsdangerous": "BSD-3-Clause", "jinja2": "BSD-3-Clause",
    "lxml": "BSD-3-Clause", "markupsafe": "BSD-3-Clause", "openpyxl": "MIT",
    "packaging": "Apache-2.0 OR BSD-2-Clause", "pillow": "MIT-CMU", "pluggy": "MIT",
    "pygments": "BSD-2-Clause", "pypdf": "BSD-3-Clause", "pytest": "MIT",
    "reportlab": "BSD-3-Clause", "requests": "Apache-2.0", "soupsieve": "MIT",
    "waitress": "ZPL-2.1",
    "tomli": "MIT", "typing-extensions": "PSF-2.0", "urllib3": "MIT",
    "werkzeug": "BSD-3-Clause", "zipp": "MIT",
}
MCP_LICENSES = {
    "aiofile": "Apache-2.0", "annotated-types": "MIT", "anyio": "MIT", "attrs": "MIT",
    "authlib": "BSD-3-Clause", "beartype": "MIT", "cachetools": "MIT", "caio": "Apache-2.0",
    "canvas-mcp": "MIT", "certifi": "MPL-2.0", "cffi": "MIT-0", "click": "BSD-3-Clause",
    "colorama": "BSD-3-Clause", "cryptography": "Apache-2.0 OR BSD-3-Clause", "cyclopts": "Apache-2.0",
    "dnspython": "ISC", "docstring-parser": "MIT", "email-validator": "Unlicense",
    "exceptiongroup": "MIT", "fastmcp": "Apache-2.0", "fastmcp-slim": "Apache-2.0",
    "griffelib": "ISC", "h11": "MIT", "httpcore": "BSD-3-Clause", "httpx": "BSD-3-Clause",
    "httpx-sse": "MIT", "idna": "BSD-3-Clause", "jaraco-classes": "MIT", "jaraco-context": "MIT",
    "jaraco-functools": "MIT", "jeepney": "MIT", "joserfc": "BSD-3-Clause", "jsonref": "MIT",
    "jsonschema": "MIT", "jsonschema-path": "Apache-2.0", "jsonschema-specifications": "MIT",
    "keyring": "MIT", "markdown-it-py": "MIT", "mcp": "MIT", "mdurl": "MIT",
    "more-itertools": "MIT", "openapi-pydantic": "MIT", "opentelemetry-api": "Apache-2.0",
    "packaging": "Apache-2.0 OR BSD-2-Clause", "pathable": "Apache-2.0", "platformdirs": "MIT",
    "py-key-value-aio": "Apache-2.0", "pycparser": "BSD-3-Clause", "pydantic": "MIT",
    "pydantic-core": "MIT", "pydantic-settings": "MIT", "pygments": "BSD-2-Clause",
    "pyjwt": "MIT", "pyperclip": "BSD-3-Clause", "python-dateutil": "Apache-2.0 OR BSD-3-Clause",
    "python-dotenv": "BSD-3-Clause", "python-multipart": "Apache-2.0", "pywin32": "PSF-2.0",
    "pywin32-ctypes": "BSD-3-Clause", "pyyaml": "MIT", "referencing": "MIT", "rich": "MIT",
    "rich-rst": "MIT", "rpds-py": "MIT", "secretstorage": "BSD-3-Clause", "six": "MIT",
    "sse-starlette": "BSD-3-Clause", "starlette": "BSD-3-Clause", "typing-extensions": "PSF-2.0",
    "typing-inspection": "MIT", "uncalled-for": "MIT", "uvicorn": "BSD-3-Clause",
    "watchfiles": "MIT", "websockets": "BSD-3-Clause",
}


def audit_distribution_safety(staging, disclosed_content=""):
    """Reject credentials, private paths, and prohibited payloads in staged files."""
    forbidden_paths = (".git/", ".venv/", "out/", "input/imscc/", *PRIVATE_ASSESSMENT_PREFIXES)
    forbidden_names = re.compile(
        r"(?:^|/)(?:\.env(?:\..*)?|id_rsa|id_ed25519|[^/]+\.(?:pem|p12|pfx|key)|"
        r"(?:grades?|submission[_-]?roster|student[_-]?roster)\.(?:csv|xlsx?|json))$",
        re.I,
    )
    secret_patterns = {
        "local absolute path": re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
        "OpenAI-style secret": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "literal bearer credential": re.compile(rb"(?i)Authorization\s*:\s*Bearer\s+(?!<token>)[A-Za-z0-9._-]{16,}"),
        "assigned Canvas or Mistral credential": re.compile(
            rb"(?i)\b(?:MISTRAL_API_KEY|CANVAS_API_TOKEN|CANVAS_API_KEY)\s*=\s*[\"']"
            rb"(?![<.$])(?=[A-Za-z0-9._-]{16,}[\"'])[A-Za-z0-9._-]+[\"']"
        ),
        "JWT-like credential": re.compile(rb"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    }
    violations, scanned = [], 0

    def inspect(name, data):
        nonlocal scanned
        scanned += 1
        if name.startswith(forbidden_paths) or forbidden_names.search(name):
            violations.append({"path": name, "reason": "prohibited path or credential-file name"})
        for reason, pattern in secret_patterns.items():
            if pattern.search(data):
                violations.append({"path": name, "reason": reason})

    for path in sorted(item for item in staging.rglob("*") if item.is_file()):
        rel = path.relative_to(staging).as_posix()
        data = path.read_bytes()
        inspect(rel, data)
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as nested:
                for member in nested.infolist():
                    if not member.is_dir():
                        inspect(f"{rel}!/{member.filename}", nested.read(member))
    if violations:
        raise RuntimeError(f"Distribution safety audit failed: {violations}")
    return {
        "schema": "canvas-automation-distribution-safety/v1",
        "status": "PASS",
        "scanned_files_including_nested_archives": scanned,
        "checks": ["no credential or student-data file names", "no local macOS absolute paths", "no literal bearer credentials", "no assigned Canvas/Mistral credentials", "no OpenAI-style or JWT-like secrets", "no private assessment authoring or output", "no private IMSCC input or generated output"],
        "disclosed_content": disclosed_content,
    }


def source_files(root, excluded_files=()):
    excluded = set(excluded_files)
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        first = rel.split("/", 1)[0]
        wanted_input = rel.startswith("input/") and not rel.startswith("input/imscc/")
        if rel in TOP_FILES or first in INCLUDE_DIRS or wanted_input:
            if rel in excluded:
                continue
            if rel != ".gitignore" and any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            if any(part in {".git", ".venv", "__pycache__", "out", "dist", "build"} for part in path.relative_to(root).parts):
                continue
            files.append((rel, path))
    return sorted(files)


def sanitize(rel, data):
    special_manifests = {"course/course-manifest.json"}
    course_text = rel.startswith("course/") and Path(rel).suffix in {".html", ".json", ".md"}
    if rel != "course/course.config.jsonc" and rel not in special_manifests and not rel.endswith(".config.jsonc") and not course_text:
        return data
    text = data.decode("utf-8")
    if rel == "course/course.config.jsonc":
        config = jsonc.loads(text); config["course_url"] = "https://canvas.example.edu/courses/12345"
        config["institution"] = {"name": "Example Institution", "homepage": "https://www.example.edu/", "canvas_host": "canvas.example.edu", "policy_search_domains": ["example.edu"], "library_resolver_hosts": []}
        return ("// Run commands/initialize.command before use; contains no credentials.\n" + json.dumps(config, indent=2) + "\n").encode()
    if rel == "course/course-manifest.json":
        manifest = json.loads(text); manifest["course_id"] = 12345
        manifest["course_url"] = "https://canvas.example.edu/courses/12345"; manifest["requires_reinitialization"] = True
        manifest["course_name"] = "Example Course Authoring Baseline"; manifest["course_code"] = "EXAMPLE-COURSE"
        for item in manifest["objects"]: item["canvas_id"] = 0
        return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    if rel == "course/links-manifest.json":
        manifest = json.loads(text)
        manifest["institution"] = {
            "name": "Example Institution",
            "homepage": "https://www.example.edu/",
            "canvas_host": "canvas.example.edu",
            "policy_search_domains": ["example.edu"],
            "library_resolver_hosts": [],
        }
        text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if course_text:
        text = re.sub(
            r"https://[^/\s\"']+((?:/api/v1)?/courses/)[1-9][0-9]*",
            r"https://canvas.example.edu\g<1>12345",
            text,
        )
        text = re.sub(r"(?<![0-9])/courses/[1-9][0-9]*", "/courses/12345", text)
        if Path(rel).suffix == ".json":
            text = re.sub(r'("course_id"\s*:\s*)\d+', r'\g<1>12345', text)
        return text.encode("utf-8")
    text = re.sub(r'("course_id"\s*:\s*)\d+', r'\g<1>12345', text)
    text = re.sub(
        r'("sandbox_course_url"\s*:\s*)"[^"]+"',
        r'\g<1>"https://canvas.example.edu/courses/12345"', text,
    )
    return text.encode("utf-8")


def mcp_version(root):
    return next(
        line.split("==", 1)[1].split()[0].strip()
        for line in (root / "mcp/requirements.lock").read_text().splitlines()
        if line.strip().startswith("canvas-mcp==")
    )


def build_sbom(root):
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    components = []
    for package in sorted(lock["package"], key=lambda item: (item["name"], item["version"])):
        name = package["name"]
        if name not in LICENSES:
            raise RuntimeError(f"No SPDX license mapping for locked package: {name}")
        components.append({
            "type": "library", "name": name, "version": package["version"],
            "purl": f"pkg:pypi/{name}@{package['version']}",
            "licenses": [{"expression": LICENSES[name]}],
        })
    locked_mcp = []
    for line in (root / "mcp/requirements.lock").read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)", line)
        if match:
            locked_mcp.append((match.group(1).lower().replace("_", "-"), match.group(2)))
    for name, version in locked_mcp:
        if name not in MCP_LICENSES:
            raise RuntimeError(f"No SPDX license mapping for locked MCP package: {name}")
        component = {
            "type": "application" if name == "canvas-mcp" else "library",
            "name": name, "version": version, "purl": f"pkg:pypi/{name}@{version}",
            "scope": "optional", "group": "canvas-mcp-environment",
            "licenses": [{"expression": MCP_LICENSES[name]}],
        }
        if name == "canvas-mcp":
            component["externalReferences"] = [{"type": "vcs", "url": "https://github.com/vishalsachdev/canvas-mcp"}]
        components.append(component)
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "metadata": {"component": {"type": "application", "name": "canvas-automation", "version": "0.1.0"}},
        "components": components,
    }


def render_index(root):
    template = (root / "templates/distribution-index.html").read_text(encoding="utf-8")
    return template.replace("{{MCP_VERSION}}", mcp_version(root))


def write_zip(staging, output):
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(staging.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(staging).as_posix()
            info = zipfile.ZipInfo(rel, FIXED_ZIP_TIME)
            info.create_system = 3
            executable = path.suffix in {".command", ".sh"} or path.name == "canvas-mcp-launcher"
            info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def publish_release(root, built_archive, provenance_path, config):
    """Copy a verified build to one obvious release directory and prune build snapshots."""
    configured = config.get("release_dir")
    if not configured:
        return built_archive
    release_dir = Path(str(configured).replace("$ENGINE", str(root))).resolve()
    root = root.resolve()
    if root not in release_dir.parents:
        raise ValueError("release_dir must be inside the project root")
    release_dir.mkdir(parents=True, exist_ok=True)
    release_archive = release_dir / built_archive.name
    shutil.copyfile(built_archive, release_archive)
    shutil.copyfile(provenance_path, release_dir / "provenance.json")

    keep = int(config.get("retained_timestamped_builds", 0))
    if keep < 0:
        raise ValueError("retained_timestamped_builds must be zero or greater")
    build_root = built_archive.parent.parent.resolve()
    if root not in build_root.parents:
        raise ValueError("distribution output must be inside the project root before pruning")
    snapshot_name = re.compile(r"^\d{8}T\d{6}Z__canvas-automation-distribution(?:-\d+)?$")
    snapshots = sorted(
        (
            path for path in build_root.iterdir()
            if path.is_dir() and not path.is_symlink() and snapshot_name.fullmatch(path.name)
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    for obsolete in snapshots[keep:]:
        shutil.rmtree(obsolete)
    return release_archive


def build(root, config):
    out_dir = fresh_out_dir(resolve_out_base(root, config, "distribution"), "canvas-automation-distribution")
    with tempfile.TemporaryDirectory(prefix="canvas_distribution_") as temp:
        staging = Path(temp)
        for rel, source in source_files(root, config.get("exclude_paths", [])):
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(sanitize(rel, source.read_bytes()))
        (staging / "INDEX.html").write_text(render_index(root), encoding="utf-8")
        (staging / "sbom.json").write_text(json.dumps(build_sbom(root), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        safety = audit_distribution_safety(staging, config.get("disclosed_content", ""))
        (staging / "DISTRIBUTION-SAFETY.json").write_text(json.dumps(safety, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files = []
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                files.append({"path": path.relative_to(staging).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
        manifest = {"schema": "canvas-automation-distribution/v1", "sanitized": True, "files": files}
        (staging / "DISTRIBUTION-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output = out_dir / config.get("archive_name", "canvas-automation-toolkit.zip")
        write_zip(staging, output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    provenance = {"schema": "canvas.provenance/v1", "artifact": output.name, "sha256": digest, "license_note": "Mixed licensing; see LICENSES.md and sbom.json", "sanitized": True}
    provenance_path = out_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    published = publish_release(root, output, provenance_path, config)
    return published, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--config", type=Path, default=Path("commands/build-distribution.config.jsonc"))
    args = parser.parse_args()
    config = jsonc.load_and_validate(args.config)
    output, digest = build(args.root.resolve(), config)
    print(json.dumps({"output": str(output), "sha256": digest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
