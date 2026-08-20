# research/

The committed "why" for this project: design research, decisions, and the
reasoning behind places this tool departs from the tooling handbook's
default shape. Not user-facing; it exists so nobody (human or AI) has to
re-derive a decision that was already made once.

- `canvas-api-endpoints.md`: the Canvas REST API research behind every
  command, including the rubric criteria format and the gradebook
  workaround, which are the two most likely spots for a new contributor
  to reintroduce a bug.
- `00-retrofit-notes.md`: what changed when this project was brought up to
  the tooling handbook's standard, and why a few of the handbook's
  defaults (network-free runtime, byte-identical determinism,
  choose_input) do not transfer to a live API integration tool, with the
  reasoning kept here instead of silently dropped.
- `01-course-packet-and-merge-pdfs.md`: the same kind of reasoning for
  export-course-packet and merge-pdfs, added after the initial retrofit.
- `02-engine-root-resolution.md`: a real bug that shipped (output landing
  in $HOME instead of the project's out/) and the multi-layered fix,
  written up in enough detail that it should not get silently
  reintroduced by a future edit.
- `03-testmaker-to-canvas-quizzes.md`: source-format and quiz conversion decisions.
- `04-imscc-generation.md`: Common Cartridge structure and compatibility.
- `05-canvas-mcp-selection.md`: MCP candidates, selection, and pinning.
- `06-distribution-and-link-qa.md`: sanitized release design, platform scope, and provider-aware media checks.
- `07-iat210-materials-v2.md`: specification-driven, identifier-preserving course-material migration and derived tests.
- `08-assignment-instruction-canaries.md`: gated research and implementation plan for hidden instruction canaries and deterministic received-writing scans.
- `09-iat210-mistral-assignment-qa.md`: Mistral-only student simulation, rubric grading, specificity findings, local Actual-Play revisions, and deferred live synchronization.
- `10-iat210-mistral-course-standards-audit.md`: cited standards profile,
  reproducible Mistral course audit, returned model version, and human review of
  the model's useful findings.
