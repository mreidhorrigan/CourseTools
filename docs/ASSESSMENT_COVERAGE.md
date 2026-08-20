# Assessment coverage and private-material format

Real assessment specifications belong in `private/testmaking/assessment-blueprint.json`.
Git and collaborator distributions exclude that directory. The tracked schema is
`docs/schemas/assessment-blueprint.schema.json`.

The blueprint is the authoritative map of:

- each material's stable ID, week, title, access route, local stored copy, and rights status;
- exactly which material IDs each quiz or examination tests;
- question count, candidate-pool size, time limit, attempt limit, and availability window;
- target-specific random groups and their Bloom-level distribution; and
- the private Testmaker source and generated-output locations.

Use stable material IDs already shown to students, such as `W03-R2`. Give each
course-authored week page an ID such as `W03-PAGE`. A material is examinable only
when `testable` is true and its ID appears in an assessment's `material_ids`.
Recommended or optional material remains unexamined unless the course syllabus and
blueprint are deliberately revised together.

Run `scripts/download_test_materials.py` to copy local sources and download lawful
remote sources into `private/testmaking/materials/`. The resulting
`download-record.json` stores hashes, media types, and failures. A DOI metadata
record or paywalled landing page does not establish that the full text was reviewed;
questions must be grounded in a stored, instructor-reviewed source.

The LLM handoff file may contain citations, learning objectives, constraints, and
the requested output schema. Keep full copyrighted works, existing questions,
answers, and keys out of online chatbot uploads unless institutional policy and the
rightsholder permit that use.
