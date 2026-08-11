> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Build checklist (definition of done)

The ordered recipe for shipping a tool from zero, and the acceptance test it must pass. Work
top to bottom. Copy from [templates/](templates/) at step 1 and most of this is already done.

## Build recipe

### 1. Scaffold the tree

Copy `templates/STRUCTURE.txt` and create the standard dirs. See
[02-project-structure.md](02-project-structure.md).

```
mkdir -p TOOL_NAME/{src,bin,commands,out,research,detritus,archive}
cd TOOL_NAME && git init
cp -R <handbook>/templates/. ./   # _lib.sh, _jsonc.py, skeletons, .gitignore, README, setup-after-move
```

### 2. Build the engine in `src/`

Write the real logic as a plain library plus a CLI. Python via `uv venv .venv`. The CLI takes
positional args and flags, prints the output path, exits non-zero on failure. No interactive
prompts in the core (those live in the `.command` skin). The engine must run with no AI. See
[01-principles.md](01-principles.md).

### 3. Expose one `*.command` + `*.config.jsonc` per function

- One launcher per major function. Subtle options go in its config, not in new launchers.
- The `.command` sources `_lib.sh`, runs `eval "$(read_config ...)"`, calls `launch "$OUT_DIR" -- <tool>`, then holds the window with `read`.
- Make it dual-interface: a positional-args path so a shell or local AI runs it headlessly, and a
  double-click path. A tool that reads an input resolves it with `choose_input`: pick a folder,
  the config's `DEFAULT_INPUT`, or its `CONFIG_INPUT`. A positional path skips that menu.
- See [03-command-and-config.md](03-command-and-config.md).

### 4. Write the config as the whole interface

Header comment block (what the tool does, how to run it, where output lands, the determinism
contract). Active options uncommented, advanced ones commented out with a note. Include `seed`,
`name`, `out_dir`. Ship a sibling `*.schema.json` and reference it so editors validate and
autocomplete. See [04-config-files-jsonc.md](04-config-files-jsonc.md).

### 5. Wire determinism, provenance, never-overwrite

- Output to a fresh `out/<name>/<timestamp>/`. Never overwrite.
- Same config plus same seed yields byte-identical output. Pin any non-deterministic encoder
  to single-thread deterministic mode.
- Emit a `provenance.json` next to every artifact (inputs, seed, versions, `license_note`).
  Make it required and emit it from the shared launcher path so a tool cannot forget. See
  [05-git-and-artifacts.md](05-git-and-artifacts.md).

### 6. Git: commit the recipe, ignore the bulk, keep the manifest

- Start from `templates/gitignore.sample`. Ignore `.venv/ out/ models/ vendor/ __pycache__/`
  and secrets. Keep manifests with a negated pattern (`!.../manifest.json`).
- Commit `src/`, `commands/`, configs, `research/`, `README.md`, `pyproject.toml`, `uv.lock`.
- Never commit secrets (`.external-service.json` and the like; mode `0600`). See
  [05-git-and-artifacts.md](05-git-and-artifacts.md).

### 7. Pin the environment

Commit `uv.lock`. Make `setup-after-move.command` run `uv sync` so a relocation reproduces the
locked environment rather than re-resolving it. See [06-vendoring-and-linking.md](06-vendoring-and-linking.md).

### 8. Document

A per-tool `README.md` (what / why / setup / use / config / output), topic guides for anything
deep, and `research/` notes for the why behind decisions. Apply the house style. See
[09-documentation-and-house-style.md](09-documentation-and-house-style.md).

### 9. Decide on MCP / API (usually no)

Default to a plain `.command` and CLI. Add an MCP only when an AI must drive a live external
app. Add an API only when a service is genuinely needed. Keep the core runnable without either.
See [07-mcp-and-apis.md](07-mcp-and-apis.md).

### 10. Optionally add a skill

If an AI will operate the tool often, add a `SKILL.md` telling it which `.command` and which
config knobs to use for common jobs. See [08-skills-and-ai-integration.md](08-skills-and-ai-integration.md).

### 11. Add a verify gate

A network-free `verify.command` (or `make check`) that runs the tests, a double-render
byte/hash equality check, and config-schema validation. Copy `templates/verify.command` and
wire it to a pre-commit hook so a red tree cannot be committed.

> Retrofitting an existing tool rather than starting fresh? Follow
> [12-adopting-in-existing-projects.md](12-adopting-in-existing-projects.md), which maps each
> upgrade above to a template and does the cheap, high-leverage ones first.

## Definition of done

A tool is shippable only when every box is true.

- [ ] Runs full-featured by double-clicking its `*.command`, with no AI and no network.
- [ ] One `*.command` per function, each paired with one `*.config.jsonc`.
- [ ] *(multi-step tools)* Steps run one at a time; a shared per-run/profile config overlays the
      per-step configs (precedence CLI > per-step override > shared > default); outputs isolate per run.
- [ ] *(R&D fan-outs)* A multi-agent run persists each subagent's result to disk as it lands and is
      resumable from a journal; no result lives only in memory, and a terminal limit pauses-and-resumes
      instead of restarting.
- [ ] Every option is documented inside the config. The config alone is enough to operate it.
- [ ] Dual interface: double-click for a human, positional args for a script or local AI.
- [ ] Deterministic: same config plus same seed yields byte-identical output, verified by a
      double render.
- [ ] Output lands in a fresh `out/<name>/<timestamp>/` and never overwrites.
- [ ] A `provenance.json` (or `manifest.json`) sits beside every artifact.
- [ ] `.gitignore` commits the recipe, ignores the bulk, keeps the manifest, excludes secrets.
- [ ] `uv.lock` (or equivalent lockfile) is committed; the env is reproducible.
- [ ] A fresh clone plus one setup step reproduces the tool and its output.
- [ ] Relocatable: `setup-after-move.command` re-resolves paths after the folder moves.
- [ ] Every `*.command` and `*.sh` passes `bash -n`.
- [ ] A `README.md` exists; prose follows the house style (no spaced em dashes).
- [ ] `research/` holds the design rationale and any audit or citations.
- [ ] A license / SBOM roll-up names vendored code and model weights before any release.
