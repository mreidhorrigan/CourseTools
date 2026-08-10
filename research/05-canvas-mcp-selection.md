# Canvas MCP selection and integration

Selected: `vishalsachdev/canvas-mcp`, currently pinned at 1.7.0.

Version 1.7.0 was adopted for the collaborator distribution on 2026-08-08. It
adds shared postcondition checks for Canvas writes and fixes operations that
previously trusted HTTP 200 without confirming the requested state. The MCP
environment now uses a universal, hash-locked transitive requirements file,
compiled from `mcp/requirements.in` by the stored updater.

Compared with `DMontgomery40/mcp-canvas-lms`, the selected server has a larger
educator-oriented surface, more active contributors and adoption, explicit
Codex support, role-based tool filtering, Canvas pagination/User-Agent
compliance, rubric creation/association fixes, PII log redaction, token
validation, and safer bulk-delete defaults. It is MIT licensed and published as
the `canvas-mcp` Python package.

Primary project references:

- https://github.com/vishalsachdev/canvas-mcp
- https://github.com/vishalsachdev/canvas-mcp/blob/main/SECURITY.md
- https://github.com/DMontgomery40/mcp-canvas-lms

The MCP is an independent project, not an Instructure product. For this reason,
the deterministic API and IMSCC paths remain authoritative for repeatable bulk
work. MCP changes should be small and reviewed.

## Local security design

The package lives in `mcp/.venv`; the committed requirement pins its top-level
version. Codex stores only the absolute launcher path and `--role educator`.
The launcher reads the API URL and token from macOS Keychain services
`canvas-automation-mcp-url` and `canvas-automation-mcp-token`. No token is
stored in TOML, JSONC, `.env`, provenance, logs, or source control.
