// import_shots.mjs — turn the screenshot manifest into 1:1 question rows.
//
// Design rules (per Lucas's instructions):
//   * ONE database question per question area — never merge two questions into
//     one row, never create two rows for the same area. The manifest id is the
//     primary key, so re-running is idempotent (INSERT OR REPLACE).
//   * A question is identified by a NUMBER (1., 2., …); letter-led subparts are
//     counted, not split into separate questions. The screenshot engine already
//     enforced that, so each manifest record == exactly one question.
//   * The crop image is the source of truth; we do NOT reconstruct text.
//
// Usage:
//   node import_shots.mjs [--manifest FILE] [--dry-run] [--prefix PREFIX]
//
// The manifest is the jsonl written by screenshot_questions.py.

import db from '../src/db.js';
import { insertQuestion } from '../src/questionRepo.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_MANIFEST = path.join(__dirname, 'screenshot_manifest.jsonl');

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a) => {
    if (a.startsWith('--')) acc.push([a.slice(2), true]);
    else if (acc.length) acc[acc.length - 1][1] = a;
    return acc;
  }, [])
);

const MANIFEST = args.manifest || DEFAULT_MANIFEST;
const DRY = args['dry-run'] === true;
const ONLY_PREFIX = args.prefix || null;

// prefix e.g. MATH-2024.5-P2-TZ1  / PHY-2025.05-P2-TZ1  / CS-2025.05-P2-TZ2
const SUBJ = { MATH: 'Math AA HL', PHY: 'Physics', CS: 'CS' };
const SUBJ_SHORT = { MATH: 'Math HL', PHY: 'Physics HL', CS: 'CS HL' };
const PAPER = { P1A: 'Paper 1A', P1B: 'Paper 1B', P1: 'Paper 1', P2: 'Paper 2', P3: 'Paper 3' };

function parsePrefix(prefix) {
  const m = prefix.match(/^(MATH|PHY|CS)-(\d{4})\.(\d{1,2})-([^-]+)-TZ\d$/);
  if (!m) {
    // tolerate a few variants (no TZ, etc.)
    const m2 = prefix.match(/^(MATH|PHY|CS)-(\d{4})\.(\d{1,2})-([^-]+)$/);
    if (!m2) return null;
    const [, subj, year, mon, paper] = m2;
    return build(subj, year, mon, paper);
  }
  const [, subj, year, mon, paper] = m;
  return build(subj, year, mon, paper);
}
function build(subj, year, mon, paper) {
  const key = String(paper).toUpperCase();
  const paperName = PAPER[key] || key;
  const monthName = (mon === '11' || mon === '11') ? 'Nov'
    : (mon === '5' || mon === '05') ? 'May'
    : `M${mon}`;
  return {
    subject: SUBJ[subj],
    short: SUBJ_SHORT[subj],
    year, monthName,
    paperName
  };
}

function toQuestion(rec) {
  const p = parsePrefix(rec.prefix);
  if (!p) {
    return { skip: true, reason: `unparseable prefix "${rec.prefix}"` };
  }
  const source = `IB 真题 ${p.year} ${p.monthName} ${p.short} ${p.paperName}`;
  const topic = `${p.year} ${p.monthName}`;
  const hasAnswer = Boolean(rec.answer_image);
  return {
    skip: false,
    q: {
      id: rec.id,
      subject: p.subject,
      level: 'HL',
      topic,
      subtopic: null,
      paper_type: p.paperName,
      command_term: null,
      marks: null,
      difficulty: null,
      question: `Question ${rec.number}.`,
      figure: null,
      answer: hasAnswer ? 'See markscheme image.' : 'See question image (past-paper screenshot).',
      explanation: 'Screenshot of the original past-paper question — no text reconstruction, so there is no OCR error.',
      source,
      tags: ['shot', rec.profile, `q${rec.number}`],
      authored_by: 'shot',
      created_at: new Date().toISOString(),
      knowledge_point_ids: [],
      question_image: rec.image,
      answer_image: rec.answer_image || null,
      figure_image: null,
      source_type: 'paper'
    }
  };
}

function main() {
  if (!fs.existsSync(MANIFEST)) {
    console.error(`manifest not found: ${MANIFEST}`);
    process.exit(1);
  }
  const lines = fs.readFileSync(MANIFEST, 'utf8').split('\n').filter(Boolean);
  let total = 0, inserted = 0, skipped = 0, skipReasons = {};
  const tx = db.transaction((recs) => {
    for (const rec of recs) {
      total++;
      const r = toQuestion(rec);
      if (r.skip) { skipped++; skipReasons[r.reason] = (skipReasons[r.reason] || 0) + 1; continue; }
      if (DRY) { inserted++; continue; }
      insertQuestion(r.q, { id: r.q.id, authored_by: 'shot', overwrite: true });
      inserted++;
    }
  });
  const recs = lines.map((l) => JSON.parse(l))
    .filter((r) => r.type === 'question')
    .filter((r) => !ONLY_PREFIX || r.prefix === ONLY_PREFIX);
  tx(recs);
  console.log(`[import_shots] total=${total} upserted=${inserted} skipped=${skipped}` +
    (skipped ? ` skipReasons=${JSON.stringify(skipReasons)}` : '') +
    (DRY ? ' (dry-run)' : ''));
}

main();
