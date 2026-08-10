# Reconfiguration research

## Research targets

- Institution homepage and official Canvas host
- Academic calendar, term dates, closures, and examination period
- Accessibility or disability-support office
- Academic integrity policy and reporting procedure
- Grade scale and grade-appeal policy
- Privacy, intellectual-property, conduct, and academic-concession policies
- Library resolver behavior and stable open-access alternatives
- Course outline, instructor contact information, delivery mode, and location

Use primary institutional pages. Record stable human-facing URLs in canonical
course prose and let `refresh-links` collect their occurrences. Put search or
resolver hosts in `course.config.jsonc`; do not present a search-results URL as
a validated reading.

## Deterministic sequence

```sh
.venv/bin/python scripts/course_authoring.py verify
.venv/bin/python scripts/course_authoring.py refresh-links
.venv/bin/python scripts/course_authoring.py build-imscc
./verify.command
```

With explicit authorization and a matching guarded server:

```sh
.venv/bin/python scripts/course_authoring.py apply --confirm SYNC-AUTHORING-COURSE_ID
```

After applying, rerun `verify`. Use Canvas Link Validator, Student View, and
manual accessibility review before production release.
