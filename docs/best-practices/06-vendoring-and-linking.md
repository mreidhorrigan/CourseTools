> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Vendoring, linking, portability

How a tool gets third-party code, how tools reference each other, and how a folder stays
reproducible and movable. The rule underneath all of it: a fresh clone plus one setup step
reproduces the tool and its output.

## Vendoring: buildable from setup, not committed

Third-party source that you clone or compile lives in `vendor/`, and it is **gitignored and
rebuilt by a setup script**, not committed. Canvas Automation Toolkit's `.gitignore`:

```gitignore
# ysfx build (cloned C++ source + compiled libs) — buildable from setup; not committed
vendor/
*.so
*.dylib
```

What you keep in git instead: the thin wrapper scripts that call the vendored binary, a
`NOTES.md` recording where it came from and how to build it, and a lockfile. Canvas Automation Toolkit does the
same for its fidelity tools under `tools/`, keeping "wrapper scripts, NOTES.md,
requirements.lock.txt" and ignoring "venvs, scratch, downloaded weights/models, and large
vendored binaries."

Why ignore the build: it is large, platform-specific, and regenerable from the setup script.
Committing it bloats history and breaks on the next machine anyway. The setup script is the
source of truth for "how to get this dependency."

## Python environments with uv

- One `.venv` per tool, created with `uv venv .venv`, gitignored.
- Reference the interpreter explicitly: `.venv/bin/python`, `$ENGINE/.venv/bin/gen`. No reliance
  on an activated shell, so a double-clicked `.command` works.
- **Commit `uv.lock`.** It pins every transitive dependency so `uv sync` reproduces an identical
  environment. Canvas Automation Toolkit already commits one; make it universal (audit P1-C).
- Optional features use extras, not separate tools. orchestrator installs with
  `uv pip install -p .venv/bin/python ".[collage]"`, so one suite venv carries optional feature
  sets. See [11-suites-and-sharing.md](11-suites-and-sharing.md).

## Linking across the suite

Tools reference each other by **path**, and one tool's `out/` is another tool's input. orchestrator's
`course-package.config.jsonc` ingests footage straight from a sibling:

```jsonc
"footage": "../CANVAS_AUTOMATION/out/footage/cosmic",  // folder of clips (absolute path is fine)
```

Canvas Automation Toolkit describes itself as a "sibling engine" whose seeded, provenance-tagged output "the
`orchestrator` orchestrator (CANVAS_AUTOMATION) can ingest into the shared media library like
any other source." This is the suite pattern: independent engines, a shared library, linked by
path. See [11-suites-and-sharing.md](11-suites-and-sharing.md).

### Vendor, link, or copy

| Situation | Do this |
|---|---|
| Third-party source you build (a C++ lib, a model repo) | **vendor** it: clone/compile into `vendor/`, gitignore, rebuild from setup |
| Another suite tool's output you consume | **link** by path to its `out/`; let determinism keep it fresh |
| A specific input you must freeze against upstream change | **copy** the bytes in, and record provenance for the copy |
| A Python dependency | declare it in `pyproject.toml`, pin in `uv.lock`; do not vendor |

Prefer link over copy inside the suite (one source of truth), and copy only when you need to
freeze an input. Prefer a pinned dependency over vendoring whenever the dependency ships as a
package.

## Portability and relocatability

A tool folder must survive being moved or copied to another machine.

**`setup-after-move.command`.** Double-click after relocating to re-resolve baked-in paths.
Canvas Automation Toolkit's wrapper is a thin skin over the real script:

```bash
#!/usr/bin/env bash
#  DOUBLE-CLICK THIS FILE (in Finder) AFTER MOVING THE PROJECT FOLDER.
cd "$(dirname "$0")" || exit 1
bash scripts/setup_after_move.sh
echo
read -n 1 -s -r -p "Press any key to close this window…"
```

Have the underlying script run `uv sync` (not a re-resolving `uv pip install`) so a relocation
reproduces the **locked** environment, and rebuild `vendor/` from setup. A move then restores a
byte-for-byte working tool.

**Env-var home overrides.** A drop-in launcher finds its engine through an overridable variable
with an absolute default:

```bash
REPO="${CANVAS_AUTOMATION_HOME:-<toolkit-root>}"
```

Set `CANVAS_AUTOMATION_HOME` and the launcher works from any location; unset, it falls back to
the known path. See the drop-in pattern in [03-command-and-config.md](03-command-and-config.md).

## The CLI is the portable contract

The engine in `src/` stays POSIX and Python: no `open`, no `osascript`, no `read`, no macOS-only
calls. Those conveniences live only in the `.command` skin. This keeps the real tool portable
and testable, and it is the same progressive-enhancement idea used for the future GUI in
[10-gui-extensions.md](10-gui-extensions.md).

Where sharing to Linux or Windows matters (audit P2-B), add a sibling `run.sh` (POSIX) that the
`.command` itself calls, so a Linux user runs the `.sh` and a macOS user double-clicks the
`.command`, both hitting one code path. A `.bat` is optional and only if a Windows recipient is
real. See [11-suites-and-sharing.md](11-suites-and-sharing.md).

## The reproducibility guarantee

Putting it together, a recipient can:

1. `git clone` the repo (small: recipe, configs, manifests, lockfile).
2. Run one setup step: `uv sync` plus the `vendor/` rebuild plus any weight download.
3. Double-click a `.command` and get byte-identical output to yours.

If any of those three steps cannot be done from what is in the repo, something that should be a
committed recipe is missing. Fix that, do not paper over it with a committed binary.
