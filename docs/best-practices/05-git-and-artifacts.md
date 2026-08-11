> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Git, artifacts, provenance

How we version a tool: commit the recipe, ignore the bulk, keep the manifest. The history stays
small and every artifact stays reconstructable.

## Per-project git

Each tool is its own git repo (`git init` at the tool root). Several of these repos are
local-only by design. Canvas Automation Toolkit's `AGENTS.md` is explicit that there is no remote and that
"frequent commits ARE the safety net." That is a deliberate local-first posture. The audit
flags the one real risk it carries (single-disk durability) and the fix is in
[11-suites-and-sharing.md](11-suites-and-sharing.md) and recommendation P3-A of
the source handbook's process audit: a one-command encrypted
off-machine mirror.

## The .gitignore philosophy

Three rules, in order:

1. **Commit the recipe.** Source, configs, `_lib.sh`/`_jsonc.py`, `research/`, `README.md`,
   `pyproject.toml`, and the lockfile. These are small and they regenerate everything else.
2. **Ignore the bulk.** Generated output, model weights, vendored builds, virtual envs, caches.
   All large, all regenerable.
3. **Keep the manifest.** When a directory of bulky assets is ignored, keep the one small file
   that records what is in it, so provenance survives in history.

### Keep-the-manifest, in practice

From `CANVAS_AUTOMATION/.gitignore`:

```gitignore
# Downloaded CC0 sound library (large) — keep ONLY the manifest (provenance/reproducibility)
sounds/external-service/*
!sounds/external-service/manifest.json

# Canvas Automation Toolkit-generated source cache — keep ONLY the manifest (the recipe reproduces the WAV in the
# pinned env; the WAV itself is large + regenerable from generation_recipe)
sounds/Canvas Automation Toolkit/*
!sounds/Canvas Automation Toolkit/manifest.json

# Iteration session snapshots: the .RPP is large (~2 MB text) and fully regenerable from the
# tiny meta.json params (procedural). Keep meta.json + metrics.json; ignore the RPP itself.
sessions/iterations/*/project.RPP
```

The negated pattern (`!.../manifest.json`) re-includes the manifest after ignoring its
directory. The history then records *what* was generated and *how*, while the bytes stay out of
git. For regenerable assets this beats Git LFS, which still stores and transfers the bytes. The
audit rates this "ahead of frontier." The one caveat: it only works when the asset truly is
regenerable, which is why determinism (see [01-principles.md](01-principles.md)) is the
foundation.

### Secrets, never committed

The first line of Canvas Automation Toolkit's `.gitignore` is its secret:

```gitignore
# Secrets — never commit
.external-service.json
```

API keys live in a gitignored dotfile (mode `0600`) or an env var, never in a tracked file. See
[07-mcp-and-apis.md](07-mcp-and-apis.md).

### A recommended baseline

```gitignore
# Secrets — never commit
.external-service.json
*.key

# Python env / caches / build
.venv/
__pycache__/
*.pyc
*.egg-info/
build/
dist/

# Large + regenerable
out/
models/
vendor/

# macOS
.DS_Store

# Keep the manifests for any ignored asset dirs
# assets/<lib>/*
# !assets/<lib>/manifest.json
```

`templates/gitignore.sample` ships this. Adjust the asset lines per tool.

## Provenance: the recipe beside the artifact

Every generated artifact ships a sidecar recipe. Canvas Automation Toolkit writes a `provenance.json` per output.
Its README states the contract:

> Each run writes `out/<utc>__audio__<slug>/audio.wav` + `provenance.json` (model, prompt, seed,
> steps, sample rate, licence note, library-ingestable). Same prompt + seed + args => the same
> audio. Outputs are never overwritten.

The record is schema-versioned (`Canvas Automation Toolkit.provenance/v1`) and captures model id, prompt, negative
prompt, seed, steps, guidance, device, the exact `torch`/`diffusers` versions, and a
`license_note`. That is build provenance: proof of how, when, and with what an artifact was
made. Two upgrades from the audit:

- **Make it required, not recommended.** Emit `provenance.json` from the shared launcher path
  so a tool cannot forget it (recommendation P2-C). Reuse the `Canvas Automation Toolkit.provenance/v1` schema
  across tools.
- **Roll up licenses.** A per-artifact `license_note` is good; add a project-level
  `LICENSES.md` or a CycloneDX/SPDX `sbom.json` naming vendored code and model weights with
  SPDX license IDs, so the gitignored `vendor/` and `models/` surface stays auditable before
  any release (recommendation P2-A). See [06-vendoring-and-linking.md](06-vendoring-and-linking.md).

## Pin the environment

Output determinism is only real if the environment is pinned. Commit `uv.lock` per project and
have setup run `uv sync`. Keep the per-artifact `torch`/`diffusers` stamps as a cross-check
against the lockfile. The audit's P1-C: several projects pin nothing beyond `pyproject.toml`,
which lets a fresh setup resolve different transitive versions and break byte-equality. See
[06-vendoring-and-linking.md](06-vendoring-and-linking.md).

## Backups and snapshots

Alongside git, the suite keeps periodic full snapshots: dated archives such as
`<toolkit-root>/archive/CANVAS_AUTOMATION_backup_20260624_170720.tar.gz`, and project `*.zip` copies. These
capture the non-regenerable inputs and a known-good whole-folder state. Two improvements:

- Prefer an encrypted off-machine copy over a `*.zip` on the same disk (P3-A).
- The keep-the-manifest hygiene keeps a backup small: only the non-regenerable inputs (human
  saves, source recordings) need the real bytes; everything else rebuilds from the recipe.

## How `archive/` and `detritus/` meet git

- `research/` is tracked. It is the committed "why." See [02-project-structure.md](02-project-structure.md).
- `archive/` is tracked or rolled into a dated `*.zip`. It is finished, superseded material you
  do not want to lose.
- `detritus/` is gitignored or pruned. It is throwaway scratch.

## The verify gate

Make a network-free `verify.command` (or `make check`, since Canvas Automation Toolkit already has a `Makefile`)
that runs the test suite, a double-render byte/hash equality check, and config-schema
validation, and wire it into a pre-commit hook so a red tree cannot be committed (P1-B). Canvas Automation Toolkit
already has the seed of this in `scripts/check_loudness_floors.py`, a deterministic regression
guard that exits non-zero on drift. Generalise it.
