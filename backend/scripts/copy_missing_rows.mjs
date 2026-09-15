// Recover question rows that exist in the local dev SQLite DB but were never
// pushed to the target DB (Turso, in production).
//
// Why this exists: some past-paper batches were written straight into the local
// SQLite file by the OCR importers (ocr/import_physics_topic.mjs,
// import_math_topic.mjs, ...), which INSERT directly. Nothing replayed them into
// production, so production is missing whole papers.
//
// Why not just use the API or src/import.js: both call validateQuestion(), which
// requires a non-empty `explanation`. Past-paper / topic / questionbank rows
// legitimately have `explanation = ''` (10,042 of them at the time of writing),
// so those paths reject the repo's own existing data. This script writes through
// questionRepo.insertQuestion, which does NOT validate — deliberately, to match
// how the rows were created in the first place.
//
// Reads the local DB strictly read-only. Writes are upserts (INSERT OR REPLACE
// by id), so re-running is safe and never duplicates.
//
// Usage:
//   TURSO_URL=... TURSO_AUTH_TOKEN=... node scripts/copy_missing_rows.mjs \
//       --category=past --day=2026-09-12 [--dry-run]
//
//   --category  required; the `category` column to copy
//   --day       optional; only rows whose created_at starts with this date
//   --id-like   optional; SQL LIKE pattern on id (e.g. 'SPEC%')
//   --dry-run   report what would be written, write nothing
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import Database from 'better-sqlite3';
import db from '../src/db.js';
import { insertQuestion } from '../src/questionRepo.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LOCAL_DB = path.resolve(__dirname, '..', 'data', 'app.db');

const argv = process.argv.slice(2);
const flag = (name) => {
  const hit = argv.find((a) => a === `--${name}` || a.startsWith(`--${name}=`));
  if (!hit) return undefined;
  const eq = hit.indexOf('=');
  return eq === -1 ? true : hit.slice(eq + 1);
};

const category = flag('category');
const day = flag('day');
const idLike = flag('id-like');
const dryRun = Boolean(flag('dry-run'));

if (!category) {
  console.error('Usage: node scripts/copy_missing_rows.mjs --category=<c> [--day=YYYY-MM-DD] [--id-like=PATTERN] [--dry-run]');
  process.exit(1);
}
if (!fs.existsSync(LOCAL_DB)) {
  console.error(`local DB not found: ${LOCAL_DB}`);
  process.exit(1);
}

// --- read the source rows (read-only) --------------------------------------
const local = new Database(LOCAL_DB, { readonly: true, fileMustExist: true });
const where = ['category = ?'];
const params = [category];
if (day) { where.push("substr(created_at,1,10) = ?"); params.push(day); }
if (idLike) { where.push('id LIKE ?'); params.push(idLike); }

const rows = local
  .prepare(`SELECT * FROM questions WHERE ${where.join(' AND ')} ORDER BY id`)
  .all(...params);
local.close();

const target = process.env.TURSO_URL ? 'TURSO (production)' : 'LOCAL SQLite';
console.log(`copy_missing_rows: ${rows.length} source row(s) [category=${category}${day ? ` day=${day}` : ''}${idLike ? ` id-like=${idLike}` : ''}]`);
console.log(`  source : ${LOCAL_DB}`);
console.log(`  target : ${target}${dryRun ? '   (dry run)' : ''}`);

if (!rows.length) { console.log('  nothing to copy.'); process.exit(0); }

// JSON-encoded columns must go back in as arrays.
const hydrate = (r) => ({
  ...r,
  tags: r.tags ? JSON.parse(r.tags) : [],
  knowledge_point_ids: r.knowledge_point_ids ? JSON.parse(r.knowledge_point_ids) : []
});

if (dryRun) {
  for (const r of rows) console.log(`  would write ${r.id}  (${r.subject} ${r.paper_type ?? '-'})`);
  console.log(`DONE dry-run=${rows.length}`);
  process.exit(0);
}

await db.init();
let written = 0;
const failed = [];
for (const r of rows) {
  try {
    await insertQuestion(hydrate(r), { authored_by: r.authored_by || 'import' });
    written += 1;
    if (written % 20 === 0) console.log(`  ... ${written}/${rows.length}`);
  } catch (e) {
    failed.push({ id: r.id, error: e.message });
    console.error(`  FAILED ${r.id}: ${e.message}`);
  }
}

const n = (await db.prepare('SELECT COUNT(*) c FROM questions WHERE category = ?').get(category)).c;
console.log(`DONE written=${written} failed=${failed.length}  (category '${category}' now ${n})`);
if (failed.length) process.exitCode = 1;
