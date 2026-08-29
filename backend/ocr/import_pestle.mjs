// Session 12 importer — Math AA questions (Pestle question-bank export).
// Reads backend/data/pestle_manifest.json and upserts each question via
// questionRepo.insertQuestion (idempotent: DELETE per source, then INSERT OR REPLACE).
// Run AFTER stopping the backend (avoids WAL lock contention).
import { insertQuestion } from '../src/questionRepo.js';
import db from '../src/db.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const MANIFEST = path.join(ROOT, 'backend/data/pestle_manifest.json');
const SOURCE = 'Pestle AA Question Bank';

const recs = JSON.parse(fs.readFileSync(MANIFEST, 'utf-8'));
console.log(`Manifest records: ${recs.length}`);

const before = db.prepare('SELECT COUNT(*) AS c FROM questions WHERE source = ?').get(SOURCE).c;
db.prepare('DELETE FROM questions WHERE source = ?').run(SOURCE);
let total = 0;
let noimg = 0;
for (const r of recs) {
  insertQuestion(r, { id: r.id, authored_by: r.authored_by || 'ib' });
  total++;
  if (!r.question_image || !r.answer_image) noimg++;
}
const after = db.prepare('SELECT COUNT(*) AS c FROM questions WHERE source = ?').get(SOURCE).c;
console.log(`  ${SOURCE}: deleted ${before}, inserted ${after} (expected ${recs.length})`);
console.log(`TOTAL inserted: ${total}`);

const byCat = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE category='past' AND source=?").get(SOURCE).c;
const nw = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE review_status='new' AND source=?").get(SOURCE).c;
const withQimg = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE source=? AND question_image IS NOT NULL AND question_image<>''").get(SOURCE).c;
const withAimg = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE source=? AND answer_image IS NOT NULL AND answer_image<>''").get(SOURCE).c;
const emptyQ = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE source=? AND (question IS NULL OR question='')").get(SOURCE).c;
const emptyA = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE source=? AND (answer IS NULL OR answer='')").get(SOURCE).c;
console.log(`DB check -> past rows: ${byCat}, review_status='new': ${nw}`);
console.log(`  question_image set: ${withQimg}, answer_image set: ${withAimg}`);
console.log(`  empty question text: ${emptyQ}, empty answer text: ${emptyA}`);
