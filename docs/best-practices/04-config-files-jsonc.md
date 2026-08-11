> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Writing .config.jsonc files

The config is the whole interface. A person operates the tool by editing this one file, so it
has to be readable, complete, and self-documenting. This chapter is how.

## Why JSONC

JSONC is JSON plus `//` and `/* */` comments and trailing commas. We use it because the config
doubles as the documentation:

- **Comments** let every option carry its own explanation, inline, next to the value.
- **Trailing commas** mean you can comment a line out or reorder without breaking the next
  line.
- **JSON underneath** means values follow ordinary, predictable rules and parse with the
  standard library.

YAML is whitespace-fragile and has surprising type coercion. TOML is fine but less familiar for
nested data and does not comment-out as cleanly. Plain JSON forbids comments, which defeats the
"config is the docs" goal. JSONC is the sweet spot for human-edited knobs.

## The documentation discipline

The rule, from orchestrator's `course-package.config.jsonc` header:

> Every option lives in this file: the ACTIVE ones are uncommented, the rest are commented out
> with notes. Uncomment to enable.

So:

- **Active options are uncommented** with a value and a short note.
- **Advanced or rare options are commented out** with a note explaining what they do, so the
  user discovers them by reading, not by consulting external docs.
- **Defaults happen by commenting out.** A commented option means "the tool's default applies."
  To override, uncomment and set.

## The header block

Open every config with a comment block that makes the file self-contained. orchestrator's is the
model:

```jsonc
// ============================================================================
//  DENSE MOVING COLLAGE — your config. Edit this file, then double-click
//  course-package.command (or run: .venv/bin/canvas-automation collage config course-package.config.jsonc)
//
//  Every option lives in this file: the ACTIVE ones are uncommented, the rest are
//  commented out with notes — uncomment to enable. Output lands in a fresh
//  out/<name>/<timestamp>/ folder (never overwritten). Same config + same "seed"
//  always renders the exact same video. Full guide: DENSE_COLLAGE.md
// ============================================================================
```

A good header names: what the tool does, how to run it (double-click and CLI), where output
lands, the determinism contract, and a pointer to any deeper guide.

## A worked example

Patterned on `generate-image.config.jsonc` and `course-package.config.jsonc`:

```jsonc
{
  // =============== generate-audio === text -> sound (an optional model / Stable Audio) ===
  // Edit, then double-click generate-audio.command. Output: a fresh out/<name>/<timestamp>/
  // with audio.wav + provenance.json. Same prompt + seed + args => the same audio.

  "PROMPT": "a slow evolving metallic drone, dark, distant",
  "SECS": 10,                 // clip length in seconds (1..600)
  "SEED": 7,                  // the variation control: same seed => identical output
  // "MODEL": "optional-model",     // optional-model (default, robust) | optional-model2 | stable-audio (gated, best)
  // "NAME": "metallic-drone",// output name (default: derived from the prompt)
  "OUT_DIR": "$HOME/Desktop/Canvas Automation Toolkit-output"

  // --- ADVANCED (uncomment to use) ------------------------------------------
  // ,"GUIDANCE": 3.5         // prompt adherence; higher = closer, less natural
  // ,"DTYPE": "float32"      // keep float32 for audio on MPS (fp16 gets noisy)
}
```

Conventions visible here:

- `SEED`, `NAME`, `OUT_DIR` are near-universal. `SEED` is the determinism knob, `OUT_DIR`
  expands `$HOME`.
- Notes state ranges and the effect of each value, not just its name.
- Advanced options sit at the bottom, commented, each on a `,"KEY"` line so uncommenting one
  does not require touching the line above (trailing-comma friendliness).

## The string-aware loader

Comments must be stripped without mangling a `//` that appears inside a real string (a path, an
`http://` URL). orchestrator's `src/canvas_automation/jsonc.py` is string-aware and explains why:

> The stripper is STRING-AWARE: `//` inside a quoted value (e.g. a path or `http://` URL) is
> preserved; only real comments and trailing commas are removed. The result is handed to the
> stdlib `json` parser, so values follow normal JSON rules.

Reuse this loader. Do not hand-roll a regex that eats `//` blindly. Canvas Automation Toolkit's
`commands/_jsonc.py` is the variant that also emits shell `KEY=value` lines and expands `~`,
`$ENGINE`, and `$HOME` inside string values, which is what `read_config` calls. See
[03-command-and-config.md](03-command-and-config.md).

## Variable expansion

String values may use `~`, `$HOME`, and `$ENGINE`, expanded at load time. That keeps configs
portable: `"OUT_DIR": "$HOME/Desktop/Canvas Automation Toolkit-output"` works on any machine without a hardcoded
user path. Keep expansion to a small, documented set so a config stays predictable.

## Validate, fail fast, fail readably

The audit's top recommendation (P1-A in
the source handbook's process audit): the config is the whole
interface, so a bad value should fail in the editor or at load, not deep in a run.

- **Ship a JSON Schema** beside each config (`generate-audio.schema.json`) describing types,
  ranges, enums, and required keys. Reference it so an editor validates and autocompletes:

  ```jsonc
  {
    // "$schema": "./generate-audio.schema.json",  // editor validation + autocomplete; ignored at runtime
    "MODEL": "optional-model",  // enum: optional-model | optional-model2 | stable-audio
    "SECS": 10            // integer, 1..600
  }
  ```

  Keep `$schema` commented (or teach the loader to drop it) so it does not leak into the shell
  vars, and map it in the workspace `json.schemas` setting if you prefer.
- **Validate on load.** When a value is the wrong type or an unknown key appears, print the
  offending key and the allowed values, then exit non-zero. The loader already surfaces JSON
  syntax errors via `__CONFIG_ERROR__`; extend it to type and range checks. Do not silently
  drop unknown keys or fall back to a default without saying so.

## Determinism keys

Honour the contract from [01-principles.md](01-principles.md):

- A single `SEED` (or `seed`) controls all variation. Document that same config plus same seed
  yields byte-identical output.
- Pin any non-deterministic step (a multi-threaded encoder) to a deterministic mode in the
  engine, not the config, so the user cannot accidentally break reproducibility.

## Style

Apply the house style to config comments too: plain, concrete, no spaced em dashes. A comment
says what the option does and what a sensible value is, in as few words as carry the meaning.
See [09-documentation-and-house-style.md](09-documentation-and-house-style.md).
