# Retrofit notes: bringing this project up to the tooling handbook

This project started as a one-off build, then was brought up to
mreidhorrigan/best-practices-for-tool-development's standard following
12-adopting-in-existing-projects.md. Most of the checklist transferred
directly. A few items needed a deliberate, disclosed departure instead of
a mechanical one, because this tool is a different kind of thing than the
handbook's exemplars (generative and media-processing pipelines: gendiff,
studio, reaper, mvx). This tool's entire job is a live call to a remote
service (Canvas), which changes what "done" can honestly mean for two of
the handbook's non-negotiables.

## What transferred directly

- One `*.command` per major function, paired with one `*.config.jsonc`.
- `commands/_lib.sh` and `commands/_jsonc.py` are the handbook's own
  templates, copied verbatim, not reimplemented.
- `launch()` is used for every command that produces an artifact
  (create-assignment, create-rubric, create-discussion, create-page,
  download-content): output lands in a fresh `out/<command>/<timestamp>/`
  and is never overwritten.
- A `provenance.json` is written by a single shared helper
  (`util.write_provenance`), not left to each command to remember.
- `uv.lock` is committed; `setup-after-move.command` runs `uv sync`.
- Config-schema validation happens twice: `commands/_jsonc.py` does the
  handbook's shallow, top-level-only check before anything runs, and
  `canvas_automation.jsonc.validate_config` does a full recursive check
  once the CLI loads the config for real (see "Nested configs" below for
  why a second, deeper layer exists at all).
- `verify.command` runs the test suite and config-schema validation.
- House style: no spaced em dashes anywhere in this project's prose,
  configs, or status messages.

## Nested configs: why read_config alone was not enough

The handbook's `_jsonc.py` (and so `read_config`) only turns FLAT
top-level scalars into shell `KEY=value` lines; it explicitly skips
objects and arrays. That fits tools whose config is a flat parameter list
(`PROMPT`, `SEED`, `WIDTH`). Canvas's own API is not flat: an assignment
has a dozen fields, a rubric has a list of criteria that each have a list
of ratings. Flattening that into `ASSIGNMENT_NAME`, `ASSIGNMENT_POINTS_POSSIBLE`,
and so on would lose structure for anything list-shaped (there is no
sane flat encoding for "a variable number of rubric criteria, each with a
variable number of ratings").

The resolution: `eval "$(read_config ...)"` still runs in every
`*.command`, and still does two things for free: it catches a JSON syntax
error anywhere in the file before anything else runs, and it picks up the
one genuinely flat key every config needs anyway, `OUT_DIR`. The nested
data (`assignment`, `rubric`, `page`, the discussion's flat-but-many
fields) is read directly by the CLI from the same config file, using
`canvas_automation.jsonc`, a full nested-aware parser and validator built
for this project. Both layers read the identical file and the identical
`*.schema.json`; they just look at different parts of it. No config had to
be redesigned around the shell layer's limits.

## Why no choose_input

`choose_input` resolves the one input a tool reads, a folder or a file,
three ways (a positional path, a native picker, or a configured default).
It fits a tool whose subject is "process this folder of images." None of
this tool's commands work that way: create-assignment's subject is an
assignment described entirely in its config (with a couple of fields
optionally pulled from a named file in `input/`), not a folder chosen at
launch. The handbook itself calls this the generate-from-config case
(03-command-and-config.md, using generate-image as the example) and says
plainly that such a tool drops choose_input and reads its subject from a
config key. That is what every command here does.

## Why start-server and stop-server do not use launch()

`launch()` assumes a bounded command: run it, wait for it to exit, then
open the newest thing in `OUT_DIR`. start-server's job is an unbounded
foreground process (the local server, stopped by Ctrl+C or
stop-server.command), and stop-server's job is one HTTP POST with no
artifact at all. Neither produces "the newest item in an out_dir" in any
meaningful sense, so both source `_lib.sh` for `read_config` (and, in
start-server's case, its config-error check) but call the underlying CLI
directly rather than through `launch()`. This is the same kind of
judgment call as skipping `choose_input` where it does not fit: use the
part of the shared library that matches what the command actually does,
not all of it unconditionally.

## What does not transfer, and why

Two Definition of Done items are structural, not aspirational, for a live
API integration tool, and this project marks them explicitly rather than
quietly passing over them or gaming them with a hollow offline mode:

- **"Runs full-featured with no AI and no network."** This tool's only
  purpose is creating and reading content in a remote Canvas instance.
  There is no offline mode for "create an assignment in a school's LMS";
  removing the network removes the entire function, not an enrichment on
  top of one. The handbook's own guidance for external APIs (07-mcp-and-apis.md)
  says to fail soft and keep a core that runs offline when a service is
  an add-on; here the service is not an add-on, it is the tool. What DOES
  hold from the prime directive: this tool needs no AI at runtime, and no
  API key is ever required to operate the commands/*.command layer itself
  (only the already-running local server holds one, in memory, for as
  long as it runs).
- **"Same config plus same seed yields byte-identical output."** Canvas
  assigns its own ids, timestamps, and URLs on creation, so the same
  create-assignment config run twice produces two different Canvas
  objects by design, not two identical ones. There is no seed to control
  that variation because there is no generative randomness here to
  control. What this project asserts and tests instead, honestly, is
  determinism of the request rather than the response:
  `tests/test_engine.py` confirms that loading the same config twice
  produces byte-identical JSON payloads, which is the part actually under
  this tool's control. `verify.command` documents this substitution
  rather than stubbing out a check that could never pass for the right
  reasons.

## Directory naming

`src/` is reserved for the engine under the standard layout, and this
project already had a folder of user-authored upload content living at
that path before the retrofit. It is renamed `input/` here, following the
`reword` tool's precedent for a single local input folder
(handbook's research/input-dir-convention.md), rather than colliding with
the engine directory or inventing a third convention.
