> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Skills and multi-AI integration

How a tool gets driven by many AIs, including lightweight local ones, without ever needing an
AI to run. The enabler is the architecture itself; skills are the thin layer that teaches an
agent which knobs to turn.

## The enabler: an AI-free headless core

Because every tool is a headless CLI plus a `.command` with a documented config, any agent can
operate it the same way a shell does: call the command with positional args, read the printed
output path. No special protocol, no runtime model dependency. This is the dual interface from
[03-command-and-config.md](03-command-and-config.md), and it is why "usable by multiple AIs"
costs almost nothing: you built it once, for humans and scripts, and agents come along for free.

So the integration order is:

1. **Default:** the AI drives the CLI directly (positional args). Nothing to add.
2. **If the AI operates the tool often:** add a `SKILL.md` so it knows which command and which
   config knobs to use for common jobs.
3. **Only if the AI must drive a live external app:** add an MCP. See
   [07-mcp-and-apis.md](07-mcp-and-apis.md).

## Writing a SKILL.md

A skill is a markdown file with YAML frontmatter (a `name` and a precise description of *when*
to apply it) and a body (when it applies, the rules, the source of truth). The frontmatter is
what an agent reads to decide relevance, so it must be specific. From
`bio/.agents/skills/house-style-writing/SKILL.md`:

```markdown
---
name: house-style-writing
description: >-
  Apply the matthorrigan.com house writing style when composing or revising any
  reader-facing prose on the site: tool pages, the home page, the CV, and all
  button, label, hint, placeholder, and status text. Enforces no spaced em dashes,
  ... Use it whenever you add or edit words that a visitor will read.
---

# matthorrigan.com house writing style

## When this applies
**Reader-facing prose only:** ...

## The rules
### 1. No spaced em dashes. Ever.
...
```

The shape to copy:

- **`name`**: kebab-case, matches the directory.
- **`description`**: states the trigger ("use it whenever ..."), concrete enough that an agent
  knows when to load it. This is progressive disclosure: the agent reads name and description
  first and pulls the body only when it activates, which matches the Agent Skills standard the
  audit cites.
- **Body**: a "When this applies" section that scopes it, then numbered rules, then any tables
  or examples. One skill is the single source of truth for its topic.

`templates/SKILL.md.template` ships this skeleton.

## A per-tool operating skill

For a tool an AI runs often, write a skill that teaches the mapping from job to command and
config. Sketch:

```markdown
---
name: Canvas Automation Toolkit-operating
description: >-
  Use when asked to generate audio, an image, or a short video with Canvas Automation Toolkit
  (CANVAS_AUTOMATION). Tells you which .command to run and which .config.jsonc
  keys to set for common requests.
---

# Operating Canvas Automation Toolkit

## When this applies
Any request to synthesize sound design, a still, or a short clip from a text prompt.

## The commands
- Audio  → `commands/generate-audio.command`  (config: PROMPT, SECS, SEED, MODEL)
- Image  → `commands/generate-image.command`  (config: PROMPT, WIDTH, HEIGHT, STEPS, SEED)
- Video  → `commands/generate-video.command`  (config: PROMPT, FRAMES, SEED)

## How to run headless
`./commands/generate-image.command` is double-click; to run from a shell, edit the config or
call the engine directly: `.venv/bin/gen img "PROMPT" --seed 7 --steps 30`.

## Rules
- Always set SEED for reproducibility. Same prompt + seed => same artifact.
- Output + provenance.json land in out/<name>/<timestamp>/. Never overwrite.
```

This is the standing-prompt idea (see the README) applied per tool: the skill records the
operating knowledge so a session does not re-derive it.

## Session bootstrap: AGENTS.md and AGENTS.md

A project carries a `AGENTS.md` (and/or `AGENTS.md`) at its root as the first thing a session
reads. Several suite projects already do (`CANVAS_AUTOMATION/AGENTS.md`,
`CANVAS_AUTOMATION/AGENTS.md`, `CANVAS_AUTOMATION/AGENTS.md`). Keep it short and point
outward:

- The determinism and provenance contracts for this tool.
- Where the commands and configs are, and what each does.
- A pointer to this handbook and to the tool's `research/`.

The bootstrap tells a new session "here is how this tool works and here are the conventions,"
which is exactly what stops the re-prompting.

## Lightweight local models

A small local model can drive these tools if you keep two things true:

- **The CLI is deterministic and explicit.** Clear flags, clear errors, a printed output path.
  A small model succeeds when the interface is unambiguous and fails when it has to guess.
- **The instructions are concrete.** A per-tool skill that lists exact commands and config keys
  (above) lets a small model pattern-match a request to a command instead of reasoning from
  scratch.

The same property that makes a tool good for humans (one command, one documented config) makes
it tractable for a small model. You do not lower the ceiling for big models by doing this; you
raise the floor for small ones.

## What never changes

No AI is required to run the tool. Skills and MCPs help an AI *build* or *drive* it, but a
human with the `.command` and the config is always a complete operator. If a tool starts to
need an AI to function, that is a regression to fix, not a feature.
