# Testmaker quiz authoring

`create-quiz` accepts the Testmaker paragraph-tagged format. It remains compatible with the
instructor's earlier `MCQer.html` sources, although this toolkit uses the name Testmaker.
DOCX, Markdown, or plain text. Separate logical entries with blank paragraphs.

```text
[Question.] Which answer is correct?
[Correct.] This one
[Distractor.] Not this one
[Distractor.] Nor this one
```

`[Answer.]` is a synonym for `[Correct.]`. A question without distractors
becomes an essay item; its answer remains only in the local plan as an
instructor key. `[Paragraph.]` creates a zero-point text item in Classic
Quizzes. `[Page break.]` is ignored with a warning because Canvas pagination is
a quiz setting.

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
