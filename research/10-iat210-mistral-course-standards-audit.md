# Mistral standards audit of IAT 210

Date: 2026-08-16

## Purpose and reproducibility

`scripts/mistral_course_standards_audit.py` builds three deterministic text
packets from the authoritative direct-authoring layer, sends each packet and the
cited standards profile to Mistral, and requests a fourth synthesis pass. The
script preserves packet hashes, packet text, every raw response, API metadata,
parsed JSON, and a readable report. It reads `MISTRAL_API_KEY` only from the
environment and does not write the key to an output.

This run is stored outside the public distribution at:

`out/course-development/mistral-course-standards-audit/20260816T093954Z__course-audit/`

The requested model alias was `mistral-small-latest`. Every successful API
response returned `mistral-small-latest` as the model identifier. Mistral's API
did not return an immutable dated build in this run, so a more precise model
version cannot be claimed. The result records the exact returned identifier,
request metadata, and usage metadata for each call.

## Standards researched and supplied to Mistral

The complete, reusable prompt source is
`research/standards/course-audit-standards.md`. It records the following
frameworks and scope limits:

1. **Quality Matters Higher Education Rubric, Seventh Edition.** The audit used
   the eight publicly listed General Standards and QM's central alignment
   principle: course overview; objectives; assessment; materials; activities
   and interaction; technology; learner support; and accessibility/usability.
   The detailed proprietary rubric was not supplied, and this is not a QM
   review or certification.
   Source: https://www.qualitymatters.org/qa-resources/rubric-standards/higher-ed-rubric
2. **OSCQR.** The audit used the published formative-review areas: overview and
   information; technology and tools; design and layout; content and
   activities; interaction; and assessment and feedback.
   Source: https://oscqr.suny.edu/
3. **WCAG 2.2.** The audit used perceivable, operable, understandable, and
   robust as its accessibility structure, with course-specific checks for
   alternatives, captions/transcripts, semantics, link purpose, contrast,
   keyboard use, consistency, and accessible documents. Model review cannot
   establish WCAG conformance.
   Source: https://www.w3.org/TR/WCAG22/
4. **CAST Universal Design for Learning Guidelines 3.0 (2024).** The audit
   reviewed engagement, representation, and action/expression, including
   learner agency, choice, belonging, accessible representations, graduated
   support, planning, progress monitoring, and action-oriented feedback.
   Sources: https://udlguidelines.cast.org/ and
   https://udlguidelines.cast.org/more/downloads/
5. **SFU workload and student-facing policy guidance.** The audit used SFU's
   emphasis on transparent total workload for online and in-person courses,
   together with current academic-integrity information. The historical
   three-unit benchmark in the cited Senate paper is about nine total learning
   hours per week and explicitly acknowledges variation by learner, week, and
   course format.
   Sources:
   - https://www.sfu.ca/content/dam/sfu/senate/senate-documents/2022/0404/S.22-47.pdf
   - https://www.sfu.ca/students/academicintegrity/faculty/prevention/syllabus.html
   - https://www.sfu.ca/students/enrolment-services/academic-integrity.html

The standards were supplied as review criteria rather than as equivalent or
fully testable compliance regimes. Mistral was instructed to cite local course
evidence, distinguish defects from absent evidence, and avoid legal or
certification claims.

## What Mistral found that was useful

Human review confirmed three useful lines of inquiry:

1. **Required-media accessibility is still provisional.** Week 2 says that
   caption/transcript availability “must be confirmed before term,” and Week 3
   says YouTube captions “should be reviewed before term.” Every weekly access
   notice describes what required media *should* have. Mistral correctly
   classified this as unconfirmed evidence rather than demonstrated
   inaccessibility. A human must inventory required audiovisual and interactive
   materials, check captions/transcripts and keyboard access, record exceptions,
   and provide equivalent routes before publication.
2. **Reading inputs and weekly workload distribution need a human balancing
   pass.** Mistral noticed provisional book-excerpt estimates in the workload
   configuration. Direct verification found a wider issue: the automatic
   allocator makes every weekly total exactly 450 minutes while assigned
   reading ranges from zero words in Weeks 7 and 12 to 30,861 words in Week 6.
   That mechanism is transparent in the configuration, but equal totals can
   conceal unusually concentrated reading and assume project time contracts to
   compensate. Replace all provisional estimates with measured accessible
   copies, review peak reading weeks, and validate task-duration assumptions
   with humans.
3. **An annotated assessment example could improve transfer from prose to
   evidence.** Mistral recommended an example connecting an actual-play event,
   timestamped transcript, evidence map, and rubric criterion. The current plan
   defines a consequential choice and the final-submission instructions explain
   timestamped evidence precisely, so the requirement is not ambiguous in the
   way Mistral first claimed. A short annotated example would still provide
   graduated support and make the expected evidence relationship easier to
   recognize without lowering the criterion.

Mistral also appropriately called for human checks of captions and transcripts,
document accessibility, assistive-technology behavior, workload experience,
and final-examination alignment. These checks cannot be completed from extracted
prose alone.

## Findings rejected or qualified during human verification

The audit also demonstrates why model findings require source verification:

- The claimed 7.5-versus-7.7-hour inconsistency is unsupported. Current weekly
  pages all state about 7.5 hours.
- The claimed absence of weekly links and a due-date overview is unsupported.
  The syllabus contains a linked weekly schedule and dated quiz links, and each
  weekly page links back to that schedule.
- The claimed absence of quiz purpose and final-examination details is
  unsupported. The syllabus describes formative retrieval practice, quiz
  settings, availability windows, exam weighting, scope, and a link to the
  60-question/90-minute examination instructions.
- The claimed absence of SFU academic-integrity and accessibility links is
  unsupported. The syllabus links SFU academic-integrity rules and reporting,
  the Centre for Accessible Learning, and academic-concessions guidance.
- The proposed project estimate of 20–25 hours was invented by the model. No
  such number should be added without calculation and human validation.
- The claim that peer-review prompts lack rubric alignment is overstated. The
  ideation rubric includes peer development, and the discussion requires two
  replies with a strength, risk, and next step. Further specificity remains a
  design choice rather than a demonstrated defect.
- Choice of submission format cannot be inferred to be a UDL defect where a
  format is part of a media-production learning outcome. Alternatives should be
  evaluated against outcomes and accommodation needs rather than added
  mechanically.

## Decision

Retain the deterministic audit as a repeatable external-reader check. Address
the verified media-accessibility inventory and reading/workload balancing before
publication. Consider an annotated actual-play evidence example. Treat other
model recommendations as research prompts unless a human can reproduce them in
the authoritative course sources or live Canvas behavior.
