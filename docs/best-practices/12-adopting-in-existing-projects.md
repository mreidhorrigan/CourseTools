> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Adopting the standard in an existing project

A retrofit guide. The chapters describe how to build a tool right from the start. This is how to
bring an already-built tool up to the standard, item by item, lowest cost first. It follows the
eight adopt-now recommendations from the source handbook's process audit,
each backed by a template in [templates/](templates/).

## How to use this

Work the table top to bottom. Each row is independent, so you can stop after any of them and the
project is strictly better than before. P1 is high leverage and low cost, do those first.

| # | Upgrade | Priority | Template | Chapter |
|---|---|---|---|---|
| 1 | JSON Schema per config + fail-fast validation | P1 | `do-thing.schema.json`, `_jsonc.py` | [04](04-config-files-jsonc.md) |
| 2 | Commit `uv.lock`; `setup-after-move` runs `uv sync` | P1 | `setup-after-move.command` | [06](06-vendoring-and-linking.md) |
| 3 | A network-free `verify.command` gate + pre-commit hook | P1 | `verify.command` | [05](05-git-and-artifacts.md) |
| 4 | `provenance.json` required, emitted by the shared path | P2 | (engine) | [05](05-git-and-artifacts.md) |
| 5 | License / SBOM roll-up | P2 | `LICENSES.md` | [11](11-suites-and-sharing.md) |
| 6 | `run.sh` portable contract for non-mac sharing | P2 | `run.sh` | [06](06-vendoring-and-linking.md) |
| 7 | `research/` standard in this project | P3 | (dir) | [02](02-project-structure.md) |
| 8 | One-command off-machine mirror | P3 | `mirror.command` | [05](05-git-and-artifacts.md) |

## 1. Schema-validated configs (P1)

The config is the whole interface, so a bad value should fail before a run, not deep inside one.

1. Copy `templates/do-thing.schema.json` to `commands/<stem>.schema.json` and edit its
   `properties`, `required`, `enum`, and `minimum`/`maximum` to match the config's keys.
2. Use the `templates/_jsonc.py` in this handbook (it validates against a sibling
   `<stem>.schema.json` automatically, with no external dependency). It finds the schema from a
   `"$schema"` line or by deriving the name, and on a bad value prints `__CONFIG_ERROR__` so
   `launch` reports it.
3. Optionally add a commented `// "$schema": "./<stem>.schema.json"` line so VS Code
   autocompletes and validates as you edit.

Verify: run `commands/_jsonc.py commands/<stem>.config.jsonc` and confirm a deliberately bad
value prints `__CONFIG_ERROR__`.

## 2. Pin the environment (P1)

1. `uv lock` to produce `uv.lock`, then commit it.
2. Edit `setup-after-move.command` (or the setup script it calls) to run `uv sync`, not a
   re-resolving install, so a relocation reproduces the locked environment.
3. Keep the per-artifact `torch`/`diffusers` stamps in `provenance.json` as a cross-check.

## 3. The verify gate (P1)

1. Copy `templates/verify.command` to the project root and wire its three sections: the test
   suite, the double-render hash-equality check (the determinism contract), and config-schema
   validation (already generic).
2. Add a pre-commit hook so a red tree cannot land:

   ```bash
   printf '#!/usr/bin/env bash\nexec "$(git rev-parse --show-toplevel)/verify.command"\n' \
     > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
   ```

   Canvas Automation Toolkit already has a `Makefile`; add a `make check` target that calls the same script.

## 4. Required provenance (P2)

Promote `provenance.json` from recommended to required, and emit it from the shared launcher or
engine exit path so a tool cannot forget it. Reuse the `Canvas Automation Toolkit.provenance/v1` schema across
tools and add a `schema_version` to configs. Signing (for example a local minisign key) is a
later nicety; suite-wide coverage is the win here.

## 5. License / SBOM roll-up (P2)

Copy `templates/LICENSES.md`, fill in the Python deps (from the lockfile), the `vendor/`
components, and the `models/` weights with their SPDX ids. Walk the release gate before sharing
anything. A machine-readable CycloneDX/SPDX `sbom.json` can sit beside it for tooling.

## 6. Portable `run.sh` (P2, only where non-mac sharing is real)

Copy `templates/run.sh` and point it at your engine. Have the macOS `.command` delegate its core
to `run.sh` so logic never forks across operating systems: the `.command` stays the mac skin,
`run.sh` is the portable contract, and a Linux user or CI runs the `.sh`.

## 7. Add `research/` (P3)

Create `research/` and move the design rationale into it: a `README.md` stub, a `CITATIONS.md`
(Canvas Automation Toolkit's model), and an ADR-style decision log so the "why" is committed and stops being
re-derived. Keep it distinct from throwaway `detritus/`. See [02-project-structure.md](02-project-structure.md).

## 8. Off-machine mirror (P3)

Copy `templates/mirror.command`, set the destination (an external or cloud drive), and edit the
non-regenerable input list. It pushes a small full-history `git bundle` plus only the inputs the
recipe cannot rebuild, optionally encrypted. This removes single-disk risk while keeping the
local-first posture.

## Done

Re-run the Definition of Done in [checklist.md](checklist.md). A retrofitted project should now
pass every box, the same as a freshly scaffolded one.
