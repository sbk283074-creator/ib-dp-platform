// Copy the book import from the LOCAL SQLite database to the production Turso
// database.
//
// Why this exists: the OCR/import scripts go through src/db.js, which only
// writes to Turso when TURSO_URL is set. There is no .env in this repo (only
// .env.example), so every book import landed in backend/data/app.db and never
// reached production. That is why the deployed site shows an empty Books page
// while the local file holds 19 books and 7,304 questions.
//
// Usage (from the backend/ directory):
//   TURSO_URL="libsql://<db>.turso.io" TURSO_AUTH_TOKEN="<token>" \
//     node scripts/sync_books_to_turso.mjs
//
// Safe to re-run: every write is INSERT OR REPLACE, and the script verifies the
// remote counts at the end rather than trusting what it thinks it sent.

import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Database from 'better-sqlite3';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const LOCAL_DB = path.join(__dirname, '..', 'data', 'app.db');

const url = process.env.TURSO_URL;
const authToken = process.env.TURSO_AUTH_TOKEN;
if (!url || !authToken) {
  console.error('TURSO_URL and TURSO_AUTH_TOKEN must both be set, e.g.');
  console.error('  TURSO_URL="libsql://xxx.turso.io" TURSO_AUTH_TOKEN="..." \\');
  console.error('    node scripts/sync_books_to_turso.mjs');
  process.exit(1);
}

const CHUNK = 200;

function columnsOf(sqlite, table) {
  return sqlite.prepare(`PRAGMA table_info(${table})`).all().map((c) => c.name);
}

function insertStatements(table, cols, rows) {
  const sql = `INSERT OR REPLACE INTO ${table} (${cols.join(',')}) VALUES (`
    + cols.map(() => '?').join(',') + ')';
  return rows.map((r) => ({
    sql,
    args: cols.map((c) => (r[c] === undefined ? null : r[c]))
  }));
}

async function main() {
  const sqlite = new Database(LOCAL_DB, { readonly: true });

  // 1. Create/migrate the remote schema by reusing the app's own migrations,
  //    so the two databases cannot drift apart.
  const db = (await import('../src/db.js')).default;
  await db.init();
  console.log(`remote mode: ${db.mode}`);

  const { createClient } = await import('../src/turso-http.js');
  const remote = createClient({ url, authToken });

  const targets = [
    ['books', sqlite.prepare('SELECT * FROM books').all()],
    ['questions', sqlite.prepare("SELECT * FROM questions WHERE category = 'book'").all()]
  ];
  for (const [t, rows] of targets) console.log(`local ${t}: ${rows.length}`);

  for (const [table, rows] of targets) {
    if (!rows.length) {
      console.log(`${table}: nothing to sync`);
      continue;
    }
    const localCols = columnsOf(sqlite, table);
    const remoteCols = (await remote.execute(`PRAGMA table_info(${table})`)).rows.map((r) => r[1]);
    const cols = localCols.filter((c) => remoteCols.includes(c));
    const dropped = localCols.filter((c) => !remoteCols.includes(c));
    if (dropped.length) console.log(`  note: remote ${table} has no ${dropped.join(', ')} - skipped`);

    let done = 0;
    for (let i = 0; i < rows.length; i += CHUNK) {
      const slice = rows.slice(i, i + CHUNK);
      await remote.batch(insertStatements(table, cols, slice));
      done += slice.length;
      process.stdout.write(`\r  ${table}: ${done}/${rows.length}`);
    }
    process.stdout.write('\n');
  }

  // 2. Verify against the remote, not against what we believe we sent.
  for (const [table, rows] of targets) {
    const where = table === 'questions' ? " WHERE category = 'book'" : '';
    const r = await remote.execute(`SELECT COUNT(*) FROM ${table}${where}`);
    const n = Number(r.rows[0][0]);
    const ok = n >= rows.length;
    console.log(`${ok ? 'OK  ' : 'FAIL'} remote ${table}${where}: ${n} (local ${rows.length})`);
    if (!ok) process.exitCode = 1;
  }

  sqlite.close();
  db.close();
  console.log(process.exitCode ? 'FAILED - counts do not match.' : 'Done.');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
