#!/usr/bin/env node
/**
 * clean_past_footers.mjs — strip IB exam page furniture from past-paper text.
 *
 * Past-paper questions were transcribed page by page, so the running footers,
 * page-turn markers and copyright lines ended up inside the question text, e.g.
 *
 *   10. Discuss one ethical consideration ... [3]
 *   M16/4/COMSC/HP1/ENG/TZ0/XX      <- paper code
 *   Turn over                        <- footer
 *   Section B
 *
 * Only whole lines that are *entirely* page furniture are removed; any line
 * carrying real question content is left untouched.
 *
 * Usage:  node scripts/clean_past_footers.mjs [--dry-run] [--category=past]
 */
import Database from 'better-sqlite3';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DB = path.join(HERE, '..', 'data', 'app.db');
const dry = process.argv.includes('--dry-run');
const catArg = process.argv.find((a) => a.startsWith('--category='));
const CATEGORY = catArg ? catArg.split('=')[1] : 'past';

// A line is page furniture if it matches one of these in full.
const FURNITURE = [
  /^turn over\.?$/i,
  /^please do not write on this page\.?$/i,
  /^do ?n[o']?t write solutions on this page\.?( any working on this page will not be marked\.?)?$/i,
  /^do not write in this area\.?$/i,
  /^blank page\.?$/i,
  /^this page is intentionally blank\.?$/i,
  // this footer often wraps: "Answers written on this page will" / "not be marked."
  /^answers written on this page( will( not( be marked\.?)?)?)?$/i,
  /^not be marked\.?$/i,
  /^\(\s*(question|option)[^)]*\bcontinued\s*\)$/i,
  /^©\s*international baccalaureate organization\s*\d{4}\.?$/i,
  // paper codes: N20/4/COMSC/HP2/ENG/TZ0/XX  (and similar)
  /^[A-Z]{1,2}\d{2}\/\d\/[A-Z0-9]+\/[A-Z0-9]+\/[A-Z0-9]{2,4}\/[A-Z0-9]+\/[A-Z0-9]{1,4}$/,
  // bare page numbers with dashes:  – 5 –   /  — 12 —
  /^[–—-]\s*\d{1,3}\s*[–—-]$/,
];

const isFurniture = (line) => {
  const t = line.trim();
  if (!t) return false;
  return FURNITURE.some((re) => re.test(t));
};

const clean = (text) => {
  if (!text) return { out: text, removed: 0, dropped: [] };
  const lines = text.split('\n');
  const kept = [];
  const dropped = [];
  for (const ln of lines) {
    if (isFurniture(ln)) { dropped.push(ln.trim()); continue; }
    kept.push(ln);
  }
  // collapse runs of blank lines left behind by the removals
  const out = kept.join('\n').replace(/\n{3,}/g, '\n\n').replace(/^\s+|\s+$/g, '');
  return { out, removed: dropped.length, dropped };
};

const db = new Database(DB, { readonly: dry });
const rows = db.prepare(
  `select id, question, answer from questions where category = ? and question is not null`
).all(CATEGORY);

let changed = 0, linesRemoved = 0, emptyAfter = 0;
const samples = [];
const upd = dry ? null : db.prepare(`update questions set question = ?, answer = ? where id = ?`);
const tx = dry ? null : db.transaction((items) => { for (const it of items) upd.run(it.q, it.a, it.id); });

const pending = [];
for (const r of rows) {
  const cq = clean(r.question);
  const ca = clean(r.answer);
  if (cq.removed === 0 && ca.removed === 0) continue;
  changed += 1;
  linesRemoved += cq.removed + ca.removed;
  if (!cq.out) emptyAfter += 1;
  if (samples.length < 8) samples.push({ id: r.id, before: r.question, after: cq.out, dropped: cq.dropped });
  pending.push({ id: r.id, q: cq.out, a: ca.out });
}

if (!dry && pending.length) tx(pending);
db.close();

console.log(`category=${CATEGORY}  questions=${rows.length}`);
console.log(`changed=${changed}  furniture lines removed=${linesRemoved}  emptied=${emptyAfter}`);
for (const s of samples) {
  console.log('\n### ' + s.id);
  console.log('  removed line(s): ' + JSON.stringify(s.dropped));
  console.log('  before-len=' + s.before.length + '  after-len=' + s.after.length);
  console.log('  after: ' + JSON.stringify(s.after.slice(0, 160)));
}
console.log(dry ? '\n(dry run — nothing written)' : '\nwritten.');
