# Project TODO

## Deferred infrastructure

- [ ] Replace Flask's development server with a production-quality local WSGI
  server while preserving loopback-only binding, in-memory token handling,
  graceful shutdown, macOS `.command` behavior, health reporting, and the
  single-course guard. Add lifecycle and failure-mode tests, lock the dependency,
  update operator/security documentation, and verify that no credentials are
  persisted or logged. This is intentionally deferred from the IAT 210 sandbox
  replacement work because it is a separate infrastructure change.

## IAT 210 assignment-integrity research

- [ ] Research, policy-review, accessibility-test, and implement the configurable
  instruction-canary proposal described in `research/08-assignment-instruction-canaries.md`.
  Do not activate hidden canaries or submission scanning until the documented
  accessibility, notice, false-positive, privacy, and institutional-policy gates pass.
- [ ] If approved, add syllabus language directing students to work from the
  assignment page and prohibiting copying the assignment instructions into a
  submission, prompt, working document, or other file. Preserve legitimate
  accessibility, accommodation, translation, offline-access, and note-taking routes.
- [ ] If approved, add deterministic injection, verification, received-writing
  scanning, reporting, and removal scripts driven by one versioned dictionary of
  obsolete or invented canary terms, beginning with `falsiloquence`.
