#!/usr/bin/env node
/**
 * verify_bank.mjs — post-import integrity checks for the question bank.
 *
 * Checks:
 *   1. per-category counts
 *   2. book questions == sum of the extracted JSON counts (no duplicate-id loss)
 *   3. every question id is unique
 *   4. every book question_image resolves on disk, and no two questions share one
 *   5. no past-paper text still carries exam page furniture
 *   6. no book section name is a shattered running head
 *   7. books.total_questions matches the actual row count
 *
 * Usage: node scripts/verify_bank.mjs
 */
import Database from 'better-sqlite3';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const DB = path.join(ROOT, 'data', 'app.db');
const JSONDIR = path.join(ROOT, 'ocr', 'book_json2');
const PUBLIC = path.join(ROOT, 'public');

const db = new Database(DB, { readonly: true });
const q = (s, ...a) => db.prepare(s).all(...a);
let fails = 0;
const ok = (cond, msg) => { console.log((cond ? '  PASS  ' : '  FAIL  ') + msg); if (!cond) fails++; };

console.log('=== 1. counts by category ===');
let total = 0;
for (const r of q(`select category, count(*) c from questions group by category order by c desc`)) {
  console.log('   ' + String(r.c).padStart(6) + '  ' + r.category); total += r.c;
}
console.log('   ' + String(total).padStart(6) + '  TOTAL');

console.log('\n=== 2. book questions vs extracted JSON ===');
let jsonTotal = 0;
for (const f of fs.readdirSync(JSONDIR).filter((x) => x.endsWith('.json'))) {
  try { jsonTotal += (JSON.parse(fs.readFileSync(path.join(JSONDIR, f), 'utf8')).questions || []).length; } catch {}
}
const dbBook = q(`select count(*) c from questions where category='book'`)[0].c;
ok(dbBook === jsonTotal, `book rows in DB (${dbBook}) == sum of JSON (${jsonTotal})`);

console.log('\n=== 3. id uniqueness ===');
const dups = q(`select id, count(*) c from questions group by id having c > 1`);
ok(dups.length === 0, `no duplicate question ids (${dups.length} found)`);

console.log('\n=== 4. book images resolve and are not shared ===');
const rows = q(`select id, question_image from questions where category='book' and question_image is not null`);
const seen = new Map();
let missing = 0, shared = 0;
for (const r of rows) {
  const rel = r.question_image.replace(/^\/figures\//, '');
  const abs = path.join(PUBLIC, 'figures', rel);
  if (!fs.existsSync(abs)) missing++;
  if (seen.has(r.question_image)) shared++; else seen.set(r.question_image, r.id);
}
ok(missing === 0, `all ${rows.length} book images exist (${missing} missing)`);
ok(shared === 0, `no book image path is shared by 2+ questions (${shared} shared)`);

console.log('\n=== 5. past-paper page furniture ===');
const F = [/^turn over\.?$/i, /^please do not write on this page\.?$/i,
  /^do ?n[o']?t write solutions on this page\.?/i, /^blank page\.?$/i,
  /^answers written on this page/i, /^\(\s*(question|option)[^)]*continued\s*\)$/i,
  /^©\s*international baccalaureate organization/i,
  /^[A-Z]{1,2}\d{2}\/\d\/[A-Z0-9]+\/[A-Z0-9]+\/[A-Z0-9]{2,4}\/[A-Z0-9]+\/[A-Z0-9]{1,4}$/];
let dirty = 0;
for (const r of q(`select question from questions where category='past' and question is not null`)) {
  if (r.question.split('\n').some((l) => F.some((re) => re.test(l.trim())))) dirty++;
}
ok(dirty === 0, `no past question still holds furniture lines (${dirty} rows)`);

console.log('\n=== 6. book section names ===');
const secs = q(`select distinct book_section s from questions where category='book'`);
const bad = secs.filter(({ s }) => {
  if (!s) return true;
  const toks = s.split(/\s+/);
  const ones = toks.filter((t) => /^[A-Za-z]$/.test(t)).length;
  return toks.length >= 4 && ones / toks.length >= 0.45;
});
ok(bad.length === 0, `no shattered running-head section names (${bad.length} found)`);
for (const b of bad.slice(0, 5)) console.log('        ' + JSON.stringify(b.s));

console.log('\n=== 7. books.total_questions ===');
const mism = q(`select b.id, b.total_questions t, (select count(*) from questions x where x.book_id=b.id) c
                from books b where b.total_questions <> (select count(*) from questions x where x.book_id=b.id)`);
ok(mism.length === 0, `every books.total_questions matches its row count (${mism.length} mismatched)`);
for (const m of mism.slice(0, 8)) console.log('        ' + m.id + ': claims ' + m.t + ', has ' + m.c);

db.close();
console.log(fails === 0 ? '\nALL CHECKS PASSED' : `\n${fails} CHECK(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);
