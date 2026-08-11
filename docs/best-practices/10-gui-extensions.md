> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Future GUI extensions (HTML on the core)

The forward path for tools that want a graphical face. A GUI is layered on top of the existing
command and config core by progressive enhancement. The CLI stays the source of truth and the
tool stays AI-free.

## The key insight: the config is already the model

A `*.config.jsonc` is a structured description of a run. That is exactly what a GUI form edits.
So a GUI is not a rewrite, it is a **view** over the same model:

- The form **reads** the `.config.jsonc` to populate its fields.
- The user edits fields.
- The form **writes** the `.config.jsonc` back.
- A "Run" button **shells out** to the same `.command`.

No tool logic moves into the GUI. The engine, the config, and the launcher are untouched. The
GUI is a convenience skin, the same way the `.command` is a convenience skin over the CLI (see
[06-vendoring-and-linking.md](06-vendoring-and-linking.md)).

## The precedent in the suite

CANVAS_AUTOMATION already ships HTML bundles served locally. `out/dist/<bundle>/serve.command`:

```bash
#!/bin/bash
# Double-click to serve this bundle over http and open it in your browser.
cd "$(dirname "$0")"
exec python3 serve.py
```

A double-click serves a static bundle over http and opens the browser. That is the pattern to
generalise: a small local server (or just a file open) in front of an HTML view, launched by
the same kind of `.command` everything else uses.

## The recommended progression

Start as small as possible and only grow if the tool earns it.

**Stage 1: a single-file HTML form, zero build step.**
One `.html` file with a form whose fields mirror the config keys, a "Save" that writes the
`.config.jsonc`, and a "Run" that invokes the `.command`. Open it with a `serve.command` like
the precedent above. No framework, no bundler, no `node_modules`. This covers most tools.

**Stage 2: a small local server.**
If the GUI needs to run the tool and stream output back, add a tiny local server (a `serve.py`)
that serves the page and exposes one endpoint that runs the `.command` and streams its stdout.
Still local, still AI-free, still the same engine underneath.

**Stage 3: anything heavier** is a deliberate decision, not a default. Most tools never need it.

## Rules

- **Do not fork logic into JavaScript.** The GUI computes nothing the engine could compute. If
  you find yourself reimplementing a feature in JS, stop and call the CLI instead. One source of
  truth, the engine.
- **Do not make the GUI mandatory.** The `.command` and the config must still work with no GUI.
  The GUI is additive. A user who never opens it loses nothing.
- **Round-trip the real config.** The GUI reads and writes the actual `.config.jsonc`, comments
  and all, so a config edited in the GUI is identical to one edited by hand and vice versa. Use
  the same string-aware loader from [04-config-files-jsonc.md](04-config-files-jsonc.md) so
  comments survive.
- **Keep it local and AI-free.** Serve from localhost, no external calls, no model at runtime.
  The GUI is one more AI-free operator of the same core, alongside the human at the `.command`
  and the agent at the CLI (see [08-skills-and-ai-integration.md](08-skills-and-ai-integration.md)).
- **Launch it the standard way.** A `serve.command` double-click, a held window, the browser
  opened for the user. Same conventions as every other launcher in
  [03-command-and-config.md](03-command-and-config.md).

## Why this stays true to the prime directive

A GUI built this way never becomes a dependency the tool needs to function. It is a nicer way to
edit the same config and press the same button. Remove it and the tool is exactly as capable
from the `.command`. That is the test for any enhancement: it adds a way in, it never becomes
the only way in.
