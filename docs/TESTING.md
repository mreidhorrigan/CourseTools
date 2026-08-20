# Testing and verification

All automated tests are stored under `tests/` and run without Canvas or network
access. Run:

```sh
uv sync --extra dev
./verify.command
```

The gate runs pytest, determinism checks, Python compilation, shell syntax
tests, and validation of every shipped JSONC config against its sibling Schema.
Tests use temporary directories; generated test artifacts are not committed.

## Coverage inventory

| Area | Stored coverage |
|---|---|
| Testmaker | tagged parsing, fixed versions, pools, paragraphs, validation, payloads, images |
| Testmaking | shared-source PDF forms and keys, deterministic seeds, version filtering, question-count and distractor QA, config/CLI provenance |
| Classic/New Quizzes | item payload shapes, random-group plans, image rewriting |
| IMSCC | deterministic bytes, manifest/resources, modules, rubrics, discussions, files |
| REST facade | health secrecy, routes, clean failures, URL construction and uploads, Waitress runner and graceful callback |
| Config/payloads | JSONC, Schema validation, deterministic payloads, file fields |
| Local exports | course IDs, PDFs, merge order, gradebook rows |
| Operations | engine roots, unique output, provenance, shell syntax |
| Sandbox lifecycle | course-specific reset confirmation, guarded routes, authenticated backup download |
| Distribution | deterministic ZIP, top-level HTML guide, sanitization, manifest, provenance, SBOM |
| Link QA | URL extraction, Vimeo/YouTube oEmbed probes, resolver outtakes, protected-state reporting, authenticated Canvas-host exclusion |

## Live acceptance checklist

Automated tests cannot prove institution-specific Canvas behavior. Before a
release, use a disposable sandbox to verify one unpublished object of each
changed REST type, one Classic and one New Quiz, a DOCX image, rollback on an
intentional quiz failure, and an IMSCC import with rubric and graded discussion.
Verify Student View and the Canvas migration report. Record the Canvas instance,
date, toolkit commit, and observations locally without tokens or student data.
Run `scripts/check_external_links.py` on the package. Use
`scripts/verify_imported_course.py --check-external` when that course-specific
verifier applies. Treat `PROTECTED` as requiring manual review, not as a pass.
Treat `METADATA` as confirmation of a DOI record only; it does not establish
full-text access.

MCP acceptance consists of starting a fresh Codex session, listing a harmless
course resource, and confirming the configured server version. Perform a write
only in a sandbox and only when the release changes MCP integration.
