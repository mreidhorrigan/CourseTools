# Operations guide

## Initial setup

Run `setup-after-move.command`, then `commands/initialize.command`, then
`verify.command`. Initialization accepts the full browser URL, writes the
central `course/course.config.jsonc`, and aligns command IDs. For REST operations,
start `commands/start-server.command` and confirm the displayed Canvas user and
instance before creating content. The server derives
the numeric ID and API hostname, verifies that they match at startup, and runs
the Flask application under pinned Waitress; no development server is used.
Waitress remains a local loopback process, not an institution-facing web
deployment. The server
refuses to start without this guard, and rejects every other course ID—including
IDs sent through the raw Classic/New Quiz path.

Starting the launcher twice is safe. Before requesting a token, it checks `/health` on the
configured loopback port. It reuses a healthy server guarded to the same Canvas host and course,
and refuses an unrelated listener or a server guarded to a different course.

### Direct authoring

Edit mapped HTML under `course/content/`; preserve its semantic tags while changing prose. Run
`commands/verify-authoring.command` to compare those sources and private Testmaker Markdown under
`private/testmaking/questions/` with guarded Canvas. Use `course_authoring.py apply` for authorized
prose synchronization, `course_authoring.py build-imscc` for the cartridge, and
`testmaking_authoring.py build-pdf` for printable forms. The manifests beside these source trees
are the mappings. Live Canvas, IMSCC files, and `out/` are downstream artifacts.

### Grade-submission conversion

Double-click `commands/convert-gradebook.command` and choose a Canvas gradebook
CSV. The local converter uses `SIS User ID`, `Final Score`, and the Canvas
section name by default. It rounds the percentage to the nearest whole number
with half-up behavior before applying the scale, so 94.5 becomes 95 and receives
A+ under the supplied default. It writes a headerless CSV containing only
Subject, Catalog Nbr, Section, Student ID, and Grade, in that order, under
`out/grade-submission/latest/`.

For command-line use, pass the CSV as the runtime argument:

```sh
commands/convert-gradebook.command /path/to/canvas-gradebook.csv
```

An explicit runtime input writes the derived `-grade-submission.csv` and
`-grade-submission-conversion-record.json` files
beside the source. The source file is never overwritten. A Finder-picked input
continues to write under `out/grade-submission/latest/`.

SFU's grade-upload instructions require no column headings and accept legacy
Excel `.xls`, comma-delimited CSV, or tab-delimited TXT. The toolkit defaults to
CSV because it is directly supported without a legacy spreadsheet dependency.
Set `output_formats` to `["csv", "txt"]` when a second, headerless tab-delimited
copy is useful. `.xlsx` is deliberately not offered because the documented
upload formats do not list it.

Edit `commands/convert-gradebook.config.jsonc` to change input columns, course
fields, output formats, or thresholds. Inspect the resulting file before
submission. Grade files contain student identifiers and must remain outside the
public distribution and version control; `out/` is excluded from both.

For development without student data, use
`tests/fixtures/gradebooks/canvas-gradebook-synthetic.csv`. Every name, ID,
login, mark, and course identifier in that file is invented. Rebuild it
deterministically with `scripts/build_fake_gradebook_fixture.py`; do not replace
it with a redacted or rearranged production export.

### Private Canvas roster and gradebook pipeline

Start the server for the centrally configured course, then double-click
`commands/pull-canvas-roster.command`. The read-only pipeline refuses a course
ID different from `course/course.config.jsonc`, and the server independently
enforces the same course guard. It uses Canvas's documented Enrollments,
Sections, Assignments, and bulk Submissions endpoints.

Each run creates a fresh ignored directory under `out/private-roster/` with:

- `canonical-roster.json` and `.csv`: names, preferred display names, SIS and
  Canvas IDs, sections, available avatar URLs, and whole-course grades;
- `gradebook.csv`: one published-assignment column plus whole-course totals;
- `nameplates.csv`: preferred display name and section;
- `seatplanner-source.csv`: a Canvas-shaped adapter for the original Seat
  Planner's name, note, and grade handling;
- `seating-plan.csv`: configurable seat labels, display names, IDs, and section;
- `export-summary.json`: counts and handling warning without student records.

Edit `commands/pull-canvas-roster.config.jsonc` to omit assignment scores or to
change seating columns and deterministic ordering. These files are educational
records. Keep them under `out/`, do not commit or distribute them, and remove or
relocate copies from insecure storage when the operational task is complete.
Do not use Canvas MCP for this operation: MCP log redaction does not prevent a
successful tool response from entering an AI context. The deterministic pull
prints only course ID, counts, filenames, and handling status. Do not ask an AI
to open the generated files.

Double-click `commands/build-roster-documents.command` after a roster pull. It
opens a private copy of M. Horrigan's original Nameplates tool with
`nameplates.csv` beside it. Choose that CSV, verify every parsed first name, and
print to PDF. The original three-per-page tent-fold geometry, font fitting, and
print CSS are preserved byte-for-byte. The generated workspace remains under
ignored `out/private-roster/` and contains student data.

Seating-chart generation is disabled until a reviewed room-layout CSV is set in
`commands/build-roster-documents.config.jsonc`. Supplied DOC_TOOLS layouts have
35, 48, or 60 seats. The command refuses a partial chart when the roster exceeds
the selected layout. Assignment is reproducible from the configured seed, and
the renderer retains the DOC_TOOLS PDF and CSV formats.

### Configurable syllabus links and information

Use `scripts/update_syllabus_links.py` for repeatable syllabus links, information blocks, scoped
removals, and section-introduction replacements. The script contains no course title, page slug,
institutional URL, instructor identity, or policy heading. Supply those through a JSONC config and
its sibling schema; `examples/iat210/syllabus-links.config.jsonc` demonstrates the format.

Set `sync_course_syllabus` when the Canvas Syllabus navigation page and a front-page wiki syllabus
must share the same reviewed HTML. The script checks both Canvas storage locations semantically,
accounts for Canvas-added link metadata, and updates only the location that differs. Always run a
dry run first and inspect its JSON record before using `--apply` and the configured confirmation
prefix.

For MCP, run `commands/setup-canvas-mcp.command`. It stores the API URL and
token in macOS Keychain and installs the exact version in
`mcp/requirements.lock`. Restart Codex after setup.

## Deterministic REST workflow

1. Copy and edit the relevant `commands/*.config.jsonc`.
2. Keep new objects unpublished while validating the workflow.
3. Start the local server and run the paired `.command` file.
4. Inspect the timestamped `out/` response and `provenance.json`.
5. Confirm the object in Canvas and publish only after review.

For quizzes, start with `dry_run: true`. Inspect `conversion-plan.json`, then
run live. A source containing `[Only Version X.]` must be run once per desired
`fixed_version`. Use Classic Quizzes for random take-N groups; New Quizzes for
ordinary questions, essays, fixed versions, and embedded DOCX images.

## Deterministic IMSCC workflow

1. Copy `input/course-package.example.jsonc` and edit its stable object keys.
2. Run `commands/build-imscc.command`.
3. In a clean Canvas sandbox, choose **Settings > Import Course Content >
   Common Cartridge 1.x** and select the generated `.imscc`.
4. Review the migration report, modules, links, dates, rubrics, assignments,
   discussions, files, and Student View before production use.

For packages that contain Canvas-native `course_settings/rubrics.xml`, a first
import into a genuinely empty/new course can create both the rubrics and their
assignment associations. Do not infer that a later import is equivalent after
manually deleting course objects: assignments can retain or reacquire stale
rubric identifiers, and a repeat migration may report success without
recreating the deleted rubric records. Inventory rubric IDs and assignment
associations after every import. Use `scripts/restore_imscc_native_content.py`
only as a guarded recovery path after an incomplete migration, not as a normal
post-import step.

Canvas's import screen—not this local builder—selects the destination course.
Open the sandbox course directly, verify its course ID in the browser address
bar immediately before import, and do not test IMSCC upload from a production
course's settings page.

Run `scripts/check_external_links.py PACKAGE.imscc` before import. It checks
ordinary pages and uses official oEmbed endpoints for specific YouTube and
Vimeo videos. This detects provider pages that return HTTP 200 even though the
video is unavailable. A `PROTECTED` result needs manual confirmation.
For DOI links, `METADATA` confirms the Crossref record while leaving full-text
access for a repository, publisher, library, or manual browser check.

## Distribution workflow

Run `commands/build-distribution.command`. The builder publishes the ZIP as
`release/canvas-automation-toolkit.zip` and places its provenance record beside it.
The temporary timestamped build directory is removed automatically. It generates `index.html`, a file
manifest, and a CycloneDX SBOM at archive root. It sanitizes Canvas course
targets and excludes course-specific working material, credentials, `.git`,
virtual environments, and generated output. Build twice and compare the printed
SHA-256 values before release.

## MCP-assisted workflow

Use MCP for discovery, inspection, and small supervised edits. Confirm the
target instance, course, and intended mutations. Prefer a stored config or
course spec when work must be reproducible or repeated.

The third-party MCP server does not implement this toolkit's course allowlist.
For MCP write testing, use a dedicated Canvas test account whose only course
enrollment is the sandbox, and create the API token from that account. Do not
use an instructor token that can modify production courses. With a broader
token, restrict MCP testing to reads; prompt instructions are not a security
boundary.

## Updating MCP

Run `commands/update-canvas-mcp.command 1.7.0` (substitute the reviewed target
version). The updater changes the pin, rebuilds the project-local environment,
and runs checks. Review and commit `mcp/requirements.lock` and compatibility
changes. To roll back, restore the prior pin from Git and rerun the updater with
that version. Do not use an unversioned `latest` install.

## Updating the deterministic runtime and WSGI server

Review the target package's release notes and license, then update one package
at a time. For Waitress:

```sh
uv lock --upgrade-package waitress
uv sync --extra dev
./verify.command
.venv/bin/python scripts/build_html_index.py
```

Start the guarded server in an unpublished sandbox. Confirm that `/health`
returns the expected course ID and the HTTP `Server` header identifies Waitress.
The server window prints one concise access notification per local request with
the method, route path, response status, and elapsed time. Query strings,
headers, bodies, and Canvas credentials are excluded. These notifications begin
when the server is next started; an already-running process keeps its loaded code.
Run one guarded read and the course verifier. Build two distributions and
compare their ZIP SHA-256 values. Review and commit `pyproject.toml`, `uv.lock`,
the generated root `index.html`, dependency/license documentation, tests, and
any compatibility changes together. Restore the previous commit and run
`uv sync --extra dev` to roll back.

## Recovery and credentials

Quiz creation rolls back an incomplete quiz by default. Other create commands
are create-only and can make duplicates; use the recorded object ID for
deliberate cleanup in Canvas. IMSCC output is disposable and reproducible.

To rotate REST credentials, stop and restart the server with a new token. For
MCP, rerun setup to replace the Keychain item, then restart Codex. Revoke
exposed or retired tokens in Canvas immediately.

## Sandbox replacement lifecycle

Use `scripts/sandbox_course_lifecycle.py` for inventory, pre-reset cartridge
backup, and an explicitly confirmed Canvas content reset. The script has no
token access and communicates only through the guarded local server. Examples:

```sh
.venv/bin/python scripts/sandbox_course_lifecycle.py --course 12345 inventory
.venv/bin/python scripts/sandbox_course_lifecycle.py --course 12345 backup \
  --output out/backups/course-12345-before-reset.imscc
.venv/bin/python scripts/sandbox_course_lifecycle.py --course 12345 reset \
  --confirm RESET-COURSE-12345 --record out/backups/course-12345-reset.json
```

Canvas reset deletes the old course and returns a newly created equivalent
empty course with a new ID. Save the response, update `sandbox_course_url`, and
restart the guarded server before any import. Never infer or silently reuse the
old ID after reset.

If the institution denies the reset permission, use the driver's two-phase
`cleanup-plan` and `cleanup` commands. Review the stored plan before supplying
`DELETE-CONTENT-COURSE_ID`; cleanup aborts if any object identifier changed
between planning and deletion.
Because Canvas always requires a front page, cleanup retains a uniquely named
unpublished smoke-test page temporarily. After import/finalization makes the
new syllabus front page, delete that temporary page.

Canvas object-by-object cleanup is not a perfect substitute for importing into
a newly reset course. In particular, a subsequent cartridge import can reuse
assignment migration identities while failing to recreate rubrics that those
assignments formerly referenced. Prefer Canvas's course reset when authorized;
when it is unavailable, treat rubric and quiz inventories as explicit import
acceptance checks rather than trusting the migration's `completed` state alone.

Use `import-package` to upload and poll an IMSCC deterministically through the
guarded local server. It stores the final migration and issue report:

```sh
.venv/bin/python scripts/sandbox_course_lifecycle.py --course 12345 \
  import-package --package input/imscc/PACKAGE/course.imscc \
  --record out/imports/course-12345-migration.json
```

For a course-to-course transition, use the combined command. It verifies the
target guard and unpublished state, creates and validates a target backup,
records the pre-import inventory, refuses a nonempty target unless explicitly
allowed, and only then starts the import:

```sh
.venv/bin/python scripts/sandbox_course_lifecycle.py --course 12345 \
  backup-and-import --package out/backups/source-course.imscc \
  --backup out/backups/target-before-import.imscc \
  --confirm COPY-INTO-COURSE-12345 \
  --record out/imports/course-12345-transition.json
```
# Course-design dossier PDF

Edit `commands/build-course-dossier.config.jsonc` to choose and order public
course sources. Each entry accepts a title, a path under `course/content/`, and an
optional CSS selector for including one section of a page. Double-click
`commands/build-course-dossier.command`, or run:

```sh
.venv/bin/python scripts/build_course_dossier.py --config commands/build-course-dossier.config.jsonc
```

Headless Chrome renders each source with the course stylesheet. The configured
`DOSSIER_TOOLS/dossier.py` supplies the contents page, PDF bookmarks, continuous
page labels, and final merge. Set `chrome_path` and `dossier_tools_directory`
after transferring the toolkit to another machine. The command accepts sources
only beneath `course/content/`, which excludes private test materials and access
credentials.
