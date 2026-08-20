const fs = require('fs');
const path = require('path');
const { program } = require('commander');
const { JSDOM } = require('jsdom');
const { jsPDF } = require('jspdf');

// jspdf reaches for browser globals even when only drawing vector text/rects.
// A tiny JSDOM document satisfies it so the CLI needs no native dependency.
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.atob = (s) => Buffer.from(s, 'base64').toString('binary');
global.btoa = (s) => Buffer.from(s, 'binary').toString('base64');

// ── CLI Configuration ─────────────────────────────────────────────────────────
const configPath = path.resolve(__dirname, 'seatplanner.config.json');
let config = {};
if (fs.existsSync(configPath)) {
  try {
    config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch (e) {
    console.warn('Warning: Could not parse seatplanner.config.json, using defaults.');
  }
}

const DEFAULT_FLAG_TERMS = ['integrity concern', 'integrity flag'];

program
  .name('seatplanner-headless')
  .description('Headless Seat Planner — turn a roster (+ optional room layout) into a seating chart')
  .version('1.1.0')
  .option('-s, --students <path>', 'Path to the roster CSV (simple or Canvas gradebook export)', config.students || 'students.csv')
  .option('-l, --layout <path>', 'Path to an optional classroom layout CSV', config.layout || null)
  .option('-o, --output <path>', 'Output directory', config.output || './output')
  .option('--rank', 'Rank by gradebook score: lower scores toward the bottom of the chart', config.rank === true)
  .option('--flag', "Flag students whose Canvas Notes contain an integrity term", config.flag === true)
  .option('--flag-terms <list>', 'Comma-separated Notes substrings that trigger a flag',
    (config.flagTerms && config.flagTerms.length ? config.flagTerms.join(',') : DEFAULT_FLAG_TERMS.join(',')))
  .option('--flag-terms-file <path>', 'File of flag terms, one per line (merged with --flag-terms)')
  .option('--no-pdf', 'Skip the PDF output (CSV only)')
  .parse(process.argv);

const options = program.opts();

// ════════════════════════════════════════════════════════════════════════════
//  CORE LOGIC — kept in lock-step with the browser tool (SeatPlanner.html).
//  parseCSV / isCanvasGradebook / ingest* / noteMatches / selectFilledSeats /
//  assignSeats are intentionally identical to their counterparts there; fix
//  bugs in BOTH.
// ════════════════════════════════════════════════════════════════════════════

// 5 rows, 9 cols: X X _ X X X _ X X
const DEFAULT_LAYOUT = (function () {
  const pattern = ['X', 'X', '', 'X', 'X', 'X', '', 'X', 'X'];
  return Array.from({ length: 5 }, () => [...pattern]);
})();

// ── CSV parsing (RFC-4180-ish: quoted fields, embedded commas/quotes/newlines) ─
function parseCSV(text) {
  const rows = [];
  let row = [], field = '', inQuotes = false;
  text = text.replace(/\r\n?/g, '\n');
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else inQuotes = false;
      } else field += ch;
    } else {
      if (ch === '"') inQuotes = true;
      else if (ch === ',') { row.push(field); field = ''; }
      else if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
      else field += ch;
    }
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows.map(r => r.map(c => c.trim()));
}

// ── Canvas gradebook detection & ingestion ────────────────────────────────────
function isCanvasGradebook(rows) {
  if (!rows.length) return false;
  const header = rows[0].map(h => h.toLowerCase());
  return header[0] === 'student' && header.some(h => h.includes('sis login id'));
}

// "Last, First Middle" → "First Middle Last"
function flipName(raw) {
  const s = (raw || '').trim();
  const comma = s.indexOf(',');
  if (comma === -1) return s;
  const last = s.slice(0, comma).trim();
  const first = s.slice(comma + 1).trim();
  return (first + ' ' + last).trim() || s;
}

// Ingest returns RAW per-student data: { name, score (number|null), note (string) }.
// Whether a score is used for ranking, and whether a note becomes a flag, is
// decided later from the run options — not here.
function ingestCanvas(rows) {
  const header = rows[0].map(h => h.toLowerCase());
  const idxNotes = header.indexOf('notes');
  const idxScore = header.indexOf('unposted current score');   // ranking uses the UNPOSTED score

  // Skip Canvas metadata rows: "Manual Posting" (blank name) and "Points Possible".
  let dataRows = rows.slice(1).filter(r => {
    const name = (r[0] || '').trim();
    if (!name) return false;
    if (/^points possible/i.test(name)) return false;
    return true;
  });

  // Drop Canvas's reserved Test Student, but only if real students remain.
  const isTestStudent = n => /^\s*(student,\s*test|test\s+student)\s*$/i.test(n || '');
  if (dataRows.some(r => !isTestStudent(r[0])))
    dataRows = dataRows.filter(r => !isTestStudent(r[0]));

  const students = dataRows.map(r => {
    const scoreRaw = idxScore >= 0 ? r[idxScore] : '';
    const score = (scoreRaw !== undefined && scoreRaw !== '' && !isNaN(parseFloat(scoreRaw)))
      ? parseFloat(scoreRaw) : null;
    const note = idxNotes >= 0 ? (r[idxNotes] || '').trim() : '';
    return { name: flipName(r[0]), score, note };
  }).filter(s => s.name);

  return { students, hasScores: students.some(s => s.score !== null),
           hasNotes: students.some(s => s.note !== ''), source: 'canvas' };
}

function ingestSimple(rows) {
  const dataRows = rows.filter(r => r[0] && r[0].toLowerCase() !== 'name');
  const numericCol2 = dataRows.length > 0 &&
    dataRows.every(r => r[1] !== undefined && r[1] !== '' && !isNaN(parseFloat(r[1])));
  const students = dataRows.map(r => ({
    name: r[0],
    score: numericCol2 ? parseFloat(r[1]) : null,
    note: (r[2] !== undefined ? r[2] : '').trim()
  }));
  return { students, hasScores: students.some(s => s.score !== null),
           hasNotes: students.some(s => s.note !== ''), source: 'simple' };
}

function ingestRoster(rows) {
  return isCanvasGradebook(rows) ? ingestCanvas(rows) : ingestSimple(rows);
}

// ── Integrity-flag term matching ──────────────────────────────────────────────
function noteMatches(note, terms) {
  const n = (note || '').toLowerCase();
  return terms.some(t => t && n.includes(t));
}

// ── Even seat selection ───────────────────────────────────────────────────────
// Choose `count` seats to FILL, spreading the EMPTY seats evenly across the room
// (proportionally per row by largest-remainder, then evenly spaced within each
// row). Replaces farthest-point sampling, which tended to leave whole rows empty.
function selectFilledSeats(seats, count) {
  const M = seats.length;
  if (count >= M) return seats.slice();
  const K = M - count;                       // empties to place

  const byRow = new Map();
  for (const s of seats) {
    if (!byRow.has(s[0])) byRow.set(s[0], []);
    byRow.get(s[0]).push(s);
  }
  for (const arr of byRow.values()) arr.sort((a, b) => a[1] - b[1]);

  const rows = [...byRow.keys()].sort((a, b) => a - b).map(k => {
    const n = byRow.get(k).length, exact = K * n / M, floor = Math.floor(exact);
    return { k, n, floor, frac: exact - floor };
  });
  let assigned = rows.reduce((s, r) => s + r.floor, 0);
  rows.slice().sort((a, b) => b.frac - a.frac || b.n - a.n)
    .slice(0, K - assigned).forEach(r => r.floor++);

  const empty = new Set();
  for (const r of rows) {
    const rowSeats = byRow.get(r.k), n = r.n, e = r.floor;
    if (e <= 0) continue;
    const phase = Math.random();             // random phase: reshuffles move gaps, evenly
    for (let j = 0; j < e; j++) {
      let idx = Math.floor(((j + phase) * n) / e);
      if (idx >= n) idx = n - 1;
      let tries = 0;
      while (empty.has(rowSeats[idx]) && tries < n) { idx = (idx + 1) % n; tries++; }
      empty.add(rowSeats[idx]);
    }
  }
  return seats.filter(s => !empty.has(s));
}

// ── Assignment ────────────────────────────────────────────────────────────────
// students: [{ name, grade (number|null), flagged (bool) }] — already resolved.
function assignSeats(studentsData, layoutData, gradesActive, flagsActive) {
  const seats = [];
  for (let r = 0; r < layoutData.length; r++)
    for (let c = 0; c < layoutData[r].length; c++)
      if (layoutData[r][c] && layoutData[r][c].toUpperCase() === 'X') seats.push([r, c]);

  if (!seats.length) throw new Error('No seats found. Make sure the layout CSV has cells containing "X".');
  if (!studentsData || !studentsData.length) throw new Error('No student names found in the roster.');

  const count = Math.min(studentsData.length, seats.length);
  const filled = selectFilledSeats(seats, count);     // even spread of empties, always
  const bottomFirst = (a, b) => (a[0] !== b[0] ? b[0] - a[0] : a[1] - b[1]);
  let orderedSeats, orderedStudents;

  if (gradesActive) {
    // lower grades toward the bottom; flagged → very bottom
    orderedSeats = [...filled].sort(bottomFirst);
    orderedStudents = [...studentsData]
      .sort((a, b) => {
        const ea = a.flagged ? -Infinity : (a.grade ?? 0);
        const eb = b.flagged ? -Infinity : (b.grade ?? 0);
        return ea - eb;
      })
      .slice(0, count);
  } else if (flagsActive) {
    orderedSeats = [...filled].sort(bottomFirst);
    const flagged = studentsData.filter(s => s.flagged).sort(() => Math.random() - 0.5);
    const unflagged = studentsData.filter(s => !s.flagged).sort(() => Math.random() - 0.5);
    orderedStudents = [...flagged, ...unflagged].slice(0, count);
  } else {
    orderedSeats = filled;                              // order irrelevant — evenness is in `filled`
    orderedStudents = [...studentsData].sort(() => Math.random() - 0.5).slice(0, count).map(s => ({ ...s }));
  }

  const rows = layoutData.length;
  const cols = Math.max(...layoutData.map(r => r.length));

  const resultGrid = Array.from({ length: rows }, (_, r) =>
    Array.from({ length: cols }, (_, c) => {
      const v = layoutData[r] && layoutData[r][c] !== undefined ? layoutData[r][c] : '';
      return v.toUpperCase() === 'X' ? '' : v;
    })
  );
  const gradeGrid = Array.from({ length: rows }, () => Array(cols).fill(null));
  const flagGrid = Array.from({ length: rows }, () => Array(cols).fill(false));

  for (let i = 0; i < orderedSeats.length; i++) {
    const [r, c] = orderedSeats[i];
    const student = orderedStudents[i];
    if (!student) break;
    resultGrid[r][c] = student.name;
    gradeGrid[r][c] = student.grade;
    flagGrid[r][c] = student.flagged || false;
  }

  const isSeatAt = (r, c) =>
    layoutData[r] && layoutData[r][c] !== undefined && layoutData[r][c].toUpperCase() === 'X';

  return {
    resultGrid, gradeGrid, flagGrid, isSeatAt,
    totalSeats: seats.length,
    totalStudents: studentsData.length,
    assigned: orderedSeats.length
  };
}

// ════════════════════════════════════════════════════════════════════════════
//  OUTPUT WRITERS (headless-only)
// ════════════════════════════════════════════════════════════════════════════
function gridToCSV(resultGrid) {
  return resultGrid.map(row =>
    row.map(cell => {
      if (cell && (cell.includes(',') || cell.includes('"') || cell.includes('\n')))
        return `"${cell.replace(/"/g, '""')}"`;
      return cell;
    }).join(',')
  ).join('\n');
}

// A clean grid rendering that mirrors the browser's printed chart: names only
// (grade badges / flag markers are intentionally omitted, as the browser PDF
// suppresses them). The chart stays agnostic about which end faces the room.
function buildPDF(plan, meta) {
  const { resultGrid, isSeatAt } = plan;
  const doc = new jsPDF({ unit: 'pt', format: 'letter', orientation: 'landscape' });

  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 40;

  const accent = [107, 31, 42];   // --accent #6b1f2a
  const ink = [26, 26, 26];       // --ink   #1a1a1a
  const muted = [89, 89, 89];     // --muted #595959

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(...accent);
  doc.text('SEAT PLANNER', margin, margin);

  doc.setFontSize(18);
  doc.setTextColor(...ink);
  doc.text('Seating Plan', margin, margin + 18);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.setTextColor(...muted);
  const metaLines = [
    `${meta.totalStudents} students  ·  ${meta.totalSeats} seats`,
    `${meta.assigned} assigned  ·  ${meta.totalSeats - meta.assigned} empty`,
    `Generated ${meta.dateStr}`
  ];
  metaLines.forEach((line, i) => doc.text(line, pageW - margin, margin + i * 12, { align: 'right' }));

  const headerBottom = margin + 30;
  doc.setDrawColor(...accent);
  doc.setLineWidth(1.5);
  doc.line(margin, headerBottom, pageW - margin, headerBottom);

  const numRows = resultGrid.length;
  const numCols = Math.max(...resultGrid.map(r => r.length));
  const gridTop = headerBottom + 22;
  const footerH = 34;
  const availW = pageW - margin * 2;
  const availH = pageH - gridTop - footerH;
  const cellW = availW / numCols;
  const cellH = Math.min(availH / numRows, 70);
  const gridW = cellW * numCols;
  const gridLeft = margin + (availW - gridW) / 2;

  doc.setFontSize(9);
  for (let r = 0; r < numRows; r++) {
    for (let c = 0; c < numCols; c++) {
      const val = resultGrid[r] ? (resultGrid[r][c] || '') : '';
      const seat = isSeatAt(r, c);
      if (!seat && !val) continue;

      const x = gridLeft + c * cellW;
      const y = gridTop + r * cellH;

      if (seat && val) {
        doc.setFillColor(243, 238, 241);
        doc.setDrawColor(189, 169, 176);
        doc.setLineWidth(0.8);
        doc.rect(x, y, cellW, cellH, 'FD');
        doc.setTextColor(...ink);
        doc.setFont('helvetica', 'bold');
        const lines = doc.splitTextToSize(val, cellW - 8);
        const lineH = 11;
        let ty = y + cellH / 2 - ((lines.length - 1) * lineH) / 2 + 3;
        lines.forEach(line => { doc.text(line, x + cellW / 2, ty, { align: 'center' }); ty += lineH; });
      } else if (seat) {
        doc.setFillColor(251, 249, 250);
        doc.setDrawColor(221, 210, 214);
        doc.setLineWidth(0.8);
        doc.rect(x, y, cellW, cellH, 'FD');
        doc.setTextColor(194, 184, 188);
        doc.setFont('helvetica', 'italic');
        doc.text('empty', x + cellW / 2, y + cellH / 2 + 3, { align: 'center' });
      }
    }
  }

  // Only when ranking is on, note the gradient — described for the chart, not the
  // room (the tool is agnostic about which end faces the front).
  if (meta.rankActive) {
    const cueY = gridTop + numRows * cellH + 16;
    doc.setFont('helvetica', 'italic');
    doc.setFontSize(8);
    doc.setTextColor(138, 138, 138);
    doc.text('Lower scores ranked toward the bottom of the chart', pageW / 2, cueY, { align: 'center' });
  }

  return Buffer.from(doc.output('arraybuffer'));
}

// ── Flag-term resolution ──────────────────────────────────────────────────────
function resolveFlagTerms(opts) {
  let terms = (opts.flagTerms || '').split(',').map(t => t.trim()).filter(Boolean);
  if (opts.flagTermsFile) {
    const p = path.resolve(opts.flagTermsFile);
    if (fs.existsSync(p))
      terms = terms.concat(fs.readFileSync(p, 'utf8').split(/\r?\n/).map(t => t.trim()).filter(Boolean));
    else console.warn(`Warning: --flag-terms-file not found: ${p}`);
  }
  if (!terms.length) terms = DEFAULT_FLAG_TERMS.slice();
  return [...new Set(terms.map(t => t.toLowerCase()))];
}

// ════════════════════════════════════════════════════════════════════════════
//  MAIN
// ════════════════════════════════════════════════════════════════════════════
function run() {
  const studentsPath = path.resolve(options.students);
  const layoutPath = options.layout ? path.resolve(options.layout) : null;
  const outDir = path.resolve(options.output);

  if (!fs.existsSync(studentsPath)) {
    console.error(`Roster file not found: ${studentsPath}`);
    process.exit(1);
  }
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  console.log(`Reading roster ${studentsPath}...`);
  const roster = ingestRoster(parseCSV(fs.readFileSync(studentsPath, 'utf8')));
  if (!roster.students.length) {
    console.error('No students found in the roster CSV.');
    process.exit(1);
  }

  // Resolve the optional ranking / flagging features from the run options.
  const rankActive = options.rank && roster.hasScores;
  const terms = resolveFlagTerms(options);
  const resolved = roster.students.map(s => ({
    name: s.name,
    grade: rankActive ? s.score : null,
    flagged: options.flag ? noteMatches(s.note, terms) : false,
  }));
  const flagsActive = options.flag && resolved.some(s => s.flagged);

  console.log(
    `Loaded ${roster.students.length} students` +
    (roster.source === 'canvas' ? ' from a Canvas gradebook export' : '') + '.'
  );
  console.log(`Ranking: ${options.rank ? (rankActive ? 'on (by Unposted Current Score)' : 'on, but no scores found') : 'off'}` +
    `  ·  Flagging: ${options.flag ? (flagsActive ? `on (${resolved.filter(s => s.flagged).length} flagged; terms: ${terms.join(', ')})` : 'on, but no notes matched') : 'off'}`);

  let layoutData = DEFAULT_LAYOUT;
  if (layoutPath) {
    if (!fs.existsSync(layoutPath)) {
      console.error(`Layout file not found: ${layoutPath}`);
      process.exit(1);
    }
    layoutData = parseCSV(fs.readFileSync(layoutPath, 'utf8'));
    const seats = layoutData.flat().filter(c => c.toUpperCase() === 'X').length;
    console.log(`Loaded layout: ${layoutData.length} rows × ${layoutData[0].length} cols — ${seats} seats.`);
  } else {
    console.log('No layout supplied — using the default 35-seat layout.');
  }

  const plan = assignSeats(resolved, layoutData, rankActive, flagsActive);
  console.log(`Assigned ${plan.assigned} of ${plan.totalStudents} students to ${plan.totalSeats} seats.`);

  const baseName = path.basename(studentsPath).replace(/\.csv$/i, '');

  const csvPath = path.join(outDir, `${baseName}_seating-chart.csv`);
  fs.writeFileSync(csvPath, gridToCSV(plan.resultGrid));
  console.log(`Wrote ${csvPath}`);

  if (options.pdf) {
    const dateStr = new Date().toLocaleString('en-CA',
      { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    const pdfPath = path.join(outDir, `${baseName}_seating-chart.pdf`);
    fs.writeFileSync(pdfPath, buildPDF(plan, {
      totalStudents: plan.totalStudents, totalSeats: plan.totalSeats,
      assigned: plan.assigned, dateStr, rankActive
    }));
    console.log(`Wrote ${pdfPath}`);
  }

  console.log('Done!');
}

try { run(); }
catch (err) { console.error(err.message || err); process.exit(1); }
