# Canvas import-package generation

The reference was `IAT210_Fall2026_course_package_v1.9.0`. Its central lesson
is that a valid ZIP is not necessarily a valid Canvas migration: module items
must reference real object migration identifiers, resource files must be
enumerated in `imsmanifest.xml`, and workflow-state values differ between
Canvas object families.

`build-imscc` therefore generates identifiers deterministically from stable
spec keys, writes Canvas course/module/assignment metadata, writes a Common
Cartridge 1.1 manifest, and makes a ZIP with stable entry order and timestamps.
The same spec and input bytes produce the same cartridge bytes.

The initial from-scratch schema intentionally covers the dependable core:
course settings, assignment groups, pages, assignments, graded or ungraded
discussions, rubrics, files, and modules.
The v1.9 package's post-import finalizer is course-specific and is not copied;
generated packages should first be imported into a clean sandbox and reviewed.
