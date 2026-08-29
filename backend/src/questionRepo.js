// Shared question validation + insert logic.
// Used by src/api.js (single + bulk endpoints) and src/import.js (CLI bulk importer)
// so that the rules stay identical no matter how questions enter the database.
import crypto from 'crypto';
import db from './db.js';

export const COLUMNS = [
  'id', 'subject', 'level', 'topic', 'subtopic', 'paper_type', 'command_term',
  'marks', 'difficulty', 'question', 'figure', 'answer', 'explanation',
  'source', 'tags', 'authored_by', 'created_at', 'knowledge_point_ids',
  'answer_figure', 'question_image', 'answer_image', 'figure_image', 'definition_basis',
  'book_id', 'book_section', 'book_page', 'in_book_order', 'source_type',
  'category', 'review_status'
];

export function rowToQuestion(row) {
  if (!row) return null;
  return {
    ...row,
    tags: row.tags ? JSON.parse(row.tags) : [],
    knowledge_point_ids: row.knowledge_point_ids ? JSON.parse(row.knowledge_point_ids) : []
  };
}

// A question needs these five fields to be usable in search / practice / export.
const REQUIRED = ['subject', 'topic', 'question', 'answer', 'explanation'];

/**
 * Validate one incoming question object.
 * @returns {{ok:boolean, error?:string}}
 */
export function validateQuestion(b) {
  if (!b || typeof b !== 'object') return { ok: false, error: 'not an object' };
  for (const k of REQUIRED) {
    if (b[k] === undefined || b[k] === null || String(b[k]).trim() === '') {
      return { ok: false, error: `missing ${k}` };
    }
  }
  if (b.marks != null && Number.isNaN(Number(b.marks))) return { ok: false, error: 'marks must be a number' };
  if (b.difficulty != null && Number.isNaN(Number(b.difficulty))) return { ok: false, error: 'difficulty must be a number' };
  if (b.tags != null && !Array.isArray(b.tags)) return { ok: false, error: 'tags must be an array' };
  if (b.knowledge_point_ids != null && !Array.isArray(b.knowledge_point_ids)) {
    return { ok: false, error: 'knowledge_point_ids must be an array' };
  }
  return { ok: true };
}

/**
 * Insert (or upsert) a single question.
 * @param b        raw question object
 * @param opts.id          explicit id (makes it an upsert via INSERT OR REPLACE)
 * @param opts.authored_by defaults to 'import'
 * @param opts.overwrite   if true and no id given, still treat as replace (rarely used)
 * @returns {Promise<string>} the id used
 */
export async function insertQuestion(b, opts = {}) {
  const id = opts.id || b.id || crypto.randomUUID();
  const authored_by = opts.authored_by || b.authored_by || 'import';
  const useReplace = Boolean(id) && (opts.overwrite ?? true); // id present => upsert

  const category =
    b.category ??
    (b.source_type === 'book'
      ? 'book'
      : authored_by === 'ai'
        ? 'ai'
        : typeof b.source === 'string' && b.source.includes('classified')
          ? 'topic'
          : 'past');
  const review_status = b.review_status ?? 'new';

  const created_at = b.created_at || new Date().toISOString();

  const sql = `
    ${useReplace ? 'INSERT OR REPLACE' : 'INSERT'} INTO questions
      (id, subject, level, topic, subtopic, paper_type, command_term,
       marks, difficulty, question, figure, answer, explanation, source, tags,
       authored_by, created_at, knowledge_point_ids, definition_basis,
       answer_figure, question_image, answer_image, figure_image,
       book_id, book_section, book_page, in_book_order, source_type,
       category, review_status)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
  `;
  await db.prepare(sql).run(
    id,
    b.subject,
    b.level ?? null,
    b.topic,
    b.subtopic ?? null,
    b.paper_type ?? null,
    b.command_term ?? null,
    b.marks ?? null,
    b.difficulty ?? null,
    b.question,
    b.figure ?? null,
    b.answer,
    b.explanation,
    b.source ?? null,
    JSON.stringify(b.tags || []),
    authored_by,
    created_at,
    JSON.stringify(b.knowledge_point_ids || []),
    b.definition_basis ?? null,
    b.answer_figure ?? null,
    b.question_image ?? null,
    b.answer_image ?? null,
    b.figure_image ?? null,
    b.book_id ?? null,
    b.book_section ?? null,
    b.book_page ?? null,
    b.in_book_order ?? 0,
    b.source_type ?? 'paper',
    category,
    review_status
  );
  return id;
}
