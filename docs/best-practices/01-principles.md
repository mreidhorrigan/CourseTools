> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Principles and the prime directive

The ideas every other chapter implements. If a decision is ever unclear, resolve it in favour
of these.

## The prime directive: AI builds it, the tool runs AI-free

AI does the R&D: it designs the engine, writes the code, tunes the defaults, and authors the
docs. The shipped tool then runs **without any AI at all**. A person double-clicks a
`*.command`, edits a `*.config.jsonc`, and gets a full-featured result. There is no model in
the runtime, no API key required to operate it, no network call.

Why this matters:

- **It still works in five years.** No dependency on a model endpoint that may change, cost
  money, or vanish. This is the operational half of local-first software: your tools live on
  your machine and keep working regardless of the cloud.
- **It is fast and free to run.** The expensive, slow, probabilistic part (the AI) happened
  once, at build time. Runtime is deterministic code.
- **It scales to many operators.** The same headless core serves a human (double-click), a
  shell script (positional args), and a lightweight local AI (same args). See the dual
  interface in [08-skills-and-ai-integration.md](08-skills-and-ai-integration.md).

The audit in the source handbook's process audit calls this "the right
inversion" and notes most AI tools fail it outright because they cannot run without a live
model. Do not regress to a tool that needs an AI to function.

## One command per major function

Each thing the tool does well gets one `*.command`. Subtle variations are options in that
command's `*.config.jsonc`, not new launchers. Genuinely different functions are separate
files. Canvas Automation Toolkit's `commands/_lib.sh` states the rule directly:

> ONE .command per major function; subtle options live in its .config.jsonc (commentable JSON,
> comment a line out to use the default). Major differences = separate files.

This keeps the surface legible: a folder of `*.command` files reads like a menu. See
[03-command-and-config.md](03-command-and-config.md).

## The config is the whole interface

A human operates the tool by editing one commented file. Every option lives there: the active
ones uncommented, the rare ones commented out with a note explaining them. The config is the
documentation. There is nothing else to consult to drive the tool. See
[04-config-files-jsonc.md](04-config-files-jsonc.md).

The frontier extension (from the audit) is to ship a JSON Schema beside each config so an
editor validates types and autocompletes, and so a wrong value fails in the editor instead of
at runtime.

## Determinism is a contract

Same config plus same seed yields **byte-identical** output. This is stated and load-bearing,
not aspirational. `CANVAS_AUTOMATION/AGENTS.md` puts it plainly:

> Same campaign + same seed => bit-identical emission. Encoders that aren't bit-exact by
> default (e.g. SVT-AV1) are pinned single-thread in the suite's deterministic mode.

Determinism is what makes "regenerate from the recipe" true, which is what lets git ignore the
bulky output and keep only the recipe. It is the foundation the whole artifact strategy stands
on. See [05-git-and-artifacts.md](05-git-and-artifacts.md).

## Never overwrite

Output goes to a fresh `out/<name>/<timestamp>/` every run. A new render never destroys an old
one. Canvas Automation Toolkit's launcher opens the newest item after a run; the timestamped dir guarantees the
newest is always the one you just made, and the previous ones survive.

## Provenance beside every artifact

Each artifact ships a sidecar recipe. Canvas Automation Toolkit writes a `provenance.json` per output recording
the model, prompt, seed, steps, guidance, device, the exact `torch`/`diffusers` versions, and a
`license_note`. That is, in substance, build provenance: proof of how, when, and with what an
artifact was made. Make it required and emit it from the shared launcher path so a tool cannot
forget it. See [05-git-and-artifacts.md](05-git-and-artifacts.md).

## Reproducible from a fresh clone plus one setup step

A clone plus one `setup` reproduces the tool and its output. That means: pin the environment
(commit `uv.lock`, run `uv sync`), make `vendor/` rebuildable from a setup script rather than
committed, and keep paths relocatable. Output determinism is only real if the environment that
produces it is pinned too. See [06-vendoring-and-linking.md](06-vendoring-and-linking.md).

## Portability and relocatability

A tool folder can be moved or copied without breaking. `setup-after-move.command` re-resolves
baked-in paths after a move, and env-var home overrides (such as `CANVAS_AUTOMATION_HOME`)
let a launcher find its repo from anywhere. The CLI is the portable contract; the `.command`
is a thin macOS skin over it. See [06-vendoring-and-linking.md](06-vendoring-and-linking.md).

## Easy to use, extend, suite, and share

Every principle above ladders up to four goals:

- **Use:** double-click, edit one commented file, done.
- **Extend:** add a function by copying a `.command` + `.config.jsonc` pair; the shared
  `_lib.sh` already handles loading and launching.
- **Suite:** consistent structure and config UX let tools ingest each other's output and feel
  like one product. See [11-suites-and-sharing.md](11-suites-and-sharing.md).
- **Share:** commit the recipe and the lockfile, ignore the bulk, and a recipient reproduces it
  from a fresh clone.

## How this kills the re-prompting problem

The reason this handbook exists: we kept re-deriving these conventions per project, prompt by
prompt. Encoding them once, as a standing reference plus copyable [templates/](templates/),
means a new session starts from the conventions instead of rebuilding them. The principles are
stable; only the engine in `src/` changes per tool.
