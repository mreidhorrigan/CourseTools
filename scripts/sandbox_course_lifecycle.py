#!/usr/bin/env python3
"""Guarded, reproducible lifecycle operations for one Canvas sandbox course.

This script never accepts a Canvas token. It talks only to the toolkit's local
server, which enforces the configured sandbox course. Destructive reset requires
an exact confirmation string and writes the Canvas response to disk.
"""
from __future__ import annotations

import argparse
import json
import time
import zipfile
from pathlib import Path

import requests


RESOURCES = (
    "pages",
    "assignments",
    "quizzes",
    "discussion_topics",
    "modules",
    "files",
    "rubrics",
    "assignment_groups",
)


class GuardedCanvas:
    def __init__(self, server: str, course_id: int):
        self.server = server.rstrip("/")
        self.course_id = course_id

    def health(self) -> dict:
        response = requests.get(f"{self.server}/health", timeout=10)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Local/Canvas request failed ({response.status_code}) "
                f"{method} {path}: {response.text[:1000]}"
            )
        health = response.json()
        if health.get("allowed_course_id") != self.course_id:
            raise RuntimeError(
                f"Local server allows course {health.get('allowed_course_id')}, "
                f"not requested course {self.course_id}."
            )
        return health

    def raw(self, method: str, path: str, payload=None, params=None):
        body = {"method": method, "path": path}
        if payload is not None:
            body["payload"] = payload
        if params is not None:
            body["params"] = params
        response = requests.post(f"{self.server}/api/raw", json=body, timeout=60)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Local/Canvas request failed ({response.status_code}) "
                f"{method} {path}: {response.text[:1000]}"
            )
        return response.json() if response.content else None

    def inventory(self) -> dict:
        self.health()
        course = self.raw("GET", f"/courses/{self.course_id}")
        counts = {}
        for resource in RESOURCES:
            result = self.raw(
                "GET", f"/courses/{self.course_id}/{resource}", params={"per_page": 100}
            )
            counts[resource] = len(result) if isinstance(result, list) else None
        return {"course": course, "counts": counts}

    def backup(self, output: Path, poll_seconds: float = 2.0, timeout: float = 300.0) -> dict:
        self.health()
        export = self.raw(
            "POST",
            f"/courses/{self.course_id}/content_exports",
            {"export_type": "common_cartridge"},
        )
        deadline = time.monotonic() + timeout
        while export.get("workflow_state") not in {"exported", "failed"}:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Canvas export {export.get('id')} did not finish in time")
            time.sleep(poll_seconds)
            export = self.raw(
                "GET", f"/courses/{self.course_id}/content_exports/{export['id']}"
            )
        if export.get("workflow_state") != "exported":
            raise RuntimeError(f"Canvas export failed: {export}")
        attachment = export.get("attachment") or {}
        file_id = attachment.get("id")
        if not file_id:
            raise RuntimeError("Completed Canvas export did not include an attachment")
        output.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(
            f"{self.server}/api/courses/{self.course_id}/files/{file_id}/download",
            timeout=120,
        )
        response.raise_for_status()
        output.write_bytes(response.content)
        if not zipfile.is_zipfile(output):
            raise RuntimeError(f"Downloaded backup is not a readable IMSCC: {output}")
        record = {
            "course_id": self.course_id,
            "export_id": export["id"],
            "attachment_id": file_id,
            "bytes": output.stat().st_size,
            "path": str(output),
        }
        output.with_suffix(output.suffix + ".json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        return record

    def reset(self, confirmation: str) -> dict:
        expected = f"RESET-COURSE-{self.course_id}"
        if confirmation != expected:
            raise ValueError(f"Reset requires --confirm {expected}")
        self.health()
        return self.raw("POST", f"/courses/{self.course_id}/reset_content", {})

    def import_package(
        self, package: Path, poll_seconds: float = 2.0, timeout: float = 600.0
    ) -> dict:
        if not package.is_file() or not zipfile.is_zipfile(package):
            raise ValueError(f"Package is not a readable IMSCC: {package}")
        self.health()
        with package.open("rb") as stream:
            response = requests.post(
                f"{self.server}/api/courses/{self.course_id}/content_migrations",
                files={"file": (package.name, stream, "application/zip")},
                timeout=180,
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Migration upload failed ({response.status_code}): {response.text[:1000]}"
            )
        created = response.json()
        migration_id = (created.get("migration") or {}).get("id")
        if not migration_id:
            raise RuntimeError(f"Migration upload returned no migration ID: {created}")
        return self.monitor_migration(migration_id, package, poll_seconds, timeout)

    def monitor_migration(
        self,
        migration_id: int,
        package: Path | None = None,
        poll_seconds: float = 2.0,
        timeout: float = 600.0,
    ) -> dict:
        """Resume monitoring an already-created Canvas content migration."""
        self.health()
        deadline = time.monotonic() + timeout
        migration = self.raw(
            "GET", f"/courses/{self.course_id}/content_migrations/{migration_id}"
        )
        while migration.get("workflow_state") not in {"completed", "failed"}:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Canvas migration {migration_id} did not finish in time")
            time.sleep(poll_seconds)
            migration = self.raw(
                "GET", f"/courses/{self.course_id}/content_migrations/{migration_id}"
            )
        issues = self.raw(
            "GET",
            f"/courses/{self.course_id}/content_migrations/{migration_id}/migration_issues",
            params={"per_page": 100},
        )
        result = {
            "course_id": self.course_id,
            "package": str(package) if package else None,
            "migration": migration,
            "issues": issues,
        }
        if migration.get("workflow_state") != "completed":
            raise RuntimeError(f"Canvas migration failed: {result}")
        return result

    def cleanup_plan(self) -> dict:
        """Capture exact deletable object identifiers for drift-safe cleanup."""
        self.health()
        objects = {}
        fields = {
            "modules": ("id", "name"),
            "quizzes": ("id", "title"),
            "discussion_topics": ("id", "title"),
            "assignments": ("id", "name"),
            "pages": ("url", "title"),
            "rubrics": ("id", "title"),
            "assignment_groups": ("id", "name"),
        }
        for resource, (identifier, label) in fields.items():
            items = self.raw(
                "GET", f"/courses/{self.course_id}/{resource}", params={"per_page": 100}
            )
            objects[resource] = [
                {"identifier": item[identifier], "label": item.get(label, "")}
                for item in items
                if identifier in item
            ]
        return {"course_id": self.course_id, "objects": objects}

    @staticmethod
    def _plan_identity(plan: dict) -> dict:
        return {
            kind: sorted(str(item["identifier"]) for item in items)
            for kind, items in plan.get("objects", {}).items()
        }

    def cleanup(self, plan: dict, confirmation: str) -> dict:
        expected = f"DELETE-CONTENT-{self.course_id}"
        if confirmation != expected:
            raise ValueError(f"Cleanup requires --confirm {expected}")
        if plan.get("course_id") != self.course_id:
            raise ValueError("Cleanup plan course does not match --course")
        current = self.cleanup_plan()
        planned_ids = self._plan_identity(plan)
        current_ids = self._plan_identity(current)
        unexpected = {
            kind: sorted(set(ids) - set(planned_ids.get(kind, [])))
            for kind, ids in current_ids.items()
            if set(ids) - set(planned_ids.get(kind, []))
        }
        if unexpected:
            raise RuntimeError(
                f"Course gained unexpected content after planning; review a new plan: {unexpected}"
            )
        deleted = []
        # Remove containers and dependent learning objects before groups/rubrics.
        endpoint_names = {
            "modules": "modules",
            "quizzes": "quizzes",
            "discussion_topics": "discussion_topics",
            "assignments": "assignments",
            "pages": "pages",
            "rubrics": "rubrics",
            "assignment_groups": "assignment_groups",
        }
        temporary_front_page = None
        remaining_pages = {
            str(item["identifier"]): item
            for item in current.get("objects", {}).get("pages", [])
        }
        if remaining_pages:
            smoke_pages = [
                item for item in remaining_pages.values()
                if item.get("label", "").startswith("Canvas Automation Smoke Test")
            ]
            if smoke_pages:
                temporary_front_page = smoke_pages[0]["identifier"]
                self.raw(
                    "PUT",
                    f"/courses/{self.course_id}/pages/{temporary_front_page}",
                    {"wiki_page": {"front_page": True, "published": True}},
                )
        for kind in endpoint_names:
            for item in plan["objects"].get(kind, []):
                identifier = item["identifier"]
                if str(identifier) not in set(current_ids.get(kind, [])):
                    deleted.append({"kind": kind, **item, "status": "already_removed"})
                    continue
                if kind == "pages" and identifier == temporary_front_page:
                    deleted.append({"kind": kind, **item, "status": "temporary_front_page"})
                    continue
                try:
                    self.raw(
                        "DELETE",
                        f"/courses/{self.course_id}/{endpoint_names[kind]}/{identifier}",
                    )
                    deleted.append({"kind": kind, **item, "status": "deleted"})
                except RuntimeError as exc:
                    # A dependency deletion can concurrently remove a backing object.
                    if "404" in str(exc):
                        deleted.append({"kind": kind, **item, "status": "already_removed"})
                        continue
                    raise
        return {"course_id": self.course_id, "deleted": deleted}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5055")
    parser.add_argument("--course", required=True, type=int)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory")
    backup = commands.add_parser("backup")
    backup.add_argument("--output", required=True, type=Path)
    reset = commands.add_parser("reset")
    reset.add_argument("--confirm", required=True)
    reset.add_argument("--record", required=True, type=Path)
    plan = commands.add_parser("cleanup-plan")
    plan.add_argument("--output", required=True, type=Path)
    cleanup = commands.add_parser("cleanup")
    cleanup.add_argument("--plan", required=True, type=Path)
    cleanup.add_argument("--confirm", required=True)
    cleanup.add_argument("--record", required=True, type=Path)
    package_import = commands.add_parser("import-package")
    package_import.add_argument("--package", required=True, type=Path)
    package_import.add_argument("--record", required=True, type=Path)
    monitor = commands.add_parser("monitor-migration")
    monitor.add_argument("--migration-id", required=True, type=int)
    monitor.add_argument("--record", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    canvas = GuardedCanvas(args.server, args.course)
    if args.command == "inventory":
        result = canvas.inventory()
    elif args.command == "backup":
        result = canvas.backup(args.output)
    elif args.command == "reset":
        result = canvas.reset(args.confirm)
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(result, indent=2), encoding="utf-8")
    elif args.command == "cleanup-plan":
        result = canvas.cleanup_plan()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    elif args.command == "cleanup":
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        result = canvas.cleanup(plan, args.confirm)
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(result, indent=2), encoding="utf-8")
    elif args.command == "import-package":
        result = canvas.import_package(args.package)
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        result = canvas.monitor_migration(args.migration_id)
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
