> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# The .command + .config.jsonc architecture

The heart of the system. A double-clickable launcher plus a commented config, sharing a stem,
backed by one small shared library. This is how a tool stays AI-free and full-featured.

## The pairing rule

One `*.command` per major function, paired with one `*.config.jsonc` of the same stem. Subtle
options live in the config. Genuinely different functions are separate pairs. Canvas Automation Toolkit's
`commands/_lib.sh` header states it:

> ONE .command per major function; subtle options live in its .config.jsonc (commentable JSON,
> comment a line out to use the default). Major differences = separate files.

A `commands/` folder then reads like a menu of what the tool does.

## Anatomy of a `.command`

From `CANVAS_AUTOMATION/commands/generate-image.command`:

```bash
#!/usr/bin/env bash
# Generate an IMAGE from a text prompt (SDXL). Settings: generate-image.config.jsonc
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"
source "$HERE/_lib.sh"
eval "$(read_config "$HERE/generate-image.config.jsonc")"
export Canvas Automation Toolkit_OUT_DIR="$OUT_DIR"
args=( "$ENGINE/.venv/bin/gen" img "$PROMPT" --width "$WIDTH" --height "$HEIGHT" --steps "$STEPS" )
[ -n "${NAME:-}" ] && args+=( --name "$NAME" )
launch "$OUT_DIR" -- "${args[@]}"
echo; read -rp "Press return to close… " _
```

Line by line, the load-bearing parts:

- `#!/usr/bin/env bash` and a one-line comment naming the function and its config file.
- `set -uo pipefail`: unset variables and failed pipes are errors. (We use `-uo`, not `-e`, so
  a non-zero tool exit is handled and reported by `launch` rather than killing the script
  before the window-hold.)
- `HERE=...`: resolve the launcher's own directory from `${BASH_SOURCE[0]}`, so a double-click
  from Finder (any working directory) still finds its siblings.
- `source "$HERE/_lib.sh"`: pull in `read_config` and `launch`.
- `eval "$(read_config ...)"`: load the config's keys as shell variables.
- build the `args` array, conditionally adding optional flags.
- `launch "$OUT_DIR" -- ...`: run the engine, stream output, open the newest result.
- `read -rp "Press return to close… "`: hold the Terminal window open so a human reads the
  result instead of watching it flash shut.

## The shared library: `_lib.sh`

One file, a few small helpers, sourced by every launcher. The two core ones are below, from
`CANVAS_AUTOMATION/commands/_lib.sh`:

```bash
# Parse a JSONC config into shell `KEY=value` lines (expands ~ and $ENGINE/$HOME in strings).
read_config() {
  export ENGINE HOME
  "$ENGINE/.venv/bin/python" "$HERE/_jsonc.py" "$1"
}

# Run a command, stream output live, then open the newest item created in <out_dir>.
launch() {
  local out_dir="$1"; shift
  [ "${1:-}" = "--" ] && shift
  if [ -n "${__CONFIG_ERROR__:-}" ]; then echo "❌ $__CONFIG_ERROR__"; return 1; fi
  mkdir -p "$out_dir"
  echo "▶ Running…"; printf '   %q' "$@"; echo; echo
  "$@"; local rc=$?
  echo
  if [ "$rc" -ne 0 ]; then
    echo "❌ Failed (exit $rc). Check the messages above and the paths in your .config.jsonc."
    return "$rc"
  fi
  local newest; newest="$(ls -dt "$out_dir"/* 2>/dev/null | head -1)"
  if [ -n "$newest" ]; then
    [ -d "$newest" ] || newest="$out_dir"
    echo "✓ Output: $newest"; open "$newest" 2>/dev/null || true
  else
    echo "⚠ Finished, but found no new output in: $out_dir"
  fi
  return "$rc"
}
```

The contract:

- `read_config <file>` prints `KEY=value` lines (and surfaces a parse error as
  `__CONFIG_ERROR__`). The caller does `eval "$(read_config ...)"`.
- `launch <out_dir> -- <cmd...>` runs any command (its own venv, a binary, a `cd`+env, all
  fine), reports the exit code in plain language, and opens the newest output. Every launcher
  points its tool's output at `OUT_DIR`.

The handbook's `templates/_lib.sh` adds a third helper, `choose_input`, for a tool that reads an
input (a folder or a file). It is the input half of the dual interface below: a positional
argument runs headless, a bare double-click gets a three-way menu. A generate-from-config tool
does not need it.

Because the launcher is this thin, adding a new function is copying a pair and editing two
small files. The library is shared, so the behaviour stays uniform.

## The dual interface

A launcher serves two operators from one file: a human double-clicking, and a shell or local AI
passing arguments. The hard rule: a positional argument runs headless and skips any prompt, while
a bare double-click is interactive. A clean headless callable is also an agent callable, which is
why the same tool serves a human, a script, and an MCP later with no change.

For a tool that reads an input (a folder or a file), `choose_input` from `_lib.sh` encodes both
halves. The skeleton wires it like this:

```bash
# Sort args: the first non-KEY=VALUE arg is the input; KEY=VALUE lines override config keys.
ARG_INPUT=""
for kv in "$@"; do
  case "$kv" in *=*) export "${kv?}" ;; *) [ -z "$ARG_INPUT" ] && ARG_INPUT="$kv" ;; esac
done

INPUT="$(choose_input "$ARG_INPUT")" || { echo "Nothing to do."; exit 0; }
```

`choose_input` resolves the one input three ways:

- **A positional argument** is echoed back unchanged and skips the menu.
  `./do-thing.command /path/to/input` runs with no prompts. This is the non-negotiable half: the
  shell and local-AI path.
- **No argument** (a Finder double-click) opens a numbered menu in the Terminal window:
  1. **Pick a folder** opens a native macOS folder chooser.
  2. **Default input folder** is `DEFAULT_INPUT` from the paired `.config.jsonc` (the tool's usual
     input location).
  3. **Path set in the config** is `CONFIG_INPUT` from the paired `.config.jsonc` (a fixed path).
- **Cancel**, or a source whose config key is unset, resolves nothing and returns non-zero, so
  the launcher stops with a plain "Nothing to do" instead of running on an empty path.

The two keys live in the config. Comment `CONFIG_INPUT` out to drop option 3:

```jsonc
"DEFAULT_INPUT": "$HOME/Desktop/TOOL_NAME-input",   // menu option 2: the usual input folder
// "CONFIG_INPUT": "$HOME/Documents/fixed/input",   // menu option 3: a fixed path (uncomment to offer it)
```

Prompts and the menu print to stderr. Only the resolved path prints to stdout, so
`INPUT="$(choose_input …)"` captures the path alone. A headless run with no argument (no Terminal
for a menu) falls back to `CONFIG_INPUT` then `DEFAULT_INPUT`, so a script or cron job still
resolves an input.

This is the three-way upgrade of an older pattern: read `$1`, else pop one `osascript` picker,
else use one hardcoded default. `<toolkit-root>/archive/CANVAS_AUTOMATION/Build course package.command` still shows that
shape (`SRC="${1:-}"`, else a picker, else `src/course package/course package.txt`). The menu turns those
baked-in fallbacks into three sources the operator chooses at runtime, while keeping the
positional-argument rule intact. To migrate a launcher: source `_lib.sh`, add the two config keys,
and replace its picker block with one `choose_input` call.

Not every launcher takes an input, and those skip `choose_input`. A generate-from-config tool
(generate-image above) reads its subject from a config key. The staged-pipeline `pipeline.command`
takes a profile name positionally and reads the run's `INPUT` from the profile config, and
`mirror.command` takes a destination, not an input. The engine underneath stays AI-free, so the
same code path serves a non-technical human, a script, and an agent. This is also why an MCP fits
cleanly later: a clean headless callable is already an agent callable. See
[07-mcp-and-apis.md](07-mcp-and-apis.md) and [08-skills-and-ai-integration.md](08-skills-and-ai-integration.md).

## Two launcher styles

**Fixed launcher (Canvas Automation Toolkit, orchestrator).** The `.command` and `.config.jsonc` live in the tool's
`commands/` folder. The user edits the config in place and double-clicks. orchestrator's
`course-package.command` is a self-contained example: it checks the venv exists, runs the
module on its config, finds the latest `out/` dir, and opens it, printing friendly errors at
each step.

**Drop-in template (Canvas Automation Toolkit).** The pair lives in `scripts/templates/`. The user copies
`compose.command` + `compose.config` into a working directory full of inputs, edits the config,
and double-clicks there. From `CANVAS_AUTOMATION/scripts/templates/compose.command`:

```bash
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="${CANVAS_AUTOMATION_HOME:-<toolkit-root>}"
"$REPO/.venv/bin/python" "$REPO/scripts/pipeline_compose.py" "$SELF_DIR"
```

Note the env-var home override (`${CANVAS_AUTOMATION_HOME:-...}`): the dropped-in launcher
finds its engine from anywhere, and a move only requires setting one variable. See
[06-vendoring-and-linking.md](06-vendoring-and-linking.md).

## Behaviours every launcher gets right

- **Window-hold.** End with a `read` so the window stays open. Canvas Automation Toolkit uses
  `read -rp "Press return to close… "`; Canvas Automation Toolkit uses `read -r _`; the relocation script uses
  `read -n 1 -s -r -p "Press any key…"`.
- **Open the output.** `launch` (or the script) opens the newest `out/` item so the result is
  in front of the user immediately.
- **Plain-language errors.** On a non-zero exit, say what failed and point at the config. Never
  flash shut on an error.
- **`bash -n` clean.** Every launcher passes a syntax check. The verify gate enforces this.

## Adding a function (the extend path)

1. Copy `templates/skeleton.command` and `templates/skeleton.config.jsonc` to the new stem.
2. Point the `args` array at your engine subcommand and map config keys to flags. If the tool
   reads an input, resolve it with `choose_input` (the skeleton shows it) and set `DEFAULT_INPUT`
   and `CONFIG_INPUT` in the config. A generate-from-config tool drops that line.
3. Document every new option in the config (active or commented-out-with-a-note).
4. `chmod +x the-new.command`, run `bash -n` on it, double-click to test.

No change to `_lib.sh` is needed: `read_config`, `choose_input`, and `launch` are already there.
That is the point.
