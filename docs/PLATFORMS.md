# Platform support

## macOS: supported and tested

macOS is the primary platform. It supports the double-click `*.command`
launchers, Finder file selection, automatic Finder output opening, hidden token
prompts, and optional Canvas MCP credentials in macOS Keychain.

Run `setup-after-move.command` after unzipping or moving the folder. This builds
only the deterministic environment. Run `commands/setup-canvas-mcp.command`
later if you also want local AI access through MCP.

The deterministic setup installs the locked runtime and `pytest` verification
extra, including the Waitress WSGI server. It does not install Canvas MCP or
store any credential.

## Linux: supported CLI core, manual conveniences

The Python engine, Waitress loopback server, configuration files, IMSCC builder, link checker, and tests
are portable. Install `uv`, run `bash scripts/setup.sh`, then use commands such
as:

```sh
.venv/bin/canvas-automation build-imscc --engine "$PWD" --config commands/build-imscc.config.jsonc
.venv/bin/python scripts/check_external_links.py path/to/course.imscc
```

The macOS `*.command` launchers, Finder dialogs, `open`, and Keychain launcher do
not work on Linux. Configure an optional MCP client from the upstream Canvas MCP
documentation and supply credentials through that client's secure mechanism.

## Windows: experimental CLI core

The engine and Waitress server are ordinary Python and should run under PowerShell with `uv`, but the
project does not yet ship PowerShell launchers or Windows credential-store
integration. This path is documented, not part of the tested release gate:

```powershell
uv sync
.venv\Scripts\canvas-automation.exe build-imscc --engine . --config commands\build-imscc.config.jsonc
.venv\Scripts\python.exe scripts\check_external_links.py path\to\course.imscc
```

Do not run the Bash `*.command` files from Windows. A future Windows release
should add thin PowerShell wrappers around the same CLI rather than fork the
engine.
