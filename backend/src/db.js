// Dual-mode async database layer.
//
// - LOCAL (no TURSO_URL): uses better-sqlite3 (synchronous underneath, wrapped
//   in Promises so callers can uniformly `await`).
// - PROD (TURSO_URL set): uses @libsql/client (libSQL / Turso). better-sqlite3
//   is NEVER imported, so Netlify's build never tries to compile the native
//   module.
//
// Every public method returns a Promise in BOTH modes, so all call sites can
// `await db.prepare(sql).get/all/run(...)` uniformly.
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// `dataDir` is only needed in local (better-sqlite3) mode. Compute it lazily and
// tolerate `import.meta.url` being undefined — Netlify's esbuild bundle emits
// this module as CJS where `import.meta.url` is undefined, so evaluating it at
// module load would throw and crash every request in production (turso) mode.
let dataDir = null;
function ensureDataDir() {
  if (dataDir) return dataDir;
  let dir;
  try {
    dir = path.dirname(fileURLToPath(import.meta.url || `file://${process.cwd()}/`));
  } catch {
    dir = process.cwd();
  }
  dataDir = path.join(dir, '..', 'data');
  fs.mkdirSync(dataDir, { recursive: true });
  return dataDir;
}

let mode = 'local'; // 'local' | 'turso'
let sqlite = null; // better-sqlite3 Database (local)
let libsql = null; // libSQL client (turso)
let initialized = null; // module-scope promise (run init once, reused across warm starts)

// libSQL rejects `undefined` args; coerce to null (SQL NULL).
function sanitize(args) {
  return (args || []).map((a) => (a === undefined ? null : a));
}

// libSQL returns rows as arrays + a columns[] list; remap to objects.
function rowToObj(row, columns) {
  if (!row) return undefined;
  const o = {};
  for (let i = 0; i < columns.length; i++) o[columns[i]] = row[i];
  return o;
}

// ---------------------------------------------------------------------------
// Shared DDL (identical for both engines; SQLite syntax is compatible).
// ---------------------------------------------------------------------------
const SCHEMA = `
  CREATE TABLE IF NOT EXISTS questions (
    id           TEXT PRIMARY KEY,
    subject      TEXT NOT NULL,
    level        TEXT,
    topic        TEXT,
    subtopic     TEXT,
    paper_type   TEXT,
    command_term TEXT,
    marks        INTEGER,
    difficulty   INTEGER,
    question     TEXT,
    figure       TEXT,
    answer       TEXT,
    explanation  TEXT,
    source       TEXT,
    tags         TEXT,
    authored_by  TEXT DEFAULT 'ai',
    created_at   TEXT,
    knowledge_point_ids TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_q_subject ON questions(subject);
  CREATE INDEX IF NOT EXISTS idx_q_topic   ON questions(topic);
  CREATE INDEX IF NOT EXISTS idx_q_paper   ON questions(paper_type);

  CREATE TABLE IF NOT EXISTS books (
    id            TEXT PRIMARY KEY,
    subject       TEXT NOT NULL,
    title         TEXT NOT NULL,
    publisher     TEXT,
    edition       TEXT,
    has_answers   INTEGER DEFAULT 0,
    answer_source TEXT,
    cover_path    TEXT,
    total_questions INTEGER DEFAULT 0,
    created_at    TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_b_subject ON books(subject);

  CREATE TABLE IF NOT EXISTS topics (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT,
    name   TEXT,
    parent TEXT
  );

  CREATE TABLE IF NOT EXISTS progress (
    question_id   TEXT PRIMARY KEY,
    status        TEXT DEFAULT 'unattempted',
    attempts      INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    wrong_count   INTEGER DEFAULT 0,
    last_result   TEXT,
    last_seen     TEXT,
    mastery_level INTEGER DEFAULT 0,
    completed_at  TEXT
  );

  CREATE TABLE IF NOT EXISTS wrong_notebook (
    question_id    TEXT PRIMARY KEY,
    added_at       TEXT,
    last_wrong_at  TEXT,
    times_wrong    INTEGER DEFAULT 1,
    mastered       INTEGER DEFAULT 0,
    note           TEXT DEFAULT '',
    srs_level      INTEGER DEFAULT 0,
    next_review_at TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_wn_mastered ON wrong_notebook(mastered);
  CREATE INDEX IF NOT EXISTS idx_wn_due ON wrong_notebook(next_review_at);

  CREATE TABLE IF NOT EXISTS knowledge_points (
    id          TEXT PRIMARY KEY,
    subject     TEXT NOT NULL,
    code        TEXT,
    theme       TEXT,
    title       TEXT NOT NULL,
    description TEXT,
    refs        TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_kp_subject ON knowledge_points(subject);

  DROP TABLE IF EXISTS favorites;

  CREATE TABLE IF NOT EXISTS collections (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS collection_items (
    collection_id TEXT,
    question_id   TEXT,
    PRIMARY KEY (collection_id, question_id)
  );
  INSERT OR IGNORE INTO collections (id, name) VALUES ('default-favorites', 'Favorites');

  CREATE TABLE IF NOT EXISTS question_notes (
    question_id TEXT PRIMARY KEY,
    note        TEXT DEFAULT '',
    updated_at  TEXT
  );

  CREATE TABLE IF NOT EXISTS paper_templates (
    id            TEXT PRIMARY KEY,
    subject       TEXT NOT NULL,
    paper_type    TEXT NOT NULL,
    name          TEXT NOT NULL,
    duration_min  INTEGER,
    total_marks   INTEGER,
    calculator    INTEGER DEFAULT 0,
    num_questions INTEGER DEFAULT 0,
    question_mode TEXT DEFAULT 'marks',
    description   TEXT DEFAULT '',
    sort_order    INTEGER DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS exam_papers (
    id           TEXT PRIMARY KEY,
    template_id  TEXT,
    subject      TEXT NOT NULL,
    paper_type   TEXT NOT NULL,
    name         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    duration_min INTEGER,
    total_marks  INTEGER,
    num_questions INTEGER,
    note         TEXT DEFAULT ''
  );

  CREATE TABLE IF NOT EXISTS exam_paper_items (
    exam_id     TEXT NOT NULL,
    question_id TEXT NOT NULL,
    position    INTEGER NOT NULL,
    marks       INTEGER,
    PRIMARY KEY (exam_id, question_id)
  );

  CREATE TABLE IF NOT EXISTS question_usage (
    id          TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    usage_type  TEXT NOT NULL,
    ref_id      TEXT,
    used_at     TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_qu_question ON question_usage(question_id);
  CREATE INDEX IF NOT EXISTS idx_qu_type ON question_usage(usage_type);

  CREATE TABLE IF NOT EXISTS reports (
    id            TEXT PRIMARY KEY,
    question_id   TEXT NOT NULL,
    reason        TEXT NOT NULL,
    detail        TEXT DEFAULT '',
    page_ref      TEXT DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'open',
    created_at    TEXT NOT NULL,
    resolved_at   TEXT,
    resolved_note TEXT DEFAULT ''
  );
  CREATE INDEX IF NOT EXISTS idx_reports_question ON reports(question_id);
  CREATE INDEX IF NOT EXISTS idx_reports_status   ON reports(status);
`;

// Columns added after the original schema (live migrations).
const COLUMN_MIGRATIONS = [
  ['progress', 'correct_count', 'INTEGER DEFAULT 0'],
  ['progress', 'wrong_count', 'INTEGER DEFAULT 0'],
  ['progress', 'last_result', 'TEXT'],
  ['questions', 'knowledge_point_ids', 'TEXT'],
  ['questions', 'answer_figure', 'TEXT'],
  ['questions', 'question_image', 'TEXT'],
  ['questions', 'answer_image', 'TEXT'],
  ['questions', 'figure_image', 'TEXT'],
  ['questions', 'definition_basis', 'TEXT'],
  ['wrong_notebook', 'srs_level', 'INTEGER DEFAULT 0'],
  ['wrong_notebook', 'next_review_at', 'TEXT'],
  ['progress', 'mastery_level', 'INTEGER DEFAULT 0'],
  ['progress', 'completed_at', 'TEXT'],
  ['questions', 'book_id', 'TEXT'],
  ['questions', 'book_section', 'TEXT'],
  ['questions', 'book_page', 'INTEGER'],
  ['questions', 'in_book_order', 'INTEGER DEFAULT 0'],
  ['questions', 'source_type', 'TEXT DEFAULT "paper"'],
  ['questions', 'category', "TEXT DEFAULT 'past'"],
  ['questions', 'review_status', 'TEXT'],
  ['questions', 'well_down', 'INTEGER DEFAULT 0'],
  ['questions', 'well_down_at', 'TEXT'],
  ['questions', 'well_down_note', "TEXT DEFAULT ''"]
];

async function addColumnTurso(table, col, def) {
  try {
    await libsql.execute(`ALTER TABLE ${table} ADD COLUMN ${col} ${def}`);
  } catch (e) {
    // idempotent: column already exists is fine
    if (!/duplicate column|already exists/i.test(e.message || '')) throw e;
  }
}

function addColumnLocal(table, col, def) {
  const cols = sqlite.prepare(`PRAGMA table_info(${table})`).all().map((c) => c.name);
  if (!cols.includes(col)) {
    sqlite.prepare(`ALTER TABLE ${table} ADD COLUMN ${col} ${def}`).run();
  }
}

async function runColumnMigrations() {
  for (const [table, col, def] of COLUMN_MIGRATIONS) {
    if (mode === 'turso') await addColumnTurso(table, col, def);
    else addColumnLocal(table, col, def);
  }
}

// One-time backfill of the `category` column for pre-existing rows.
async function backfillCategories() {
  const need = await db.get(`
    SELECT COUNT(*) AS c FROM questions
    WHERE category = 'past' AND (
      source_type = 'book'
      OR source LIKE '%classified%'
      OR authored_by = 'ai'
    )
  `);
  if (!need || !need.c) return;
  await db.run(`UPDATE questions SET category='book' WHERE source_type='book'`);
  await db.run(`UPDATE questions SET category='topic' WHERE source_type='paper' AND source LIKE '%classified%'`);
  await db.run(`UPDATE questions SET category='ai' WHERE authored_by='ai'`);
}

async function runIndexMigrations() {
  await db.exec(`
    CREATE INDEX IF NOT EXISTS idx_q_category ON questions(category);
    CREATE INDEX IF NOT EXISTS idx_q_review   ON questions(review_status);
  `);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
const db = {
  get mode() {
    return mode;
  },

  /**
   * Open the database and run migrations. Idempotent + cached so it runs once
   * per process (and is reused across Netlify Function warm starts).
   * @returns {Promise<void>}
   */
  init() {
    if (!initialized) {
      initialized = (async () => {
        if (process.env.TURSO_URL) {
          // Pure-JS Turso HTTP client (no native binary — required for Netlify
          // CLI deploys that bundle on macOS). See backend/src/turso-http.js.
          const { createClient } = await import('./turso-http.js');
          libsql = createClient({
            url: process.env.TURSO_URL,
            authToken: process.env.TURSO_AUTH_TOKEN
          });
          mode = 'turso';
          await libsql.executeMultiple(SCHEMA);
        } else {
          const Database = (await import('better-sqlite3')).default;
          sqlite = new Database(path.join(ensureDataDir(), 'app.db'));
          sqlite.pragma('journal_mode = WAL');
          mode = 'local';
          sqlite.exec(SCHEMA);
        }
        await runColumnMigrations();
        await runIndexMigrations();
        await backfillCategories();
      })().catch((e) => {
        initialized = null; // allow a retry on next call
        throw e;
      });
    }
    return initialized;
  },

  // Returns a statement-like object with async get/all/run in both modes.
  prepare(sql) {
    if (mode === 'turso') {
      return {
        async get(...params) {
          const r = await libsql.execute({ sql, args: sanitize(params) });
          return rowToObj(r.rows[0], r.columns);
        },
        async all(...params) {
          const r = await libsql.execute({ sql, args: sanitize(params) });
          return r.rows.map((row) => rowToObj(row, r.columns));
        },
        async run(...params) {
          const r = await libsql.execute({ sql, args: sanitize(params) });
          return {
            lastInsertRowid: r.lastInsertRowid == null ? 0 : Number(r.lastInsertRowid),
            changes: Number(r.rowsAffected ?? 0)
          };
        }
      };
    }
    // local: better-sqlite3 statement (sync methods, callers `await` no-ops)
    const stmt = sqlite.prepare(sql);
    return {
      get(...params) {
        return stmt.get(...sanitize(params));
      },
      all(...params) {
        return stmt.all(...sanitize(params));
      },
      run(...params) {
        return stmt.run(...sanitize(params));
      }
    };
  },

  async get(sql, ...params) {
    if (mode === 'turso') {
      const r = await libsql.execute({ sql, args: sanitize(params) });
      return rowToObj(r.rows[0], r.columns);
    }
    return Promise.resolve(sqlite.prepare(sql).get(...sanitize(params)));
  },

  async all(sql, ...params) {
    if (mode === 'turso') {
      const r = await libsql.execute({ sql, args: sanitize(params) });
      return r.rows.map((row) => rowToObj(row, r.columns));
    }
    return Promise.resolve(sqlite.prepare(sql).all(...sanitize(params)));
  },

  async run(sql, ...params) {
    if (mode === 'turso') {
      const r = await libsql.execute({ sql, args: sanitize(params) });
      return {
        lastInsertRowid: r.lastInsertRowid == null ? 0 : Number(r.lastInsertRowid),
        changes: Number(r.rowsAffected ?? 0)
      };
    }
    return Promise.resolve(sqlite.prepare(sql).run(...sanitize(params)));
  },

  async exec(sql) {
    if (mode === 'turso') return libsql.executeMultiple(sql);
    return sqlite.exec(sql);
  },

  /**
   * Transaction wrapper.
   * - local: real BEGIN/COMMIT/ROLLBACK on the single connection.
   * - turso: best-effort sequential (libSQL over HTTP has no session-wide
   *   transaction); each statement autocommits. Acceptable for this single-user
   *   study app. Documented limitation.
   * @param {() => Promise<void>|void} fn
   */
  async transaction(fn) {
    if (mode === 'local') {
      await db.run('BEGIN');
      try {
        await fn();
        await db.run('COMMIT');
      } catch (e) {
        await db.run('ROLLBACK');
        throw e;
      }
    } else {
      await fn();
    }
  }
};

export default db;
