# Seat Planner Headless

The command-line counterpart to `SeatPlanner.html`. It turns a class roster (and
an optional room layout) into a seating chart, written out as a CSV grid and a
PDF. The roster parsing and seat-assignment logic are kept **identical** to the
browser tool — fix bugs in both.

## Installation

Ensure you have Node.js installed, then run:

```bash
npm install
```

The Seat Planner CLI only needs `commander`, `jsdom`, and `jspdf` (all already
listed in `package.json`). It has **no native dependency** — `jspdf` runs against
a tiny JSDOM document, so there is nothing to compile.

## Quick Start (macOS)

For a one-click run using the defaults in `seatplanner.config.json`:

1. Place your roster in a file named `students.csv` in this directory.
2. Double-click `run_seatplanner.command`.

## Roster formats

The same upload accepts either format — the tool auto-detects which:

* **Simple** — column 1 = name, column 2 (optional) = score, column 3 (optional)
  = a note.
* **Canvas gradebook export** — drop the export as-is. Names (`Last, First` →
  `First Last`), the **Unposted Current Score** column, and the **Notes** column
  are read automatically. Canvas's metadata rows ("Manual Posting", "Points
  Possible") and the reserved Test Student are skipped.

By default every student is **spread evenly** across the room (empty seats are
distributed evenly too). Two optional features change that:

* **Ranking** (`--rank`) places students with **lower scores toward the bottom**
  of the chart. The chart is agnostic about which end faces the room — it just
  ranks low-to-bottom.
* **Flagging** (`--flag`) flags students whose note contains one of the integrity
  terms and seats them at the **bottom-most** seats. Terms default to
  `integrity concern` and `integrity flag`; override them with `--flag-terms`
  or `--flag-terms-file`.

## Layout format

Optional CSV where any cell containing `X` is a valid seat and everything else is
an aisle/gap. With no layout supplied, a default 5×9 layout (35 seats, two aisles)
is used.

## Configuration

Edit `seatplanner.config.json` to change the defaults used when no flags are passed:

```json
{
  "students": "students.csv",
  "layout": null,
  "output": "output",
  "rank": false,
  "flag": false,
  "flagTerms": ["integrity concern", "integrity flag"]
}
```

## Usage

```bash
node seatplanner.js --students <roster.csv> [options]
```

### Options

* `-s, --students <path>`: Path to the roster CSV (simple or Canvas). Default `students.csv`.
* `-l, --layout <path>`: Optional classroom layout CSV.
* `-o, --output <path>`: Output directory (default `./output`).
* `--rank`: Rank by gradebook score — lower scores toward the bottom (off by default).
* `--flag`: Flag students whose Notes contain an integrity term (off by default).
* `--flag-terms <list>`: Comma-separated Notes substrings that trigger a flag
  (default `integrity concern,integrity flag`).
* `--flag-terms-file <path>`: A file of flag terms, one per line (merged with `--flag-terms`).
* `--no-pdf`: Write only the CSV, skip the PDF.

### Output

For a roster named `roster.csv` the tool writes, into the output directory:

* `roster_seating-chart.csv` — the grid of names (same layout as the chart).
* `roster_seating-chart.pdf` — a printed seating chart (landscape, names only).
  When ranking is on it carries a caption "Lower scores ranked toward the bottom
  of the chart."

### Example

```bash
# Canvas export, ranked + flagged, on a custom room layout
node seatplanner.js \
  -s examples/gradebook_canvas_example.csv \
  -l examples/layout_60-seats_5-rows_1-aisle.csv \
  -o ./out --rank --flag

# Use a custom integrity-term list instead of the defaults
node seatplanner.js -s roster.csv --flag --flag-terms "cheating,plagiarism,proctor note"
```
