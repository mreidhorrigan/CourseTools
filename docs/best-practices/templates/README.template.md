> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# TOOL_NAME

One or two sentences: what this tool is and what it feeds. Say it plainly. (House style: no
spaced em dashes. See 09-documentation-and-house-style.md.)

## Status

| Function | Backend | State |
|---|---|---|
| do-thing | <engine> | ✅ wired |
| do-other | <engine> | 🚧 in progress |

## Setup

A fresh clone plus one step reproduces the tool:

```bash
uv sync                      # build the pinned environment from uv.lock
# optional: bash scripts/fetch_models.sh   # download weights
# optional: bash scripts/build_vendor.sh   # rebuild vendored third-party code
```

## Use

Double-click a launcher, or run it from a shell:

```bash
./commands/do-thing.command            # edit commands/do-thing.config.jsonc first
.venv/bin/TOOL do-thing "PROMPT" --seed 7
```

Output and a `provenance.json` land in a fresh `out/<name>/<timestamp>/`. Same config plus same
seed yields byte-identical output. Outputs are never overwritten.

## Config

Every option lives in the `*.config.jsonc` next to each launcher, documented in place. Active
options are uncommented, advanced ones are commented out with a note. See
04-config-files-jsonc.md.

## Output and provenance

Each run writes the artifact plus `provenance.json` (inputs, seed, versions, license note), so
any artifact is reproducible from its recipe in the pinned environment. See
05-git-and-artifacts.md.

## Notes

- Runs AI-free at runtime. No model, no network required to operate it.
- Relocatable: double-click `setup-after-move.command` after moving the folder.
- Deeper subjects: link any topic guides here.
