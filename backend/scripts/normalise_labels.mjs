#!/usr/bin/env node
/**
 * normalise_labels.mjs — make past-paper `source` labels consistent.
 *
 * Two inconsistencies were found in the data:
 *   1. the same paper is written two ways — "CS HL P1" and "CS HL Paper 3";
 *   2. the November session appears as both "November" and "Nov".
 *
 * The canonical form is "{Subject} {Level} Paper {n} · {YYYY} {May|Nov} [1A|1B] [TZn]".
 * Only `source` is touched (a display string); `paper_type` already holds the
 * structured value and is left alone.
 *
 * Usage:  node scripts/normalise_labels.mjs [--dry-run] [--category=past]
 */
import Database from 'better-sqlite3';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DB = path.join(HERE, '..', 'data', 'app.db');
const dry = process.argv.includes('--dry-run');
const catArg = process.argv.find((a) => a.startsWith('--category='));
const CATEGORY = catArg ? catArg.split('=')[1] : 'past';

// paper-label fixes, applied to the part before the "·" separator only
const LABELS = [
  [/\bCS HL P1\b/g, 'CS HL Paper 1'],
  [/\bCS HL P2\b/g, 'CS HL Paper 2'],
  [/\bCS HL P3\b/g, 'CS HL Paper 3'],
];

function normalise(src) {
  if (!src) return src;
  const i = src.indexOf('·');
  let head = i === -1 ? src : src.slice(0, i);
  let tail = i === -1 ? '' : src.slice(i);
  for (const [re, rep] of LABELS) head = head.replace(re, rep);
  // November -> Nov (the badge parser and every other row already use "Nov")
  tail = tail.replace(/\bNovember\b/g, 'Nov');
  head = head.replace(/\s+/g, ' ').replace(/\s+$/, ' ');
  return head + tail;
}

const db = new Database(DB, { readonly: dry });
const rows = db.prepare(
  `select id, source from questions where category = ? and source is not null`
).all(CATEGORY);

const pending = [];
const examples = [];
const seen = new Set();
for (const r of rows) {
  const out = normalise(r.source);
  if (out === r.source) continue;
  const shape = r.source.replace(/\d+/g, 'N');
  if (!seen.has(shape) && examples.length < 8) { seen.add(shape); examples.push([r.source, out]); }
  pending.push({ id: r.id, src: out });
}

if (!dry && pending.length) {
  const upd = db.prepare(`update questions set source = ? where id = ?`);
  const tx = db.transaction((items) => { for (const it of items) upd.run(it.src, it.id); });
  tx(pending);
}
db.close();

console.log(`category=${CATEGORY}  rows=${rows.length}  changed=${pending.length}`);
for (const [a, b] of examples) console.log('   ' + JSON.stringify(a) + '  ->  ' + JSON.stringify(b));
console.log(dry ? '(dry run — nothing written)' : 'written.');
