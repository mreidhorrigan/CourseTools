# Licenses and third-party inventory

This file is the human-readable dependency and license roll-up for Canvas
Automation. The release builder also writes `sbom.json` into each distribution
ZIP. Update both from the locked environments before a release.

## This project

- Canvas Automation: MIT. See `LICENSE`.
- No model weights or vendored source are included.
- This toolkit's Testmaker implementation follows the documented tagged interchange
  format and general QA practices from local instructor workflows. It does not
  redistribute the legacy MCQer.html application, DOC_TOOLS source, private readings, prior exams, or
  student data. Those sources retain their respective rights and licenses.
- The house-style tokens and slime artwork are supplied by Matthew Horrigan.
  The slime artwork and `assets/slime-widget.js` remain copyright Matthew Horrigan and are not
  covered by the toolkit's MIT software license.
- `docs/BEST_PRACTICES_HANDBOOK.md` is adapted from *Tooling Handbook*, copyright © 2026 Matt
  Horrigan. The source and adaptation are licensed under CC BY-SA 4.0; the adapted file states
  the changes and links to the license.
- `examples/iat210/IAT210-Fall2026-example-course-starter-v2.0.imscc` is an AI-generated example
  course starter, copyright © 2026 M. Horrigan, licensed under CC BY 4.0 with attribution
  required. It is not a production course. See `examples/iat210/README.md` for limitations,
  attribution text, checksum, and third-party exclusions.
- Instructure, Canvas, Vimeo, YouTube, and the MCP project retain their own
  names, marks, services, code, and documentation. Links do not imply endorsement.
- Mistral AI retains its service, models, names, and API documentation. The optional
  assignment-and-rubric QA harness calls that external service through Requests; no
  Mistral SDK, model weights, or Mistral source code are bundled. API use is governed
  by Mistral's current service terms and the user's account.

## Deterministic engine

Exact versions and artifact hashes are pinned in `uv.lock`.

| Direct package | Declared range | License (SPDX) |
|---|---:|---|
| Flask | `>=3.0,<4.0` | BSD-3-Clause |
| Requests | `>=2.31,<3.0` | Apache-2.0 |
| pypdf | `>=4.0` | BSD-3-Clause |
| ReportLab | `>=4.0` | BSD-3-Clause |
| Beautiful Soup | `>=4.12` | MIT |
| openpyxl | `>=3.1` | MIT |
| lxml | `>=5.0,<7.0` | BSD-3-Clause |
| Waitress | `>=3.0,<4.0` | ZPL-2.1 |
| pytest (development extra) | `>=8.0` | MIT |

Transitive packages and their exact versions appear in `sbom.json`. Their
license expressions come from package metadata and the SPDX mappings maintained
by `scripts/build_distribution.py`.

## Optional Canvas MCP

| Component | Pin | Source | License (SPDX) |
|---|---:|---|---|
| `canvas-mcp` | See `mcp/requirements.lock` | https://github.com/vishalsachdev/canvas-mcp | MIT |

Canvas MCP is an independent third-party server. It is optional and is not an
Instructure product. Its environment is separate from the deterministic engine.
Review its upstream license, security policy, release notes, and transitive
dependency changes before updating the pin.

## Release gate

- Confirm `uv.lock` and `mcp/requirements.lock` are committed.
- Run `./verify.command`.
- Build twice and compare the ZIP SHA-256 values.
- Inspect `DISTRIBUTION-MANIFEST.json` and `sbom.json` inside the ZIP.
- Confirm that no token, virtual environment, generated output, `.git` data, or undisclosed
  course-specific working material is present. The intentionally included IAT 210 course starter
  must retain its notice, checksum, and license.
