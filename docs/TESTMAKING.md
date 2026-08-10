# Testmaking toolkit

Canvas Automation includes Testmaker, a deterministic, AI-optional assessment workflow. One Testmaker-tagged `.docx`, `.md`, or `.txt` source feeds Canvas and printable PDF forms.

## Recommended workflow

1. After connecting the guarded server, run `commands/initialize-testmaking.command` to create the
   private baseline from the target course. Author the mapped `.md` files under `private/testmaking/questions/`. Humans
   and AI edit the same sources; `private/testmaking/testmaking-manifest.json` maps them to Canvas
   quizzes and PDF settings. Git ignores these files; back them up in instructor-controlled
   encrypted storage rather than a shared toolkit repository.
2. Run `scripts/validate_question_pool.py SOURCE --expect-questions 10 --json-out out/question-QA.json`. Fix every error and review warnings editorially.
3. Edit `commands/build-test-forms.config.jsonc`, then run `commands/build-test-forms.command`; AIs may invoke the equivalent CLI or `scripts/build_test_forms.py`. The fresh output includes forms, keys, a manifest recording the source hash and seed, and provenance.
4. Run `create-quiz.command` in dry-run mode. Review its conversion plan, then create the unpublished Canvas quiz.
5. Preview every Canvas question and PDF. Content validity, ambiguity, accessibility, reading alignment, and distractor plausibility require human review.

## Assessment-data boundary

Real questions, answers, quiz mappings, generated forms, answer keys, and Canvas backups belong
under `private/` or `out/`. Canvas Automation's distribution builder rejects either path if it reaches a package.
Do not put those materials under `course/`, `examples/`, or `input/`. The distributable
`input/example-testmaker-quiz.md` contains invented demonstration data and is safe to share.

An IMSCC containing populated quizzes can include correct answers. Treat locally built course
packages as instructor-only unless a separate content audit establishes that they contain no
assessment keys. Canvas Import can use such a package; do not publish it in student-visible Files.

For a configured course, `scripts/testmaking_authoring.py verify` validates all mapped sources and
compares their question counts to guarded Canvas. `build-pdf` builds every mapped form. Guarded
`apply` backs up the current questions, then replaces questions in the mapped unpublished quizzes;
it requires the course-specific `SYNC-TESTMAKING-ID` confirmation.

`[Only Version A.]` through E are honored for paper forms and by Canvas `fixed_version`. Take-N pools create randomized paper selections and native Classic Quiz question groups; Canvas draws independently for each student. To give each student 10 questions, use a pool larger than 10 with `Each version take 10`, then verify the live group has `pick_count=10`. Never publish a nominal ten-question quiz whose approved pool cannot supply ten.

This Testmaker implementation adapts the documented tagged format and general validation practices from the instructor's existing testmaking workflow. Testmaker retains compatibility with earlier MCQer files. Private readings, prior exams, student data, and unlicensed DOC_TOOLS or legacy MCQer implementation source are not redistributed. This Testmaker implementation is MIT-licensed; ReportLab generates PDFs and appears in the generated SBOM.

DOCX image tags are supported by the Canvas quiz upload path. The printable PDF
builder currently renders image tags as text references; add and verify those
images manually before using a paper form. Grammar, factual accuracy, answer-key
validity, accessibility, and distractor quality remain human review gates.
