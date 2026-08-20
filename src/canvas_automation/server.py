"""
Local HTTP server that holds the Canvas API token in memory for the
lifetime of this process and proxies requests from the CLI (and so, in
turn, from the commands/*.command launchers) to the real Canvas API.

Two layers, kept deliberately separate:

- `create_app(base_url, token)` is a pure factory: no environment reads, no
  network calls, no process exit. Safe to import and call from a test with
  any base_url/token.
- `run(host, port)` is the impure entry point `canvas-automation serve`
  calls: it reads CANVAS_BASE_URL/CANVAS_API_TOKEN from the environment,
  confirms them against Canvas, and serves until stopped. No interactive
  prompt lives here or anywhere in this package; that belongs entirely to
  commands/start-server.command, per the engine/interface split.

The token is read once, kept only in the CanvasClient this module builds,
and is never written to disk, logged, or returned in any response body.
"""
import os
import re
import sys
import threading
import time
from urllib.parse import urlparse

from flask import Flask, g, request, jsonify

from .canvas_client import CanvasClient, build_rubric_criteria_hash


_COURSE_PATH_RE = re.compile(r"(?:^|/)courses/(\d+)(?:/|$)")


def _course_id_from_path(path):
    match = _COURSE_PATH_RE.search(path or "")
    return int(match.group(1)) if match else None


def canvas_hosts_match(base_url, sandbox_course_url):
    """Require the API endpoint and guarded course URL to be one Canvas host."""
    normalized_base = base_url if "://" in base_url else "https://" + base_url
    canvas_host = (urlparse(normalized_base).hostname or "").lower()
    sandbox_host = (urlparse(sandbox_course_url).hostname or "").lower()
    return bool(canvas_host and canvas_host == sandbox_host)


def create_app(base_url, token, allowed_course_id=None, access_log=True):
    """Build a configured Flask app around one CanvasClient."""
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    base_url = base_url.rstrip("/")

    client = CanvasClient(base_url, token)
    app = Flask(__name__)
    app.canvas_client = client  # exposed so run() can do the startup whoami() check
    app.allowed_course_id = int(allowed_course_id) if allowed_course_id else None

    if access_log:
        @app.before_request
        def start_access_timer():
            g.canvas_access_started = time.perf_counter()

        @app.after_request
        def print_access_result(response):
            elapsed_ms = (time.perf_counter() - g.canvas_access_started) * 1000
            # request.path deliberately omits the query string. Never include
            # headers, bodies, or the Canvas client's authorization data here.
            print(
                f"HTTP {request.method} {request.path} -> "
                f"{response.status_code} ({elapsed_ms:.1f} ms)",
                flush=True,
            )
            return response

    def reject_wrong_course(course_id):
        if app.allowed_course_id is not None and course_id != app.allowed_course_id:
            return jsonify({
                "error": "Course blocked by the sandbox safety guard.",
                "requested_course_id": course_id,
                "allowed_course_id": app.allowed_course_id,
            }), 403
        return None

    def reject_published_course(course_id):
        """Refuse every Canvas write when the guarded course is published."""
        response = client.get(f"/courses/{course_id}")
        response.raise_for_status()
        course = response.json()
        if course.get("workflow_state") != "unpublished":
            return jsonify({
                "error": "Canvas writes are blocked because the guarded course is published.",
                "course_id": course_id,
                "workflow_state": course.get("workflow_state"),
            }), 409
        return None

    def reject_unsafe_write(course_id):
        return reject_wrong_course(course_id) or reject_published_course(course_id)

    def forward_response(resp):
        content_type = resp.headers.get("Content-Type", "application/json")
        return (resp.content, resp.status_code, {"Content-Type": content_type})

    @app.errorhandler(Exception)
    def handle_any_error(err):
        # Always return JSON, never a stack-trace HTML page. Callers assume
        # every response body is JSON they can parse.
        return jsonify({"error": str(err)}), 500

    @app.route("/health")
    def health():
        return jsonify({
            "status": "ok",
            "canvas_base_url": base_url,
            "allowed_course_id": app.allowed_course_id,
            "pid": os.getpid(),
        })

    @app.route("/api/courses/<int:course_id>/assignments", methods=["POST"])
    def create_assignment(course_id):
        blocked = reject_unsafe_write(course_id)
        if blocked:
            return blocked
        body = request.get_json(force=True) or {}
        payload = {"assignment": body.get("assignment", {})}
        resp = client.post(f"/courses/{course_id}/assignments", json_body=payload)
        return forward_response(resp)

    @app.route("/api/courses/<int:course_id>/rubrics", methods=["POST"])
    def create_rubric(course_id):
        blocked = reject_unsafe_write(course_id)
        if blocked:
            return blocked
        body = request.get_json(force=True) or {}
        rubric = dict(body.get("rubric", {}))

        criteria = rubric.get("criteria")
        if isinstance(criteria, list):
            rubric["criteria"] = build_rubric_criteria_hash(criteria)

        payload = {"rubric": rubric}
        association = body.get("rubric_association")
        if association:
            payload["rubric_association"] = association

        resp = client.post(f"/courses/{course_id}/rubrics", json_body=payload)
        return forward_response(resp)

    @app.route("/api/courses/<int:course_id>/discussion_topics", methods=["POST"])
    def create_discussion_topic(course_id):
        blocked = reject_unsafe_write(course_id)
        if blocked:
            return blocked
        # Discussion Topics uses flat top-level params, unlike assignments,
        # rubrics, and pages, which all nest under a wrapper key.
        body = request.get_json(force=True) or {}
        resp = client.post(f"/courses/{course_id}/discussion_topics", json_body=body)
        return forward_response(resp)

    @app.route("/api/courses/<int:course_id>/pages", methods=["POST"])
    def create_page(course_id):
        blocked = reject_unsafe_write(course_id)
        if blocked:
            return blocked
        body = request.get_json(force=True) or {}
        # Canvas still calls pages "wiki_page" internally; callers just say "page".
        payload = {"wiki_page": body.get("page", {})}
        resp = client.post(f"/courses/{course_id}/pages", json_body=payload)
        return forward_response(resp)

    @app.route("/api/courses/<int:course_id>/files", methods=["POST"])
    def upload_course_file(course_id):
        blocked = reject_unsafe_write(course_id)
        if blocked:
            return blocked
        uploaded = request.files.get("file")
        if not uploaded:
            return jsonify({"error": "file is required"}), 400
        folder = request.form.get("parent_folder_path", "quiz-images")
        if not folder or folder.startswith("/") or ".." in folder.split("/"):
            return jsonify({"error": "parent_folder_path must be a safe course-relative folder"}), 400
        resp = client.upload_course_file(course_id, uploaded.filename, uploaded.read(), folder)
        return forward_response(resp)

    @app.route("/api/courses/<int:course_id>/files/<int:file_id>/download", methods=["GET"])
    def download_course_file(course_id, file_id):
        """Download a known Canvas file through the in-memory credentials."""
        blocked = reject_unsafe_write(course_id)
        if blocked:
            return blocked
        metadata = client.get(f"/files/{file_id}")
        metadata.raise_for_status()
        download_url = metadata.json().get("url")
        if not download_url:
            return jsonify({"error": "Canvas file has no download URL"}), 502
        return forward_response(client.get(download_url))

    @app.route("/api/courses/<int:course_id>/content_migrations", methods=["POST"])
    def upload_content_migration(course_id):
        blocked = reject_wrong_course(course_id)
        if blocked:
            return blocked
        uploaded = request.files.get("file")
        if not uploaded:
            return jsonify({"error": "IMSCC file is required"}), 400
        result = client.upload_content_migration(
            course_id, uploaded.filename, uploaded.read()
        )
        return jsonify(result)

    @app.route("/api/raw", methods=["POST"])
    def raw_passthrough():
        """
        Generic escape hatch for anything without a dedicated route yet:
            {"method": "GET"|"POST"|"PUT"|"PATCH"|"DELETE",
             "path": "/courses/1/...",
             "payload": {...},
             "params": {...}}
        GET requests are paginated automatically. download-content uses
        this for bulk downloads.
        """
        body = request.get_json(force=True) or {}
        method = str(body.get("method", "GET")).upper()
        path = body.get("path")
        if not path:
            return jsonify({"error": "\"path\" is required"}), 400
        path_course_id = _course_id_from_path(path)
        if path_course_id is not None:
            blocked = reject_wrong_course(path_course_id)
            if blocked:
                return blocked
            if method != "GET":
                blocked = reject_published_course(path_course_id)
                if blocked:
                    return blocked
        elif method != "GET" and app.allowed_course_id is not None:
            return jsonify({
                "error": "Guarded raw mutations must contain the allowed /courses/:id path.",
                "allowed_course_id": app.allowed_course_id,
            }), 403

        if method == "GET":
            data = client.get_all_pages(path, params=body.get("params"))
            return jsonify(data)
        elif method == "POST":
            resp = client.post(path, json_body=body.get("payload"))
        elif method == "PUT":
            resp = client.put(path, json_body=body.get("payload"))
        elif method == "PATCH":
            resp = client.patch(path, json_body=body.get("payload"))
        elif method == "DELETE":
            resp = client.delete(path)
        else:
            return jsonify({"error": f"Unsupported method: {method}"}), 400

        return forward_response(resp)

    @app.route("/shutdown", methods=["POST"])
    def shutdown():
        def stop_soon():
            time.sleep(0.25)
            app.shutdown_callback()
        threading.Thread(target=stop_soon).start()
        return jsonify({"status": "shutting down"})

    # The production runner replaces this callback before accepting requests.
    # Keeping a harmless default makes Flask's test client safe.
    app.shutdown_callback = lambda: None
    return app


def run(host, port, allowed_course_id, sandbox_course_url):
    """
    Read credentials from the environment, confirm them against Canvas,
    and serve until stopped. The only function in this module that
    touches os.environ, makes a network call, or exits the process.
    """
    base_url = os.environ.get("CANVAS_BASE_URL", "").strip()
    token = os.environ.get("CANVAS_API_TOKEN", "").strip()
    if not base_url or not token:
        print("CANVAS_BASE_URL and/or CANVAS_API_TOKEN was not set.", file=sys.stderr)
        print("Run this via commands/start-server.command, which prompts for both.", file=sys.stderr)
        sys.exit(1)
    if not allowed_course_id:
        print("No allowed_course_id is configured; refusing to start without a course guard.", file=sys.stderr)
        sys.exit(1)
    if not canvas_hosts_match(base_url, sandbox_course_url):
        canvas_host = (urlparse(base_url if "://" in base_url else "https://" + base_url).hostname or "").lower()
        sandbox_host = (urlparse(sandbox_course_url).hostname or "").lower()
        print(
            f"Canvas host mismatch: API host {canvas_host!r} does not match "
            f"sandbox host {sandbox_host!r}. Refusing to start.",
            file=sys.stderr,
        )
        sys.exit(1)

    app = create_app(base_url, token, allowed_course_id)
    # The token now lives only in app.canvas_client, in this process's
    # memory. Drop it from the environment so it is not inherited by
    # anything else this process might spawn later.
    os.environ.pop("CANVAS_API_TOKEN", None)

    try:
        who = app.canvas_client.whoami()
        print(f"Connected to {app.canvas_client.base_url} as {who.get('name', 'unknown user')}.")
        print(f"Sandbox guard: only Canvas course {app.allowed_course_id} is allowed.")
    except Exception as exc:
        print(f"Could not verify the Canvas token against {app.canvas_client.base_url}: {exc}", file=sys.stderr)
        print("Double-check the domain and token, then try again.", file=sys.stderr)
        sys.exit(1)

    from waitress.server import create_server
    try:
        wsgi_server = create_server(
            app, host=host, port=port, threads=4,
            clear_untrusted_proxy_headers=True,
        )
    except OSError as exc:
        print(f"Could not start the server on {host}:{port}: {exc}", file=sys.stderr)
        print("Another copy may already be running, or the port is in use. "
              "Edit commands/start-server.config.jsonc to change the port.", file=sys.stderr)
        sys.exit(1)
    app.shutdown_callback = wsgi_server.close
    print(f"Canvas automation WSGI server listening on http://{host}:{port} (Ctrl+C to stop)")
    try:
        wsgi_server.run()
    finally:
        wsgi_server.close()
