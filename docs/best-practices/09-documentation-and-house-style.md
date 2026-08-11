> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Documentation and house style

What to write, where it lives, and the voice it is written in. Good docs are why a tool is easy
to use and easy to hand to the next session.

## The documentation layers

A tool documents itself at four levels, smallest and closest to the work first.

1. **In-config comments.** The first and most important layer. Every option is explained next
   to its value, so a user can operate the tool from the config alone. See
   [04-config-files-jsonc.md](04-config-files-jsonc.md). If the config is complete, a user
   needs nothing else for routine use.
2. **The per-tool `README.md`.** What the tool is, why it exists, how to set it up, how to run
   it, what the config controls, where output lands. The reference when the in-config comments
   are not enough.
3. **Topic guides.** A focused markdown file per deep subject, named for the subject:
   `DENSE_COLLAGE.md`, `AUDIO_PROMPTING.md`, `CONDITIONING.md`, `README_ExamTimer.md`. These go
   beyond reference into recipes and tuning.
4. **`research/`.** The committed "why": design research, the audit, citations, decisions. Not
   user-facing, but it stops the next session re-deriving a choice. See
   [02-project-structure.md](02-project-structure.md).

## The README structure

Model a tool README on Canvas Automation Toolkit's. The opening establishes what it is in two sentences, then a
status table, then a `## Use` block of copy-pasteable commands, then the operating notes. The
sections that earn their place:

- **One-paragraph what-and-why.** "A small headless engine that generates short, bespoke
  audio / image / video ... to feed the existing pipeline." Say what it is and what it feeds.
- **Status table.** What works, what backend, what state. Honest about what is wired and what is
  best-effort.
- **Use.** Real commands a reader can paste, including the determinism note ("Same prompt + seed
  + args => the same audio. Outputs are never overwritten.").
- **Setup.** The one setup step (`uv sync`, weight download), so a fresh clone runs.
- **Pointers.** Links to the topic guides for depth.

`templates/README.template.md` ships this skeleton.

## Comment density

- **Configs:** every option carries a note. This is the interface, so over-comment rather than
  under-comment. See the discipline in [04-config-files-jsonc.md](04-config-files-jsonc.md).
- **Launchers:** a header comment naming the function and its config, plus a comment on any
  non-obvious step (the `osascript` fallback, the best-effort refresh). The `.command` files in
  the suite are heavily headed for exactly this reason.
- **Engine code:** match the surrounding code. Explain *why*, not *what*. A comment that
  restates the line is noise.

## The house style

All reader-facing prose follows the matthorrigan.com house writing style, the single source of
truth for which is `bio/.agents/skills/house-style-writing/SKILL.md`. The load-bearing rules:

### 1. No spaced em dashes. Ever.

Never write a space, em dash, space. It is the one hard rule. Recast every spaced em dash:

| Instead of a spaced em dash | Use | When |
|---|---|---|
| two independent clauses | a period, two sentences | the halves stand alone |
| an explanation or list lead-in | a colon | the second half spells out the first |
| a light aside | a comma | a brief in-line qualifier |
| a parenthetical | parentheses | a true side note you could lift out |

### 2. Do not lean on the em dash at all.

Even closed up, aim for none and allow at most one per paragraph. Most are a period, colon, or
parentheses wearing a costume.

### 3. Semicolons do not join sentences.

If both sides can stand alone, write two sentences.

### 4. Plain, active, concrete.

Say the thing. Prefer the short Anglo-Saxon word, the active verb, the concrete noun.

### Scope

The style binds reader-facing prose: READMEs, topic guides, config comments, status messages,
and these handbook chapters. Code and developer comments may follow it but are not bound by it.
Creative work keeps its own voice.

## A per-tool doc checklist

- [ ] Every config option has an in-line comment.
- [ ] `README.md` covers what / why / setup / use / config / output.
- [ ] Any deep subject has a topic guide, linked from the README.
- [ ] `research/` records the design rationale and any audit or citations.
- [ ] Prose has no spaced em dashes and reads plainly.
- [ ] The determinism and provenance contracts are stated where a user will see them.
