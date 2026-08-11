> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Composing suites and sharing

How independent tools become a suite that feels like one product, and how a tool (or a suite)
gets shared so a recipient reproduces it.

## Composing a suite

The suite pattern is **independent engines, a shared library, linked by path.** Each tool is
self-contained (its own repo, venv, commands, and `out/`), and an orchestrator ingests sibling
outputs into a shared media library.

orchestrator (CANVAS_AUTOMATION) is the orchestrator. Canvas Automation Toolkit's README states the relationship:

> It is a sibling engine to `companion tool` (CANVAS_AUTOMATION) and `CANVAS_AUTOMATION`: its own venv +
> models/, a `gen` CLI, and timestamped, seeded, provenance-tagged outputs that the `orchestrator`
> orchestrator (CANVAS_AUTOMATION) can ingest into the shared media library like any other
> source.

What makes the composition clean:

- **One tool's `out/` is another's input,** referenced by path. orchestrator's config ingests
  `../CANVAS_AUTOMATION/out/footage/cosmic`. See [06-vendoring-and-linking.md](06-vendoring-and-linking.md).
- **Determinism makes linking safe.** A linked input regenerates from its recipe, so the
  consumer is never depending on a one-off byte blob. See [01-principles.md](01-principles.md).
- **Provenance makes ingestion auditable.** Every ingested artifact carries its
  `provenance.json` / `manifest.json`, so the shared library knows where each piece came from
  and under what license. See [05-git-and-artifacts.md](05-git-and-artifacts.md).
- **Shared venv with extras** lets one environment carry optional feature sets:
  `uv pip install -p .venv/bin/python ".[collage]"`. Optional features are extras, not new
  tools.

## The thing that makes a suite feel like one product

Consistency. Because every tool follows this handbook, they share a shape:

- the same `*.command` + `*.config.jsonc` interface,
- the same `out/<name>/<timestamp>/` never-overwrite output,
- the same provenance sidecar,
- the same setup and relocation story.

A user who learns one tool already knows how to drive the next. That uniformity is the suite's
real product surface, more than any single engine.

## Sharing a tool

### What to ship

Ship the recipe, not the bulk:

| Ship | Leave out |
|---|---|
| `src/`, `bin/` | `out/` (regenerable) |
| `commands/` (the `.command` + config pairs, `_lib.sh`, `_jsonc.py`) | `models/` (re-downloaded) |
| `README.md`, topic guides, `research/` | `vendor/` (rebuilt from setup) |
| `pyproject.toml`, `uv.lock` | `.venv/` (rebuilt by `uv sync`) |
| the setup script and `setup-after-move.command` | secrets (`.external-service.json` and the like) |
| manifests for any ignored asset dirs | the assets themselves |

This is just the `.gitignore` philosophy from [05-git-and-artifacts.md](05-git-and-artifacts.md):
a clone is already the shareable artifact.

### The reproducibility guarantee

A recipient runs three steps and gets your tool, byte-for-byte:

1. `git clone` (or unzip the snapshot).
2. One setup step: `uv sync`, rebuild `vendor/`, download weights.
3. Double-click a `.command`.

If a recipient cannot reproduce a run from those three steps, a committed recipe is missing. Fix
the recipe rather than shipping a binary.

### Snapshots and backups

For a whole-folder handoff or a durable checkpoint, the suite uses dated archives
(`CANVAS_AUTOMATION_backup_20260624_170720.tar.gz`) and project `*.zip` copies. Keep these for the
non-regenerable inputs and a known-good state. Prefer an encrypted off-machine copy over a zip
on the same disk (audit P3-A in the source handbook's process audit).

### Cross-platform sharing

Launchers are macOS-only by construction (`.command`, `open`, `osascript`, `read`). The engine
is portable Python. Where a Linux or Windows recipient is real, add a sibling `run.sh` (POSIX)
that the `.command` calls, so both hit one code path (audit P2-B). The CLI is the portable
contract; the `.command` is the macOS skin. See [06-vendoring-and-linking.md](06-vendoring-and-linking.md).

### License and provenance hygiene

Before sharing anything with third-party code or model weights, roll up the licenses. A
committed `LICENSES.md` or a CycloneDX/SPDX `sbom.json` names vendored code and weights with
their SPDX license IDs, turning the per-artifact `license_note` records into one auditable list
(audit P2-A). Canvas Automation Toolkit's per-artifact note is the seed of this:

> an optional model v1 weights are research-oriented (CC-BY-NC style); verify the licence before any
> commercial release.

## Suite and share checklist

- [ ] Each tool is self-contained: own repo, venv, commands, `out/`.
- [ ] Cross-tool inputs are linked by path to a sibling's `out/`, not copied.
- [ ] Every ingested artifact carries its provenance / manifest.
- [ ] Optional features are extras in one venv, not separate tools.
- [ ] A clone plus one setup step reproduces the tool and its output.
- [ ] No secrets, no bulk, no `vendor/` build in the shared artifact.
- [ ] A license / SBOM roll-up exists before any release.
- [ ] Where sharing off-macOS matters, a `run.sh` mirrors the `.command`.
