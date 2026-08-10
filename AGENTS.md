# Agent operating notes

Read `index.html`, `README.md`, `docs/SECURITY.md`, and the relevant config and
schema before acting.

For course prose, treat `course/content/` as authoritative. Read
`course/course-manifest.json` before editing and update `course/links-manifest.json`
with `scripts/course_authoring.py refresh-links`. Never treat live Canvas, an
IMSCC, or `out/` as the prose source unless the user explicitly requests a new
baseline export.

For real assessment questions and answers, treat `private/testmaking/` as authoritative. Never
move assessment sources, keys, or generated forms into `course/`, `examples/`, or a distribution.

For a new institution, course URL, policy set, or library environment, follow
`skills/configure-canvas-course/SKILL.md`. Research flexible institutional
values from authoritative sources and keep them in the central course config,
canonical prose, and regenerated link manifest.

- Work from stored configs and scripts. Save substantive new automation under
  `src/`, `scripts/`, or `commands/`, with tests under `tests/`.
- Use dry runs and offline IMSCC builds before live Canvas writes.
- Never ask for a Canvas token in chat. The deterministic server receives it at
  a hidden local prompt. The optional MCP launcher reads it from macOS Keychain.
- Confirm the Canvas host, pasted sandbox course URL, numeric course ID, and
  publication state before a write. The deterministic server must enforce its
  one-course guard.
- Prefer deterministic scripts or IMSCC for repeatable or bulk work. Use MCP for
  discovery and small reviewable actions.
- Never infer permission to modify another course. Back up content and inventory
  exact object IDs before destructive work.
- Run `./verify.command` after changes. Run provider-aware external link checks,
  Canvas Link Validator, Student View, and accessibility QA before release.
- Keep the macOS path first-class. Label Linux CLI support and experimental
  Windows CLI support accurately. Do not put platform-specific code in `src/`.
