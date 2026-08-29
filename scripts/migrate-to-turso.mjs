// One-shot loader: copy the local SQLite DB (backend/data/app.db) into Turso.
//
// Reuses backend/src/db.js so the Turso schema + column migrations are created
// IDENTICALLY to what the running function expects (no manual SQL needed).
//
// Usage:
//   TURSO_URL="libsql://xxxx.turso.io" TURSO_AUTH_TOKEN="yyyy" \
//     node scripts/migrate-to-turso.mjs
//
// Idempotent: INSERT OR REPLACE by primary key. Safe to re-run.
import path from 'path';
import { fileURLToPath } from 'url';
import Database from 'better-sqlite3';
import db from '../backend/src/db.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, '..');

const TURSO_URL = process.env.TURSO_URL;
const TURSO_AUTH_TOKEN = process.env.TURSO_AUTH_TOKEN;
if (!TURSO_URL || !TURSO_AUTH_TOKEN) {
  console.error('Set TURSO_URL and TURSO_AUTH_TOKEN (from `turso db show <db> --url` and `turso db tokens create <db>`).');
  process.exit(1);
}

// Open the LOCAL db read-only so we never touch the source of truth.
const local = new Database(path.join(root, 'backend', 'data', 'app.db'), { readonly: true });

// Parents before children (consistent but INSERT OR REPLACE is order-tolerant).
const TABLES = [
  'knowledge_points', 'topics', 'books', 'paper_templates',
  'questions', 'progress', 'wrong_notebook',
  'collections', 'collection_items', 'question_notes', 'reports', 'question_usage'
];

await db.init(); // creates schema + migrations on the Turso DB

for (const t of TABLES) {
  const rows = local.prepare(`SELECT * FROM ${t}`).all();
  if (!rows.length) {
    console.log(`skip ${t} (0 rows)`);
    continue;
  }
  const cols = Object.keys(rows[0]);
  const placeholders = cols.map(() => '?').join(',');
  const sql = `INSERT OR REPLACE INTO ${t} (${cols.join(',')}) VALUES (${placeholders})`;
  let inserted = 0;
  for (const r of rows) {
    await db.prepare(sql).run(...cols.map((c) => (r[c] === undefined ? null : r[c])));
    inserted++;
  }
  console.log(`inserted ${inserted} rows -> ${t}`);
}

console.log('MIGRATION DONE');
local.close();
