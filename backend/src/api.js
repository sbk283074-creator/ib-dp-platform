import express from 'express';
import crypto from 'crypto';
import db from './db.js';
import { COLUMNS, rowToQuestion, validateQuestion, insertQuestion } from './questionRepo.js';

const router = express.Router();

// Wrap an async route handler so Express 4 forwards rejected promises to the
// error handler instead of leaving the request hanging.
const asyncHandler = (fn) => (req, res, next) => {
  Promise.resolve(fn(req, res, next)).catch(next);
};

// F10: attach usage records (exam / wrong_book) to question rows for display.
async function attachUsage(rows) {
  const ids = rows.map((r) => r.id);
  if (!ids.length) return rows;
  const ph = ids.map(() => '?').join(',');
  const usages = await db.prepare(
    `SELECT question_id, usage_type, ref_id, used_at FROM question_usage WHERE question_id IN (${ph}) ORDER BY used_at`
  ).all(...ids);
  const map = {};
  for (const u of usages) (map[u.question_id] ||= []).push(u);
  return rows.map((r) => ({ ...r, usage: map[r.id] || [] }));
}

// GET /api/health
router.get('/health', (req, res) => {
  res.json({ ok: true, time: new Date().toISOString() });
});

// GET /api/facets  -> distinct filter values for the UI
router.get('/facets', asyncHandler(async (req, res) => {
  const distinct = async (col) =>
    (await db.prepare(`SELECT DISTINCT ${col} FROM questions WHERE ${col} IS NOT NULL AND ${col} <> '' ORDER BY ${col}`).all())
      .map((r) => r[col]);
  res.json({
    subjects: await distinct('subject'),
    topics: await distinct('topic'),
    paper_types: await distinct('paper_type'),
    command_terms: await distinct('command_term')
  });
}));

// GET /api/questions  -> search + filter + paginate
router.get('/questions', asyncHandler(async (req, res) => {
  const {
    q, subject, topic, paper_type, command_term, difficulty, marks, tag, knowledge_point,
    category, review_status, sort = 'recent', limit = 20, offset = 0, exclude_completed
  } = req.query;

  const filters = [];
  const params = [];

  const SUBJECT_MAP = { CS: 'Computer Science', Math: 'Mathematics', Physics: 'Physics' };
  if (subject) {
    filters.push('subject = ?');
    params.push(SUBJECT_MAP[subject] || subject);
  }
  if (topic) { filters.push('topic = ?'); params.push(topic); }
  if (paper_type) {
    const m = /^Paper\s+(\d+)$/i.exec(paper_type);
    if (m) {
      filters.push('(paper_type = ? OR paper_type = ?)');
      params.push(paper_type, `HL-paper${m[1]}`);
    } else {
      filters.push('paper_type = ?');
      params.push(paper_type);
    }
  }
  if (command_term) { filters.push('command_term = ?'); params.push(command_term); }
  if (category) {
    filters.push('category = ?');
    params.push(category);
  }
  if (review_status) {
    filters.push('review_status = ?');
    params.push(review_status);
  }
  if (difficulty) { filters.push('difficulty = ?'); params.push(Number(difficulty)); }
  if (marks) { filters.push('marks = ?'); params.push(Number(marks)); }
  if (tag) { filters.push('tags LIKE ?'); params.push(`%"${tag}"%`); }
  if (knowledge_point) {
    const kps = String(knowledge_point).split(',').map((s) => s.trim()).filter(Boolean);
    if (kps.length) {
      const ors = kps.map(() => 'knowledge_point_ids LIKE ?');
      filters.push('(' + ors.join(' OR ') + ')');
      kps.forEach((k) => params.push(`%"${k}"%`));
    }
  }
  if (q) {
    filters.push('(question LIKE ? OR answer LIKE ? OR explanation LIKE ? OR topic LIKE ?)');
    params.push(`%${q}%`, `%${q}%`, `%${q}%`, `%${q}%`);
  }
  if (exclude_completed === '1' || exclude_completed === 'true') {
    filters.push(`id NOT IN (SELECT question_id FROM progress WHERE status = 'completed')`);
  }

  const where = filters.length ? `WHERE ${filters.join(' AND ')}` : '';
  const orderBy =
    sort === 'marks' ? 'ORDER BY marks ASC' :
    sort === 'difficulty' ? 'ORDER BY difficulty ASC' :
    'ORDER BY created_at DESC';

  const total = (await db.prepare(`SELECT COUNT(*) AS c FROM questions ${where}`).get(...params)).c;
  const rows = await db.prepare(
    `SELECT ${COLUMNS.join(', ')} FROM questions ${where} ${orderBy} LIMIT ? OFFSET ?`
  ).all(...params, Number(limit), Number(offset));

  res.json({ total, limit: Number(limit), offset: Number(offset), items: await attachUsage(rows.map(rowToQuestion)) });
}));

// GET /api/questions/:id/similar  -> related questions by shared knowledge points +
// same subject/topic/command-term, scored and ranked (excluding the question itself).
router.get('/questions/:id/similar', asyncHandler(async (req, res) => {
  const q = await db.prepare(`SELECT ${COLUMNS.join(', ')} FROM questions WHERE id = ?`).get(req.params.id);
  if (!q) return res.status(404).json({ error: 'not found' });
  const myKps = q.knowledge_point_ids ? JSON.parse(q.knowledge_point_ids) : [];
  // Bound the candidate set for remote (Turso-over-HTTP) performance.
  const candidates = await db.prepare(`SELECT ${COLUMNS.join(', ')} FROM questions WHERE id <> ? LIMIT 5000`).all(q.id);
  const scored = candidates.map((c) => {
    let score = 0;
    const cKps = c.knowledge_point_ids ? JSON.parse(c.knowledge_point_ids) : [];
    const shared = myKps.filter((k) => cKps.includes(k)).length;
    score += shared * 3;
    if (c.subject === q.subject) score += 1;
    if (c.topic === q.topic) score += 2;
    if (c.command_term && c.command_term === q.command_term) score += 1;
    if (c.paper_type === q.paper_type) score += 1;
    return { ...rowToQuestion(c), _score: score, _sharedKp: shared };
  }).filter((x) => x._score > 0)
    .sort((a, b) => b._score - a._score)
    .slice(0, 12);
  res.json({ similar: scored });
}));

// GET /api/questions/:id
router.get('/questions/:id', asyncHandler(async (req, res) => {
  const row = await db.prepare(`SELECT ${COLUMNS.join(', ')} FROM questions WHERE id = ?`).get(req.params.id);
  if (!row) return res.status(404).json({ error: 'not found' });
  res.json((await attachUsage([rowToQuestion(row)]))[0]);
}));

// POST /api/questions  -> add a single custom (user-authored) question
router.post('/questions', asyncHandler(async (req, res) => {
  const b = req.body || {};
  const v = validateQuestion(b);
  if (!v.ok) return res.status(400).json({ error: v.error });
  const id = await insertQuestion(b, { authored_by: 'user' });
  res.status(201).json({ id });
}));

// POST /api/questions/bulk  -> import many questions at once (idempotent by id)
router.post('/questions/bulk', asyncHandler(async (req, res) => {
  const body = req.body || {};
  const arr = Array.isArray(body) ? body : body.questions;
  if (!Array.isArray(arr)) {
    return res.status(400).json({ error: 'expected a JSON array or { questions: [...] }' });
  }
  const inserted = [];
  const errors = [];
  await db.transaction(async () => {
    for (const item of arr) {
      const v = validateQuestion(item);
      if (!v.ok) {
        errors.push({ index: arr.indexOf(item), id: item && item.id, error: v.error });
        continue;
      }
      inserted.push(await insertQuestion(item, { authored_by: item.authored_by || 'import' }));
    }
  });
  res.json({ inserted: inserted.length, total: arr.length, errors });
}));

// ---------------------------------------------------------------------------
// F2 / F3  Knowledge points
// ---------------------------------------------------------------------------
router.get('/knowledge-points', asyncHandler(async (req, res) => {
  const { subject } = req.query;
  const rows = subject
    ? await db.prepare('SELECT * FROM knowledge_points WHERE subject = ? ORDER BY code').all(subject)
    : await db.prepare('SELECT * FROM knowledge_points ORDER BY subject, code').all();
  res.json(rows.map((r) => ({ ...r, references: r.refs ? JSON.parse(r.refs) : [] })));
}));

router.get('/knowledge-points/:id', asyncHandler(async (req, res) => {
  const kp = await db.prepare('SELECT * FROM knowledge_points WHERE id = ?').get(req.params.id);
  if (!kp) return res.status(404).json({ error: 'not found' });
  kp.references = kp.refs ? JSON.parse(kp.refs) : [];
  const questions = await db.prepare(
    `SELECT ${COLUMNS.join(', ')} FROM questions WHERE knowledge_point_ids LIKE ?`
  ).all(`%"${kp.id}"%`).map(rowToQuestion);
  res.json({ kp, questions });
}));

router.post('/knowledge-points', asyncHandler(async (req, res) => {
  const b = req.body || {};
  if (!b.id || !b.title) return res.status(400).json({ error: 'missing id or title' });
  await db.prepare(`
    INSERT OR REPLACE INTO knowledge_points (id, subject, code, theme, title, description, refs)
    VALUES (?,?,?,?,?,?,?)
  `).run(b.id, b.subject || 'CS', b.code || null, b.theme || null, b.title,
        b.description || null, JSON.stringify(b.references || []));
  res.status(201).json({ ok: true });
}));

// ---------------------------------------------------------------------------
// F1  Favorites — implemented as the default "Favorites" collection
// ---------------------------------------------------------------------------
const FAV_COLLECTION = 'default-favorites';

router.get('/favorites', asyncHandler(async (req, res) => {
  const rows = await db.prepare(`
    SELECT q.* FROM collection_items ci JOIN questions q ON q.id = ci.question_id
    WHERE ci.collection_id = ?
    ORDER BY ci.rowid DESC
  `).all(FAV_COLLECTION);
  res.json(rows.map(rowToQuestion));
}));

router.post('/favorites', asyncHandler(async (req, res) => {
  const { question_id } = req.body || {};
  if (!question_id) return res.status(400).json({ error: 'missing question_id' });
  const exists = await db.prepare('SELECT id FROM questions WHERE id = ?').get(question_id);
  if (!exists) return res.status(404).json({ error: 'question not found' });
  const already = await db.prepare(
    'SELECT question_id FROM collection_items WHERE collection_id = ? AND question_id = ?'
  ).get(FAV_COLLECTION, question_id);
  if (already) {
    await db.prepare('DELETE FROM collection_items WHERE collection_id = ? AND question_id = ?')
      .run(FAV_COLLECTION, question_id);
    return res.json({ favorited: false });
  }
  await db.prepare('INSERT OR IGNORE INTO collection_items (collection_id, question_id) VALUES (?,?)')
    .run(FAV_COLLECTION, question_id);
  res.json({ favorited: true });
}));

router.delete('/favorites/:qid', asyncHandler(async (req, res) => {
  await db.prepare('DELETE FROM collection_items WHERE collection_id = ? AND question_id = ?')
    .run(FAV_COLLECTION, req.params.qid);
  res.json({ ok: true });
}));

// ---------------------------------------------------------------------------
// F5  Collections
// ---------------------------------------------------------------------------
router.get('/collections', asyncHandler(async (req, res) => {
  const rows = await db.prepare(`
    SELECT c.*, (SELECT COUNT(*) FROM collection_items ci WHERE ci.collection_id = c.id) AS item_count
    FROM collections c ORDER BY c.name
  `).all();
  res.json(rows);
}));

router.post('/collections', asyncHandler(async (req, res) => {
  const { name } = req.body || {};
  if (!name) return res.status(400).json({ error: 'missing name' });
  const id = crypto.randomUUID();
  await db.prepare('INSERT INTO collections (id, name) VALUES (?,?)').run(id, name);
  res.status(201).json({ id, name });
}));

router.get('/collections/:id', asyncHandler(async (req, res) => {
  const c = await db.prepare('SELECT * FROM collections WHERE id = ?').get(req.params.id);
  if (!c) return res.status(404).json({ error: 'not found' });
  const items = (await db.prepare(`
    SELECT q.* FROM collection_items ci JOIN questions q ON q.id = ci.question_id
    WHERE ci.collection_id = ? ORDER BY ci.rowid
  `).all(req.params.id)).map(rowToQuestion);
  res.json({ collection: c, items });
}));

router.delete('/collections/:id', asyncHandler(async (req, res) => {
  if (req.params.id === FAV_COLLECTION) {
    return res.status(400).json({ error: 'the default Favorites collection cannot be deleted' });
  }
  await db.transaction(async () => {
    await db.prepare('DELETE FROM collection_items WHERE collection_id = ?').run(req.params.id);
    await db.prepare('DELETE FROM collections WHERE id = ?').run(req.params.id);
  });
  res.json({ ok: true });
}));

router.post('/collections/:id/items', asyncHandler(async (req, res) => {
  const { question_id } = req.body || {};
  if (!question_id) return res.status(400).json({ error: 'missing question_id' });
  const c = await db.prepare('SELECT id FROM collections WHERE id = ?').get(req.params.id);
  if (!c) return res.status(404).json({ error: 'collection not found' });
  const q = await db.prepare('SELECT id FROM questions WHERE id = ?').get(question_id);
  if (!q) return res.status(404).json({ error: 'question not found' });
  await db.prepare('INSERT OR IGNORE INTO collection_items (collection_id, question_id) VALUES (?,?)')
    .run(req.params.id, question_id);
  res.json({ ok: true });
}));

router.delete('/collections/:id/items/:qid', asyncHandler(async (req, res) => {
  await db.prepare('DELETE FROM collection_items WHERE collection_id = ? AND question_id = ?')
    .run(req.params.id, req.params.qid);
  res.json({ ok: true });
}));

// ---------------------------------------------------------------------------
// F8  Question-level notes (any question)
// ---------------------------------------------------------------------------
router.get('/question-notes/:qid', asyncHandler(async (req, res) => {
  const row = await db.prepare('SELECT note FROM question_notes WHERE question_id = ?').get(req.params.qid);
  res.json({ note: row ? row.note : '' });
}));

router.put('/question-notes/:qid', asyncHandler(async (req, res) => {
  const { note } = req.body || {};
  await db.prepare(`
    INSERT INTO question_notes (question_id, note, updated_at) VALUES (?,?,?)
    ON CONFLICT(question_id) DO UPDATE SET note = excluded.note, updated_at = excluded.updated_at
  `).run(req.params.qid, note ?? '', new Date().toISOString());
  res.json({ ok: true });
}));

// ---------------------------------------------------------------------------
// Progress (existing) + F6 aggregations
// ---------------------------------------------------------------------------
router.get('/progress', asyncHandler(async (req, res) => {
  const rows = await db.prepare('SELECT * FROM progress').all();
  res.json(rows);
}));

// PATCH /api/progress/:id
router.patch('/progress/:id', asyncHandler(async (req, res) => {
  const id = req.params.id;
  const exists = await db.prepare('SELECT id FROM questions WHERE id = ?').get(id);
  if (!exists) return res.status(404).json({ error: 'question not found' });
  const { completed, mastery_level } = req.body || {};
  const now = new Date().toISOString();
  const cur = await db.prepare('SELECT * FROM progress WHERE question_id = ?').get(id);
  const mastery = mastery_level != null ? Number(mastery_level) : (cur?.mastery_level ?? 0);
  let status = cur?.status ?? 'unattempted';
  let completedAt = cur?.completed_at ?? null;
  if (completed === true) {
    status = 'completed';
    completedAt = now;
  } else if (completed === false) {
    status = (cur?.attempts ?? 0) > 0 ? 'attempted' : 'unattempted';
    completedAt = null;
  }
  await db.prepare(`
    INSERT INTO progress (question_id, status, attempts, correct_count, wrong_count, last_result, last_seen, mastery_level, completed_at)
    VALUES (?,?,?,?,?,?,?,?,?)
    ON CONFLICT(question_id) DO UPDATE SET
      status = excluded.status,
      mastery_level = excluded.mastery_level,
      completed_at = excluded.completed_at,
      last_seen = excluded.last_seen
  `).run(id, status, cur?.attempts ?? 0, cur?.correct_count ?? 0, cur?.wrong_count ?? 0,
        cur?.last_result ?? null, now, mastery, completedAt);
  res.json({ ok: true, status, mastery_level: mastery, completed_at: completedAt });
}));

// GET /api/progress/review
router.get('/progress/review', asyncHandler(async (req, res) => {
  const { from, to, mastery } = req.query;
  const clauses = [`p.status = 'completed'`, `p.completed_at IS NOT NULL`];
  const params = [];
  if (from) { clauses.push('p.completed_at >= ?'); params.push(from + 'T00:00:00.000Z'); }
  if (to)   { clauses.push('p.completed_at <= ?'); params.push(to + 'T23:59:59.999Z'); }
  if (mastery) { clauses.push('p.mastery_level = ?'); params.push(Number(mastery)); }
  const where = 'WHERE ' + clauses.join(' AND ');
  const rows = await db.prepare(`
    SELECT q.*, p.mastery_level, p.completed_at, p.status
    FROM progress p JOIN questions q ON q.id = p.question_id
    ${where}
    ORDER BY p.completed_at DESC
  `).all(...params);
  res.json(rows.map(rowToQuestion));
}));

// F6: accuracy aggregated by topic
router.get('/progress/by-topic', asyncHandler(async (req, res) => {
  const rows = await db.prepare(`
    SELECT q.topic AS topic,
           COUNT(*) AS attempted,
           SUM(p.correct_count) AS correct,
           SUM(p.wrong_count) AS wrong
    FROM progress p JOIN questions q ON q.id = p.question_id
    GROUP BY q.topic ORDER BY q.topic
  `).all();
  const out = rows.map((r) => {
    const correct = r.correct || 0, wrong = r.wrong || 0, answered = correct + wrong;
    return { topic: r.topic, attempted: r.attempted, correct, wrong, accuracy: answered ? Math.round((correct / answered) * 100) : 0 };
  });
  res.json(out);
}));

// F6: accuracy aggregated by knowledge point.
// Optimized: build a Map<id, question> once (O(n)) instead of O(n*m) .find().
router.get('/progress/by-kp', asyncHandler(async (req, res) => {
  const progress = await db.prepare('SELECT * FROM progress').all();
  const questions = await db.prepare(`SELECT id, knowledge_point_ids FROM questions`).all();
  const qById = new Map(questions.map((q) => [q.id, q]));
  const kpMap = {};
  for (const p of progress) {
    const q = qById.get(p.question_id);
    const kps = q && q.knowledge_point_ids ? JSON.parse(q.knowledge_point_ids) : [];
    const targets = kps.length ? kps : ['(unlinked)'];
    for (const k of targets) {
      kpMap[k] = kpMap[k] || { kp: k, attempted: 0, correct: 0, wrong: 0 };
      kpMap[k].attempted += 1;
      kpMap[k].correct += p.correct_count || 0;
      kpMap[k].wrong += p.wrong_count || 0;
    }
  }
  const out = Object.values(kpMap).map((v) => ({
    kp: v.kp, attempted: v.attempted, correct: v.correct, wrong: v.wrong,
    accuracy: (v.correct + v.wrong) ? Math.round((v.correct / (v.correct + v.wrong)) * 100) : 0
  })).sort((a, b) => a.kp.localeCompare(b.kp));
  res.json(out);
}));

// ---------------------------------------------------------------------------
// Attempt + 错题本 + F7 Spaced repetition
// ---------------------------------------------------------------------------
const SRS_INTERVALS = [1, 3, 7, 16, 35];

// POST /api/attempt
router.post('/attempt', asyncHandler(async (req, res) => {
  const { question_id, result } = req.body || {};
  if (!question_id || !['correct', 'incorrect'].includes(result)) {
    return res.status(400).json({ error: 'missing question_id or invalid result' });
  }
  const now = new Date().toISOString();
  const p = await db.prepare('SELECT * FROM progress WHERE question_id = ?').get(question_id);
  const attempts = (p?.attempts ?? 0) + 1;
  const correct_count = (p?.correct_count ?? 0) + (result === 'correct' ? 1 : 0);
  const wrong_count = (p?.wrong_count ?? 0) + (result === 'incorrect' ? 1 : 0);
  const status = result === 'correct' ? 'correct' : wrong_count > 0 ? 'wrong' : 'attempted';

  await db.transaction(async () => {
    await db.prepare(`
      INSERT INTO progress (question_id, status, attempts, correct_count, wrong_count, last_result, last_seen)
      VALUES (?,?,?,?,?,?,?)
      ON CONFLICT(question_id) DO UPDATE SET
        status = excluded.status,
        attempts = excluded.attempts,
        correct_count = excluded.correct_count,
        wrong_count = excluded.wrong_count,
        last_result = excluded.last_result,
        last_seen = excluded.last_seen
    `).run(question_id, status, attempts, correct_count, wrong_count, result, now);

    if (result === 'incorrect') {
      const w = await db.prepare('SELECT * FROM wrong_notebook WHERE question_id = ?').get(question_id);
      await db.prepare(`
        INSERT INTO wrong_notebook (question_id, added_at, last_wrong_at, times_wrong, mastered, note, srs_level, next_review_at)
        VALUES (?,?,?,?,0,'',0,?)
        ON CONFLICT(question_id) DO UPDATE SET
          last_wrong_at = excluded.last_wrong_at,
          times_wrong = excluded.times_wrong,
          srs_level = 0,
          next_review_at = excluded.next_review_at
      `).run(question_id, w?.added_at ?? now, now, (w?.times_wrong ?? 0) + 1, now);
    } else {
      const w = await db.prepare('SELECT * FROM wrong_notebook WHERE question_id = ?').get(question_id);
      if (w) {
        const lvl = Math.min((w.srs_level ?? 0) + 1, SRS_INTERVALS.length);
        const days = SRS_INTERVALS[lvl - 1] ?? SRS_INTERVALS[SRS_INTERVALS.length - 1];
        const next = new Date(Date.now() + days * 86400000).toISOString();
        await db.prepare('UPDATE wrong_notebook SET srs_level = ?, next_review_at = ? WHERE question_id = ?')
          .run(lvl, next, question_id);
      }
    }
  });
  res.json({ ok: true });
}));

// GET /api/wrong-questions
router.get('/wrong-questions', asyncHandler(async (req, res) => {
  const includeMastered = req.query.all === '1' || req.query.all === 'true';
  const dueOnly = req.query.due === '1' || req.query.due === 'true';
  const clauses = [];
  const params = [];
  if (!includeMastered) { clauses.push('wn.mastered = 0'); }
  if (dueOnly) { clauses.push('wn.next_review_at <= ?'); params.push(new Date().toISOString()); }
  const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
  const rows = await db.prepare(`
    SELECT q.*, wn.times_wrong, wn.added_at, wn.last_wrong_at, wn.mastered, wn.note, wn.srs_level, wn.next_review_at
    FROM wrong_notebook wn
    JOIN questions q ON q.id = wn.question_id
    ${where}
    ORDER BY wn.last_wrong_at DESC
  `).all(...params);
  res.json(rows.map(rowToQuestion));
}));

// POST /api/wrong-questions/:id
router.post('/wrong-questions/:id', asyncHandler(async (req, res) => {
  const id = req.params.id;
  const exists = await db.prepare('SELECT id FROM questions WHERE id = ?').get(id);
  if (!exists) return res.status(404).json({ error: 'question not found' });
  const now = new Date().toISOString();
  await db.prepare(`
    INSERT INTO wrong_notebook (question_id, added_at, last_wrong_at, times_wrong, mastered, note, srs_level, next_review_at)
    VALUES (?,?,?,1,0,?,0,?)
    ON CONFLICT(question_id) DO UPDATE SET mastered = 0
  `).run(id, now, now, req.body?.note ?? '', now);
  await db.prepare(`
    INSERT OR REPLACE INTO question_usage (id, question_id, usage_type, ref_id, used_at)
    VALUES (?, ?, 'wrong_book', ?, ?)
  `).run(`WB:${id}`, id, id, now);
  res.json({ ok: true });
}));

// PATCH /api/wrong-questions/:id
router.patch('/wrong-questions/:id', asyncHandler(async (req, res) => {
  const id = req.params.id;
  const { mastered, note, next_review_at } = req.body || {};
  const sets = [];
  const params = [];
  if (mastered !== undefined) { sets.push('mastered = ?'); params.push(mastered ? 1 : 0); }
  if (note !== undefined) { sets.push('note = ?'); params.push(note); }
  if (next_review_at !== undefined) { sets.push('next_review_at = ?'); params.push(next_review_at); }
  if (!sets.length) return res.status(400).json({ error: 'nothing to update' });
  params.push(id);
  await db.prepare(`UPDATE wrong_notebook SET ${sets.join(', ')} WHERE question_id = ?`).run(...params);
  res.json({ ok: true });
}));

// DELETE /api/wrong-questions/:id
router.delete('/wrong-questions/:id', asyncHandler(async (req, res) => {
  await db.prepare('DELETE FROM wrong_notebook WHERE question_id = ?').run(req.params.id);
  res.json({ ok: true });
}));

// ============================================================
// Books
// ============================================================
router.get('/books', asyncHandler(async (req, res) => {
  const { subject } = req.query;
  const rows = subject
    ? await db.prepare('SELECT * FROM books WHERE subject = ? ORDER BY title').all(subject)
    : await db.prepare('SELECT * FROM books ORDER BY subject, title').all();
  res.json(rows);
}));

router.get('/books/:id', asyncHandler(async (req, res) => {
  const book = await db.prepare('SELECT * FROM books WHERE id = ?').get(req.params.id);
  if (!book) return res.status(404).json({ error: 'book not found' });
  const questions = (await db.prepare(
    `SELECT ${COLUMNS.join(', ')} FROM questions WHERE book_id = ? ORDER BY book_section, in_book_order`
  ).all(book.id)).map(rowToQuestion);
  const sections = {};
  for (const q of questions) {
    const s = q.book_section || 'General';
    (sections[s] ||= []).push(q);
  }
  res.json({ book, sections, questions });
}));

router.post('/books', asyncHandler(async (req, res) => {
  const b = req.body || {};
  if (!b.id || !b.title || !b.subject) return res.status(400).json({ error: 'missing id / title / subject' });
  await db.prepare(`
    INSERT OR REPLACE INTO books (id, subject, title, publisher, edition, has_answers, answer_source, cover_path, total_questions, created_at)
    VALUES (?,?,?,?,?,?,?,?,?,?)
  `).run(b.id, b.subject, b.title, b.publisher || null, b.edition || null,
        b.has_answers ? 1 : 0, b.answer_source || null, b.cover_path || null,
        b.total_questions || 0, b.created_at || new Date().toISOString());
  res.status(201).json({ ok: true, id: b.id });
}));

// POST /api/books/import
router.post('/books/import', asyncHandler(async (req, res) => {
  const body = req.body || {};
  const payload = Array.isArray(body) ? body : [body];
  const inserted = [];
  const errors = [];
  await db.transaction(async () => {
    for (const entry of payload) {
      const { book, questions } = entry;
      if (!book || !book.id || !questions) { errors.push({ error: 'each entry needs book + questions', entry }); continue; }
      await db.prepare(`
        INSERT OR REPLACE INTO books (id, subject, title, publisher, edition, has_answers, answer_source, cover_path, total_questions, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
      `).run(book.id, book.subject, book.title, book.publisher || null, book.edition || null,
            book.has_answers ? 1 : 0, book.answer_source || null, book.cover_path || null,
            questions.length, book.created_at || new Date().toISOString());
      for (const q of questions) {
        const v = validateQuestion(q);
        if (!v.ok) { errors.push({ id: q.id, error: v.error }); continue; }
        if (!q.book_id) q.book_id = book.id;
        inserted.push(await insertQuestion(q, { authored_by: q.authored_by || 'import' }));
      }
    }
  });
  res.json({ inserted: inserted.length, books: payload.length, errors });
}));

// POST /api/export
router.post('/export', asyncHandler(async (req, res) => {
  const ids = (req.body && req.body.ids) || [];
  const rows = ids.length
    ? await db.prepare(`SELECT ${COLUMNS.join(', ')} FROM questions WHERE id IN (${ids.map(() => '?').join(',')})`).all(...ids)
    : [];
  res.json({ html: renderWorksheet(rows.map(rowToQuestion)) });
}));

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function kpLabel(ids) {
  if (!ids || !ids.length) return '';
  return ' · KP: ' + ids.join(', ');
}

function renderWorksheet(items) {
  const qImgs = (it) => (it.question_image ? it.question_image.split(',').filter(Boolean) : []);
  const aImgs = (it) => (it.answer_image ? it.answer_image.split(',').filter(Boolean) : []);
  const fImgs = (it) => (it.figure_image ? it.figure_image.split(',').filter(Boolean) : []);
  const questionsHtml = items.map((it, i) => `
    <div class="q">
      <div class="qmeta">${escapeHtml(it.subject)} · ${escapeHtml(it.topic)}${it.paper_type ? ' · ' + escapeHtml(it.paper_type) : ''}${it.marks ? ' · [' + it.marks + ' marks]' : ''}${escapeHtml(kpLabel(it.knowledge_point_ids))}</div>
      ${qImgs(it).length
        ? `<div class="qimgs">${qImgs(it).map((s) => `<img src="${escapeHtml(s)}" alt="question"/>`).join('')}</div>`
        : `<div class="qbody">${i + 1}. ${escapeHtml(it.question)}</div>
           ${it.figure ? `<div class="qfig"><img src="${escapeHtml(it.figure)}" alt="figure"/></div>` : ''}`
      }
      ${fImgs(it).length ? `<div class="qfig"><img src="${escapeHtml(fImgs(it)[0])}" alt="figure"/></div>` : ''}
    </div>`).join('');

  const keyHtml = items.map((it, i) => `
    <div class="k">
      <div class="khead"><b>${i + 1}.</b> Answer</div>
      ${aImgs(it).length
        ? `<div class="qimgs">${aImgs(it).map((s) => `<img src="${escapeHtml(s)}" alt="answer"/>`).join('')}</div>`
        : `${it.answer_figure ? `<div><img src="${escapeHtml(it.answer_figure)}" alt="answer figure"/></div>` : ''}
           <div class="kbody">${escapeHtml(it.answer)}</div>`
      }
      <div class="kexp"><i>Explanation:</i> ${escapeHtml(it.explanation)}</div>
    </div>`).join('');

  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>IB DP Worksheet</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body,{delimiters:[{left:'$',right:'$',display:false},{left:'$$',right:'$$',display:true}]})"></script>
<style>
  body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:820px;margin:32px auto;padding:0 24px;color:#111;line-height:1.55}
  h1{font-size:22px;margin-bottom:4px}
  .meta{color:#666;font-size:13px;margin-bottom:24px}
  .q{border-bottom:1px solid #eee;padding:14px 0}
  .qmeta{color:#0c447c;font-size:12px;font-weight:600;margin-bottom:6px}
  .qbody{white-space:pre-wrap}
  .kbody{white-space:pre-wrap}
  .qfig{margin-top:8px;color:#555;font-size:13px}
  .qimgs{margin:8px 0}
  .qimgs img{display:block;max-width:100%;height:auto;border:1px solid #ddd;border-radius:6px;margin:6px 0}
  .pagebreak{page-break-before:always}
  h2{font-size:18px;margin-top:8px}
  .k{border-bottom:1px solid #eee;padding:12px 0}
  .khead{font-weight:600;margin-bottom:4px}
  .kexp{color:#444;font-size:13px;margin-top:4px}
  @media print{body{margin:0}}
</style></head>
<body>
  <h1>IB DP Practice Worksheet</h1>
  <div class="meta">Generated ${new Date().toLocaleString()} · ${items.length} question(s)</div>
  ${questionsHtml || '<p>No questions selected.</p>'}
  <div class="pagebreak"></div>
  <h2>Answer Key</h2>
  ${keyHtml || '<p>No questions selected.</p>'}
  <script>window.onload=()=>setTimeout(()=>window.print(),600);</script>
</body></html>`;
}

// ============================================================
// F10 试卷生成 (mock exam paper generation)
// ============================================================
router.get('/paper-templates', asyncHandler(async (req, res) => {
  const rows = await db.prepare('SELECT * FROM paper_templates ORDER BY sort_order').all();
  res.json(rows);
}));

router.get('/exams', asyncHandler(async (req, res) => {
  const rows = await db.prepare(`
    SELECT ep.*, COUNT(ei.question_id) AS item_count
    FROM exam_papers ep
    LEFT JOIN exam_paper_items ei ON ei.exam_id = ep.id
    GROUP BY ep.id ORDER BY ep.created_at DESC
  `).all();
  res.json(rows);
}));

router.get('/exams/:id', asyncHandler(async (req, res) => {
  const exam = await db.prepare('SELECT * FROM exam_papers WHERE id = ?').get(req.params.id);
  if (!exam) return res.status(404).json({ error: 'exam not found' });
  const items = await db.prepare(`
    SELECT ei.position, ei.marks, q.* FROM exam_paper_items ei JOIN questions q ON q.id = ei.question_id
    WHERE ei.exam_id = ? ORDER BY ei.position
  `).all(exam.id);
  exam.items = await attachUsage(items.map(rowToQuestion));
  exam.total_marks_actual = exam.items.reduce((s, it) => s + (it.marks || 0), 0);
  res.json(exam);
}));

// POST /api/exams/generate
router.post('/exams/generate', asyncHandler(async (req, res) => {
  const { template_id, include_used = false, authored_filter } = req.body || {};
  const tpl = await db.prepare('SELECT * FROM paper_templates WHERE id = ?').get(template_id);
  if (!tpl) return res.status(404).json({ error: 'template not found' });

  let pool = await db.prepare(
    'SELECT * FROM questions WHERE subject = ? AND paper_type = ?'
  ).all(tpl.subject, tpl.paper_type);
  if (authored_filter === 'ai') pool = pool.filter((q) => q.authored_by === 'ai');
  else if (authored_filter === 'real') pool = pool.filter((q) => q.authored_by !== 'ai');
  if (!include_used) {
    const used = new Set(
      (await db.prepare('SELECT DISTINCT question_id FROM question_usage').all()).map((r) => r.question_id)
    );
    pool = pool.filter((q) => !used.has(q.id));
  }
  if (!pool.length) {
    return res.status(400).json({
      error: 'No unused questions available for this paper. Import the question bank or allow re-using used questions.',
      available: 0,
    });
  }

  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }

  const targetMarks = req.body?.override_marks || tpl.total_marks || 60;
  const targetCount = req.body?.override_count || tpl.num_questions || 0;
  const selected = [];
  let sum = 0;
  if (tpl.question_mode === 'count' || targetCount > 0) {
    const n = Math.min(targetCount, pool.length);
    selected.push(...pool.slice(0, n));
    sum = selected.reduce((s, q) => s + (q.marks || 1), 0);
  } else {
    for (const q of pool) {
      if (sum >= targetMarks) break;
      const m = q.marks || 1;
      if (m <= targetMarks - sum) { selected.push(q); sum += m; }
    }
    if (sum < targetMarks) {
      const rest = pool.filter((q) => !selected.includes(q));
      rest.sort((a, b) => (a.marks || 1) - (b.marks || 1));
      for (const q of rest) {
        if (sum >= targetMarks) break;
        selected.push(q);
        sum += q.marks || 1;
      }
    }
  }
  if (!selected.length) return res.status(400).json({ error: 'Could not assemble a paper from the available pool.' });

  const id = `EXAM-${Date.now()}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`;
  const now = new Date().toISOString();
  await db.transaction(async () => {
    await db.prepare(`
      INSERT INTO exam_papers (id, template_id, subject, paper_type, name, created_at, duration_min, total_marks, num_questions, note)
      VALUES (?,?,?,?,?,?,?,?,?,?)
    `).run(id, tpl.id, tpl.subject, tpl.paper_type, tpl.name, now, tpl.duration_min, sum, selected.length,
      `Auto-composed · ${tpl.name}${include_used ? ' · includes previously used questions' : ''}${authored_filter === 'ai' ? ' · AI-generated only' : authored_filter === 'real' ? ' · real past-paper questions only' : ''}`);
    for (const q of selected) {
      await db.prepare(`
        INSERT OR REPLACE INTO exam_paper_items (exam_id, question_id, position, marks) VALUES (?,?,?,?)
      `).run(id, q.id, selected.indexOf(q) + 1, q.marks);
      await db.prepare(`
        INSERT OR REPLACE INTO question_usage (id, question_id, usage_type, ref_id, used_at) VALUES (?,?,?,?,?)
      `).run(`EX:${id}:${q.id}`, q.id, 'exam', id, now);
    }
  });
  const exam = await db.prepare('SELECT * FROM exam_papers WHERE id = ?').get(id);
  const items = await db.prepare(`
    SELECT ei.position, ei.marks, q.* FROM exam_paper_items ei JOIN questions q ON q.id = ei.question_id
    WHERE ei.exam_id = ? ORDER BY ei.position
  `).all(id);
  exam.items = await attachUsage(items.map(rowToQuestion));
  res.status(201).json(exam);
}));

// POST /api/exams/:id/items
router.post('/exams/:id/items', asyncHandler(async (req, res) => {
  const exam = await db.prepare('SELECT * FROM exam_papers WHERE id = ?').get(req.params.id);
  if (!exam) return res.status(404).json({ error: 'exam not found' });
  const { question_id } = req.body || {};
  const q = await db.prepare('SELECT id, marks FROM questions WHERE id = ?').get(question_id);
  if (!q) return res.status(404).json({ error: 'question not found' });
  const maxPos = (await db.prepare('SELECT COALESCE(MAX(position),0) AS m FROM exam_paper_items WHERE exam_id = ?').get(exam.id)).m;
  const now = new Date().toISOString();
  await db.prepare('INSERT OR REPLACE INTO exam_paper_items (exam_id, question_id, position, marks) VALUES (?,?,?,?)')
    .run(exam.id, q.id, maxPos + 1, q.marks);
  await db.prepare('INSERT OR REPLACE INTO question_usage (id, question_id, usage_type, ref_id, used_at) VALUES (?,?,?,?,?)')
    .run(`EX:${exam.id}:${q.id}`, q.id, 'exam', exam.id, now);
  res.json({ ok: true });
}));

// DELETE /api/exams/:id
router.delete('/exams/:id', asyncHandler(async (req, res) => {
  const exam = await db.prepare('SELECT * FROM exam_papers WHERE id = ?').get(req.params.id);
  if (!exam) return res.status(404).json({ error: 'exam not found' });
  await db.transaction(async () => {
    await db.prepare('DELETE FROM exam_paper_items WHERE exam_id = ?').run(exam.id);
    await db.prepare("DELETE FROM question_usage WHERE usage_type = 'exam' AND ref_id = ?").run(exam.id);
    await db.prepare('DELETE FROM exam_papers WHERE id = ?').run(exam.id);
  });
  res.json({ ok: true });
}));

// ============================================================
// F11 题目纠错报告 (question report) endpoints
// ============================================================
const REPORT_REASONS = [
  'wrong-crop', 'merged', 'split', 'missing-part', 'wrong-answer', 'wrong-mapping', 'other'
];

router.post('/reports', asyncHandler(async (req, res) => {
  const { question_id, reason, detail, page_ref } = req.body || {};
  if (!question_id) return res.status(400).json({ error: 'missing question_id' });
  if (!reason || !REPORT_REASONS.includes(reason)) {
    return res.status(400).json({ error: 'invalid reason', allowed: REPORT_REASONS });
  }
  const q = await db.prepare('SELECT id FROM questions WHERE id = ?').get(question_id);
  if (!q) return res.status(404).json({ error: 'question not found' });
  const id = crypto.randomUUID();
  await db.prepare(`
    INSERT INTO reports (id, question_id, reason, detail, page_ref, status, created_at)
    VALUES (?,?,?,?,?, 'open', ?)
  `).run(id, question_id, reason, detail || '', page_ref || '', new Date().toISOString());
  res.status(201).json({ id, ok: true });
}));

router.get('/reports', asyncHandler(async (req, res) => {
  const { status } = req.query;
  const clauses = [];
  const params = [];
  if (status && ['open', 'resolved', 'dismissed'].includes(String(status))) {
    clauses.push('r.status = ?');
    params.push(String(status));
  }
  const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
  const rows = await db.prepare(`
    SELECT r.id, r.question_id, r.reason, r.detail, r.page_ref, r.status, r.created_at, r.resolved_at, r.resolved_note,
           q.subject, q.topic, q.paper_type, q.source, q.source_type, q.question_image, q.answer_image
    FROM reports r
    JOIN questions q ON q.id = r.question_id
    ${where}
    ORDER BY r.created_at DESC
  `).all(...params);
  res.json({ total: rows.length, reports: rows });
}));

router.patch('/reports/:id', asyncHandler(async (req, res) => {
  const id = req.params.id;
  const { status, resolved_note } = req.body || {};
  const r = await db.prepare('SELECT * FROM reports WHERE id = ?').get(id);
  if (!r) return res.status(404).json({ error: 'report not found' });
  const sets = [];
  const params = [];
  if (status && ['open', 'resolved', 'dismissed'].includes(String(status))) {
    sets.push('status = ?');
    params.push(String(status));
    if (status !== 'open') {
      sets.push('resolved_at = ?');
      params.push(new Date().toISOString());
    }
  }
  if (resolved_note !== undefined) {
    sets.push('resolved_note = ?');
    params.push(resolved_note);
  }
  if (!sets.length) return res.status(400).json({ error: 'nothing to update' });
  params.push(id);
  await db.prepare(`UPDATE reports SET ${sets.join(', ')} WHERE id = ?`).run(...params);
  res.json({ ok: true });
}));

// Review workflow: mark a freshly-imported question as reviewed ('done') or reset.
router.post('/questions/:id/review-status', asyncHandler(async (req, res) => {
  const id = req.params.id;
  const { status } = req.body || {};
  if (!['new', 'done'].includes(status)) {
    return res.status(400).json({ error: 'status must be "new" or "done"' });
  }
  const q = await db.prepare('SELECT id FROM questions WHERE id = ?').get(id);
  if (!q) return res.status(404).json({ error: 'question not found' });
  await db.prepare('UPDATE questions SET review_status = ? WHERE id = ?').run(status, id);
  res.json({ ok: true, review_status: status });
}));

// Router-level error handler (catches async rejections forwarded by asyncHandler).
router.use((err, req, res, next) => {
  console.error('[api] unhandled error:', err);
  if (res.headersSent) return next(err);
  res.status(500).json({ error: String((err && err.message) || err) });
});

export default router;
