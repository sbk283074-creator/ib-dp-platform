// Seed the knowledge_points table from per-subject syllabus trees.
// Idempotent: INSERT OR REPLACE by id, so re-running is safe.
// Usage: node src/seed/knowledgePoints.js
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import db from '../db.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const seedDir = path.join(__dirname, '..', '..', 'seed');
const FILES = [
  'knowledge_points_cs.json',
  'knowledge_points_physics.json',
  'knowledge_points_math.json'
];

async function main() {
  await db.init();
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO knowledge_points (id, subject, code, theme, title, description, refs)
    VALUES (?,?,?,?,?,?,?)
  `);
  await db.transaction(async () => {
    for (const f of FILES) {
      const file = path.join(seedDir, f);
      if (!fs.existsSync(file)) { console.log(`[seed] skip missing ${f}`); continue; }
      const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
      const kps = data.knowledge_points || [];
      for (const k of kps) {
        await stmt.run(k.id, k.subject || 'CS', k.code || null, k.theme || null, k.title,
          k.description || null, JSON.stringify(k.references || []));
      }
      console.log(`[seed] ${f}: inserted/updated ${kps.length}`);
    }
  });

  const count = (await db.prepare('SELECT COUNT(*) AS c FROM knowledge_points').get()).c;
  console.log(`[seed] total knowledge_points in DB: ${count}`);
}

main().catch((e) => {
  console.error('[seed] failed:', e);
  process.exit(1);
});
