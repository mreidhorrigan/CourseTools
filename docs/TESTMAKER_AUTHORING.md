# Testmaker quiz authoring

`create-quiz` accepts the Testmaker paragraph-tagged format. It remains compatible with the
instructor's earlier `MCQer.html` sources, although this toolkit uses the name Testmaker.
DOCX, Markdown, or plain text. Separate logical entries with blank paragraphs.

Printable PDF and DOCX output uses the original JavaScript MCQer renderer. Python handles
validation, Canvas conversion, deterministic pool selection, and the temporary interchange file;
JavaScript retains the established page geometry and pagination behavior.

```text
[Question.] Which answer is correct?
[Correct.] This one
[Distractor.] Not this one
[Distractor.] Nor this one
[Distractor.] Or this one
[Bloom.] Apply
[Material.] W01-R1
```

`[Answer.]` is a synonym for `[Correct.]`. A question without distractors
becomes an essay item; its answer remains only in the local plan as an
instructor key. `[Paragraph.]` creates a zero-point text item in Classic
Quizzes. `[Page break.]` is ignored with a warning because Canvas pagination is
a quiz setting.

Instructor-ready assessment sources add exactly one `[Bloom.]` value and one
or more comma-separated `[Material.]` identifiers to every question. Accepted
Bloom levels are Remember, Understand, Apply, Analyze, Evaluate, and Create.
Run `scripts/validate_question_pool.py SOURCE --expect-questions N
--assessment-ready`; this requires exactly one correct answer, exactly three
distractors, material traceability, and guaranteed use of all six levels.

## Fixed versions

Prefix an entry with `[Only Version A.]` through `[Only Version E.]`. Shared
entries have no version tag. Set `fixed_version` in the command config and run
once per desired version. The selected letter is appended to the title by
default. A tagged source without `fixed_version` fails safely instead of
silently merging versions.

## Random pools

```text
[Each version take 1 of the following options.]

[Option.] [Question.] First pool question [Answer.] key

[Option.] [Question.] Second pool question [Answer.] key
```

`[Scramble the following options.]` creates a group that takes every option in
random order. Pool points are configured once because Canvas assigns points at
the group level. Pools require Classic; the public New Quiz Items API does not
provide creation of random item-bank selection blocks.

For a randomized ten-question Canvas quiz, use ten target-specific pools. Each
pool contains two equivalent variants tagged with one shared `[Target.]`
identifier, and Canvas draws one. Assign the ten pools across Remember,
Understand, Apply, Analyze, Evaluate, and Create in a 1/2/2/2/2/1 pattern. This
selects 10 of 20 candidates, preserves Bloom balance for every student, and
prevents one learning target from appearing twice in an attempt.

Use `scripts/testmaking_authoring.py apply-settings --confirm
SYNC-TESTMAKING-COURSE_ID` when dates, attempts, timing, answer visibility, or
publication state change without a question-bank change. Use `apply` when the
questions or group structure change; it saves a private backup before replacing
the mapped quiz content. Both commands refuse to modify a published course.

## DOCX images

Inline DOCX images are extracted from Word relationships, uploaded to the
course `quiz-images` folder, and replaced by authenticated Canvas file URLs.
Use meaningful image filenames and descriptive surrounding text; the source
format has no dedicated alt-text tag. Images upload only during a live run.

## Safe workflow

Keep `dry_run: true` and inspect `conversion-plan.json` for question types,
points, answers, pools, versions, and warnings. Then select `classic` or `new`,
switch off dry-run, and create the quiz unpublished in a sandbox. Creation is
not idempotent: rerunning a successful command creates another quiz.
