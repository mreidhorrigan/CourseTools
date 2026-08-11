> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Tooling Handbook (start here)

The canonical way we build software tools. Read this first, then build the same way every time.

## Why this exists

We kept re-giving the same prompts to AI sessions across many projects: how to lay out
directories, how to wire a double-click launcher, what to commit, how to keep outputs
reproducible. This handbook ends that. It is the **standing prompt**. A new session (human or
AI) reads this file and the [checklist](checklist.md), copies from [templates/](templates/),
and ships a tool that matches the rest of the suite without re-deriving any conventions.

## The prime directive

**AI is used at build and R&D time. The shipped tool runs AI-free and full-featured.**

A person operates the finished tool by double-clicking a `*.command` file and editing a
heavily-commented `*.config.jsonc`. No Claude, no cloud, no network at runtime. The same
headless core takes positional arguments, so a shell script or a lightweight local AI can
drive the exact same tool. One engine, three operators (human, script, agent), zero runtime
model dependency.

Everything below serves that directive and four goals: tools that are easy to **use**,
**extend**, compose into **suites**, and **share**.

## Non-negotiables

- **One `*.command` per major function**, paired with one `*.config.jsonc`. Subtle options
  live in the config. Genuinely different functions are separate files. See
  [03-command-and-config.md](03-command-and-config.md).
- **The config is the whole interface.** Every option lives in the file: active ones
  uncommented, rare ones commented out with a note. The config is the documentation. See
  [04-config-files-jsonc.md](04-config-files-jsonc.md).
- **Determinism is a contract.** Same config plus same seed yields byte-identical output.
  Outputs go to a fresh `out/<name>/<timestamp>/` and are never overwritten. See
  [01-principles.md](01-principles.md).
- **Provenance beside every artifact.** A `provenance.json` (or `manifest.json`) records the
  recipe (inputs, seed, versions, license note) so the artifact is reproducible from its
  recipe in the pinned environment. See [05-git-and-artifacts.md](05-git-and-artifacts.md).
- **Commit the recipe, ignore the bulk, keep the manifest.** Git holds source, configs, and
  manifests. Large regenerable output, weights, vendored builds, and secrets stay out. See
  [05-git-and-artifacts.md](05-git-and-artifacts.md).
- **Reproducible from a fresh clone plus one setup step.** Pin the environment (`uv.lock`),
  make `vendor/` buildable from a setup script, stay relocatable. See
  [06-vendoring-and-linking.md](06-vendoring-and-linking.md).
- **Dual interface, always.** Double-click for a human, positional args for a script or local
  AI. See [08-skills-and-ai-integration.md](08-skills-and-ai-integration.md).
- **AI-free at runtime.** MCPs and APIs are build-time or drive-time conveniences, never a
  runtime requirement of the core tool. See [07-mcp-and-apis.md](07-mcp-and-apis.md).

## Standard project tree

```
TOOL_NAME/
├── README.md              # what / why / setup / use / config / output (per-tool)
├── src/                   # hand-written source (the engine + CLI)
├── bin/                   # thin entry-point wrappers (optional)
├── commands/              # the *.command + *.config.jsonc pairs (or scripts/templates/)
│   ├── _lib.sh            # shared read_config() + launch() helpers
│   ├── _jsonc.py          # string-aware JSONC -> shell loader
│   ├── do-thing.command
│   └── do-thing.config.jsonc
├── out/                   # generated artifacts (gitignored, timestamped, never overwritten)
├── models/                # downloaded weights (gitignored)
├── vendor/                # third-party code, buildable from setup (gitignored)
├── research/              # committed design research, audits, citations, decisions
├── detritus/              # throwaway scratch (gitignored or pruned)
├── archive/               # old-but-kept material
├── .venv/                 # uv virtual env (gitignored)
├── .gitignore             # commit the recipe, ignore the bulk, keep the manifest
├── uv.lock + pyproject.toml   # pinned environment
└── setup-after-move.command   # re-resolve paths after relocating the folder
```

Full detail and the dir-by-dir git status table: [02-project-structure.md](02-project-structure.md).

## How to use this handbook

**A new AI session, on day one:**

1. Read this README and [checklist.md](checklist.md).
2. Copy [templates/](templates/) into the new tool and rename. You now have a runnable
   skeleton (a `*.command`, a commented `*.config.jsonc`, `_lib.sh`, `_jsonc.py`, a
   `.gitignore`, a `setup-after-move.command`, a README, and a project tree).
3. Build the engine in `src/`, expose one `*.command` + `*.config.jsonc` per function.
4. Follow the chapters for any area you touch (git, vendoring, MCP, skills, GUI, suites).
5. Walk the Definition of Done at the bottom of [checklist.md](checklist.md) before calling it
   shipped.

**Matt, or anyone reviewing a tool:** the checklist is the acceptance test. If a tool fails a
box, it is not done.

## Table of contents

- [checklist.md](checklist.md): the build recipe and Definition of Done
- [01-principles.md](01-principles.md): the philosophy and the prime directive in depth
- [02-project-structure.md](02-project-structure.md): the standard directory tree
- [03-command-and-config.md](03-command-and-config.md): the `.command` + `.config.jsonc` architecture
- [04-config-files-jsonc.md](04-config-files-jsonc.md): writing `.config.jsonc` files
- [05-git-and-artifacts.md](05-git-and-artifacts.md): git, artifacts, provenance
- [06-vendoring-and-linking.md](06-vendoring-and-linking.md): vendoring, linking, portability
- [07-mcp-and-apis.md](07-mcp-and-apis.md): when to add MCPs and APIs
- [08-skills-and-ai-integration.md](08-skills-and-ai-integration.md): skills and multi-AI integration
- [09-documentation-and-house-style.md](09-documentation-and-house-style.md): documentation and house style
- [10-gui-extensions.md](10-gui-extensions.md): future GUI extensions (HTML on the core)
- [11-suites-and-sharing.md](11-suites-and-sharing.md): composing suites and sharing
- [12-adopting-in-existing-projects.md](12-adopting-in-existing-projects.md): retrofitting the standard into an already-built tool
- [13-staged-pipelines-and-shared-config.md](13-staged-pipelines-and-shared-config.md): staged pipelines, a shared per-run/profile config overlay, and a one-step-at-a-time driver
- [14-resilient-agentic-subprocesses.md](14-resilient-agentic-subprocesses.md): keeping a fan-out of AI subagents resumable so a rate limit or crash never wipes a session's work
- [15-mcp-tools-for-weak-models.md](15-mcp-tools-for-weak-models.md): hardening an MCP's tools and errors, plus a tool-agnostic circuit breaker, so a weak or free tool-calling model can drive them
- [templates/](templates/): copy-paste skeletons for a new tool
- [research/](research/): the process audit and the online (standard plus frontier) comparison
  that informed this handbook. Start with
  the source handbook's process audit.

## CourseTools as the reference implementation

The Canvas Automation Toolkit applies the handbook throughout its public source tree:

| Practice | CourseTools implementation |
|---|---|
| Thin human launchers over a reusable engine | `commands/`, `src/canvas_automation/` |
| Reviewed configuration as an interface | documented `*.config.jsonc` and schemas |
| Deterministic output and provenance | IMSCC, test-form, manifest, SBOM, and release builders |
| Guarded external writes | one-course Canvas API guard and sandbox initialization |
| Optional agent integration | `skills/`, `mcp/`, and deterministic commands |
| Portable distribution | `setup-after-move.command`, `uv.lock`, platform notes, and stored tests |
