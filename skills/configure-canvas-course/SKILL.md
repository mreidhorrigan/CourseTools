---
name: configure-canvas-course
description: Initialize, research, and reconfigure the Canvas Automation Toolkit for one guarded target course. Use when an agent must adapt course URLs, institutional policy links, library resolvers, instructor/course details, canonical course prose, Canvas object mappings, or IMSCC output without making the user hunt through configs.
---

# Configure a Canvas course

1. Read `course/AUTHORING.md`, `course/course.config.jsonc`,
   `course/course-manifest.json`, and `course/links-manifest.json`.
2. If the target has not been initialized, run `scripts/initialize_toolkit.py`
   with explicit arguments or direct the human to run `commands/initialize.command`.
   Never request or store a token.
3. Confirm that the pasted course URL, guarded server health response, manifest
   course ID, and unpublished Canvas course all agree before a write.
4. Treat `course/content/` as authoritative. Treat live Canvas, IMSCC files,
   and `out/` as generated targets. Use `export-live --initialize` only when the
   human explicitly requests a new baseline.
5. Inspect the link manifest by category. Research unresolved institutional
   policies, accessibility services, grading rules, academic integrity,
   privacy, concessions, library access, and calendars using authoritative
   institution or government sources. See `references/reconfiguration.md`.
6. Put reusable target values in `course/course.config.jsonc`; put prose in its
   mapped source file; regenerate `course/links-manifest.json`. Do not hardcode
   target values in scripts.
7. Run `course_authoring.py verify`, review drift, and use the guarded `apply`
   confirmation only with authorization. Build the IMSCC from the same sources.
8. Run link QA, `scripts/audit_portability.py`, and `./verify.command`. Report
   remaining manual Canvas UI checks.

Prefer small reviewed changes. Preserve semantic headings, Canvas migration
link attributes, accessible link text, tables, and attribution. Never expose
credentials, student data, private exports, or unpublished assessment content.
