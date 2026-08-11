> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# When to add MCPs and APIs

The default is no MCP and no API. A tool is a plain `.command` plus a CLI that runs AI-free.
Add an MCP or an external service only when there is a specific reason, and never let it become
a runtime requirement of the core.

## Decide first

```
Does the tool need to DRIVE a live external app (Canvas, Canvas, Canvas Automation Toolkit) from an AI?
  └─ yes → add an MCP server for the drive-time work; the CLI still runs without it
  └─ no  → no MCP

Does the tool need data or compute from an external SERVICE (an asset API, a hosted model)?
  └─ yes → add the API; key in a gitignored dotfile or env; record provenance for fetched assets
  └─ no  → no API
```

Both are **build-time or drive-time** conveniences. The shipped tool must still run with no MCP
and no network, per the prime directive in [01-principles.md](01-principles.md). An MCP fits
cleanly precisely because the tool is already a clean headless callable: see the dual interface
in [03-command-and-config.md](03-command-and-config.md).

## MCP wiring patterns

A project that needs an MCP carries a `.mcp.json` at its root. There are two patterns in the
suite.

**Pattern A: run a project entry point with uv.** `CANVAS_AUTOMATION/.mcp.json`:

```json
{
  "mcpServers": {
    "canvas-mcp": {
      "command": "uv",
      "args": ["--directory", "<toolkit-root>",
               "run", "canvas-mcp"]
    }
  }
}
```

The server lives in the project, declared as a console script, and `uv run` launches it in the
project's pinned env. Use this when the MCP server is your own code in the repo.

**Pattern B: an installed binary plus env config.** `CANVAS_AUTOMATION/.mcp.json`:

```json
{
  "mcpServers": {
    "Canvas": {
      "command": "<local-bin>/canvas-mcp",
      "args": [],
      "env": {
        "CANVAS_WORKSPACE": "<toolkit-root>",
        "CANVAS_MCP_COMMAND": "/Applications/Canvas.app/Contents/MacOS/Canvas",
        "CANVAS_TIMEOUT": "120",
        "CANVAS_MAX_FILE": "52428800"
      }
    }
  }
}
```

Use this when the server is an installed binary configured entirely through env vars
(workspace, the app binary to drive, timeouts, limits). Prefix the vars with a short tool tag
(`INKS_*`).

Ship a small client-check script so a session can confirm the server answers, as Canvas Automation Toolkit does
with `scripts/mcp_client_check.py`. `templates/mcp.json.sample` carries both patterns.

MCP is the right standard for this: it is now an industry standard with a large public server
ecosystem, and the audit rates the suite's "MCP-only-where-needed" restraint as on-par to ahead
of frontier. Wire it where a live app must be driven, not as a default.

## External APIs

When a tool genuinely needs a service (an asset library, a hosted model):

- **Keys live outside git.** A gitignored dotfile (Canvas Automation Toolkit's `.external-service.json`, mode `0600`) or
  an environment variable. The dotfile is the first line of the `.gitignore`. Never commit a
  key. See [05-git-and-artifacts.md](05-git-and-artifacts.md).
- **Record provenance for fetched assets.** Keep a `manifest.json` for any downloaded library
  (Canvas Automation Toolkit keeps `sounds/external-service/manifest.json` with per-asset license URLs) and gitignore the
  bulk. The manifest is the recipe that re-fetches the asset and records its license.
- **Fail soft when the service is absent.** The core tool should still run offline. Treat the
  API as an optional enrichment, the way Canvas Automation Toolkit's build "best-effort" refreshes an appendix and
  falls back to the last-built copy if the refresh tool is unavailable.

## Keep the runtime AI-free

The test: unplug the network and remove every MCP, then double-click the tool's `.command`. It
must still run full-featured. The MCP let an AI build or drive the tool; it is not part of how
the tool works for a human. If removing the MCP breaks the core, the architecture has leaked,
and the fix is to push the real work back into the AI-free engine and CLI.

## Letting AIs drive the AI-free tool

You usually do not need an MCP to let an AI operate a tool. Because the `.command` and CLI take
positional args and run headlessly, any agent (cloud or local) can drive the tool by calling
the command, exactly as a shell would. Reserve the MCP for the case where the AI must
interactively control a live, stateful external application. For the general "an AI uses this
tool" case, see [08-skills-and-ai-integration.md](08-skills-and-ai-integration.md).
