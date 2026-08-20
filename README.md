# Canvas Automation

Open `index.html` for the concise visual guide. Regenerate it deterministically
after editing its template or dependency pins with
`.venv/bin/python scripts/build_html_index.py`.

## Authoritative prose and questions

`course/content/` is the source of truth for course prose. `course/course-manifest.json` maps each
file to its Canvas and IMSCC target, while `course/links-manifest.json` organizes every discovered
course, institutional, contact, and external link. Edit these source files directly; verify or
apply them with `scripts/course_authoring.py`.

`private/testmaking/questions/` contains the authoritative Testmaker Markdown used for both Canvas
quizzes and deterministic PDF forms. `private/testmaking/testmaking-manifest.json` stores shared
quiz settings and mappings. Testmaker accepts `.md`, `.markdown`, `.txt`, and `.docx`; Markdown is the
preferred human/AI authoring format. The entire `private/` tree and all generated `out/` material
are excluded from collaborator distributions and Canvas-hosted toolkit archives.

Run `commands/initialize.command` once for a new target. It prompts for the pasted course URL and
central institution values, writes `course/course.config.jsonc`, and aligns command course IDs.
For flexible institutional research and policy-link adaptation, direct an agent to read
`skills/configure-canvas-course/SKILL.md`.

Local `.command`-driven tools for scripting Canvas content creation on macOS,
without ever writing a Canvas API token to disk. The Python CLI also supports
Linux and experimental Windows use as described in `docs/PLATFORMS.md`.

## Prime directive, and where it does and does not apply

GPT-5.6 Sol, Claude Fable 5, and Claude Opus 4.8 built this tool. The shipped tool runs without AI: a person
operates it by double-clicking a `.command` file and editing its paired
`.config.jsonc`. Two usual guarantees in the best-practices handbook do not transfer to
a tool whose entire job is a live call to a remote service. See
`research/00-retrofit-notes.md` for the full reasoning, and the Definition
of Done tracking near the bottom of this file for exactly which two, and why.

## How it fits together

    commands/*.command   ->  local server (holds the Canvas token in memory)  ->  Canvas API
          ^                                                                           |
    commands/*.config.jsonc                                                         out/
          ^
       input/  (files a config points at)

1. `commands/start-server.command` derives the Canvas domain from the guarded
   sandbox URL, asks only for the API token, starts a small local server, and keeps the token in memory for
   as long as it runs. The token is never written to a file, logged, or
   sent anywhere except Canvas itself.
   The Flask WSGI application runs under the pinned, cross-platform Waitress
   production server, bound to loopback only.
2. Every other `commands/*.command` file reads a `.jsonc` config and talks
   only to that local server. None of them ever sees the token.
3. The server makes the authenticated call to Canvas and hands the result
   back. Everything Canvas returns lands in a fresh, timestamped folder
   under `out/`, next to a `provenance.json` describing what produced it.

## Requirements

- macOS
- [uv](https://docs.astral.sh/uv/), for the environment and lockfile.
  Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`, or
  `brew install uv`.
- A Canvas API access token. In Canvas: **Account -> Settings -> New
  Access Token**.

## First-time setup

1. Unzip this folder anywhere.
2. Double-click **`setup-after-move.command`**. It runs `uv sync` against
   the committed lockfile and installs the deterministic tools. Run this again
   any time you move the folder. MCP setup is separate and optional.
3. Confirm `sandbox_course_url` in `commands/start-server.config.jsonc`, then
   double-click **`commands/start-server.command`** and enter your API token.
   The API host is derived from that URL and the token is not echoed as typed.
4. Leave that window open. It prints which Canvas user it connected as.
   That is your running server.

## Running a command

With the server running, double-click any `commands/create-*.command` or
`commands/download-content.command`. Each one reads its paired
`.config.jsonc`, sends the request through the local server, prints the
result, and writes a fresh `out/<command>/<timestamp>/` folder, which
Finder opens automatically, holding a copy of what Canvas returned plus a
`provenance.json`.

Every command is also a plain CLI, driven the same way by a script or a
local AI:

    .venv/bin/canvas-automation create-assignment --config commands/create-assignment.config.jsonc

| Command | Config | What it does |
|---|---|---|
| `start-server.command` | `start-server.config.jsonc` | Starts the local server |
| `stop-server.command` | reads start-server's config | Convenience way to stop the server |
| `create-assignment.command` | `create-assignment.config.jsonc` | Creates an assignment |
| `create-rubric.command` | `create-rubric.config.jsonc` | Creates a rubric |
| `create-discussion.command` | `create-discussion.config.jsonc` | Creates a discussion topic |
| `create-page.command` | `create-page.config.jsonc` | Creates a page |
| `create-quiz.command` | `create-quiz.config.jsonc` | Converts a Testmaker-tagged DOCX/Markdown/text file into a Classic Canvas Quiz, including random take-N pools |
| `build-test-forms.command` | `build-test-forms.config.jsonc` | Builds deterministic PDF and DOCX forms and answer keys with the original JavaScript MCQer layout; no Canvas connection needed |
| `build-imscc.command` | `build-imscc.config.jsonc` | Builds an offline Common Cartridge containing course settings, pages, assignments, files, and modules |
| `build-distribution.command` | `build-distribution.config.jsonc` | Builds a sanitized deterministic ZIP with a top-level HTML guide, manifest, provenance, and SBOM |
| `test-assignment-rubric.command` | `test-assignment-rubric.config.jsonc` | Uses Mistral to simulate literal student responses, grade them with a rubric, and identify specification gaps |
| `download-content.command` | `download-content.config.jsonc` | Downloads existing content into `out/` |
| `export-course-packet.command` | `export-course-packet.config.jsonc` | Prompts for a course URL, then downloads published assignments as one combined PDF and builds a gradebook CSV/XLSX |
| `build-course-dossier.command` | `build-course-dossier.config.jsonc` | Builds a local, bookmarked course-design PDF from selected canonical course sources |
| `merge-pdfs.command` | `merge-pdfs.config.jsonc` | Opens a Finder dialog to pick any number of PDFs and merges them into one. Purely local; does not need the server running |
| `convert-gradebook.command` | `convert-gradebook.config.jsonc` | Converts a Canvas gradebook CSV into a headerless five-column registrar-upload CSV using configurable whole-percentage rounding and letter-grade thresholds |
| `pull-canvas-roster.command` | `pull-canvas-roster.config.jsonc` | Read-only guarded pull of the configured course roster, grades, and assignment scores into private canonical, nameplate, and seating-plan datasets |
| `build-roster-documents.command` | `build-roster-documents.config.jsonc` | Opens the original Nameplates tool with a private roster adapter and optionally builds a deterministic DOC_TOOLS seating chart from a reviewed room layout |

Additional details for these commands:

- `export-course-packet` asks for a course URL every run instead of
  reading `course_id` from its config, since it is meant to be pointed at
  a different course each time. Its gradebook is synthesized from three
  separate Canvas endpoints, not a real CSV export: Canvas has no
  documented API for the one the Gradebook UI's own "Export" button
  produces (see `research/canvas-api-endpoints.md`).
- `merge-pdfs` opens a native Finder dialog (`choose file ... with
  multiple selections allowed`), not a config-driven file list, since the
  whole point is picking an arbitrary set of PDFs fresh each run. See
  `research/01-course-packet-and-merge-pdfs.md`.

## Creating a quiz from a Testmaker question pool

`create-quiz.command` reads Testmaker's tagged paragraph format. Testmaker accepts
`.docx`, `.md`, `.markdown`, and `.txt` files. It also remains
compatible with tagged files created by the earlier `MCQer.html` application. The
sample config begins with `dry_run: true`; this validates the source and
writes `conversion-plan.json` without contacting Canvas. Inspect that file,
change `dry_run` to `false`, start the local server, and run the command again
to create the quiz.

The important mappings are:

| Testmaker source | Canvas result |
|---|---|
| `[Question.]` + `[Answer.]` + `[Distractor.]` | multiple-choice question |
| `[Question.]` without distractors | manually graded essay question |
| `[Paragraph.]` | zero-point text-only item |
| `[Each version take N ...]` + `[Option.]` | native question group with `pick_count=N` |
| `[Scramble ...]` + `[Option.]` | native question group that picks all questions in random order |
| `[Page break.]` | ignored with a warning; use `one_question_at_a_time` for Canvas pagination |
| `[Only Version X.]` | supported through `fixed_version`; run once per desired fixed-version quiz |

Canvas question groups select independently for each student, rather than
building fixed A/B/C paper versions. Pool questions must have the same point
value because Canvas stores points on the group. Answer text attached to a
written question remains in the local conversion plan as an instructor key;
it is not exposed to students through the essay question.

For fixed versions, set `fixed_version` to `A`, run the command, then repeat
with `B`, `C`, and so on. Shared questions appear in every quiz and tagged
questions appear only in their matching quiz. Titles receive ` - Version X`
unless `append_version_to_title` is disabled.

The live workflow always creates the quiz unpublished, adds every group and
question, and only then applies `published: true` if requested. By default it
deletes an incomplete quiz if an upload step fails. As with the other create
commands, running it twice creates a duplicate; it does not update in place.

## Building a Canvas import package

`build-imscc.command` is the offline Course Import branch. Its JSONC course
spec describes course settings, weighted assignment groups, pages, assignments,
ordinary files, and module ordering. It emits a deterministic `.imscc` for
**Settings > Import Course Content > Common Cartridge 1.x** without contacting
Canvas or requiring a token. Start from `input/course-package.example.jsonc`.

Every object key becomes a stable migration identifier, module references point
to those actual identifiers, and the manifest enumerates every packaged file.
Import into a clean sandbox, inspect the migration report, and check Student
View before copying into a live course. This from-scratch branch currently
covers pages, assignments, files, modules, assignment groups,
rubrics (including assignment associations), and course settings. Classic
quizzes remain available through `create-quiz.command`. The IMSCC specification
also emits native graded or ungraded discussions and rubric associations.
Canvas can import those native rubrics directly into a clean course. Reimporting
after object-by-object cleanup is a distinct recovery case: Canvas may reuse
migration identities without recreating deleted rubric records, so the toolkit
verifies live rubric associations and does not assume that a successful
migration status proves they exist.

`create-quiz` supports both `quiz_engine: "classic"` and `quiz_engine: "new"`.
New Quizzes currently accept ordinary MCQs, essays, fixed versions, and embedded
DOCX images; Testmaker take-N pools require Classic Quizzes because the public New
Quiz Items API does not expose creation of random item-bank selection blocks.
DOCX images are extracted, uploaded to the course's `quiz-images` folder, and
rewritten to authenticated Canvas file URLs in question and answer HTML.

## Three Canvas access modes

1. **Deterministic API scripting:** start `start-server.command`, then use the
   `create-*`, download, and export commands. The token remains in that local
   server's memory.
2. **Deterministic Course Import:** use `build-imscc.command`, then upload its
   Common Cartridge through Canvas's Import Course Content screen.
3. **LLM-driven MCP:** version 1.7.0 of `canvas-mcp` and its transitive environment are hash-pinned in
   `mcp/requirements.lock` and registered with Codex as `canvas-lms`. Run
   `commands/setup-canvas-mcp.command` once to save the Canvas API URL and token
   in macOS Keychain, then open a new Codex session. The token is never written
   into this project or Codex configuration.

Use MCP for discovery and small reviewable actions. Prefer the deterministic
commands or an IMSCC for repeatable/bulk production; an LLM may prepare or
inspect their configs and outputs without replacing their deterministic core.

## Config files

Every `commands/*.config.jsonc` has a header comment, active settings
uncommented, and disabled ones commented out with a note, following
`04-config-files-jsonc.md`. A sibling `*.schema.json` documents and
validates every field, both in your editor and at run time.

Config conventions:

- **`course_id`** is which Canvas course the action applies to.
- **`<field>_file`** (for example `description_file`, `message_file`,
  `body_file`) reads that file from `/input` and uses it as `<field>`. Use
  `<field>` directly instead for anything short enough to write inline.

## Project layout

    commands/    one *.command + *.config.jsonc (+ *.schema.json) pair per action
    src/         the engine: canvas_client.py, server.py, cli.py, jsonc.py, payloads.py, util.py
    input/       local content a config points at, uploaded to Canvas
    out/         everything Canvas returns, one fresh timestamped folder per run, gitignored
    research/    design rationale, including the Canvas API quirks this tool depends on
    tests/       the pytest suite verify.command runs

## Maintainer documentation

- `docs/best-practices/README.md` begins the complete adapted Tooling Handbook, including all
  15 chapters, its checklist, templates, license, and adaptation record.
- `docs/BEST_PRACTICES_HANDBOOK.md` is the concise CourseTools-specific operating guide.
- `docs/ARCHITECTURE.md` defines component and security boundaries.
- `docs/OPERATIONS.md` is the setup, run, update, rollback, and import runbook.
- `docs/SECURITY.md` documents credentials, privacy, and MCP risk controls.
- `docs/TESTING.md` inventories stored coverage and the live acceptance gate.
- `docs/QUALITY_ASSURANCE.md` lists the course, link, media, accessibility, and Student View checks.
- `docs/PLATFORMS.md` labels macOS, Linux, and Windows support precisely.
- `docs/TESTMAKER_AUTHORING.md` is the quiz-source authoring reference.
- `docs/TESTMAKING.md` documents the shared-source Canvas/PDF workflow and QA gate.
- `docs/ASSIGNMENT_RUBRIC_QA.md` documents Mistral-based boundary testing for assignment instructions and rubrics.
- `mcp/README.md` documents installation and version-controlled MCP updates.

## Security notes

- The token lives only in the running server process's memory. Closing
  that window (Ctrl+C, or `stop-server.command`) discards it for good.
- The server binds to `127.0.0.1` only.
- No file in this project ever holds the token. `start-server.config.jsonc`
  holds only a host and a port.

## MCP implementation

The installed MCP is the independent, MIT-licensed `canvas-mcp` project. Its
educator profile supplies broad read/write Canvas coverage while this toolkit
retains the narrower deterministic workflows. `mcp/canvas-mcp-launcher` is the
security boundary: it retrieves credentials from Keychain and then launches
the pinned project-local server over stdio.

## Definition of Done

Tracking `checklist.md`. The two struck-through items are structural for a
live API integration tool, not oversights. `research/00-retrofit-notes.md`
has the full reasoning for both.

- [x] One `.command` per major function, paired with one `.config.jsonc`
- [x] Every option lives in the config; disabled options stay in, commented and documented
- [x] Dual interface: double-click for a human, a plain CLI for a script or a local AI
- [ ] ~~Runs full-featured with no AI and no network~~. This tool's function is a live Canvas API call. No AI is needed at runtime, but the network is the point, not an add-on.
- [ ] ~~Same config plus same seed yields byte-identical output~~. Canvas assigns its own ids and timestamps, so the same config yields byte-identical *requests* instead. That is tested, and it is the part this tool actually controls.
- [x] Outputs go to a fresh `out/<name>/<timestamp>/`, never overwritten
- [x] A `provenance.json` sits beside every artifact
- [x] `.gitignore` keeps the recipe, ignores the bulk
- [x] `uv.lock` committed. The environment is reproducible
- [x] Relocatable: `setup-after-move.command` re-syncs after the folder moves
- [x] Every `.command` and `.sh` passes `bash -n`
- [x] README exists, and the prose follows house style
- [x] `research/` holds the design rationale
- [x] MIT project license, `LICENSES.md`, and a generated CycloneDX SBOM in distributions

## Troubleshooting

- **"Could not reach the local Canvas server"**. Start, or restart,
  `commands/start-server.command`, and make sure that window is still open.
- **"Could not verify the Canvas token"**. Double-check the domain
  (include `https://`) and generate a fresh token if needed.
- **A server is already running.** `start-server.command` checks the configured port before
  requesting a token. A matching guarded server is reused. An unrelated process or a server
  guarded to another course is identified; stop it or change `port` in
  `commands/start-server.config.jsonc`.
- **Double-clicking a `.command` file does nothing, or opens a text
  editor**. It lost its executable bit. In Terminal:
  `chmod +x *.command commands/*.command`.
- **A window disappears before you can read an error**. Every `.command`
  file pauses on "Press return to close" specifically so this does not
  happen. If you still miss it, run the file from Terminal instead of
  double-clicking it, so everything stays visible as it scrolls by.

## Canvas API references

See `research/canvas-api-endpoints.md` for the specifics, especially the
rubric criteria format. Instructure's current documentation:

- https://developerdocs.instructure.com/services/canvas/resources/assignments
- https://developerdocs.instructure.com/services/canvas/resources/rubrics
- https://developerdocs.instructure.com/services/canvas/resources/discussion_topics
- https://developerdocs.instructure.com/services/canvas/resources/pages

## Sharing the toolkit

Run `commands/build-distribution.command`. It writes the current collaborator package to
`release/canvas-automation-toolkit.zip`, with `provenance.json` beside it. Temporary
timestamped distribution builds are removed automatically. The same source and locks produce
the same ZIP bytes. The builder uses an allowlist, sanitizes course IDs and the
sandbox URL, and excludes undisclosed course-specific working material, tokens, `.git`,
virtual environments, and generated output. After unzipping, the collaborator
starts with `index.html` at the top level.

Before release, run `./verify.command`. Its portability audit scans the same
file set used by the distribution builder. Institution-, course-, instructor-,
and content-specific markers may live in documented JSONC configuration and
under `examples/`; the audit fails when they occur in reusable code. Adapt the
marker list in `commands/portability-audit.config.jsonc` for another institution
or course. `index.html` lists every configuration recipients must review.

The distribution intentionally includes
`examples/iat210/IAT210-Fall2026-example-course-starter-v2.0.imscc`. This seven-quiz,
non-production course starter was generated with AI under the direction of M. Horrigan. Its
adjacent notice documents required review and requires attribution to M. Horrigan under CC BY
4.0. The package excludes unpublished outtake pages and the locally uploaded Trammell PDF.

For external course links, run:

```sh
.venv/bin/python scripts/check_external_links.py path/to/course.imscc --outtakes-out out/link-outtakes.json
```

Vimeo and YouTube links use their official oEmbed endpoints. A provider page
that returns HTTP 200 while showing an unavailable video therefore fails QA.
DOI links are checked through Crossref and reported as `METADATA`: the citation
exists, while full-text access still requires a publisher, repository, library,
or manual browser check. Prefer an authoritative open-access item link when one
is available.
Institutional library search-result URLs configured in the example course are `OUTTAKE`, never
verified: replace them with a stable DOI or verified publisher, repository, or
author URL. Configure resolver hosts in the course's `link-check.config.jsonc`.
HTTP success cannot prove that a search result is the intended work.
