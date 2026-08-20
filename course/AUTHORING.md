# Direct course authoring

Files under `content/` are the authoritative semantic course prose. Edit them directly with a
text editor or AI. Presentation rules live separately in `styles/canvas.css`. Authoring files
must not contain `<style>`, stylesheet `<link>`, or inline `style` attributes. The deterministic
build applies the shared CSS cascade and emits Canvas-compatible inline styles only in generated
HTML, live API payloads, and IMSCC packages.

`course-manifest.json` maps every source file to its Canvas object and IMSCC resources.
`links-manifest.json` inventories course-specific and external links and is regenerated from the
authoritative prose. `course.config.jsonc` is the single target-course configuration.

Run these from the toolkit root:

```sh
.venv/bin/python scripts/course_authoring.py verify
.venv/bin/python scripts/course_authoring.py compile
.venv/bin/python scripts/course_authoring.py apply --confirm SYNC-AUTHORING-COURSE_ID
.venv/bin/python scripts/course_authoring.py build-imscc
```

Run `export-live --initialize` only when intentionally establishing or replacing the authoring
baseline from the guarded Canvas course. Normal editing flows from `content/` to Canvas and IMSCC.
Generated packages and `out/` are never authoritative.

`compile` writes a fresh `out/course-compiled/<timestamp>/` directory containing the exact HTML
that Canvas will receive and a hash manifest linking every compiled file to its semantic source
and stylesheet. The compiler disables network access. During `apply`, Canvas's `preview_html`
endpoint processes each changed fragment before the guarded update is sent.

Assessment questions and answers are intentionally outside this course-content tree. Their shared
human/AI authoring location is `private/testmaking/`; see `docs/TESTMAKING.md`. Do not move answer
material under `course/`, because course content may be packaged or uploaded for student access.
