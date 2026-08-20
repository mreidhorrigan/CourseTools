# Canvas API research: the four create-* endpoints

Confirmed directly against Instructure's current API reference before writing
`src/canvas_automation/canvas_client.py` and `server.py`. Instructure moved
their docs from `canvas.instructure.com/doc/api/` to
`developerdocs.instructure.com/services/canvas/` in mid-2026; the links
below are the current location. All four endpoints sit under
`/api/v1/courses/:course_id/<resource>` and authenticate with an
`Authorization: Bearer <token>` header.

## Assignments

`POST /courses/:course_id/assignments`, body nested under `assignment`:
`assignment[name]`, `assignment[description]`, `assignment[points_possible]`,
`assignment[due_at]` (ISO 8601), `assignment[submission_types][]`,
`assignment[published]`, and so on. The response includes `html_url`, so
create-assignment can print a working link directly.
https://developerdocs.instructure.com/services/canvas/resources/assignments

## Rubrics: the one genuine gotcha

`POST /courses/:course_id/rubrics` takes two top-level objects: `rubric`
and `rubric_association`. The association is not optional in practice: a
rubric fundamentally lives in a context (a course or an account) and is
then optionally linked further to an assignment, so create-rubric.config.jsonc
always sends one, defaulting to `association_type: "Course"` with
`purpose: "bookmark"` so a rubric can be created before an assignment
exists to attach it to.

The real trap is `rubric[criteria]`. Instructure's own docs describe it as
an indexed Hash of RubricCriteria objects, where the keys are integer ids,
not a JSON array. In form-encoding terms that is
`rubric[criteria][0][description]=...`, which is how Rails-style nested
params represent a hash-like structure; the JSON equivalent is nested
objects keyed "0", "1", "2", and the same is true one level deeper for
each criterion's `ratings`. Sending a plain JSON array for either field is
the single most common way this endpoint silently misbehaves, because the
receiving code expects a hash and gets an array instead.

This project keeps that translation in exactly one place,
`build_rubric_criteria_hash()` in `canvas_client.py`, so a config author
never has to think about it: `create-rubric.config.jsonc` writes criteria
as an ordinary list, and the server converts it before the request goes
out. The response is also nested one level deeper than the other three
resources: `{"rubric": {...}, "rubric_association": {...}}`, which is why
`cli.py` reads `created["rubric"]["id"]` rather than `created["id"]`.

https://developerdocs.instructure.com/services/canvas/resources/rubrics

## Discussion topics: flat, not wrapped

`POST /courses/:course_id/discussion_topics` takes flat top-level fields
(`title`, `message`, `discussion_type`, `published`, `delayed_post_at`,
`require_initial_post`, and so on), not a nested wrapper key the way
assignments, rubrics, and pages are. A graded discussion adds an
`assignment` sub-object with its own `points_possible` etc. This is why
`build_discussion_payload()` sends the config through almost as is, only
stripping the two bookkeeping keys (`course_id`, `OUT_DIR`) that are not
part of the Canvas payload, instead of reading a named sub-key the way the
other three builders do.

https://developerdocs.instructure.com/services/canvas/resources/discussion_topics

## Pages: wiki_page, and page_id instead of id

`POST /courses/:course_id/pages` takes its body nested under `wiki_page`,
Canvas's internal name for a page (`wiki_page[title]`, `wiki_page[body]`,
`wiki_page[editing_roles]`, `wiki_page[published]`). The config and CLI
just say `page`; `server.py` does the rename before forwarding to Canvas,
so that internal naming detail never surfaces to whoever edits the
config.

Two more differences from the other three resources: the returned object
is keyed `page_id`, not `id` (this is why `_DOWNLOAD_ID_FIELDS` and
`cmd_create_page` special-case it), and there is no `html_url` in the
response, so `cli.py` builds the page's URL manually from the course id
and the returned `url` slug (`.../courses/<id>/pages/<slug>`) rather than
reading one back from Canvas.

https://developerdocs.instructure.com/services/canvas/resources/pages

## Pagination

Canvas paginates list endpoints (used by download-content) with a
standard `Link` response header carrying `rel="next"`, the same mechanism
GitHub's API uses. `CanvasClient.get_all_pages()` follows it until
exhausted rather than assuming a single page of results, which matters
for any course with more than the default page size of assignments,
pages, rubrics, or discussion topics.

## Gradebook export: no documented endpoint exists

Confirmed by searching Instructure's community forums, not just the API
reference: there is no supported, token-friendly API endpoint that
returns the same CSV the Gradebook UI's "Export" button produces.
`POST /courses/:course_id/gradebook_csv`, which shows up in Chrome's
network tab when using that button, is not part of the public API. It
requires a browser-authenticated session with cookies and a CSRF token,
and returns a session-timeout error when called with only a bearer token,
which multiple people on the Instructure Community forums confirm
independently after trying it. `Content Exports`
(`/courses/:course_id/content_exports`) does not cover it either; that
endpoint is for course content packages (Common Cartridge, QTI), not
grades.

The standard workaround, also from that same community discussion, is to
synthesize an equivalent table from three endpoints that are documented:

- `GET /courses/:course_id/assignments`: names, points, and (via published)
  which columns should exist at all.
- `GET /courses/:course_id/enrollments` with `type[]=StudentEnrollment`
  and `include[]=user`: the roster, plus a `grades` object per enrollment
  with `current_score`/`final_score` already included whenever the
  requester has grading permissions (no extra `include` needed for those
  two fields specifically; `current_points` is the one that does need an
  explicit `include[]`).
- `GET /courses/:course_id/students/submissions` with
  `student_ids[]=all` (a documented special value meaning every student in
  the course), `assignment_ids[]=<the ids from the assignments call>`, and
  `grouped=true`: one entry per student, each with a list of that
  student's submissions, letting `course_packet.build_gradebook_rows()`
  build a student x assignment score grid without a separate call per
  assignment.

This does not reproduce assignment-GROUP subtotals the way the UI export
does (people in that same thread note the same limitation), which is
documented in export-course-packet's config rather than silently glossed
over.

https://developerdocs.instructure.com/services/canvas/resources/enrollments
https://developerdocs.instructure.com/services/canvas/resources/submissions
# Private roster and gradebook derivatives

The read-only roster pipeline uses documented endpoints rather than Canvas's
browser-session gradebook export:

- `GET /api/v1/courses/:course_id/enrollments` with active
  `StudentEnrollment` filtering supplies roster identities and whole-course
  grade fields.
- `GET /api/v1/courses/:course_id/sections` resolves section IDs to labels.
- `GET /api/v1/courses/:course_id/assignments` defines gradebook columns.
- `GET /api/v1/courses/:course_id/students/submissions` with
  `student_ids[]=all` and `grouped=true` supplies assignment scores.

Official documentation:

- https://developerdocs.instructure.com/services/canvas/resources/enrollments
- https://developerdocs.instructure.com/services/canvas/resources/sections
- https://developerdocs.instructure.com/services/canvas/resources/submissions

The outputs are private educational records under ignored `out/`; only the
transformations and synthetic tests belong in version control.
