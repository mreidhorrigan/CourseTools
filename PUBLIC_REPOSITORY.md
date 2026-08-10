# Publishing this toolkit as a public GitHub repository

Use the contents of `release/canvas-automation-toolkit.zip` as the source of a new public repository. Do not publish the development checkout directly. The release builder starts from an allowlist, sanitizes the active Canvas target, scans nested archives, and excludes Git history, credentials, private assessment authoring, generated reports, Canvas backups, virtual environments, and local working output.

## What the public release includes

- Reusable source code, commands, documentation, schemas, and dependency locks.
- Invented automated software tests and fixtures under `tests/` and `input/assignment-qa.example/`. These are useful for continuous integration and contain no student or exam data.
- An attributed IAT 210 example course starter governed by the notice in `examples/iat210/README.md`. It is an AI-generated, non-production example and intentionally contains public course and instructor information.
- License notices, a CycloneDX SBOM, a content manifest, and `DISTRIBUTION-SAFETY.json`.

## What the public release excludes

- Canvas and Mistral API keys, `.env` files, Keychain data, and local server memory.
- Real Testmaker questions, answer mappings, exam forms, answer keys, and testmaking output under `private/` or `out/`.
- Student work, names, identifiers, grades, rosters, submissions, accommodation information, and Mistral QA reports.
- The development repository's `.git` history and the instructor's unrestricted IMSCC inputs or Canvas backups.

The tracked `tests/` directory is software test code. It should normally remain public. “Test data” in the security boundary means real assessment content and student-derived data, which the release excludes.

## Publication procedure

1. Run `./verify.command` in the development checkout.
2. Run `commands/build-distribution.command` or `.venv/bin/python scripts/build_distribution.py`.
3. Confirm that `release/provenance.json` and the printed SHA-256 agree.
4. Unzip `release/canvas-automation-toolkit.zip` into a new empty directory.
5. Open `DISTRIBUTION-SAFETY.json`; require `"status": "PASS"`.
6. Review `DISTRIBUTION-MANIFEST.json`, `LICENSES.md`, and `examples/iat210/README.md`.
7. Initialize a new Git repository inside that extracted directory. Do not copy the development checkout's `.git`, `private`, `out`, `release`, `.venv`, or credential files.
8. Before each push, inspect `git status --short` and `git ls-files`. Enable GitHub secret scanning and push protection when available.

If real course or student data is ever added to a public clone, removing the current file is insufficient after a push because Git history retains prior blobs. Revoke any exposed credential immediately and follow GitHub's documented sensitive-data removal process before making the repository public again.
