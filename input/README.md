# input/

Local content that gets uploaded *to* Canvas.

This plays the role of `reword`'s `input/` folder in the tooling handbook:
a plain, tool-local folder for content a config points at, rather than the
handbook's `choose_input`/`DEFAULT_INPUT` menu (see
research/00-retrofit-notes.md for why). That menu is for a tool with one
input folder or file per run; this tool's configs reference several small
named files individually (a description here, a page body there), which
does not fit a single "pick the input" prompt.

Reference a file from here in any config's `..._file` field, for example
`description_file`, `message_file`, or `body_file`, and its contents
become that field's value. The `_file` key is swapped for the real one
before anything is sent to Canvas, so Canvas never sees the `_file` suffix.

Not named `src/`: that name is reserved for the engine's own source code
under the standard project layout (see 02-project-structure.md), so this
folder is `input/` instead, matching the handbook's own precedent for a
single-input tool (`research/input-dir-convention.md` in the handbook
repo, not this one; summarised in this project's research/00-retrofit-notes.md).

The example files and course specification here match the sample configs in
`commands/`. Copy or replace them when using your own content; keep reusable
test-only material under `tests/fixtures/` instead.
