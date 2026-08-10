# Engine-root resolution: a real shipped bug and its fix

`export-course-packet` wrote its output under `$HOME/out/...` instead of
`$ENGINE/out/...` in real use, and `create-page` failed to find files
under `/input` for the same underlying reason. Both are fixed. Recorded
here in enough detail that the failure mode does not get silently
reintroduced by a future edit that looks harmless in isolation.

## The two independent failures that stacked

1. **`ENGINE` never reached the Python process.** `commands/_lib.sh`'s
   `read_config()` does `export ENGINE HOME`, but `read_config` is called
   as `eval "$(read_config "$CONFIG")"`, i.e. inside a `$(...)` command
   substitution. That runs in a forked subshell; an `export` done inside
   it affects only that subshell's own process tree (which is where
   `_jsonc.py` runs, so *that* call saw `ENGINE` correctly) and evaporates
   the moment the subshell exits. It never touches the parent
   `.command` script's own environment. So when `launch()` later started
   `canvas-automation` as a direct child of the parent script, that child
   had no `ENGINE` variable at all, despite `read_config` appearing to set
   it moments earlier in the same script.

2. **The fallback then failed too, for an unrelated reason.** With no
   `ENGINE` in the environment, `find_engine_root()` tried to infer the
   project root from `Path(sys.executable).resolve()`, checking whether
   the resolved path's parent was named `bin` and its grandparent `.venv`.
   `uv venv` creates `.venv/bin/python` as a *symlink* to the system
   interpreter. `sys.executable` itself correctly reports the path inside
   `.venv/bin/`, but calling `.resolve()` on it follows the symlink to
   its target, which is outside the venv entirely (confirmed directly:
   `sys.executable` reported `.../CANVAS_AUTOMATION/.venv/bin/python`,
   `.resolve()` turned that into `/usr/bin/python3.12`). The venv-shaped
   check then failed to match, and the function fell through to its last
   resort, `Path.cwd()`.

With both of those gone, `Path.cwd()` won: whatever directory the shell
happened to be in when the `.command` file was invoked (the reported
case: the user's home directory, since the script never explicitly `cd`s
anywhere and they ran it via an absolute path from `~`).

A third, smaller issue surfaced while fixing this: the CLI never actually
read a config's `OUT_DIR` value at all. Every `cmd_*` function computed
its own `engine/out/<command_name>` path directly, so even a correctly
resolved `engine` would have silently ignored anyone customizing
`OUT_DIR`, which every shipped config invites you to do.

## The fix: several independent layers, not one patch

- **`--engine` is now passed explicitly** by every `commands/*.command`
  file to every `canvas-automation` invocation (`cmd_serve`/`cmd_stop`
  included, since they were equally exposed despite not going through
  `launch()`). This is the primary channel: a plain CLI argument, not
  dependent on any shell export/subshell scoping subtlety.
- **`find_engine_root()`'s fallback now uses `sys.prefix`**, not
  `sys.executable`. `sys.prefix` is set by the interpreter itself at
  startup from `.venv/pyvenv.cfg` and is correct regardless of whether
  the interpreter binary is a symlink; it does not require resolving
  anything. Order: `--engine` argument, then the `ENGINE` environment
  variable (for a direct headless invocation that skips `--engine`), then
  `sys.prefix`, then `cwd()` as the true last resort.
- **Every `.command` file now also exports `ENGINE`/`HOME` itself** (not
  relying on `read_config`'s subshell-scoped export) and **`cd`s into
  `$ENGINE`** before doing anything else. Neither is load-bearing given
  the fix above, but both are cheap, and the `cd` means even the last-resort
  `cwd()` fallback is correct if this CLI is ever invoked some other way.
- **`resolve_path()` substitutes `$ENGINE` directly from the already-resolved
  `engine` argument**, not via `os.path.expandvars()` (which reads
  `os.environ`). This closes a subtler version of the same class of bug:
  without it, a correct `--engine` argument with no matching `ENGINE`
  environment variable would still have left a literal, unexpanded
  `"$ENGINE"` in any path read from a config (`OUT_DIR`, `description_file`,
  etc.), because expansion had a different, weaker source of truth than
  resolution did. `resolve_out_base()` and `resolve_file_field()` both
  route through `resolve_path()`, so this fix covers both this bug's
  original symptoms (course-packet output location, create-page's
  `input/` lookup) from one place.
- **`resolve_out_base()` is new** and is what every `cmd_*` function calls
  before `fresh_out_dir()`, so a customized `OUT_DIR` is now actually
  respected instead of silently overridden.

## Test coverage added

`tests/test_engine.py` gained direct coverage for every layer above:
`find_engine_root()` with an explicit argument, with only the environment
variable, with only `sys.prefix` (a venv simulated via monkeypatch, with
`sys.executable` never even consulted), and with nothing at all (`cwd()`).
`resolve_out_base()` is tested both for the default path and for a
customized `OUT_DIR`, including one that contains `$ENGINE` with no
`ENGINE` environment variable present, which is the specific case that
silently broke before. The most direct regression test runs the actual
built `canvas-automation` console script as a subprocess, from a working
directory that is deliberately not the project, with `ENGINE` stripped
from its environment, and asserts the output lands under the real engine
root rather than next to the fake working directory. That is the closest
a test in this repository can get to the exact scenario that was reported
from a live run on macOS.
