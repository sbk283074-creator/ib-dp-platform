// Import the official IB specimen ("mock") papers produced by
// ocr/extract_specimen.py (ocr/specimen_json/specimen.json).
//
// Rows land with category='mock' so the UI can filter them on their own,
// separate from past papers / topic questions / book questions.
//
// Usage: node scripts/import_specimen.mjs [--dry-run]
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import db from '../src/db.js';
import { validateQuestion, insertQuestion } from '../src/questionRepo.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dryRun = process.argv.includes('--dry-run');
const FILE = path.resolve(__dirname, '..', 'ocr', 'specimen_json', 'specimen.json');

if (!fs.existsSync(FILE)) { console.error(`no such file: ${FILE}`); process.exit(1); }

await db.init();

const data = JSON.parse(fs.readFileSync(FILE, 'utf8'));
const questions = data.questions || [];
console.log(`specimen import: ${questions.length} questions${dryRun ? '  (dry run)' : ''}`);

const good = [];
let bad = 0;
for (const q of questions) {
  const v = validateQuestion(q);
  if (v.ok) good.push(q); else { bad++; console.error(`  bad ${q.id}: ${v.error}`); }
}

if (!dryRun) {
  // idempotent: replace the previous mock set, never touching other categories
  const removed = await db.prepare(
    "DELETE FROM questions WHERE category = 'mock' OR id LIKE 'SPEC%'"
  ).run();
  console.log(`  removed ${removed.changes ?? 0} previous mock rows`);
  for (const q of good) {
    await insertQuestion({ ...q, category: 'mock', source_type: 'mock' }, { authored_by: 'import' });
  }
  const n = (await db.prepare("SELECT COUNT(*) c FROM questions WHERE category='mock'").get()).c;
  console.log(`  now in bank: ${n}`);
}

const byPaper = {};
for (const q of good) byPaper[q.subtopic] = (byPaper[q.subtopic] || 0) + 1;
for (const [k, v] of Object.entries(byPaper).sort()) console.log(`  ${String(v).padStart(4)}  ${k}`);
console.log(`DONE imported=${good.length} skipped=${bad}`);
process.exit(0);
