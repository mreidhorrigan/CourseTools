# IAT 210 materials-registry migration

## Source and scope

The course-specific builder consumes the instructor's `IAT210-Fall2026-CODEX-MATERIALS-SPEC.md` and verifies that the baseline cartridge has the SHA-256 recorded in that specification. It produces a new cartridge and never overwrites v1.9.1.

```sh
.venv/bin/python scripts/build_iat210_materials_update.py \
  --baseline input/imscc/IAT210-Fall2026-Canvas-v1.9.1.imscc \
  --spec /path/to/IAT210-Fall2026-CODEX-MATERIALS-SPEC.md \
  --output out/iat210-materials-v2/IAT210-Fall2026-Canvas-v2.0-draft.imscc
```

The first pass implements the specification's safe subset:

- preserve the 13 page resource IDs and 13 module IDs;
- rewrite week pages and retitle their module/manifest entries;
- publish only fully scoped `required` materials;
- label `recommended` and `optional` materials as not examined;
- omit `TODO` and `required_pending_scope` items from required lists;
- synchronize `course_settings/syllabus.html` and the syllabus wiki page;
- preserve all assessment weights, dates, quizzes, rubrics, assignments, and discussions;
- leave project module references in their baseline weeks until the instructor resolves the project-date mismatch.

Each material is visibly marked by its stable registry ID; an HTML comment also aids offline diffs, although Canvas may strip comments during import. Week pages include access-route and accommodation guidance without claiming that an unresolved accessibility audit has passed.

## Tests derived from the real migration

`tests/test_iat210_materials_update.py` proves:

- two builds have identical bytes;
- every archive member outside the explicit page/syllabus/module/manifest allowlist remains byte-identical to v1.9.1;
- no student-facing week page contains `TODO`;
- both syllabus copies are identical;
- all XML parses;
- stable material markers exist; and
- the known unavailable Vimeo item is absent from the new Week 3 page.

The live sandbox acceptance sequence remains backup, guarded import, migration-issue review, authenticated internal validation, provider-aware external-link validation, and manual Student View/accessibility review.
