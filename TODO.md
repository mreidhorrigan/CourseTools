# Project TODO

## Deferred infrastructure

- [ ] Consider porting MCQer's proven JavaScript spatial formatting and
  pagination renderer to Python only if maintaining the Node backend becomes a
  material portability or maintenance burden. Preserve byte-tested visual and
  pagination parity before changing the authoritative backend.

- [x] Run the Flask application under the pinned Waitress WSGI server while
  preserving loopback-only binding, in-memory token handling, macOS `.command`
  behavior, health reporting, and the single-course guard.
- [x] Add concise access notifications to the WSGI server window after current
  sandbox testing concludes. Each notification should show the HTTP method,
  route path, response status, and elapsed time. Never log authorization data,
  API tokens, request or response bodies, or query-string values. Add automated
  tests and operator documentation, and make the change effective on the next
  server restart without weakening loopback binding or the course guard.

## IAT 210 assignment-integrity research

## IAT 210 curriculum-design research

- [ ] Evaluate an interactive digital narrative (IDN) pathway as an alternative
  or addition to the procedural-ecology videogame-design round. Use the scope
  and decision criteria in `course/research/idn-videogame-design-option.md`.

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
