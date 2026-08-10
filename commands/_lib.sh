# _lib.sh — shared logic for a tool's *.command launchers (its double-click interface).
# Sourced by each .command AFTER it sets $HERE (the launcher's dir) and $ENGINE (project root).
# Not run directly. See 03-command-and-config.md.
#
#   source "$HERE/_lib.sh"
#   eval "$(read_config "$HERE/<task>.config.jsonc")"   # load JSONC settings as shell vars
#   INPUT="$(choose_input "$ARG")" || exit 0            # input-consuming tools: arg, else 3-way menu
#   launch "$OUT_DIR" -- <command...>                   # run any tool; open the newest output
#
# Design principle: ONE .command per major function; subtle options live in its .config.jsonc
# (comment a line out to use the default). Major differences = separate files.
#
# Optional overlay for a MULTI-STEP tool: set PROFILE=<name> (or PROFILE_HOME=<dir>) and read_config
# layers a shared profiles/<name>/profile.config.jsonc + a per-step configs/<step>.config.jsonc on
# top of the suite default. With NO profile set it is the single-file loader, unchanged (fully
# back-compatible). See 13-staged-pipelines-and-shared-config.md.

# Emit ONE JSONC config file as shell `KEY=value` lines (expands ~ , $HOME/$ENGINE, and when a
# profile is active $PROFILE/$PROFILE_HOME). Prints __CONFIG_ERROR__='...' so `launch` can report it.
_jsonc_emit() {
  "$ENGINE/.venv/bin/python" "$HERE/_jsonc.py" "$1" 2>/dev/null \
    || python3 "$HERE/_jsonc.py" "$1"   # fallback if the venv python is missing
}

# The active profile's home dir, or empty. An explicit $PROFILE_HOME wins; else profiles/<PROFILE>.
# A "profile" is one run/variant of a multi-step pipeline (13-staged-pipelines-and-shared-config.md).
_profile_home() {
  if [ -n "${PROFILE_HOME:-}" ]; then echo "$PROFILE_HOME"
  elif [ -n "${PROFILE:-}" ] && [ -d "$ENGINE/profiles/$PROFILE" ]; then echo "$ENGINE/profiles/$PROFILE"; fi
}

# read_config <step.config.jsonc> — emit KEY=value lines for `eval`.
# Parses the suite-default config (expands ~ and $ENGINE/$HOME in strings). If a PROFILE is ACTIVE
# (env PROFILE=<name>, or PROFILE_HOME=<dir>), its shared config and its per-step override are
# layered AFTER the default, so precedence is (last wins):
#   CLI  >  profiles/<name>/configs/<step>.config.jsonc  >  profiles/<name>/profile.config.jsonc  >  suite default
# Configure a run ONCE in the profile; every step inherits it. With NO profile active the behaviour
# is identical to loading the single suite-default file. See 13-staged-pipelines-and-shared-config.md.
read_config() {
  export ENGINE HOME
  _jsonc_emit "$1"
  local pdir; pdir="$(_profile_home)"
  if [ -n "$pdir" ]; then
    export PROFILE="${PROFILE:-$(basename "$pdir")}" PROFILE_HOME="$pdir"  # so $PROFILE/$PROFILE_HOME expand in the profile's configs
    local stem; stem="$(basename "$1")"; stem="${stem%.config.jsonc}"
    [ -f "$pdir/profile.config.jsonc" ]        && _jsonc_emit "$pdir/profile.config.jsonc"
    [ -f "$pdir/configs/$stem.config.jsonc" ]  && _jsonc_emit "$pdir/configs/$stem.config.jsonc"
  fi
}

# Run a command (own venv / binary / cd+env all fine), stream output live, then open the
# newest item created in <out_dir>. Each .command points its tool's output at OUT_DIR.
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
    echo "✓ Output: $newest"
    open "$newest" 2>/dev/null || true
  else
    echo "⚠ Finished, but found no new output in: $out_dir"
  fi
  return "$rc"
}

# choose_input [positional] — resolve the ONE input a tool reads (a folder or a file) and echo it.
# This is the dual interface for input-consuming tools:
#
#   INPUT="$(choose_input "$ARG_INPUT")" || { echo "Nothing to do."; exit 0; }
#
# A non-empty positional arg WINS and is echoed unchanged, so a shell or local AI runs headless
# with NO menu (the hard rule in 03-command-and-config.md's dual interface). With no arg a Finder
# double-click gets a three-way menu in the Terminal window:
#   1) Pick a folder…          a native macOS folder chooser
#   2) Default input folder     $DEFAULT_INPUT from the .config.jsonc (the tool's usual location)
#   3) Path set in the config   $CONFIG_INPUT  from the .config.jsonc (a fixed path)
# Cancel, or a source whose config key is unset, resolves nothing and returns non-zero, so the
# caller stops with a plain message instead of running on an empty path. Prompts and the menu go
# to stderr. Only the resolved path is printed to stdout, so $(choose_input …) captures the path
# alone. $DEFAULT_INPUT/$CONFIG_INPUT come from read_config. An unset one shows as unavailable.
# Headless with no arg (no Terminal for a menu) falls back to $CONFIG_INPUT then $DEFAULT_INPUT, so
# a script or cron run still resolves an input. See 03-command-and-config.md.
choose_input() {
  # Dual interface: an explicit positional input wins and skips the menu entirely.
  if [ -n "${1:-}" ]; then echo "$1"; return 0; fi

  local def="${DEFAULT_INPUT:-}" cfg="${CONFIG_INPUT:-}"

  # No Terminal to show a menu (a headless run): fall back to the configured path, then the default.
  if [ ! -t 0 ]; then
    if   [ -n "$cfg" ]; then echo "$cfg"; return 0
    elif [ -n "$def" ]; then echo "$def"; return 0
    else echo "No input. Pass a path as the first argument." >&2; return 1; fi
  fi

  # A double-click: offer the three sources as a Terminal menu, echo the chosen path.
  local pick="" choice PS3="Choose a number: "
  echo "Where is the input?" >&2
  select choice in \
    "Pick a folder…" \
    "Default input folder${def:+  ($def)}" \
    "Path set in the config${cfg:+  ($cfg)}" \
    "Cancel"; do
    case "$REPLY" in
      1) pick="$(osascript -e 'try' \
                 -e 'POSIX path of (choose folder with prompt "Choose the input folder")' \
                 -e 'on error' -e 'return ""' -e 'end try' 2>/dev/null)"; break ;;
      2) if [ -n "$def" ]; then pick="$def"; break; fi; echo "No DEFAULT_INPUT set in the .config.jsonc. Choose another." >&2 ;;
      3) if [ -n "$cfg" ]; then pick="$cfg"; break; fi; echo "No CONFIG_INPUT set in the .config.jsonc. Choose another." >&2 ;;
      4) break ;;
      *) echo "Enter 1, 2, 3, or 4." >&2 ;;
    esac
  done

  if [ -z "$pick" ]; then echo "Nothing chosen. Nothing to do." >&2; return 1; fi
  echo "$pick"
}
