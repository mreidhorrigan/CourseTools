# Classroom document tools: provenance and format preservation

This directory integrates M. Horrigan's established classroom-document tools.
The renderers are preserved rather than reimplemented so their tested spatial
formatting, print CSS, name fitting, and pagination remain authoritative.

Sources imported on 2026-08-18:

- `seatplanner.js`, `SeatPlanner.html`, `README_UPSTREAM.md`, and `layouts/`
  came from the DOC_TOOLS project. The headless renderer identifies itself as
  Seat Planner v1.1.0.
- `SeatPlanner-browser.html`, `Nameplates.html`, and `brand/brand.css` came
  from the corresponding bio-site versions. `Nameplates.html` is the
  authoritative tent-fold renderer: three
  bottom-anchored, automatically fitted names per US Letter page by default.

The integration creates adapter CSVs. It does not rewrite either renderer.
Nameplates remain an inspect-before-print workflow because the original tool
requires a human to verify parsed preferred names. The deterministic seating
CLI remains available for reviewed room layouts.

Source SHA-256 values:

- `seatplanner.js`: `99e03a437f23520f324d90a7fba77f61490805f6c80c865363d79dd299bd1953`
- `SeatPlanner.html`: `b66f7e0f35880399fcd0d2623de275d346c76ec36ee921b2c5c30d76f2af9e88`
- `SeatPlanner-browser.html`: `ba3eb2bb73a0ccbdb71ff005ed00a729ea47a072ef2cb51771de09161d97f092`
- `Nameplates.html`: `55ea90775691d1b70318fd3bc6b691c2c1e3b2e1c780d52e11b0dbb005587e51`
- `brand/brand.css`: `ddefe426953183ee40296c15bb4ba9fe57f53a6ebc89e6e962cd33a03ad86cbf`
- `README_UPSTREAM.md`: `0e10c3a8913f4170d34e10fd9ca8bde8d8646801af89044babefb95938d7f507`
- `layout_35-seats_5-rows_2-aisles.csv`: `2149061261846f0c1097e571ad4912a897518600c8d15844ab49585dc26a8f8f`
- `layout_48-seats_4-rows_1-aisle.csv`: `0ceecfcfc3d705ace27c81c4636db94ffc47d8e180bd7bd4f47fd0e409454565`
- `layout_60-seats_5-rows_1-aisle.csv`: `84f7fbc587ffed4d0993c41254a2d7c1515f039d851cd76be2f5bf240512c3c8`
- `layout_SIAT.csv`: `09f3417dee7339c3baaafdaaf97aad2381c7971710296f1d2ecc33b2766c1d1d`

The software is by M. Horrigan and is included under this toolkit's MIT
license. The bio-site visual assets retain the notices stated in `LICENSES.md`.
