# Architecture

Canvas Automation exposes three deliberately different Canvas access modes. They
share input conventions and provenance records, but not credentials or failure
semantics.

| Mode | Entry point | Best for | Credential boundary |
|---|---|---|---|
| REST automation | `commands/start-server.command`, then a `create-*` command | Repeatable, reviewable changes | Token exists only in the loopback server process |
| Common Cartridge | `commands/build-imscc.command` | Whole-course or bulk import | No Canvas credential is used |
| MCP | `mcp/canvas-mcp-launcher` through Codex | Conversational discovery and supervised changes | Launcher reads the token from macOS Keychain |

## Component boundaries

- `commands/` contains thin launchers, JSONC configuration, and JSON Schemas.
- `src/canvas_automation/cli.py` coordinates configuration and outputs. Domain
  transformations live in focused modules.
- `payloads.py`, `testmaker.py`, and `new_quizzes.py` are conversion code.
- `canvas_client.py` owns Canvas HTTP details; `server.py` is the loopback
  Flask WSGI application served by pinned Waitress. Waitress binds only to the
  configured loopback address; it does not broaden the security boundary.
  facade that keeps API credentials out of command processes.
- `imscc.py` creates a deterministic cartridge without Canvas access.
- `course_packet.py` and `pdf_tools.py` implement local export transforms.
- `mcp/` pins, launches, updates, and records the independently versioned MCP
  dependency. It is not vendored into the application package.

## Data flows and invariants

REST creation flows from a schema-validated config through a payload builder,
then through the loopback server to Canvas. A fresh `out/` directory stores the
response and `provenance.json`. Quiz conversion first creates a deterministic
plan; live creation remains unpublished until all items succeed and is rolled
back by default on a partial failure.

IMSCC creation flows from a course-spec JSONC file and referenced local files
to an isolated build directory. Stable identifiers, sorted ZIP members, and a
fixed ZIP timestamp make identical inputs byte-identical. Canvas itself may
normalize imported objects, so post-import equivalence is not promised.

MCP has a separate environment in `mcp/.venv`. Its version is locked in
`mcp/requirements.lock`; the launcher retrieves secrets at runtime. Updating
MCP therefore does not silently alter deterministic API or cartridge behavior.

## Extension rules

Add a deterministic operation as a builder first, cover it with a network-free
test, then expose it through CLI/config/Schema. Keep Canvas HTTP mechanics in
`CanvasClient` or the loopback route. Add cartridge content as a stable resource
plus manifest entry and test both ZIP contents and XML references. Never add an
unpinned MCP installation or persist a Canvas token in this repository.
