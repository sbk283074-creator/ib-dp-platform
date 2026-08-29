// Importer for the CS past-paper gap manifests produced by extract_cs_missing.py.
// Reads backend/data/cs_{p1_old|p2_old|p3}_manifest.json and upserts each
// question via questionRepo.insertQuestion (idempotent: DELETE per source,
// then INSERT). Run AFTER stopping the backend to avoid WAL lock contention.
//
// Usage:  node import_cs_missing.mjs p1
//         node import_cs_missing.mjs p2
//         node import_cs_missing.mjs p3
import { insertQuestion } from '../src/questionRepo.js';
import db from '../src/db.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const MAP = {
  p1: { manifest: 'cs_p1_old_manifest.json', idPrefix: 'CS_HL_P1', srcPrefix: 'CS HL Paper 1' },
  p2: { manifest: 'cs_p2_old_manifest.json', idPrefix: 'CS_HL_P2', srcPrefix: 'CS HL Paper 2' },
  p3: { manifest: 'cs_p3_manifest.json',     idPrefix: 'CS_HL_P3', srcPrefix: 'CS HL Paper 3' },
};
const mode = process.argv[2] || 'p3';
const cfg = MAP[mode];
if (!cfg) { console.error('usage: import_cs_missing.mjs [p1|p2|p3]'); process.exit(1); }
const MANIFEST = path.join(ROOT, 'backend/data', cfg.manifest);

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
console.log(`\nTOTAL inserted (${mode}): ${total}`);
const cat = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE category='past' AND source LIKE ?").get(cfg.srcPrefix + '%').c;
const nw  = db.prepare("SELECT COUNT(*) AS c FROM questions WHERE review_status='new' AND id LIKE ?").get(cfg.idPrefix + '%').c;
console.log(`DB check -> ${cfg.srcPrefix} past rows: ${cat}, review_status='new' (${cfg.idPrefix}): ${nw}`);
