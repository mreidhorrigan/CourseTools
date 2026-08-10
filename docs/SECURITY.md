# Security model

Canvas tokens must never be committed, placed in JSONC, printed, copied into
provenance, or embedded in an IMSCC. The REST token lives only in the
environment of a server bound to `127.0.0.1`. MCP credentials live in macOS
Keychain and are injected into the pinned server process by its launcher.

Treat MCP as a privileged operator: an LLM can choose tool arguments and may
misunderstand scope. Confirm the Canvas instance, course, object type, and
publication state before writes. Use least-privilege tokens, a sandbox course,
and deterministic workflows for bulk changes.

The REST server derives and enforces one course ID from the full
`sandbox_course_url` configured at startup. It also requires that the sandbox
and API hostnames match. The guard applies
for dedicated routes and raw Classic/New Quiz paths. It returns HTTP 403 before
contacting Canvas when a different course ID is requested. The independent MCP
server does not provide that guard; safe MCP mutation testing therefore
requires a dedicated Canvas account enrolled only in the sandbox. An ordinary
instructor token plus a prompt saying “sandbox only” is not sufficient
isolation. Manual IMSCC imports must be initiated from the sandbox course's own
settings page because Canvas chooses the destination in its UI.

`out/` is gitignored but may contain student names, grades, course content, and
Canvas URLs. Protect it according to institutional privacy policy; do not sync
it to an unapproved service. Provenance records identifiers but no credentials.
Review logs and screenshots before sharing them because error responses can
contain course data.

The cartridge path is credential-free but output may contain copyrighted or
sensitive teaching materials. Inspect its file list before distribution.
Dependencies are locked; update them through the documented review-and-commit
process and run the complete verification gate afterward.

The optional assignment-and-rubric QA harness sends each configured source file
to Mistral's external API. Its hidden prompt keeps `MISTRAL_API_KEY` in process
memory and reports never contain the key. Use invented examples or deliberately
selected instructional material. Do not send student work, grades, accommodation
information, private assessment keys, confidential sources, or unrestricted
Canvas exports. Review institutional requirements and the provider's current
terms before use.
