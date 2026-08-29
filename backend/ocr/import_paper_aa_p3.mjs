// Session 3 importer — Math AA HL Paper 3.
// Reads backend/data/paper_aa_p3_manifest.json and upserts each question via
// questionRepo.insertQuestion (idempotent: DELETE per source, then INSERT OR REPLACE).
// Run AFTER stopping the backend (avoids WAL lock contention).
import { insertQuestion } from '../src/questionRepo.js';
import db from '../src/db.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const MANIFEST = path.join(ROOT, 'backend/data/paper_aa_p3_manifest.json');

const recs = JSON.parse(fs.readFileSync(MANIFEST, 'utf-8'));
// group by source for clean DELETE+INSERT per paper
const bySource = new Map();
for (const r of recs) {
  if (!bySource.has(r.source)) bySource.set(r.source, []);
  bySource.get(r.source).push(r);
}

let total = 0;
for (const [source, list] of bySource) {
  const before = db.prepare('SELECT COUNT(*) AS c FROM questions WHERE source = ?').get(source).c;
  db.prepare('DELETE FROM questions WHERE source = ?').run(source);
  for (const r of list) {
    insertQuestion(r, { id: r.id, authored_by: r.authored_by || 'ib' });
    total++;
  }
  const after = db.prepare('SELECT COUNT(*) AS c FROM questions WHERE source = ?').get(source).c;
  console.log(`  ${source}: deleted ${before}, inserted ${after} (expected ${list.length})`);
}
console.log(`\nTOTAL inserted: ${total}`);
const cat = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE category='past' AND source LIKE 'AA HL P3%'").get().c;
const nw = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE review_status='new' AND source LIKE 'AA HL P3%'").get().c;
console.log(`DB check -> AA HL P3 past rows: ${cat}, review_status='new': ${nw}`);
