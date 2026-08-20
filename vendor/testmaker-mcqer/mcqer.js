const fs = require('fs');
const path = require('path');
const mammoth = require('mammoth');
const docx = require('docx');
const { PDFDocument } = require('pdf-lib');
const { jsPDF } = require('jspdf');
const { program } = require('commander');
const { JSDOM } = require('jsdom');

// canvas is optional: it's only used to measure intrinsic image dimensions, and
// its native build is fragile on newer Node. When it's unavailable we fall back
// to a tiny pure-JS header reader (readImageSize), so the CLI installs and runs
// with no native dependency. Install canvas for sub-pixel-exact sizing if needed.
let loadImage = null;
try { ({ loadImage } = require('canvas')); } catch (_) { /* optional */ }

// Mock browser globals for jspdf/parser
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
global.window = dom.window;
global.document = dom.window.document;
global.Node = dom.window.Node;
global.Image = dom.window.Image;
global.atob = (s) => Buffer.from(s, 'base64').toString('binary');
global.btoa = (s) => Buffer.from(s, 'binary').toString('base64');

// ── CLI Configuration ───────────────────────────────────────────────────────
const configPath = path.resolve(__dirname, 'config.json');
let config = {};
if (fs.existsSync(configPath)) {
  try {
    config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch (e) {
    console.warn('Warning: Could not parse config.json, using defaults.');
  }
}

program
  .name('mcqer-headless')
  .description('Headless MCQer exam generator')
  .version('1.0.0')
  .option('-i, --input <path>', 'Path to input questions .docx or .html file', config.input || 'questions.docx')
  .option('-o, --output <path>', 'Output directory', config.output || './output')
  .option('-c, --coversheet <path>', 'Path to optional PDF coversheet', config.coversheet || null)
  .option('-img, --images <path>', 'Directory containing images for [Image: ...] tags', config.images || null)
  .option('-v, --versions <number>', 'Number of versions to generate', (v) => parseInt(v), config.versions || 3)
  .option('-f, --font-size <number>', 'Font size in pt', (f) => parseInt(f), config.fontSize || 11)
  .option('-m, --margin-size <number>', 'Margin size in pt', (m) => parseInt(m), config.marginSize || 36)
  .option('--seed <text>', 'Deterministic shuffle seed', config.seed || '1')
  .parse(process.argv);

const options = program.opts();

// CourseTools addition: use deterministic shuffling for reproducible forms and
// answer keys while preserving MCQer's original Fisher-Yates behavior.
function seededRandom(seedText) {
  let h = 2166136261;
  for (const char of String(seedText)) {
    h ^= char.charCodeAt(0);
    h = Math.imul(h, 16777619);
  }
  return function random() {
    h += 0x6D2B79F5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const randomValue = seededRandom(options.seed);

// ── State and Constants ─────────────────────────────────────────────────────
const VERSION_LABELS = ['A','B','C','D','E'];
const LETTER = { width: 612, height: 792 };   // default paper size (8.5 × 11 in, points)
let parsedQuestions    = [];
let hasVersionXTag     = false;
let uploadedImages     = {};

// ── Utilities ─────────────────────────────────────────────────────────────
function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(randomValue() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ── Rich-text model ───────────────────────────────────────────────────────
const isImageRun = r => !!r.image;

function htmlToRichParagraphs(html) {
  const container = document.createElement('div');
  container.innerHTML = html;
  const blocks = container.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li');
  const list = blocks.length ? Array.from(blocks) : [container];

  return list
    .map(block => mergeRuns(collectRuns(block)))
    .filter(runs => runs.length);
}

function collectRuns(block) {
  const out = [];
  (function walk(node, underlined) {
    node.childNodes.forEach(child => {
      if (child.nodeType === 3) {                       // text
        out.push({ text: child.textContent, underline: underlined });
      } else if (child.nodeType === 1) {                // element
        const tag = child.tagName.toLowerCase();
        if (tag === 'img' && child.getAttribute('src')) {
          out.push(makeImageRun(child));
        } else {
          const u = underlined || tag === 'u' ||
            ((child.style?.textDecoration || '').includes('underline'));
          walk(child, u);
        }
      }
    });
  })(block, false);
  return out;
}

function makeImageRun(img) {
  const w = parseFloat(img.getAttribute('width'))  || null;
  const hh = parseFloat(img.getAttribute('height')) || null;
  return { text: '', underline: false,
           image: { dataUrl: img.getAttribute('src'), width: w, height: hh } };
}

function mergeRuns(runs) {
  const out = [];
  runs.forEach(r => {
    if (isImageRun(r)) { out.push(r); return; }
    if (!r.text) return;
    const last = out[out.length - 1];
    if (last && !isImageRun(last) && last.underline === r.underline) last.text += r.text;
    else out.push({ text: r.text, underline: r.underline });
  });
  return out;
}

const runsText = runs => runs.map(r => r.text).join('');
const hasImage = runs => runs.some(isImageRun);
const prependPlain = (prefix, runs) => [{ text: prefix, underline: false }, ...runs];

function sliceRuns(runs, start, end) {
  const out = [];
  let pos = 0;
  for (const r of runs) {
    if (isImageRun(r)) {
      if (pos >= start && pos <= end) out.push(r);
      continue;
    }
    const rStart = pos, rEnd = pos + r.text.length;
    if (rEnd > start && rStart < end) {
      const t = r.text.slice(Math.max(start, rStart) - rStart,
                             Math.min(end, rEnd) - rStart);
      if (t) out.push({ text: t, underline: r.underline });
    }
    pos = rEnd;
  }
  return out;
}

function trimRuns(runs) {
  if (!runs.length) return runs;
  const text = runsText(runs);
  const start = text.length - text.replace(/^\s+/, '').length;
  const end   = text.replace(/\s+$/, '').length;
  const sliced = sliceRuns(runs, start, end);
  const lead  = [], trail = [];
  for (const r of runs) { if (isImageRun(r)) lead.push(r); else if (r.text.trim()) break; }
  for (let i = runs.length - 1; i >= 0; i--) { const r = runs[i]; if (isImageRun(r)) trail.unshift(r); else if (r.text.trim()) break; }
  const dedup = arr => arr.filter(r => !sliced.includes(r));
  return [...dedup(lead), ...sliced, ...dedup(trail)];
}

function fitImage(image, maxW, maxH = 540) {
  let w = image.width || 300, h = image.height || 200;
  if (w > maxW) { h *= maxW / w; w = maxW; }
  if (h > maxH) { w *= maxH / h; h = maxH; }
  return { w: Math.round(w), h: Math.round(h) };
}

// Minimal intrinsic-size reader for the common web image formats — the fallback
// used when the optional `canvas` module isn't installed. Returns {width,height}
// or null (callers then use sensible defaults).
function readImageSize(dataUrl) {
  const comma = dataUrl.indexOf(',');
  if (comma < 0) return null;
  let buf;
  try { buf = Buffer.from(dataUrl.slice(comma + 1), 'base64'); } catch (_) { return null; }
  if (buf.length < 24) return null;

  // PNG: 8-byte signature, then IHDR with width@16 / height@20 (big-endian)
  if (buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47)
    return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };

  // GIF: width@6 / height@8 (little-endian)
  if (buf[0] === 0x47 && buf[1] === 0x49 && buf[2] === 0x46)
    return { width: buf.readUInt16LE(6), height: buf.readUInt16LE(8) };

  // JPEG: scan segments for a Start-Of-Frame marker, then read height/width
  if (buf[0] === 0xff && buf[1] === 0xd8) {
    let off = 2;
    while (off + 9 < buf.length) {
      if (buf[off] !== 0xff) { off++; continue; }
      const marker = buf[off + 1];
      const len = buf.readUInt16BE(off + 2);
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc)
        return { height: buf.readUInt16BE(off + 5), width: buf.readUInt16BE(off + 7) };
      off += 2 + len;
    }
  }
  return null;
}

async function preloadImageDimensions(items) {
  const imageRuns = [];
  const visit = runs => runs && runs.forEach(r => { if (isImageRun(r)) imageRuns.push(r); });
  items.forEach(item => {
    if (item.type === 'paragraph') visit(item.content);
    else if (item.type === 'question') { visit(item.question); visit(item.answer); (item.distractors || []).forEach(visit); }
    else if (item.questions) item.questions.forEach(q => {
      if (q.type === 'paragraph') visit(q.content);
      else { visit(q.question); visit(q.answer); (q.distractors || []).forEach(visit); }
    });
  });

  for (const r of imageRuns) {
    if (r.image.width && r.image.height) continue;
    try {
      if (loadImage) {                                 // canvas present: exact sizing
        const img = await loadImage(r.image.dataUrl);
        r.image.width = img.width;
        r.image.height = img.height;
      } else {                                         // fall back to header sniffing
        const size = readImageSize(r.image.dataUrl);
        r.image.width = size ? size.width : 300;
        r.image.height = size ? size.height : 200;
      }
    } catch (e) {
      r.image.width = 300;
      r.image.height = 200;
    }
  }
}

// ── Parser Logic ────────────────────────────────────────────────────────────
function stripVersionXParagraph(richParas) {
  hasVersionXTag = richParas.some(runs => runsText(runs).includes('[Version X]'));
  return richParas.filter(runs => runsText(runs).trim() !== '[Version X]');
}

function collectAllQuestions(items) {
  return items.flatMap(item =>
    (item.type === 'option-pool' || item.type === 'scramble-pool') ? item.questions
    : item.type === 'question' ? [item] : []);
}

const CONTENT_SPLIT_RE = /(\[Question\.\]|\[Answer\.\]|\[Correct\.\]|\[Distractor\.\])/;
const PARAGRAPH_RE      = /^\[(Paragraph|Not a question)\.\]\s*/i;
const KEEP_PREV_RE      = /^\[Keep with previous\.\]\s*/i;
const IMAGE_TAG_RE      = /\[Image:\s*([^\]]+?)\s*\]/i;

const hasContent = runs => runsText(runs).trim() !== '' || hasImage(runs);

function stripPrefix(runs, re) {
  const m = runsText(runs).match(re);
  return m ? trimRuns(sliceRuns(runs, m[0].length, runsText(runs).length)) : runs;
}

function resolveImageTags(runs) {
  const plain = runsText(runs);
  const m = plain.match(IMAGE_TAG_RE);
  if (!m) return runs;
  const name = m[1].trim();
  const dataUrl = uploadedImages[name];
  const before = trimRuns(sliceRuns(runs, 0, m.index));
  const after  = trimRuns(sliceRuns(runs, m.index + m[0].length, plain.length));
  const imgRun = dataUrl ? [{ text: '', underline: false, image: { dataUrl, width: null, height: null } }] : [];
  return resolveImageTags([...before, ...imgRun, ...after]);
}

function parseRichSegment(runs, extraProps) {
  runs = resolveImageTags(trimRuns(runs));
  const plain = runsText(runs);
  if (!hasContent(runs)) return null;

  if (PARAGRAPH_RE.test(plain)) {
    let rest = stripPrefix(runs, PARAGRAPH_RE);
    const keepWithPrev = KEEP_PREV_RE.test(runsText(rest));
    if (keepWithPrev) rest = stripPrefix(rest, KEEP_PREV_RE);
    return hasContent(rest) ? { type: 'paragraph', content: rest, keepWithPrev, ...extraProps } : null;
  }

  if (KEEP_PREV_RE.test(plain)) {
    const rest = stripPrefix(runs, KEEP_PREV_RE);
    return hasContent(rest) ? { type: 'paragraph', content: rest, keepWithPrev: true, ...extraProps } : null;
  }

  if (!/\[Question\.\]/.test(plain) && hasImage(runs)) {
    return { type: 'paragraph', content: runs, keepWithPrev: true, ...extraProps };
  }

  if (!/\[Question\.\]/.test(plain)) return null;
  return parseQuestionRuns(runs, plain, extraProps);
}

function parseQuestionRuns(runs, plain, extraProps) {
  let question = null, answer = null, tag = null, pos = 0;
  const distractors = [];

  for (const tok of plain.split(CONTENT_SPLIT_RE)) {
    if (tok === '[Question.]')                        { tag = 'q'; pos += tok.length; continue; }
    if (tok === '[Answer.]' || tok === '[Correct.]')  { tag = 'a'; pos += tok.length; continue; }
    if (tok === '[Distractor.]')                      { tag = 'd'; pos += tok.length; continue; }
    if (!tok) continue;
    const seg = trimRuns(sliceRuns(runs, pos, pos + tok.length));
    pos += tok.length;
    if (!hasContent(seg)) continue;
    if      (tag === 'q') question = seg;
    else if (tag === 'a') answer = seg;
    else if (tag === 'd') distractors.push(seg);
  }
  return question ? { type: 'question', question, answer, distractors, ...extraProps } : null;
}

function parseParagraph(runs, extraProps = {}) {
  runs = trimRuns(runs);
  const plain = runsText(runs);
  if (!plain.trim() && !hasImage(runs)) return [];

  const TAG = '[Page break.]';
  if (!plain.includes(TAG)) {
    const item = parseRichSegment(runs, extraProps);
    return item ? [item] : [];
  }

  const ranges = [];
  let cursor = 0, idx;
  while ((idx = plain.indexOf(TAG, cursor)) !== -1) { ranges.push([cursor, idx]); cursor = idx + TAG.length; }
  ranges.push([cursor, plain.length]);

  const results = [];
  ranges.forEach(([a, b], i) => {
    if (i > 0) {
      const prevWasContent = results.length && results[results.length - 1].type !== 'pagebreak';
      results.push({ type: 'pagebreak', blankPage: prevWasContent });
    }
    const seg = trimRuns(sliceRuns(runs, a, b));
    if (hasContent(seg)) {
      const item = parseRichSegment(seg, extraProps);
      if (item) results.push(item);
    }
  });
  if (!results.length) results.push({ type: 'pagebreak', blankPage: false });
  return results;
}

function parseAllParagraphs(richParas) {
  const items = [];
  let i = 0;

  function collectOptionParas() {
    const qs = [];
    while (i < richParas.length) {
      const runs = trimRuns(richParas[i]);
      const plain = runsText(runs);
      if (!/^\[Option\.\]/.test(plain)) break;
      let rest = sliceRuns(runs, plain.match(/^\[Option\.\]\s*/)[0].length, plain.length);
      let onlyVersion = null;
      const op = runsText(rest);
      const onlyMatch = op.match(/^\[Only Version ([A-E])\.\]\s*/i);
      if (onlyMatch) { onlyVersion = onlyMatch[1].toUpperCase(); rest = sliceRuns(rest, onlyMatch[0].length, op.length); }
      const parsed = parseParagraph(rest, { onlyVersion });
      parsed.forEach((p, pi) => {
        if (p.type === 'question' || p.type === 'paragraph') {
          const next = parsed[pi + 1];
          if (next && next.type === 'pagebreak') p = { ...p, pagebreakAfter: true };
          qs.push(p);
        }
      });
      i++;
    }
    return qs;
  }

  while (i < richParas.length) {
    const runs = trimRuns(richParas[i]);
    const text = runsText(runs);

    const poolMatch = text.match(/^\[Each version take (\d+) of the following options?\.\]$/i);
    if (poolMatch) {
      const take = parseInt(poolMatch[1], 10);
      i++;
      const poolQuestions = collectOptionParas();
      items.push({ type: 'option-pool', take, questions: poolQuestions });
      continue;
    }

    const scrambleMatch = text.match(/^\[Scramble the order of the following options?\.\]$/i);
    if (scrambleMatch) {
      i++;
      const poolQuestions = collectOptionParas();
      items.push({ type: 'scramble-pool', questions: poolQuestions });
      continue;
    }

    const onlyMatch = text.match(/^\[Only Version ([A-E])\.\]\s*/i);
    if (onlyMatch) {
      const onlyVersion = onlyMatch[1].toUpperCase();
      const rest = sliceRuns(runs, onlyMatch[0].length, text.length);
      parseParagraph(rest, { onlyVersion }).forEach(p => items.push(p));
      i++;
      continue;
    }

    if (/^\[Option\.\]/.test(text)) { i++; continue; }

    parseParagraph(runs, { onlyVersion: null }).forEach(p => items.push(p));
    i++;
  }

  return items;
}

function assignOptionPools(pools, versionLabels) {
  const assignments = new Map();
  pools.forEach(pool => {
    const versionMap = {};
    if (pool.type === 'scramble-pool') {
      versionLabels.forEach(lbl => { versionMap[lbl] = shuffle(pool.questions.slice()); });
      assignments.set(pool, versionMap);
      return;
    }
    const { take, questions } = pool;
    const poolSize = questions.length;
    let deck = [];
    const refill = () => { deck = shuffle(questions.slice()); };

    versionLabels.forEach(lbl => {
      const chosen = [];
      const setAside = [];
      const want = Math.min(take, poolSize);
      while (chosen.length < want) {
        if (deck.length === 0) {
          refill();
          if (deck.every(q => chosen.includes(q))) break;
        }
        const candidate = deck.shift();
        if (chosen.includes(candidate)) setAside.push(candidate);
        else chosen.push(candidate);
      }
      deck = deck.concat(setAside);
      versionMap[lbl] = chosen;
    });
    assignments.set(pool, versionMap);
  });
  return assignments;
}

function buildVersionParas(versionLabel, poolAssignments) {
  const paras = [];
  const letters = ['a','b','c','d','e'];
  paras.push({ type: 'version-label', text: 'Version ' + versionLabel });
  let questionNumber = 0;

  function emitParagraph(item) {
    paras.push({ type: 'paragraph', content: item.content, keepWithNext: true });
    if (item.pagebreakAfter) paras.push({ type: 'pagebreak', blankPage: true });
  }

  function emitQuestion(q) {
    const isMCQ = q.answer && q.distractors.length > 0;
    questionNumber++;
    const stem = prependPlain(questionNumber + '. ', q.question);
    paras.push({ type: 'question', content: stem, keepWithNext: isMCQ });
    if (isMCQ) {
      const scrambled = shuffle([{ runs: q.answer, isAnswer: true },
                                 ...q.distractors.map(d => ({ runs: d, isAnswer: false }))]);
      scrambled.forEach((opt, idx) => {
        const lettered = prependPlain('(' + letters[idx] + ') ', opt.runs);
        paras.push({ type: 'option', content: lettered, isAnswer: opt.isAnswer });
      });
    }
    if (q.pagebreakAfter) paras.push({ type: 'pagebreak', blankPage: true });
  }

  parsedQuestions.forEach(item => {
    if (item.type === 'pagebreak') {
      paras.push({ type: 'pagebreak', blankPage: item.blankPage });
      return;
    }
    if (item.type === 'option-pool' || item.type === 'scramble-pool') {
      const assigned = poolAssignments.get(item)[versionLabel] || [];
      assigned.forEach(q => {
        if (q.type === 'paragraph') emitParagraph(q);
        else emitQuestion(q);
      });
      return;
    }
    if (item.type === 'paragraph') {
      if (item.onlyVersion && item.onlyVersion !== versionLabel) return;
      emitParagraph(item);
      return;
    }
    if (item.type === 'question') {
      if (item.onlyVersion && item.onlyVersion !== versionLabel) return;
      emitQuestion(item);
    }
  });

  for (let k = 0; k < paras.length; k++) {
    if (paras[k].type === 'paragraph') {
      const next = paras[k + 1];
      if (!next || next.type === 'pagebreak') paras[k].keepWithNext = false;
    }
  }
  while (paras.length && paras[paras.length - 1].type === 'pagebreak') {
    paras.pop();
  }
  return paras;
}

// ── DOCX Generator ──────────────────────────────────────────────────────────
function makeDocxStyles(fontSize) {
  const sz = fontSize * 2;            // docx sizes are in half-points
  const bodyGap = Math.round(sz * 10 / 3);   // ≈ 80 twips at 12pt; scales with the font
  return {
    // Document default so plain (non-heading) paragraphs honour the chosen font
    // size too — without this they fall back to Word's 11pt default.
    default: { document: { run: { size: sz, font: 'Calibri', color: '000000' } } },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: sz, bold: true, font: 'Calibri', color: '000000' },
        paragraph: { spacing: { before: sz * 10, after: sz * 5 }, outlineLevel: 0 }
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: sz, bold: false, font: 'Calibri', color: '000000' },
        paragraph: { spacing: { before: bodyGap, after: bodyGap }, outlineLevel: 1 }
      }
    ]
  };
}

function buildDocx(paras, isKey, fontSize, marginSize, pageSize = LETTER) {
  const { Document, Paragraph, TextRun, ImageRun, HeadingLevel, PageBreak,
          AlignmentType, Footer, PageNumber } = docx;

  // Version-label title size, derived from the body font (15pt at the 11pt
  // default). buildBodyPdf uses the identical formula so PDF and DOCX match.
  const headPt = Math.round(fontSize * 1.33);

  function dataUrlToBytes(dataUrl) {
    const base64 = dataUrl.split(',')[1];
    return Buffer.from(base64, 'base64');
  }

  function richRuns(runs, opts = {}) {
    return runs.map(r => {
      if (isImageRun(r)) {
        const { w, h } = fitImage(r.image, 432);
        return new ImageRun({ data: dataUrlToBytes(r.image.dataUrl),
                              transformation: { width: w, height: h } });
      }
      return new TextRun({ text: r.text, underline: r.underline ? {} : undefined, bold: opts.bold });
    });
  }

  function paragraphFor(runs, { heading, keepNext, bold } = {}) {
    const opts = { keepNext, children: richRuns(runs, { bold }) };
    if (heading) opts.heading = heading;
    if (hasImage(runs) && runsText(runs).trim() === '') opts.alignment = AlignmentType.CENTER;
    return new Paragraph(opts);
  }

  const children = [];
  paras.forEach((p, idx) => {
    if (p.type === 'pagebreak') {
      children.push(new Paragraph({ children: [new PageBreak()] }));
    } else if (p.type === 'version-label') {
      // A title, sized a step above the body — kept in lock-step with the PDF's
      // version label (headPt) so the two formats look the same.
      children.push(new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: fontSize * 20, after: fontSize * 10 },
        children: [new TextRun({ text: p.text, bold: true, size: headPt * 2, font: 'Calibri' })]
      }));
    } else if (p.type === 'paragraph') {
      children.push(paragraphFor(p.content, { keepNext: p.keepWithNext }));
    } else if (p.type === 'question') {
      children.push(paragraphFor(p.content, { heading: HeadingLevel.HEADING_1, keepNext: p.keepWithNext, bold: true }));
    } else if (p.type === 'option') {
      const nextIsOption = paras[idx + 1]?.type === 'option';
      const runs = (isKey && p.isAnswer) ? prependPlain('[Answer.] ', p.content) : p.content;
      children.push(paragraphFor(runs, { heading: HeadingLevel.HEADING_2, keepNext: nextIsOption }));
    }
  });

  const footer = new Footer({
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun('Page '),
        new TextRun({ children: [PageNumber.CURRENT] }),
        new TextRun(' of '),
        new TextRun({ children: [PageNumber.TOTAL_PAGES] })
      ]
    })]
  });

  const marginTwips = marginSize * 20;
  return new Document({
    styles: makeDocxStyles(fontSize),
    sections: [{
      properties: {
        page: {
          // Paper size in twips (20 per pt), taken from the coversheet (default Letter)
          size: { width: Math.round(pageSize.width * 20), height: Math.round(pageSize.height * 20) },
          margin: { top: marginTwips, right: marginTwips, bottom: marginTwips, left: marginTwips }
        }
      },
      footers: { default: footer },
      children
    }]
  });
}

// ── PDF Generator ───────────────────────────────────────────────────────────
function buildBodyPdf(paras, isKey, fontSize, marginSize, pageSize = LETTER) {
  // Match the coversheet's paper size (jsPDF normalises [min,max] by orientation,
  // so Letter stays exactly 612×792 — the default behaviour is unchanged).
  const orientation = pageSize.width > pageSize.height ? 'landscape' : 'portrait';
  const doc = new jsPDF({ unit: 'pt', orientation,
    format: [Math.min(pageSize.width, pageSize.height), Math.max(pageSize.width, pageSize.height)] });

  const headPt = Math.round(fontSize * 1.33);   // version-label title size (15pt at 11pt body)
  const margin = marginSize;
  const marginL = margin, marginR = margin, marginT = margin, marginB = margin;
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const maxW    = pageW - marginL - marginR;
  const indentW = pageW - marginL - marginR - 20;

  let y = marginT;
  function newPage() { doc.addPage(); y = marginT; }
  function ensureSpace(h) { if (y + h > pageH - marginB) newPage(); }

  function layoutRichLines(runs, fontSize, width, fontStyle) {
    doc.setFont('helvetica', fontStyle);
    doc.setFontSize(fontSize);
    const spaceW = doc.getTextWidth(' ');
    const lines = [];
    let line = [];
    let lineW = 0;

    runs.forEach(run => {
      const words = run.text.split(/(\s+)/).filter(s => s.length > 0);
      words.forEach(word => {
        if (/^\s+$/.test(word)) {
          if (line.length > 0) { line.push({ text: ' ', underline: run.underline, w: spaceW }); lineW += spaceW; }
          return;
        }
        const w = doc.getTextWidth(word);
        if (lineW + w > width && line.length > 0) {
          while (line.length && line[line.length - 1].text === ' ') { lineW -= line[line.length-1].w; line.pop(); }
          lines.push(line); line = []; lineW = 0;
        }
        line.push({ text: word, underline: run.underline, w });
        lineW += w;
      });
    });
    if (line.length) {
      while (line.length && line[line.length - 1].text === ' ') line.pop();
      lines.push(line);
    }
    return lines;
  }

  function richHeight(runs, fontSize, width, fontStyle) {
    const lines = layoutRichLines(runs, fontSize, width, fontStyle);
    return lines.length * fontSize * 1.2;
  }

  function drawLines(lines, x, fontSize, fontStyle) {
    doc.setFont('helvetica', fontStyle);
    doc.setFontSize(fontSize);
    const lineH = fontSize * 1.2;
    lines.forEach(line => {
      let cx = x;
      line.forEach(tok => {
        doc.text(tok.text, cx, y);
        if (tok.underline && tok.text.trim()) {
          const uy = y + fontSize * 0.12;
          doc.setLineWidth(0.6);
          doc.line(cx, uy, cx + tok.w, uy);
        }
        cx += tok.w;
      });
      y += lineH;
    });
  }

  function groupHeight(startIdx) {
    // Mirror renderBlock's lead and trailing gaps exactly. The historical
    // estimate omitted four points per block and could split a group that fit
    // narrowly in the underestimated space at the bottom of a page.
    let h = 10 + richHeight(paras[startIdx].content, fontSize, maxW, 'bold') + 4;
    let j = startIdx + 1;
    while (j < paras.length && paras[j].type === 'option') {
      const measured = (isKey && paras[j].isAnswer)
        ? prependPlain('[Answer.] ', paras[j].content)
        : paras[j].content;
      h += richHeight(measured, fontSize, indentW, 'normal') + 6;
      j++;
    }
    return h;
  }

  function drawImage(run) {
    const { w, h } = fitImage(run.image, maxW);
    ensureSpace(h + 8);
    const fmt = run.image.dataUrl.startsWith('data:image/png') ? 'PNG' : 'JPEG';
    try { doc.addImage(run.image.dataUrl, fmt, marginL + (maxW - w) / 2, y, w, h); } catch (_) {}
    y += h + 8;
  }

  function renderBlock(runs, x, width, fontStyle, leadGap) {
    const textRuns = runs.filter(r => !isImageRun(r));
    const imgRuns  = runs.filter(isImageRun);
    if (runsText(textRuns).trim()) {
      const lines = layoutRichLines(textRuns, fontSize, width, fontStyle);
      ensureSpace(leadGap + lines.length * fontSize * 1.2 + 4);
      y += leadGap;
      drawLines(lines, x, fontSize, fontStyle);
      y += 4;
    } else if (leadGap) {
      y += leadGap;
    }
    imgRuns.forEach(drawImage);
  }

  paras.forEach((p, idx) => {
    if (p.type === 'pagebreak') { newPage(); return; }
    if (p.type === 'version-label') {
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(headPt);
      const lines = doc.splitTextToSize(p.text, maxW);
      const lineH = headPt * 1.2;
      ensureSpace(lines.length * lineH + 12);
      lines.forEach(line => { doc.text(line, pageW / 2, y, { align: 'center' }); y += lineH; });
      y += 12;
      return;
    }
    if (p.type === 'paragraph') { renderBlock(p.content, marginL, maxW, 'normal', 10); return; }
    if (p.type === 'question') {
      if (p.keepWithNext && !hasImage(p.content)) ensureSpace(groupHeight(idx));
      renderBlock(p.content, marginL, maxW, 'bold', 10);
      return;
    }
    if (p.type === 'option') {
      const runs = (isKey && p.isAnswer) ? prependPlain('[Answer.] ', p.content) : p.content;
      renderBlock(runs, marginL + 20, indentW, 'normal', 0);
      y += 2;
      return;
    }
  });

  const total = doc.internal.getNumberOfPages();
  for (let pg = 1; pg <= total; pg++) {
    doc.setPage(pg);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.text(`Page ${pg} of ${total}`, pageW / 2, pageH - marginB / 2, { align: 'center' });
  }
  return Buffer.from(doc.output('arraybuffer'));
}

async function mergePdfs(coverBytes, bodyBytes) {
  const merged = await PDFDocument.create();
  if (coverBytes) {
    const cover = await PDFDocument.load(coverBytes);
    const pages = await merged.copyPages(cover, cover.getPageIndices());
    pages.forEach(p => merged.addPage(p));
  }
  const body = await PDFDocument.load(bodyBytes);
  const pages = await merged.copyPages(body, body.getPageIndices());
  pages.forEach(p => merged.addPage(p));
  return merged.save();
}

// Read the body's paper size from the coversheet's first page, so the exam body
// paginates to whatever paper the coversheet uses. Honours page rotation. Returns
// null when there's no coversheet (or it can't be read) → caller defaults to Letter.
async function readCoverPageSize(coverBytes) {
  if (!coverBytes) return null;
  try {
    const cover = await PDFDocument.load(coverBytes);
    const page = cover.getPage(0);
    let { width, height } = page.getSize();
    const rot = ((page.getRotation().angle % 360) + 360) % 360;
    if (rot === 90 || rot === 270) { const t = width; width = height; height = t; }
    return { width, height };
  } catch (_) { return null; }
}

function describePaperSize({ width, height }) {
  const inch = n => +(n / 72).toFixed(2);
  const KNOWN = { Letter: [612, 792], Legal: [612, 1008], Tabloid: [792, 1224],
                  A3: [841.89, 1190.55], A4: [595.28, 841.89], A5: [419.53, 595.28] };
  const close = (a, b) => Math.abs(a - b) <= 3;
  let name = '';
  for (const [n, [pw, ph]] of Object.entries(KNOWN))
    if ((close(width, pw) && close(height, ph)) || (close(width, ph) && close(height, pw))) { name = n + ' · '; break; }
  return `${name}${inch(width)} × ${inch(height)} in`;
}

// ── Main Execution ──────────────────────────────────────────────────────────
async function run() {
  const inputPath = path.resolve(options.input);
  const outDir = path.resolve(options.output);
  const coversheetPath = options.coversheet ? path.resolve(options.coversheet) : null;
  const imagesDir = options.images ? path.resolve(options.images) : null;

  if (!fs.existsSync(inputPath)) { console.error('Input file not found.'); process.exit(1); }
  if (!fs.existsSync(outDir)) { fs.mkdirSync(outDir, { recursive: true }); }

  console.log(`Reading ${inputPath}...`);
  const inputBuffer = fs.readFileSync(inputPath);
  const baseName = path.basename(inputPath, path.extname(inputPath));

  // Load coversheet
  let coversheetPdfBytes = null;
  if (coversheetPath && fs.existsSync(coversheetPath)) {
    coversheetPdfBytes = fs.readFileSync(coversheetPath);
  }

  // Body paper size follows the coversheet's first page (default Letter 8.5×11).
  const pageSize = (await readCoverPageSize(coversheetPdfBytes)) || LETTER;
  if (coversheetPdfBytes) console.log(`Paper size from coversheet: ${describePaperSize(pageSize)} — body pages will match.`);

  // Load images
  if (imagesDir && fs.existsSync(imagesDir)) {
    const files = fs.readdirSync(imagesDir);
    for (const file of files) {
      if (/\.(png|jpe?g|gif)$/i.test(file)) {
        const filePath = path.join(imagesDir, file);
        const buffer = fs.readFileSync(filePath);
        const ext = path.extname(file).slice(1).toLowerCase();
        const mime = ext === 'jpg' ? 'jpeg' : ext;
        uploadedImages[file] = `data:image/${mime};base64,${buffer.toString('base64')}`;
      }
    }
  }

  const mammothOptions = {
    convertImage: mammoth.images.imgElement(img =>
      img.read('base64').then(data => ({ src: `data:${img.contentType};base64,${data}` })))
  };

  // CourseTools addition: accept a clean HTML interchange generated after the
  // Python layer resolves Testmaker pools. Original DOCX input still works.
  const html = /\.html?$/i.test(inputPath)
    ? inputBuffer.toString('utf8')
    : (await mammoth.convertToHtml({ buffer: inputBuffer }, mammothOptions)).value;
  const richParas = htmlToRichParagraphs(html);
  parsedQuestions = parseAllParagraphs(stripVersionXParagraph(richParas));

  const allQ = collectAllQuestions(parsedQuestions);
  console.log(`Found ${allQ.length} questions.`);

  await preloadImageDimensions(parsedQuestions);

  const versionLabels = VERSION_LABELS.slice(0, options.versions);
  const pools = parsedQuestions.filter(p => p.type === 'option-pool' || p.type === 'scramble-pool');
  const poolAssignments = assignOptionPools(pools, versionLabels);

  // Clamp page-setup to sane ranges so a bad config.json / CLI value can't break
  // the layout (matches the browser tool's field limits: font 8–24, margin 18–144).
  const fontSize   = Math.min(24,  Math.max(8,  parseInt(options.fontSize, 10)   || 11));
  const marginSize = Math.min(144, Math.max(18, parseInt(options.marginSize, 10) || 36));

  for (const lbl of versionLabels) {
    console.log(`Generating Version ${lbl}...`);
    const paras = buildVersionParas(lbl, poolAssignments);
    const keyName  = `${baseName}_answerKey_${lbl}`;
    const formName = `${baseName}_testForm_${lbl}`;

    // DOCX
    const keyDocxDoc = buildDocx(paras, true, fontSize, marginSize, pageSize);
    const formDocxDoc = buildDocx(paras, false, fontSize, marginSize, pageSize);
    fs.writeFileSync(path.join(outDir, `${keyName}.docx`), await docx.Packer.toBuffer(keyDocxDoc));
    fs.writeFileSync(path.join(outDir, `${formName}.docx`), await docx.Packer.toBuffer(formDocxDoc));

    // PDF
    const keyBodyBuf = buildBodyPdf(paras, true, fontSize, marginSize, pageSize);
    const formBodyBuf = buildBodyPdf(paras, false, fontSize, marginSize, pageSize);
    const keyPdfBytes = await mergePdfs(coversheetPdfBytes, keyBodyBuf);
    const formPdfBytes = await mergePdfs(coversheetPdfBytes, formBodyBuf);
    fs.writeFileSync(path.join(outDir, `${keyName}.pdf`), keyPdfBytes);
    fs.writeFileSync(path.join(outDir, `${formName}.pdf`), formPdfBytes);
  }

  console.log('Done!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
