# Best-practices handbook for the Canvas Automation Toolkit

This recipient-facing edition adapts Matt Horrigan's *Tooling Handbook* for this distribution.
Examples refer only to files included in the Canvas Automation Toolkit; references to private
projects have been removed. The handbook is licensed under [CC BY-SA 4.0](#license-and-attribution).
Toolkit code has separate licensing; see [`LICENSES.md`](../LICENSES.md).

## Division of responsibilities

The deterministic toolkit works without AI. Its commands parse documented inputs, validate
configuration, build PDF and Canvas quiz materials, assemble IMSCC archives, make guarded
Canvas API requests, and save reports. Network access is required for operations that contact
Canvas, an external link provider, or the optional Canvas MCP server.

AI can interpret source material, draft course text, transform material into documented Testmaker
or JSONC formats, and review reports. AI output becomes input to deterministic validation and
build steps. Never give a web chatbot a Canvas token, student information, or an unrestricted
course export.

## Operating principles

1. **Keep the deterministic core authoritative.** Use AI for interpretation and drafting. Use
   commands and tests for validation, building, guarded changes, and verification.
2. **Pair each major command with configuration.** A macOS `*.command` launcher has a sibling
   `*.config.jsonc`; a schema documents and validates structured configuration where applicable.
3. **Treat configuration as an interface.** Defaults, uncommon options, paths, safety controls,
   and output locations belong in the config or schema.
4. **Never overwrite generated output.** Use fresh timestamped directories under `out/` and
   preserve a pre-change Canvas export before substantial live work.
5. **Record provenance.** A manifest, verification report, or import record identifies inputs,
   versions, decisions, object IDs, warnings, and resulting artifacts.
6. **Commit the recipe.** Track source, commands, schemas, documentation, research, tests, and
   lockfiles. Exclude credentials, virtual environments, transient output, and private course
   material unless its distribution is intentional and licensed.
7. **Pin dependencies.** `pyproject.toml` declares Python dependencies and `uv.lock` pins them.
   The independently maintained MCP integration has its own version pin under `mcp/`.
8. **Keep the project relocatable.** `setup-after-move.command` recreates the environment after
   the folder is copied or unzipped. Code resolves paths from the project root or configuration.
9. **Require a safety boundary for live writes.** Configure one unpublished sandbox course URL.
   The local server extracts its course ID and rejects operations targeting another course.
10. **Verify every boundary.** Validate before building, inspect packages before import, inspect
    Canvas after writes, and repeat link and accessibility checks after course copies.

## Project map

| Location | Purpose | Version-control policy |
|---|---|---|
| `src/canvas_automation/` | Reusable engine and command-line interface | Track |
| `commands/` | macOS launchers, JSONC configs, and schemas | Track |
| `scripts/` | Deterministic maintenance and course-specific operations | Track substantive scripts |
| `tests/` | Automated regression tests | Track |
| `docs/` | Operator, security, QA, platform, and testmaking guides | Track |
| `research/` | Decisions, endpoint research, and upgrade assessments | Track |
| `mcp/` | Optional Canvas MCP pin, setup, and integration notes | Track pins and instructions |
| `input/` | User-supplied source material | Review licensing and privacy before tracking or sharing |
| `out/` | Timestamped packages, backups, logs, and reports | Ignore generated bulk |
| `.venv/` | Recreated locked Python environment | Ignore |

## Command and configuration pattern

On macOS, start with launchers in `commands/`. For example,
`commands/build-test-forms.command` reads `commands/build-test-forms.config.jsonc`; its schema is
`commands/build-test-forms.schema.json`. The launcher is a thin interface over the same Python
engine available through:

```sh
.venv/bin/canvas-automation --help
```

Keep interactive prompts in the launcher. Keep substantive behavior in `src/` or a reusable
script so another person, automation system, or AI CLI can run and test the same operation.

JSONC configuration may contain comments for operators. Quote paths, use relative paths when
possible, document every active field, and fail on unknown or invalid values. Never store a
Canvas token in a config file. The server launcher requests it with hidden input and removes it
from the environment after constructing the client.

## Artifacts, provenance, and Git

An artifact is reproducible when its source, configuration, dependency versions, and build
method are known. A distribution therefore includes a manifest, provenance record, SBOM,
licenses, source, configs, and tests. Build it twice and compare SHA-256 values before claiming
byte-level reproducibility.

Canvas changes also require a record of remote state. Save a course export before a substantial
change, retain the guarded operation's JSON report, and run fresh verification afterward.
Canvas may assign different object IDs on import; verify semantic properties such as titles,
order, dates, weights, links, and publication state.

Before committing:

```sh
./verify.command
git diff --check
git status --short
```

Inspect the exact staged files. Do not stage a token, private export, student data, or input
archive merely because it is inside the project folder.

## Canvas access modes

| Mode | Use it for | Review boundary |
|---|---|---|
| Guarded deterministic API | Repeatable object creation, updates, uploads, and verification | Confirm the configured sandbox and review the operation report |
| Deterministic IMSCC build and import | Whole-course structure and portable bulk materials | Inspect the archive, migration warnings, and imported course |
| Optional Canvas MCP | AI-assisted discovery and small, reviewable actions | Keep its pin explicit; verify changes through scripts or Canvas |

Prefer scripts or IMSCC for repeatable bulk changes. Use MCP when language-model reasoning is
useful for selecting or interpreting an operation. MCP does not replace the sandbox guard,
backups, deterministic verification, or Canvas import and link-validation reports.

When the MCP dependency updates:

1. Read its upstream release notes and security information.
2. Update only the pin and compatibility metadata under `mcp/`.
3. Recreate the integration in a disposable sandbox.
4. Run its health check and the toolkit test suite.
5. Exercise representative read and write operations against the guarded course.
6. Record the tested version and changed behavior before distributing it.

## Course and assessment pipeline

Use one reviewed source of truth wherever possible. The Testmaker format feeds deterministic PDF
forms and Canvas quiz endpoints; see [`TESTMAKING.md`](TESTMAKING.md) and
[`TESTMAKER_AUTHORING.md`](TESTMAKER_AUTHORING.md). Validate question structure and editorial quality
before building either endpoint. Preserve intentional directives such as `Only Version X`,
question pools, and version selection in the source and generated QA reports.

For whole-course materials:

1. Organize and license source files under `input/`.
2. Draft or transform material into documented HTML, Testmaker, or JSONC inputs.
3. Run local validation and tests.
4. Build the IMSCC or prepare a guarded API operation.
5. Save a sandbox backup and review the proposed scope.
6. Import or apply the change to the configured sandbox.
7. Inspect migration warnings, modules, assignments, quizzes, rubrics, outcomes, files, and links.
8. Record limitations and unresolved manual checks.

## Link and content quality assurance

HTTP success does not establish that a source is usable. The provider-aware checker tests video
availability through Vimeo and YouTube metadata where possible. Library-search pages may hide
failure behind a successful response; prefer stable open-access publisher or repository links.
Upload a licensed local file to Canvas when that is the most durable route.

Move sources that cannot be validated into a deterministic outtakes record. Label
authentication-protected sources for manual review. Run Canvas Link Validator, internal and
external checks, private-browser video checks, Student View, and accessibility review. Follow
[`QUALITY_ASSURANCE.md`](QUALITY_ASSURANCE.md).

## Documentation and AI handoff

Write instructions around observable actions: name the file to edit or upload, the command to
run, the expected output, the safety boundary, and the verification step. Avoid promotional
claims, unexplained abbreviations, internal filesystem paths, and references to unavailable
material.

For a web-chat AI session, upload `CHATGPT_CANVAS_COURSE_AUTHORING_GUIDE.md` first. It tells the
chatbot to request the smallest relevant set of source files. For an AI CLI, open the toolkit as
its workspace and direct it to `AGENTS.md`, this handbook, the relevant config schema, and the
applicable topic guide. Leave substantive reusable logic in `src/` or `scripts/`, with tests.

## Release checklist

- [ ] A fresh macOS setup succeeds through `setup-after-move.command`.
- [ ] Every major operation has a documented launcher or CLI command.
- [ ] JSONC configs and schemas agree and contain no credentials.
- [ ] `uv.lock` and the MCP pin are current and tested.
- [ ] `./verify.command` and the full stored test suite pass.
- [ ] Two distribution builds have matching SHA-256 values.
- [ ] The ZIP opens with `INDEX.html` at its top level.
- [ ] The ZIP contains source, scripts, configs, schemas, documentation, tests, licenses, SBOM,
      manifest, and provenance.
- [ ] No private course export, student data, access token, virtual environment, or generated
      working output is present.
- [ ] macOS instructions are primary; Linux support and experimental Windows support are labeled.
- [ ] Live-write instructions require an unpublished sandbox URL and describe the course guard.
- [ ] QA limitations and manual checks are stated directly.
- [ ] Any intentionally included example course is separated from the toolkit, labeled as
      non-production, checked for embedded third-party files, and accompanied by its own license.

## License and attribution

This adapted handbook is based on *Tooling Handbook*, copyright © 2026 Matt Horrigan, licensed
under the [Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/).

Adaptation: examples and operational guidance were rewritten for the distributable Canvas
Automation Toolkit, and references to private exemplar projects were removed. This adapted
handbook is distributed under the same CC BY-SA 4.0 license.
