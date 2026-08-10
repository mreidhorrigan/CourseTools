# Distribution and media-link QA decisions

## Distribution

The collaborator ZIP follows the project handbook's recipe-not-bulk rule. The
builder uses a fixed allowlist rather than copying the working tree, sanitizes
live course targets, fixes ZIP timestamps and permissions, and writes a content
manifest, SHA-256 provenance, human license roll-up, and CycloneDX SBOM. It
excludes `.git`, environments, output, credentials, and the IAT210 working
cartridge. Two builds from the same source and locks must have the same hash.

macOS is the tested interface. The Python CLI is the portable contract for
Linux. Windows is experimental until native wrappers and credential handling
have their own acceptance tests.

The generated `index.html` is a local, script-built landing page. It presents
four operator paths: deterministic macOS, web-chat-assisted file preparation,
CLI agent operation, and optional MCP. The deterministic path remains complete
without AI.

## External media

Generic HTTP validation produced a false positive for
`https://vimeo.com/175727157`: Vimeo returned a 200 page containing an
unavailable-video shell. Vimeo's documented oEmbed endpoint returned 404 for
that video. The shared checker therefore routes specific Vimeo and YouTube URLs
through official oEmbed endpoints. Ordinary URLs still use a redirect-following
GET. HTTP 401, 403, and 429 become `PROTECTED`, which requires manual review.

This remains one layer in a QA stack. Canvas Link Validator can find deleted and
unreachable course content, but provider security can cause false warnings. The
toolkit therefore also requires Student View, signed-out video playback, import
report review, accessibility checks, and repeated QA after course copies.

## Sources

- Canvas API endpoint attributes:
  https://developerdocs.instructure.com/services/canvas/basics/file.endpoint_attributes
- Canvas content migrations:
  https://developerdocs.instructure.com/services/canvas/resources/content_migrations
- Canvas Link Validator:
  https://community.instructure.com/en/kb/articles/661141-how-do-i-validate-links-in-a-course
- Canvas Course Import Tool:
  https://community.instructure.com/en/kb/articles/662748-what-is-the-course-import-tool
- Canvas Accessibility Checker:
  https://community.instructure.com/en/kb/articles/664351-how-do-i-use-the-accessibility-checker-in-canvas
- Vimeo oEmbed and error behavior:
  https://developer.vimeo.com/api/oembed/videos
- Canvas MCP upstream releases:
  https://github.com/vishalsachdev/canvas-mcp/releases
