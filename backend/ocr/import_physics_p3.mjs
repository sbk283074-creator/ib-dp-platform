// Session 6 importer — Physics HL Paper 3, all available options.
// Reads physics_hl_p3_manifest.json and performs idempotent DELETE+INSERT per source.
// Run after stopping the backend to avoid WAL contention.
import { insertQuestion } from '../src/questionRepo.js';
import db from '../src/db.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const MANIFEST = path.join(ROOT, 'backend/data/physics_hl_p3_manifest.json');
const recs = JSON.parse(fs.readFileSync(MANIFEST, 'utf-8'));

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

const count = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE id LIKE 'PHYS_HL_P3_%'").get().c;
const fresh = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE id LIKE 'PHYS_HL_P3_%' AND review_status='new'").get().c;
console.log(`\nTOTAL inserted: ${total}`);
console.log(`DB check -> Physics HL P3 rows: ${count}, review_status='new': ${fresh}`);
