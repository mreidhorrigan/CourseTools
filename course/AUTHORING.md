# Direct course authoring

Files under `content/` are the authoritative course prose. Edit them directly with a text editor
or AI. They contain Canvas-safe HTML so tables, internal links, accessibility markup, and inline
styles survive without a lossy conversion. Ordinary prose appears between the tags and can be
edited without changing the tags.

`course-manifest.json` maps every source file to its Canvas object and IMSCC resources.
`links-manifest.json` inventories course-specific and external links and is regenerated from the
authoritative prose. `course.config.jsonc` is the single target-course configuration.

Run these from the toolkit root:

```sh
.venv/bin/python scripts/course_authoring.py verify
.venv/bin/python scripts/course_authoring.py apply --confirm SYNC-AUTHORING-COURSE_ID
.venv/bin/python scripts/course_authoring.py build-imscc
```

Run `export-live --initialize` only when intentionally establishing or replacing the authoring
baseline from the guarded Canvas course. Normal editing flows from `content/` to Canvas and IMSCC.
Generated packages and `out/` are never authoritative.

Assessment questions and answers are intentionally outside this course-content tree. Their shared
human/AI authoring location is `private/testmaking/`; see `docs/TESTMAKING.md`. Do not move answer
material under `course/`, because course content may be packaged or uploaded for student access.
