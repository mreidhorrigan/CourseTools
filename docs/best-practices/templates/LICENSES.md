> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Licenses and third-party inventory: TOOL_NAME

A committed roll-up of every third-party dependency, vendored component, and model weight, with
its SPDX license id. The `vendor/` and `models/` directories are gitignored, so this file is the
only place the dependency surface stays auditable. Update it whenever you add or remove a
dependency or a weight, and review it before any release. See 05-git-and-artifacts.md and
11-suites-and-sharing.md.

## This project

- License: <SPDX id, e.g. MIT> (see LICENSE).

## Python dependencies

Generated from the lockfile. Regenerate with, for example:

```
uv pip list --format=freeze    # or: pip-licenses / a CycloneDX/SPDX SBOM generator
```

| Package | Version | License (SPDX) |
|---|---|---|
| example-lib | 1.2.3 | Apache-2.0 |

## Vendored third-party code (`vendor/`)

| Component | Source / commit | License (SPDX) | Notes |
|---|---|---|---|
| ysfx | github.com/... @ <commit> | ISC / BSD-2-Clause | rebuilt from setup; not committed |

## Model weights (`models/`)

| Model | Source | License (SPDX or note) | Commercial use? |
|---|---|---|---|
| SDXL base 1.0 | stabilityai/stable-diffusion-xl-base-1.0 | CreativeML-Open-RAIL++-M | check terms |
| an optional model v1 | cvssp/optional-model | CC-BY-NC (research) | NO without clearance |
| Stable Audio Open 1.0 | stabilityai/stable-audio-open-1.0 | Stability community license | check terms |

## Release gate

- [ ] Every weight used at release time is cleared for the intended use.
- [ ] No CC-BY-NC / research-only weight ships in a commercial artifact without clearance.
- [ ] This file matches the current lockfile and the actual `vendor/` and `models/` contents.
- [ ] Per-artifact `provenance.json` `license_note` values agree with this roll-up.

> A machine-readable `sbom.json` (CycloneDX or SPDX) generated from the lockfile can sit beside
> this file for tooling; this human table is the at-a-glance audit.
