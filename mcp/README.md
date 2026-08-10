# Canvas MCP integration

This project pins `canvas-mcp` and its full transitive environment in
`mcp/requirements.lock`. Codex launches it through
`canvas-mcp-launcher`, which retrieves the Canvas API URL and token from macOS
Keychain. No secret is stored in this repository or in Codex's TOML config.

Run `commands/setup-canvas-mcp.command` once, enter an API URL ending in
`/api/v1`, and enter the token at the hidden prompt. Open a new Codex session
afterward. Use MCP for conversational discovery and small, reviewable changes;
use the repository commands for repeatable scripted changes and `build-imscc`
for deterministic bulk import packages.

## Updating

Run `commands/update-canvas-mcp.command VERSION` with an explicit release. It
updates `mcp/requirements.in`, compiles a universal hash-locked transitive
environment, syncs the separate MCP venv, smoke-tests the executable, and shows
the Git diff. Run `verify.command` and review upstream release and security notes
before committing. Rollback is then a normal Git revert.

### Efficient integration path for a new MCP release

1. Read the upstream changelog, security policy, and release diff. Confirm the
   release still supports local stdio, the educator tools, and Python 3.12.
2. Run `commands/update-canvas-mcp.command VERSION`. Do not edit the generated
   lock by hand. The command updates the direct pin, compiles universal hashes,
   syncs only `mcp/.venv`, and smoke-tests `canvas-mcp-server`.
3. Run `./verify.command`. The gate checks the direct pin, transitive hash lock,
   shell syntax, schemas, and toolkit compatibility tests.
4. Run `commands/build-distribution.command` twice. Compare the printed ZIP
   SHA-256 values. The generated `index.html` reads the MCP version from the
   lock, and `sbom.json` inventories the whole optional environment.
5. In a fresh AI session, confirm the server version and make one harmless read
   in a sandbox. Make a write only when the release changes write behavior.
6. Commit `mcp/requirements.in`, `mcp/requirements.lock`, any compatibility
   changes, tests, research notes, and toolkit docs together.

If any step fails, restore the prior Git revision and sync the previous lock.
The deterministic engine remains usable throughout because its environment is
separate.
