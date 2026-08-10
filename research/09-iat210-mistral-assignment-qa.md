# IAT 210 Mistral assignment-and-rubric QA

## Method

Mistral `mistral-small-latest` performed every simulated student role, grading pass, and specificity audit. GPT did not supply a substitute student response or grade. The student pass received the assignment page and linked syllabus without the rubric. A separate Mistral pass graded the simulated submission against the current rubric. A third Mistral pass compared instructions, expected requirements, submission, and grade.

Generated reports remain under gitignored `out/assignment-rubric-qa/` because later course runs may contain sensitive instructional material. This document records decisions and aggregate results without copying the simulated submissions.

## Harness findings

The first final-submission simulation invented inaccessible ZIP links. Mistral-as-grader correctly declined to score them. The harness now requires a textual dossier that lists and represents the contents of binary deliverables without claiming an upload or inventing a link.

The Mistral free tier repeatedly returned HTTP 429 during the larger course tests. The harness now honors `Retry-After` and otherwise uses configurable bounded exponential backoff. It preserves the active trial rather than silently skipping a student or grading pass.

## Actual-Play baseline

For the 6-point plan, both Mistral students received 6/6. Both audits nevertheless reported medium grading reproducibility and repeatedly identified underspecified playable-situation elements, production responsibilities, dry-run evidence, accessibility evidence, and AI appendix handling.

For the 12-point final, the first gradeable Mistral dossier received 11/12 and the most literal dossier could not be scored because it listed files without representing evidence inside them. Audits repeatedly identified unclear session materials, consent-record formats, test-and-revision evidence, listener orientation and intelligibility, individual analysis, and criterion-specific rating descriptions.

## Local revisions

The assignment pages now provide structured, visible requirements and explain what evidence belongs inside each deliverable. The rubrics retain their original 6-point and 12-point totals while adding criterion-specific long descriptions and rating descriptions. All nine rubrics from the current IMSCC were extracted into editable JSON sources; only the Actual-Play plan and final rubrics were substantively revised in this cycle.

## Revised Mistral results

- Plan: both Mistral submissions received 6/6; both audits rated grade reproducibility high.
- Final: both Mistral submissions received 11.5/12; both audits rated grade reproducibility high.
- Mistral continued to request clarification of “consequential player choice” even though the revised page explicitly defines and requires one. This is retained as a model false positive rather than prompting duplicated prose.

The revised audits still suggest useful later review of examples for testing evidence and the boundary between session materials, access, permissions, and credits. Further cycles should test the Digital Procedural-Ecology and Board-Game sequences before live synchronization.

## Live status

No Canvas write occurred. `course/PENDING-LIVE-UPDATE.md` records the guarded later sequence. Assignment prose can be synchronized through `scripts/course_authoring.py`; rubrics can be planned and updated through `scripts/sync_course_rubrics.py`, which refuses published courses, mismatched course IDs, unknown rubrics, missing grading associations, and rubrics with existing assessments.
