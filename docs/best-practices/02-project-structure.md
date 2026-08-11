> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Standard project structure

The canonical directory tree, what each directory is for, and whether git tracks it. Copy the
shape from [templates/](templates/) and you start compliant.

## The tree

```
TOOL_NAME/
├── README.md                  # what / why / setup / use / config / output
├── pyproject.toml             # package metadata + deps (extras for optional features)
├── uv.lock                    # pinned, committed environment
├── .gitignore                 # commit the recipe, ignore the bulk, keep the manifest
├── .venv/                     # uv virtual env                          (gitignored)
├── src/                       # hand-written source: the engine + CLI
│   └── TOOL_NAME/             # the importable package
├── bin/                       # thin entry-point wrappers               (optional)
├── commands/                  # the *.command + *.config.jsonc pairs
│   ├── _lib.sh                #   shared read_config() + launch()
│   ├── _jsonc.py             #   string-aware JSONC -> shell KEY=value
│   ├── do-thing.command
│   └── do-thing.config.jsonc
├── out/                       # generated artifacts                     (gitignored)
│   └── <name>/<timestamp>/    #   never overwritten; provenance.json beside each
├── models/                    # downloaded weights                      (gitignored)
├── vendor/                    # third-party code, buildable from setup  (gitignored)
├── research/                  # committed design research / audits / decisions
├── detritus/                  # throwaway scratch                       (gitignored or pruned)
├── archive/                   # old-but-kept material
└── setup-after-move.command   # re-resolve paths after relocating
```

Some tools use `scripts/templates/` instead of `commands/` when the launcher is a drop-in pair
copied into a working directory (the Canvas Automation Toolkit pipeline pattern). Same idea, different placement.
See [03-command-and-config.md](03-command-and-config.md).

## Directory by directory

| Directory | Holds | Git | Notes |
|---|---|---|---|
| `src/` | the engine and CLI, hand-written | tracked | the only part that changes per tool |
| `bin/` | thin wrappers / entry points | tracked | optional; `orchestrator` uses `bin/` |
| `commands/` | `*.command` + `*.config.jsonc` + `_lib.sh` + `_jsonc.py` | tracked | the AI-free interface |
| `out/` | generated artifacts in timestamped subdirs | ignored | regenerable; never overwritten |
| `models/` | downloaded model weights | ignored | large; re-downloaded by setup |
| `vendor/` | cloned/compiled third-party code | ignored | rebuilt from a setup script |
| `research/` | design research, audits, citations, decisions | tracked | the committed "why" |
| `detritus/` | throwaway scratch | ignored | safe to delete anytime |
| `archive/` | old-but-kept material | tracked or zipped | superseded, not garbage |
| `.venv/` | the uv virtual environment | ignored | rebuilt from `uv.lock` |
| `profiles/` | staged tools only: one dir per run (shared + per-step config) | tracked | see [13-staged-pipelines-and-shared-config.md](13-staged-pipelines-and-shared-config.md) |

## The three "old stuff" directories, kept distinct

These are easy to conflate. Keep them separate.

- **`research/`** is the committed record of *why*. Design research, an audit, citations,
  decision notes. It is lightweight markdown, it goes in git, and a new session reads it to
  avoid re-deriving a decision. Canvas Automation Toolkit's `research/` holds `CITATIONS.md` plus topic files.
  This is now standard in **every** project (see the audit's recommendation P3-B in
  the source handbook's process audit). A subagent audit feeds this
  directory directly, exactly as the audit that informed this handbook fed
  [research/](research/).
- **`detritus/`** is throwaway scratch. Half-finished experiments, one-off debug output,
  anything safe to delete. Gitignored or periodically pruned. `<toolkit-root>/archive/detritus/` is the
  model.
- **`archive/`** is old-but-kept: superseded versions and finished material you do not want to
  lose but no longer touch. `<toolkit-root>/archive/Archive/` is the model. Either tracked, or rolled into
  a dated `*.zip`.

Rule of thumb: if it explains a decision, it is `research/`. If it might be deleted with no
loss, it is `detritus/`. If it is a finished thing you have moved past, it is `archive/`.

## `out/`: timestamped and never overwritten

Every run writes a fresh `out/<name>/<timestamp>/`. orchestrator's `course-package.config.jsonc`
states the rule in its header:

> Output lands in a fresh out/<name>/<timestamp>/ folder (never overwritten). Same config +
> same "seed" always renders the exact same video.

This is why `out/` is safe to gitignore: nothing in it is precious, because the recipe plus the
seed regenerates it. See [05-git-and-artifacts.md](05-git-and-artifacts.md). The launcher's
`launch()` helper opens the newest item in `out/` after a run.

## Naming conventions

- Directories: lowercase, the names above. Top-level tool folders are SHOUTING_SNAKE in this
  suite (`CANVAS_AUTOMATION`, `CANVAS_AUTOMATION`), matching the existing layout.
- A `*.command` and its config share a stem: `generate-image.command` and
  `generate-image.config.jsonc`. Kebab-case for the stem.
- Shared helpers are underscored so they sort first and read as "not a user entry point":
  `_lib.sh`, `_jsonc.py`.
- Timestamped output dirs use a sortable UTC stamp so newest sorts last (or use `ls -t`).

## Engine versus interface

Keep a clean split:

- `src/` is the **engine**: a library plus a headless CLI. No interactive prompts, no
  macOS-only calls. This is the portable, testable, AI-drivable core.
- `commands/` is the **interface**: the double-click skin and the commented config. macOS
  conveniences (`open`, `osascript`, `read`) live here, never in the engine.

This split is what lets the same engine serve a human, a script, an agent, and a future GUI.
See [10-gui-extensions.md](10-gui-extensions.md).
