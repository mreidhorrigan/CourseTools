# Testmaker to Canvas quiz conversion

## Decision

Use the documented Classic Quizzes REST API, not a generated Common Cartridge,
for the first implementation. It fits this repository's existing token-in-memory
architecture, produces native editable Canvas objects, and exposes the exact
question-group operation needed for Testmaker's take-N pools.

Canvas documents three relevant endpoints:

- create/edit a quiz: https://developerdocs.instructure.com/services/canvas/resources/quizzes
- create quiz questions, including `quiz_group_id`: https://developerdocs.instructure.com/services/canvas/resources/quiz_questions
- create question groups with `pick_count` and `question_points`: https://developerdocs.instructure.com/services/canvas/resources/quiz_question_groups

Question groups preserve the useful meaning of Testmaker's
`[Each version take N of the following options.]`: Canvas randomly selects N
questions from the group for each student. They do not reproduce fixed paper
versions A/B/C. `[Only Version X.]` therefore fails validation instead of being
silently changed.

## Safety and reproducibility

The deterministic artifact is `conversion-plan.json`. A dry run needs neither
a token nor a network connection. Live creation makes the quiz unpublished,
populates it, and publishes only after all calls succeed. The default
`rollback_on_error` deletes the incomplete unpublished quiz on failure.

The source parser uses only Python's standard library. DOCX text and drawing
relationships are read directly from the WordprocessingML ZIP; `.md` and `.txt`
use Testmaker's blank-line paragraph rule. Embedded images are uploaded through
Canvas's documented three-step File Upload flow and question HTML is rewritten
to the returned Canvas URL. The source is never modified. Underline formatting
is not semantically required by the quiz format and is flattened.

`quiz_engine: "new"` uses the New Quizzes and New Quiz Items APIs for choice
and essay items. Its payload UUIDs are derived deterministically. The public
items API does not expose creation of random selection blocks, so take-N pools
remain a Classic Quizzes feature and fail explicitly in New Quiz mode.

- https://developerdocs.instructure.com/services/canvas/resources/new_quizzes
- https://developerdocs.instructure.com/services/canvas/resources/new_quiz_items
- https://developerdocs.instructure.com/services/canvas/basics/file.file_uploads
