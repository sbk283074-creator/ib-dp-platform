// Fast batched loader: copy local SQLite (backend/data/app.db) -> Turso.
//
// Uses db.init() (backend/src/db.js) to create the IDENTICAL schema + column
// migrations on Turso, then batch-inserts every table using libSQL `batch`
// (one HTTP round-trip per chunk instead of one per row). Idempotent:
// INSERT OR REPLACE by primary key. Safe to re-run.
//
// Usage:
//   TURSO_URL="libsql://xxxx.turso.io" TURSO_AUTH_TOKEN="yyyy" \
//     node scripts/migrate-to-turso-fast.mjs
import path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';
import Database from 'better-sqlite3';
import db from '../backend/src/db.js';

const require = createRequire(import.meta.url);
const libsqlClient = require('@libsql/client');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, '..');

const TURSO_URL = process.env.TURSO_URL;
const TURSO_AUTH_TOKEN = process.env.TURSO_AUTH_TOKEN;
if (!TURSO_URL || !TURSO_AUTH_TOKEN) {
  console.error('Set TURSO_URL and TURSO_AUTH_TOKEN.');
  process.exit(1);
}

// Open LOCAL db read-only (source of truth is never written).
const local = new Database(path.join(root, 'backend', 'data', 'app.db'), { readonly: true });

// Create schema + migrations on the Turso DB (reuses db.js exactly).
await db.init();

// Own libSQL client for batched inserts (same DB/url/token as db.js).
const t = libsqlClient.createClient({ url: TURSO_URL, authToken: TURSO_AUTH_TOKEN });

const TABLES = [
  'knowledge_points', 'topics', 'books', 'paper_templates',
  'questions', 'progress', 'wrong_notebook',
  'collections', 'collection_items', 'question_notes', 'reports', 'question_usage'
];

const CHUNK = 400; // statements per batch round-trip

for (const tbl of TABLES) {
  const rows = local.prepare(`SELECT * FROM ${tbl}`).all();
  if (!rows.length) { console.log(`skip ${tbl} (0 rows)`); continue; }
  const cols = Object.keys(rows[0]);
  const placeholders = cols.map(() => '?').join(',');
  const sql = `INSERT OR REPLACE INTO ${tbl} (${cols.join(',')}) VALUES (${placeholders})`;
  let done = 0;
  for (let i = 0; i < rows.length; i += CHUNK) {
    const slice = rows.slice(i, i + CHUNK);
    const stmts = slice.map((r) => ({
      sql,
      args: cols.map((c) => (r[c] === undefined ? null : r[c]))
    }));
    await t.batch(stmts);
    done += slice.length;
  }
  console.log(`inserted ${done} rows -> ${tbl}`);
}

console.log('MIGRATION DONE');
local.close();
