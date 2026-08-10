# export-course-packet and merge-pdfs: design notes

Added after the initial retrofit. Both follow the same conventions as the
rest of `commands/` (one `.command` + `.config.jsonc` + `.schema.json`,
`launch()`, `fresh_out_dir()`, `write_provenance()`), with three
deliberate departures worth recording rather than leaving implicit.

## Why export-course-packet's course id lives in a prompt, not the config

Every other create-*/download-content command keeps `course_id` in its
config, because each of those configs is meant to describe one specific,
recurring thing (an assignment, a rubric) for one course. This command
was explicitly requested as something you point at a different course
each time you run it, so the course URL is asked for interactively
instead, exactly like the Canvas token is asked for in
start-server.command. The engine still takes it non-interactively
(`--course-url`, parsed by `util.parse_course_id`, tested in
tests/test_engine.py); only the `.command` layer prompts.

## Why the gradebook is synthesized, not exported

See research/canvas-api-endpoints.md: there is no documented, token-usable
API endpoint for it. `course_packet.export_gradebook()` combines
Enrollments, Assignments, and the bulk Submissions endpoint instead. The
`only_published` filter applies to the gradebook's assignment columns the
same way it applies to the PDF, since Canvas's own gradebook UI only
shows published assignments as live, gradable columns.

## Why the two PDF commands share one merge function

`pdf_tools.merge_pdfs()` is used by both export-course-packet (to combine
its own freshly-rendered per-assignment PDFs into one) and merge-pdfs (to
combine whatever the person picked in Finder). One function, one place to
get the pypdf usage right, matching the same reasoning already applied to
`build_rubric_criteria_hash` and the payload builders.

## Why merge-pdfs does not use choose_input

`choose_input` resolves the one input a tool reads, a folder or a single
file. This command's whole point is an arbitrary, multi-select list of
PDFs picked fresh each run, which is a different shape than what that
helper is for (see 03-command-and-config.md and the create-* commands'
own reasoning in 00-retrofit-notes.md for the same kind of judgment call).
merge-pdfs.command calls `osascript` directly for a native multi-select
Finder dialog, then forwards the selected paths, in the order they were
picked, to the engine, which supports either keeping that order or
switching to alphabetical via `sort_alphabetically` in the config.
