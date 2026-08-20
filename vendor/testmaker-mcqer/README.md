# Vendored MCQer printable renderer

This directory contains the original headless MCQer JavaScript renderer written
by M. Horrigan and used by Testmaker as its authoritative PDF and DOCX backend.
It preserves the spatial formatting and pagination behavior developed and
user-tested in MCQer.

Source copied from `DOC_TOOLS/mcqer.js`. The source file copied for this
integration had SHA-256
`5467388e0d3b789c074c39ddfb8ce08985e94b95251c36d4577a3aaa880ba7ba`.

CourseTools makes four contained adaptations:

1. Accept a clean HTML interchange file after Python resolves private
   Testmaker pools and version assignments.
2. Seed MCQer's original Fisher-Yates shuffling so identical inputs produce
   identical forms and answer keys.
3. Include the renderer's existing inter-block spacing in its question-group
   height calculation, including the answer-key prefix, so a complete group
   moves before reaching a page edge.
4. Apply `[Only Version X.]` filtering to explanatory paragraphs as well as
   questions, allowing resolved per-version interchange without duplication.

Install the locked dependencies with `npm ci --omit=optional` in this
directory. Do not edit files under `node_modules`; that directory is generated
and excluded from version control and distributions.
