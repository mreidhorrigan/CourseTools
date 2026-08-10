# Course quality assurance

No single checker proves that a Canvas course works. Use all of these checks in
an unpublished sandbox before students enter the course.

## Stored, deterministic checks

1. Run `./verify.command` before building or sharing Canvas Automation.
2. Build IMSCC files from stored specs. Keep the migration report and inspect
   every warning.
3. Run `scripts/check_external_links.py COURSE.imscc`. The checker uses official
   oEmbed endpoints for YouTube and Vimeo, because a provider page can return
   HTTP 200 while its video is unavailable. `PROTECTED` means automation could
   not prove playability. It is not a pass.
   Use `--outtakes-out out/link-outtakes.json`. Library search/resolver URLs are
   `OUTTAKE`: replace them with stable item-level DOI, publisher, repository,
   or author links. Keep unresolved items in outtakes until a human verifies a
   lawful access route.
4. After a guarded live import, run the relevant course verifier and review its
   JSON result. Check expected counts, publication state, rubric associations,
   quiz questions, assignment-group weights, and unresolved migration tokens.
   With `--check-external --record REPORT.json`, Canvas-host links remain in the
   authenticated internal checks while only other hosts receive public-web
   probes.

## Canvas checks

1. Open **Settings > Validate Links in Content**. Include unpublished content.
2. Check **Student View**, module sequence, prerequisites, due dates, assignment
   groups, total weights, rubrics, quiz settings, and file permissions.
3. Run Canvas's course accessibility checker when your institution enables it.
   Also review captions, transcripts, alt text, heading order, table headers,
   colour contrast, keyboard use, and external embeds by hand.
4. Open every external video in a signed-out or private browser window. Provider
   privacy, geography, embedding rules, and deletion can change after QA.
5. Export or copy the course into another empty sandbox and repeat internal-link
   checks. Hard-coded course IDs are a migration hazard.

## Canvas link rules we monitor

- Prefer native Canvas objects and migration-aware references over hard-coded
  course URLs.
- Never treat HTTP 200 alone as proof that media is playable.
- Validate page fragments as well as page slugs.
- Check links to unpublished or deleted Canvas objects.
- Check authentication and enrolment visibility in Student View.
- Re-run internal and external validation after every course copy or import.
- See `docs/canvas-html-link-research.md` for the detailed migration analysis.

## Authoritative references

- [Canvas Link Validator](https://community.instructure.com/en/kb/articles/661141-how-do-i-validate-links-in-a-course)
- [Canvas Course Import Tool](https://community.instructure.com/en/kb/articles/662748-what-is-the-course-import-tool)
- [Canvas Accessibility Checker](https://community.instructure.com/en/kb/articles/664351-how-do-i-use-the-accessibility-checker-in-canvas)
- [Canvas API endpoint attributes](https://developerdocs.instructure.com/services/canvas/basics/file.endpoint_attributes)
- [Vimeo oEmbed behavior](https://developer.vimeo.com/api/oembed/videos)
