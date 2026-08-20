---
name: author-testmaker-assessments
description: Author, revise, validate, and render private Testmaker quiz and examination sources while preserving answer integrity, Bloom balance, material traceability, and assessment-data safety.
---

# Author Testmaker assessments

1. Read `docs/TESTMAKING.md`, `docs/TESTMAKER_AUTHORING.md`, the private assessment
   blueprint, concept specification, and Testmaker manifest. Keep source questions,
   answers, keys, and generated forms under `private/` or `out/`.
2. Ground every question in its `[Material.]` identifiers. Preserve one correct
   answer, three distinct plausible distractors, the intended `[Bloom.]` level,
   and the stable `[Target.]` identifier during editorial revision.
3. Include an explicit rewording pass after factual drafting. Write each scenario
   as part of a grammatical question. Vary sentence structure and the intellectual
   action requested. Remove generator phrases such as “For this case,” “Which
   course concept,” and repeated Bloom-level templates. Rewording must not alter
   the answer key, difficulty target, source coverage, or construct being tested.
   Check semantic entailment after every rewrite: an analytical observation must
   still ask for analysis, a design decision must still ask for design, and a
   descriptive case must not acquire an unsupported normative premise such as
   “What should the designer do next?”
   Test disciplinary knowledge and reasoning directly. Do not make success depend
   on incidental memorization of course administration, which method happened to
   be “assigned,” or what the instructor called “the course method.” Name the
   relevant concept or method when the question asks students to apply it. Avoid
   vague references such as “the assigned material” when a concept, author, text,
   or analytical operation can be identified precisely.
   Test material taught in the course, while avoiding questions that test whether
   students can discriminate course material from non-course material. A stem must
   remain valid if administrative phrases such as “in this course,” “assigned,” or
   “from the readings” are removed. Identify the substantive concept, source, case,
   or operation needed to answer the question.
   Treat every question as an independent document. Resolve every pronoun,
   possessive, demonstrative, definite reference, and indexical inside that
   question. Do not rely on a preceding question, pool order, or an unstated
   source passage. Name an actual-play recording before writing “the recording”;
   name a concept before writing “this concept”; replace “here,” “above,” “the
   former,” and “the latter” with their referents. A scenario may introduce a
   noun that a later sentence in the same stem refers to.
4. Run `scripts/audit_question_stem_style.py` across all affected sources. Review
   repeated five-word prefixes even when the audit passes. Run the grammar gate
   as the final prose step; `validate_question_pool.py --assessment-ready` rejects
   malformed capitalization joins, duplicated punctuation, repeated whitespace,
   and stems that do not end as questions. Then run
   `scripts/validate_question_pool.py --assessment-ready` with the expected count.
5. Inspect near-duplicate concepts within every random draw group so one student
   does not receive two versions of the same question. Build printable forms and
   review both PDF and DOCX pagination.
6. Require human review for factual accuracy, ambiguity, accessibility, distractor
   plausibility, answer validity, and alignment with assigned materials before a
   guarded Canvas synchronization.

Use AI for contextual rewriting and editorial comparison. Use deterministic scripts
for parsing, invariants, duplication checks, pool construction, rendering, and audit
records. Never send tokens, student data, private exports, or unnecessary copyrighted
materials to an online model.
