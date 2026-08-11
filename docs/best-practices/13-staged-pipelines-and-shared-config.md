> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Staged pipelines and a shared config overlay

The forward path for a tool that is many steps, not one shot. Each step keeps its own `.command`
and `.config.jsonc` ([03-command-and-config.md](03-command-and-config.md) still holds), and a thin
overlay lets a whole run be configured once and stepped through one command at a time. The tool
stays AI-free. This is composition, not a new runtime.

## The problem

A multi-step study runs a dozen per-function commands in order. "Do a whole run" then means
hand-editing a dozen step configs to share the same inputs and the same workspace. And short key
names collide across steps: `TOPICS` is a count in one step and a path in another, `LIMIT` means
different things to a fetch step and a sampling step. One shared settings file would force those
meanings to fight.

## The mechanism: a layered `read_config`

Extend the loader so that when a **profile** (one run or variant) is active, it layers the
profile's shared config and a per-step override on top of the suite default. Precedence, last wins:

```
CLI  >  profiles/<name>/configs/<step>.config.jsonc  >  profiles/<name>/profile.config.jsonc  >  commands/<step>.config.jsonc
```

That is a few lines on the existing loader (`templates/_lib.sh`):

```bash
read_config() {
  export ENGINE HOME
  _jsonc_emit "$1"                               # 1. the suite default for this step
  local pdir; pdir="$(_profile_home)"            # the active profile, or empty
  if [ -n "$pdir" ]; then
    export PROFILE="${PROFILE:-$(basename "$pdir")}" PROFILE_HOME="$pdir"   # so $PROFILE_HOME expands below
    local stem; stem="$(basename "$1")"; stem="${stem%.config.jsonc}"
    [ -f "$pdir/profile.config.jsonc" ]       && _jsonc_emit "$pdir/profile.config.jsonc"        # 2. shared
    [ -f "$pdir/configs/$stem.config.jsonc" ] && _jsonc_emit "$pdir/configs/$stem.config.jsonc"  # 3. per-step
  fi
}
```

`eval` consumes the lines in order, so a later file wins. The launcher applies CLI `KEY=VALUE` last
of all. staged course workflow specialises the profile as a `study` rooted at `studies/<name>/`. The generic
name is a `profile` at `profiles/<name>/`.

## Why per-step override files, not one shared file

Both reasons are about scope:

- **Collision-free.** Each `configs/<step>.config.jsonc` loads only for its own step, so the same
  short key can be a count in one override and a path in another without clashing. A single shared
  file cannot.
- **Partial by design.** An override sets only the keys that differ from the default; the rest fall
  through. No schema sits beside these files, so validation is skipped
  ([04-config-files-jsonc.md](04-config-files-jsonc.md)) and a partial override is correct, not an
  error.

Genuinely cross-step keys (the run's input, its workspace) go in the one `profile.config.jsonc`.
Per-step knobs stay in `configs/<step>.config.jsonc`.

## Profile isolation

Route outputs under the profile so runs never collide. The shared config sets a workspace off
`$PROFILE_HOME` (which `read_config` exports before loading these files), for example
`"OUT_DIR": "$PROFILE_HOME/out"`. With no profile active, `_profile_home` is empty, `read_config`
loads the single suite-default file, and behaviour is exactly as before. The overlay is additive:
the original single-file tool is just the no-profile case, fully back-compatible.

## The stepwise driver

A profile is run by an ordered manifest and a small driver, not by remembering the sequence.
staged course workflow is the exemplar:

- `commands/pipeline.json` lists the steps (`n`, `step`, `desc`, a `done_if` glob) plus an
  `optional` / `gated` set. `templates/pipeline.json` is the skeleton.
- `commands/_pipeline.py` reads it and marks each step done or not from whether its `done_if`
  output exists yet.
- `commands/study.command <name>` prints the steps as `done` / `NEXT` / `todo`, and
  `study.command <name> next|<n>|<step>` runs exactly one, with the profile active
  (`PROFILE=<name>`). A gated step (network, API, local LLM) is confirmed before it runs, so those
  stay opt-in.

Running one step at a time keeps a long run legible and re-entrant. Stop after any step, see what is
done and what is next, run the next.

## How it composes

- **With [03-command-and-config.md](03-command-and-config.md).** One `.command` per function still
  holds. Each step is an ordinary launcher that runs alone; the profile is an overlay on top, not a
  replacement. Run a single step under a profile with `PROFILE=<name> ./commands/<step>.command`.
- **With [10-gui-extensions.md](10-gui-extensions.md).** The config is still the model, so a GUI can
  pick a profile, edit its `profile.config.jsonc`, and drive the steps through the same driver. The
  overlay adds one dimension (which run) without moving logic out of the engine.

The Definition of Done in [checklist.md](checklist.md) has the multi-step line this chapter earns.
