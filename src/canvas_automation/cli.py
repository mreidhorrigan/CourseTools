"""
The headless CLI. Every commands/*.command launcher calls this, and so does
a shell script or a local agent, with the same arguments and no menu: `serve`
and `stop` take no input to choose, and the create-*/download-content
subcommands are generate-from-config tools in the handbook's sense (their
subject is named in the config, not picked from a folder), so none of them
use choose_input. See 03-command-and-config.md.

No interactive prompts live here. The one interactive step in this whole
tool (asking for the Canvas token) lives entirely in
commands/start-server.command; this module only ever reads it back out of
an environment variable that command already set.

Every subcommand accepts --engine, which every commands/*.command
invocation passes explicitly (see research/02-engine-root-resolution.md
for why this exists: relying on the ENGINE environment variable alone
turned out not to be reliable enough).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import tempfile
import shutil
from pathlib import Path

import requests

from .course_packet import export_assignments_pdf, export_gradebook
from .jsonc import ConfigError, load_and_validate, load_jsonc
from .testmaker import TestmakerFormatError, Pool, for_version, parse_testmaker, question_payload, versions_in
from .imscc import build_imscc
from .new_quizzes import new_quiz_item_payload
from .payloads import (
    build_assignment_payload,
    build_discussion_payload,
    build_page_payload,
    build_rubric_payload,
)
from .pdf_tools import merge_pdfs
from .test_forms import build_forms
from .util import (
    fail,
    find_engine_root,
    fresh_out_dir,
    parse_course_id,
    resolve_out_base,
    resolve_path,
    slugify,
    write_provenance,
)


def _load_config(engine: Path, config_arg: str) -> tuple[dict, Path]:
    """
    Load and schema-validate a config. This is the deep check (recurses
    into nested objects/arrays); commands/_jsonc.py already did a shallow,
    top-level-only pass before launch() even ran this CLI, and reported a
    bad value as __CONFIG_ERROR__ there. A problem this deep check catches
    instead surfaces here, as a plain message and a non-zero exit, which
    launch() reports through its normal failed-command path.
    """
    config_path = resolve_path(engine, config_arg)
    try:
        return load_and_validate(config_path), config_path
    except ConfigError as exc:
        fail(f"Invalid config {config_path.name}: {exc}")
    except FileNotFoundError:
        fail(f"Config not found: {config_path}")
    except Exception as exc:  # a jsonc syntax error, etc.
        fail(f"Could not read {config_path.name}: {exc}")


def _server_base_url(engine: Path) -> str:
    config_path = engine / "commands" / "start-server.config.jsonc"
    settings = load_jsonc(config_path) if config_path.exists() else {}
    host = settings.get("host", "127.0.0.1")
    port = settings.get("port", 5055)
    return f"http://{host}:{port}"


def _require_server(base_url: str) -> dict:
    try:
        resp = requests.get(f"{base_url}/health", timeout=3)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException:
        fail(
            f"Could not reach the local Canvas server at {base_url}.\n"
            "Start it first with commands/start-server.command, then try this again."
        )


def _die_on_error(resp: requests.Response, action_description: str) -> None:
    if resp.status_code >= 400:
        print(f"Canvas rejected the request to {action_description} (HTTP {resp.status_code}):")
        try:
            print(json.dumps(resp.json(), indent=2))
        except ValueError:
            print(resp.text)
        sys.exit(1)


def cmd_serve(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    config_path = engine / "commands" / "start-server.config.jsonc"
    settings = load_and_validate(config_path) if config_path.exists() else {}
    host = settings.get("host", "127.0.0.1")
    port = settings.get("port", 5055)
    sandbox_course_url = settings.get("sandbox_course_url", "")
    try:
        allowed_course_id = parse_course_id(sandbox_course_url)
    except ValueError as exc:
        fail(f"Invalid sandbox_course_url in {config_path.name}: {exc}")
    from . import server
    server.run(host, port, allowed_course_id, sandbox_course_url)
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    base_url = _server_base_url(engine)
    try:
        requests.post(f"{base_url}/shutdown", timeout=3)
        print(f"Sent the stop signal to {base_url}.")
    except requests.exceptions.RequestException:
        print(f"Could not reach a server at {base_url}. It may already be stopped.")
    return 0


def cmd_create_assignment(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    config, config_path = _load_config(engine, args.config)
    course_id = args.course_id or config.get("course_id")
    if not course_id:
        fail("No course_id in the config, and none passed via --course-id.")

    payload = build_assignment_payload(config, engine)
    base_url = _server_base_url(engine)
    health = _require_server(base_url)

    resp = requests.post(f"{base_url}/api/courses/{course_id}/assignments", json=payload, timeout=30)
    _die_on_error(resp, "create the assignment")
    created = resp.json()

    out_base = resolve_out_base(engine, config, "create-assignment")
    out_dir = fresh_out_dir(out_base, slug=created.get("name"))
    (out_dir / "assignment.json").write_text(json.dumps(created, indent=2), encoding="utf-8")
    write_provenance(
        out_dir, command="create-assignment", config_path=config_path,
        canvas_base_url=health.get("canvas_base_url"), course_id=course_id,
        request_payload=payload,
        result={"type": "assignment", "id": created.get("id"), "url": created.get("html_url")},
    )

    print(f"Created assignment #{created.get('id')}: {created.get('name')}")
    print(f"  {created.get('html_url', '(no URL returned by Canvas)')}")
    print(f"  Output: {out_dir}")
    return 0


def cmd_create_rubric(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    config, config_path = _load_config(engine, args.config)
    course_id = args.course_id or config.get("course_id")
    if not course_id:
        fail("No course_id in the config, and none passed via --course-id.")

    payload = build_rubric_payload(config, engine)
    base_url = _server_base_url(engine)
    health = _require_server(base_url)

    resp = requests.post(f"{base_url}/api/courses/{course_id}/rubrics", json=payload, timeout=30)
    _die_on_error(resp, "create the rubric")
    created = resp.json()
    rubric = created.get("rubric", created)  # Canvas nests the real rubric one level down

    out_base = resolve_out_base(engine, config, "create-rubric")
    out_dir = fresh_out_dir(out_base, slug=rubric.get("title"))
    (out_dir / "rubric.json").write_text(json.dumps(created, indent=2), encoding="utf-8")
    canvas_url = (health.get("canvas_base_url") or "").rstrip("/")
    link = f"{canvas_url}/courses/{course_id}/rubrics/{rubric.get('id')}" if canvas_url else None
    write_provenance(
        out_dir, command="create-rubric", config_path=config_path,
        canvas_base_url=health.get("canvas_base_url"), course_id=course_id,
        request_payload=payload,
        result={"type": "rubric", "id": rubric.get("id"), "url": link},
    )

    print(f"Created rubric #{rubric.get('id')}: {rubric.get('title')}")
    print(f"  {link or '(no canvas_base_url from server)'}")
    print(f"  Output: {out_dir}")
    return 0


def cmd_create_discussion(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    config, config_path = _load_config(engine, args.config)
    course_id = args.course_id or config.get("course_id")
    if not course_id:
        fail("No course_id in the config, and none passed via --course-id.")

    payload = build_discussion_payload(config, engine)
    base_url = _server_base_url(engine)
    health = _require_server(base_url)

    resp = requests.post(f"{base_url}/api/courses/{course_id}/discussion_topics", json=payload, timeout=30)
    _die_on_error(resp, "create the discussion topic")
    created = resp.json()

    out_base = resolve_out_base(engine, config, "create-discussion")
    out_dir = fresh_out_dir(out_base, slug=created.get("title"))
    (out_dir / "discussion_topic.json").write_text(json.dumps(created, indent=2), encoding="utf-8")
    write_provenance(
        out_dir, command="create-discussion", config_path=config_path,
        canvas_base_url=health.get("canvas_base_url"), course_id=course_id,
        request_payload=payload,
        result={"type": "discussion_topic", "id": created.get("id"), "url": created.get("html_url")},
    )

    print(f"Created discussion topic #{created.get('id')}: {created.get('title')}")
    print(f"  {created.get('html_url', '(no URL returned by Canvas)')}")
    print(f"  Output: {out_dir}")
    return 0


def cmd_create_page(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    config, config_path = _load_config(engine, args.config)
    course_id = args.course_id or config.get("course_id")
    if not course_id:
        fail("No course_id in the config, and none passed via --course-id.")

    payload = build_page_payload(config, engine)
    base_url = _server_base_url(engine)
    health = _require_server(base_url)

    resp = requests.post(f"{base_url}/api/courses/{course_id}/pages", json=payload, timeout=30)
    _die_on_error(resp, "create the page")
    created = resp.json()

    out_base = resolve_out_base(engine, config, "create-page")
    out_dir = fresh_out_dir(out_base, slug=created.get("title"))
    (out_dir / "page.json").write_text(json.dumps(created, indent=2), encoding="utf-8")
    canvas_url = (health.get("canvas_base_url") or "").rstrip("/")
    link = f"{canvas_url}/courses/{course_id}/pages/{created.get('url')}" if canvas_url else None
    write_provenance(
        out_dir, command="create-page", config_path=config_path,
        canvas_base_url=health.get("canvas_base_url"), course_id=course_id,
        request_payload=payload,
        result={"type": "page", "id": created.get("page_id"), "url": link},
    )

    print(f"Created page: {created.get('title')}")
    print(f"  {link or '(no canvas_base_url from server)'}")
    print(f"  Output: {out_dir}")
    return 0


def _raw_request(base_url: str, method: str, path: str, payload=None, timeout=30):
    body = {"method": method, "path": path}
    if payload is not None:
        body["payload"] = payload
    response = requests.post(f"{base_url}/api/raw", json=body, timeout=timeout)
    _die_on_error(response, f"{method.lower()} {path}")
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def cmd_create_quiz(args: argparse.Namespace) -> int:
    """Build a Classic Canvas Quiz from the tagged format accepted by Testmaker."""
    engine = find_engine_root(args.engine)
    config, config_path = _load_config(engine, args.config)
    course_id = args.course_id or config.get("course_id")
    if not course_id:
        fail("No course_id in the config, and none passed via --course-id.")
    source_path = resolve_path(engine, args.input or config["source_file"])
    if not source_path.is_file():
        fail(f"Questions file does not exist: {source_path}")
    try:
        parsed = parse_testmaker(source_path)
    except TestmakerFormatError as exc:
        fail(f"Could not convert {source_path.name}: {exc}")

    explicit_versions = versions_in(parsed)
    fixed_version = str(config.get("fixed_version", "")).strip().upper()
    if explicit_versions and not fixed_version:
        fail("This source uses [Only Version X.]. Set fixed_version to A, B, C, D, or E and run once per desired Canvas quiz.")
    if fixed_version:
        if fixed_version not in "ABCDE":
            fail("fixed_version must be A, B, C, D, or E.")
        parsed = for_version(parsed, fixed_version)

    quiz_cfg = dict(config["quiz"])
    if fixed_version and config.get("append_version_to_title", True):
        quiz_cfg["title"] = f"{quiz_cfg['title']} - Version {fixed_version}"
    intended_published = bool(quiz_cfg.get("published", False))
    quiz_cfg["published"] = False  # never expose an incompletely populated quiz
    mcq_points = config.get("mcq_points", 1)
    written_points = config.get("written_points", 1)
    group_points = config.get("pool_question_points", written_points)

    # The plan is deterministic and useful on its own in dry-run mode.
    plan = {"quiz": {"quiz": quiz_cfg}, "fixed_version": fixed_version or None,
            "source_versions": explicit_versions, "items": [], "warnings": parsed.warnings}
    question_number = 0
    pool_number = 0
    for item in parsed.items:
        if isinstance(item, Pool):
            pool_number += 1
            pool_payloads = []
            for offset, pool_q in enumerate(item.questions, start=1):
                qp = question_payload(pool_q, name=f"Pool {pool_number} question {offset}",
                                      mcq_points=group_points, written_points=group_points)
                qp["source_answer_key"] = pool_q.answer
                pool_payloads.append(qp)
            plan["items"].append({
                "kind": "group", "name": f"Testmaker pool {pool_number}", "pick_count": item.take,
                "question_points": group_points, "questions": pool_payloads,
                "scramble_all": item.scramble_all,
            })
        else:
            question_number += 1
            qp = question_payload(
                item, name=f"Question {question_number}", mcq_points=mcq_points,
                written_points=written_points,
            )
            qp["source_answer_key"] = item.answer
            plan["items"].append({"kind": "question", **qp})

    out_base = resolve_out_base(engine, config, "create-quiz")
    out_dir = fresh_out_dir(out_base, slug=quiz_cfg.get("title"))
    (out_dir / "conversion-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    if config.get("dry_run", False):
        write_provenance(
            out_dir, command="create-quiz", config_path=config_path, course_id=course_id,
            request_payload=plan, result={"type": "dry_run", "source_file": str(source_path)},
        )
        print(f"Validated {len(parsed.questions)} question(s); no Canvas changes were made (dry_run=true).")
        print(f"  Output: {out_dir}")
        return 0

    base_url = _server_base_url(engine)
    health = _require_server(base_url)
    image_urls = {}
    for filename, content in parsed.assets.items():
        uploaded = requests.post(
            f"{base_url}/api/courses/{course_id}/files",
            files={"file": (filename, content)},
            timeout=60,
        )
        _die_on_error(uploaded, f"upload quiz image {filename}")
        info = uploaded.json()
        image_urls[filename] = info.get("url") or info.get("preview_url")

    if config.get("quiz_engine", "classic") == "new":
        if any(isinstance(x, Pool) for x in parsed.items):
            fail("New Quizzes item API cannot create Testmaker take-N pools. Use Classic Quizzes for this source.")
        total=sum((mcq_points if q.distractors else written_points) for q in parsed.items if not q.text_only)
        nq={"title":quiz_cfg["title"],"points_possible":max(total,0.01),"grading_type":"points",
            "instructions":quiz_cfg.get("description","")}
        for key in ("assignment_group_id","due_at","lock_at","unlock_at"):
            if key in quiz_cfg:nq[key]=quiz_cfg[key]
        created=_raw_request(base_url,"POST",f"/api/quiz/v1/courses/{course_id}/quizzes",{"quiz":nq})
        assignment_id=created.get("assignment_id") or created.get("id"); created_questions=[]
        try:
            position=0
            for q in parsed.items:
                if q.text_only: continue
                position+=1; points=mcq_points if q.distractors else written_points
                created_questions.append(_raw_request(base_url,"POST",f"/api/quiz/v1/courses/{course_id}/quizzes/{assignment_id}/items",
                    new_quiz_item_payload(q,name=f"Question {position}",points=points,position=position,image_urls=image_urls)))
            if intended_published:
                _raw_request(base_url,"PUT",f"/courses/{course_id}/assignments/{assignment_id}",{"assignment":{"published":True}})
        except BaseException:
            if config.get("rollback_on_error",True):
                try:_raw_request(base_url,"DELETE",f"/api/quiz/v1/courses/{course_id}/quizzes/{assignment_id}")
                except Exception:pass
            raise
        result_record={"quiz":created,"items":created_questions,"engine":"new","source_file":str(source_path)}
        (out_dir/"quiz.json").write_text(json.dumps(result_record,indent=2),encoding="utf-8")
        write_provenance(out_dir,command="create-quiz",config_path=config_path,canvas_base_url=health.get("canvas_base_url"),course_id=course_id,
                         request_payload=plan,result={"type":"new_quiz","id":assignment_id,"item_count":len(created_questions)})
        print(f"Created New Quiz assignment #{assignment_id}: {quiz_cfg['title']}"); print(f"  Output: {out_dir}"); return 0
    created = _raw_request(base_url, "POST", f"/courses/{course_id}/quizzes", {"quiz": quiz_cfg})
    quiz_id = created.get("id")
    created_questions = []
    created_groups = []
    try:
        question_number = 0
        pool_number = 0
        for item in parsed.items:
            if isinstance(item, Pool):
                pool_number += 1
                group_result = _raw_request(base_url, "POST", f"/courses/{course_id}/quizzes/{quiz_id}/groups", {
                    "quiz_groups": [{"name": f"Testmaker pool {pool_number}", "pick_count": item.take,
                                     "question_points": group_points}]
                })
                group = group_result[0] if isinstance(group_result, list) else group_result
                group_id = group.get("id")
                created_groups.append(group)
                for pool_q in item.questions:
                    question_number += 1
                    result = _raw_request(base_url, "POST", f"/courses/{course_id}/quizzes/{quiz_id}/questions",
                                          question_payload(pool_q, name=f"Question {question_number}",
                                                           mcq_points=group_points, written_points=group_points,
                                                           group_id=group_id,image_urls=image_urls))
                    created_questions.append(result)
            else:
                question_number += 1
                result = _raw_request(base_url, "POST", f"/courses/{course_id}/quizzes/{quiz_id}/questions",
                                      question_payload(item, name=f"Question {question_number}",
                                                       mcq_points=mcq_points, written_points=written_points,image_urls=image_urls))
                created_questions.append(result)
        if intended_published:
            created = _raw_request(base_url, "PUT", f"/courses/{course_id}/quizzes/{quiz_id}",
                                   {"quiz": {"published": True, "notify_of_update": False}})
    except BaseException:
        if config.get("rollback_on_error", True) and quiz_id:
            try:
                _raw_request(base_url, "DELETE", f"/courses/{course_id}/quizzes/{quiz_id}")
                print(f"Rolled back incomplete quiz #{quiz_id}.", file=sys.stderr)
            except Exception as cleanup_exc:
                print(f"Could not roll back incomplete quiz #{quiz_id}: {cleanup_exc}", file=sys.stderr)
        raise

    result_record = {"quiz": created, "groups": created_groups, "questions": created_questions,
                     "warnings": parsed.warnings, "source_file": str(source_path)}
    (out_dir / "quiz.json").write_text(json.dumps(result_record, indent=2), encoding="utf-8")
    write_provenance(
        out_dir, command="create-quiz", config_path=config_path,
        canvas_base_url=health.get("canvas_base_url"), course_id=course_id,
        request_payload=plan,
        result={"type": "quiz", "id": quiz_id, "url": created.get("html_url"),
                "question_count": len(created_questions), "group_count": len(created_groups)},
    )
    print(f"Created Classic Quiz #{quiz_id}: {created.get('title')}")
    print(f"  {created.get('html_url', '(no URL returned by Canvas)')}")
    print(f"  {len(created_questions)} question(s), {len(created_groups)} random pool(s)")
    for warning in parsed.warnings:
        print(f"  Warning: {warning}")
    print(f"  Output: {out_dir}")
    return 0


# Canvas's "list pages" endpoint omits each page's body unless asked for it.
_DOWNLOAD_EXTRA_PARAMS = {"pages": {"include[]": "body"}}
# Almost every Canvas resource is keyed by "id"; pages are the one exception.
_DOWNLOAD_ID_FIELDS = {"pages": "page_id"}


def cmd_download_content(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    config, config_path = _load_config(engine, args.config)
    course_id = args.course_id or config.get("course_id")
    if not course_id:
        fail("No course_id in the config, and none passed via --course-id.")

    resources = config.get("resources", [])
    if not resources:
        fail(f"No resources listed in the config. Uncomment at least one in {config_path}.")

    base_url = _server_base_url(engine)
    health = _require_server(base_url)

    out_base = resolve_out_base(engine, config, "download-content")
    out_dir = fresh_out_dir(out_base, slug=f"course-{course_id}")
    counts = {}
    for resource in resources:
        print(f"Fetching {resource} ...")
        body = {
            "method": "GET",
            "path": f"/courses/{course_id}/{resource}",
            "params": {"per_page": 100, **_DOWNLOAD_EXTRA_PARAMS.get(resource, {})},
        }
        resp = requests.post(f"{base_url}/api/raw", json=body, timeout=60)
        if resp.status_code >= 400:
            print(f"  Skipped ({resp.status_code}): {resp.text[:300]}")
            counts[resource] = 0
            continue

        items = resp.json()
        if not isinstance(items, list):
            items = [items]

        id_field = _DOWNLOAD_ID_FIELDS.get(resource, "id")
        resource_dir = out_dir / resource
        saved = 0
        for item in items:
            if id_field not in item:
                continue
            resource_dir.mkdir(parents=True, exist_ok=True)
            (resource_dir / f"{item[id_field]}.json").write_text(json.dumps(item, indent=2), encoding="utf-8")
            saved += 1
        counts[resource] = saved
        print(f"  Saved {saved} item(s)")

    write_provenance(
        out_dir, command="download-content", config_path=config_path,
        canvas_base_url=health.get("canvas_base_url"), course_id=course_id,
        request_payload={"resources": resources},
        result={"type": "download", "counts": counts},
    )
    print(f"Output: {out_dir}")
    return 0


def cmd_export_course_packet(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    config, config_path = _load_config(engine, args.config)

    try:
        course_id = parse_course_id(args.course_url)
    except ValueError as exc:
        fail(str(exc))

    base_url = _server_base_url(engine)
    health = _require_server(base_url)

    out_base = resolve_out_base(engine, config, "export-course-packet")
    out_dir = fresh_out_dir(out_base, slug=f"course-{course_id}")
    summary = {}

    assignments_cfg = config.get("assignments_pdf", {})
    if assignments_cfg.get("enabled", True):
        print("Fetching published assignments and building the combined PDF...")
        summary["assignments_pdf"] = export_assignments_pdf(base_url, course_id, out_dir, assignments_cfg)

    gradebook_cfg = config.get("gradebook", {})
    if gradebook_cfg.get("enabled", True):
        print("Fetching enrollments and submissions to build the gradebook...")
        summary["gradebook"] = export_gradebook(base_url, course_id, out_dir, gradebook_cfg)

    write_provenance(
        out_dir, command="export-course-packet", config_path=config_path,
        canvas_base_url=health.get("canvas_base_url"), course_id=course_id,
        request_payload={"course_url": args.course_url, "assignments_pdf": assignments_cfg, "gradebook": gradebook_cfg},
        result=summary,
    )

    print(f"Course {course_id} packet exported.")
    if "assignments_pdf" in summary:
        ap = summary["assignments_pdf"]
        print(f"  {ap['assignment_count']} published assignment(s), {ap['page_count']} page(s) -> assignments_combined.pdf")
    if "gradebook" in summary:
        gb = summary["gradebook"]
        print(f"  {gb['student_count']} student(s) x {gb['assignment_columns']} assignment column(s) -> gradebook.csv"
              + (" and gradebook.xlsx" if gb.get("xlsx") else ""))
    print(f"  Output: {out_dir}")
    return 0


def cmd_merge_pdfs(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine)
    config, config_path = _load_config(engine, args.config)
    output_name = config.get("output_name", "merged.pdf")
    if not output_name.lower().endswith(".pdf"):
        output_name += ".pdf"
    sort_alpha = config.get("sort_alphabetically", False)

    paths = [Path(p) for p in args.pdfs]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        fail("These selected files could not be read:\n" + "\n".join(str(p) for p in missing))

    if sort_alpha:
        paths = sorted(paths, key=lambda p: p.name.lower())

    out_base = resolve_out_base(engine, config, "merge-pdfs")
    out_dir = fresh_out_dir(out_base, slug=Path(output_name).stem)
    out_path = out_dir / output_name
    page_count = merge_pdfs(paths, out_path)

    write_provenance(
        out_dir, command="merge-pdfs", config_path=config_path,
        request_payload={"input_files": [str(p) for p in paths], "sort_alphabetically": sort_alpha},
        result={"type": "merged_pdf", "path": str(out_path), "source_count": len(paths), "page_count": page_count},
    )

    print(f"Merged {len(paths)} PDF(s) ({page_count} page(s) total) into {out_path.name}")
    if len(paths) == 1:
        print("  (Only one file was selected, so this is effectively a copy of it.)")
    print(f"  Output: {out_dir}")
    return 0


def cmd_build_imscc(args: argparse.Namespace) -> int:
    engine=find_engine_root(args.engine); config,config_path=_load_config(engine,args.config)
    spec_path=resolve_path(engine,args.spec or config["spec_file"])
    try: spec=load_jsonc(spec_path)
    except Exception as exc: fail(f"Could not read course spec {spec_path}: {exc}")
    out_dir=fresh_out_dir(resolve_out_base(engine,config,"build-imscc"),slug=spec["course"]["title"])
    name=config.get("output_name") or f"{slugify(spec['course']['title'])}.imscc"
    if not name.endswith(".imscc"): name += ".imscc"
    with tempfile.TemporaryDirectory(prefix="canvas_imscc_") as td:
        work=Path(td); summary=build_imscc(spec,engine,work,out_dir/name)
        shutil.copy2(work/"build-summary.json",out_dir/"build-summary.json")
    write_provenance(out_dir,command="build-imscc",config_path=config_path,
                     request_payload={"spec_file":str(spec_path)},result={"type":"imscc","path":str(out_dir/name),**summary})
    print(f"Built importable Canvas package: {out_dir/name}"); print(f"  {summary}"); return 0


def cmd_build_test_forms(args: argparse.Namespace) -> int:
    engine = find_engine_root(args.engine); config, config_path = _load_config(engine, args.config)
    source = resolve_path(engine, args.input or config["source_file"])
    title = config["title"]; versions = config.get("versions", 3); seed = str(config.get("seed", "1"))
    out_dir = fresh_out_dir(resolve_out_base(engine, config, "build-test-forms"), slug=title)
    manifest = build_forms(source, out_dir, title, versions, seed)
    write_provenance(out_dir, command="build-test-forms", config_path=config_path,
                     request_payload={"source_file": str(source), "title": title, "versions": versions, "seed": seed},
                     result={"type": "pdf-test-forms", "manifest": manifest})
    print(f"Built {versions} test form(s) and answer key(s): {out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    # Shared by every subcommand via parents=[...], so --engine can appear
    # after the subcommand name (canvas-automation create-page --engine ...)
    # rather than needing to precede it.
    engine_parent = argparse.ArgumentParser(add_help=False)
    engine_parent.add_argument(
        "--engine", default=None,
        help="Project root. commands/*.command always passes this explicitly; "
             "only worth setting by hand for a direct, headless invocation "
             "from somewhere find_engine_root()'s fallbacks would not reach.",
    )

    parser = argparse.ArgumentParser(prog="canvas-automation", description=__doc__)
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser(
        "serve", parents=[engine_parent],
        help="Start the local server (reads CANVAS_BASE_URL/CANVAS_API_TOKEN from the environment)",
    ).set_defaults(func=cmd_serve)
    sub.add_parser(
        "stop", parents=[engine_parent], help="Ask a running server to shut down",
    ).set_defaults(func=cmd_stop)

    for name, func, help_text in [
        ("create-assignment", cmd_create_assignment, "Create a Canvas assignment"),
        ("create-rubric", cmd_create_rubric, "Create a Canvas rubric"),
        ("create-discussion", cmd_create_discussion, "Create a Canvas discussion topic"),
        ("create-page", cmd_create_page, "Create a Canvas page"),
        ("download-content", cmd_download_content, "Download existing Canvas content into out/"),
    ]:
        p = sub.add_parser(name, parents=[engine_parent], help=help_text)
        p.add_argument("--config", required=True, help="Path to the *.config.jsonc, relative to the project root")
        p.add_argument("--course-id", type=int, default=None, help="Override course_id from the config")
        p.set_defaults(func=func)

    p_quiz = sub.add_parser(
        "create-quiz", parents=[engine_parent],
        help="Convert a Testmaker-tagged DOCX/Markdown/text file into a Classic Canvas Quiz",
    )
    p_quiz.add_argument("--config", required=True, help="Path to the *.config.jsonc, relative to the project root")
    p_quiz.add_argument("--course-id", type=int, default=None, help="Override course_id from the config")
    p_quiz.add_argument("--input", default=None, help="Override source_file from the config")
    p_quiz.set_defaults(func=cmd_create_quiz)

    p_packet = sub.add_parser(
        "export-course-packet", parents=[engine_parent],
        help="Download published assignments as one combined PDF, plus a synthesized gradebook CSV/XLSX",
    )
    p_packet.add_argument("--config", required=True, help="Path to the *.config.jsonc, relative to the project root")
    p_packet.add_argument("--course-url", required=True, help="A full Canvas course URL, or a bare course id")
    p_packet.set_defaults(func=cmd_export_course_packet)

    p_merge = sub.add_parser(
        "merge-pdfs", parents=[engine_parent], help="Concatenate PDF files into one, in the order given",
    )
    p_merge.add_argument("--config", default="commands/merge-pdfs.config.jsonc")
    p_merge.add_argument("pdfs", nargs="+", help="PDF files to merge, in order")
    p_merge.set_defaults(func=cmd_merge_pdfs)

    p_imscc=sub.add_parser("build-imscc",parents=[engine_parent],help="Build an offline Canvas Common Cartridge for Course Import")
    p_imscc.add_argument("--config",required=True); p_imscc.add_argument("--spec",default=None,help="Override spec_file")
    p_imscc.set_defaults(func=cmd_build_imscc)

    p_forms=sub.add_parser("build-test-forms",parents=[engine_parent],help="Build deterministic PDF forms and keys from Testmaker source")
    p_forms.add_argument("--config",required=True); p_forms.add_argument("--input",default=None,help="Override source_file")
    p_forms.set_defaults(func=cmd_build_test_forms)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args) or 0
    except SystemExit:
        raise
    except Exception as exc:  # last-resort safety net: never dump a raw traceback on a user
        if os.environ.get("CANVAS_AUTOMATION_DEBUG"):
            traceback.print_exc()
        else:
            print(f"Unexpected error: {exc}", file=sys.stderr)
            print("Set CANVAS_AUTOMATION_DEBUG=1 for a full traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
