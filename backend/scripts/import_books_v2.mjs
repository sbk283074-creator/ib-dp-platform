// Import every book produced by ocr/extract_v3.py (ocr/book_json2/*.json)
// into the question bank: upsert the `books` row, replace that book's questions,
// then backfill category='book'.
//
// Usage: node scripts/import_books_v2.mjs [--dir <path>] [--dry-run]
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import db from '../src/db.js';
import { validateQuestion, insertQuestion } from '../src/questionRepo.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const dirArg = args.indexOf('--dir');
const DIR = dirArg >= 0 ? args[dirArg + 1] : path.resolve(__dirname, '..', 'ocr', 'book_json2');

if (!fs.existsSync(DIR)) { console.error(`no such dir: ${DIR}`); process.exit(1); }

await db.init();   // open the DB + run migrations before any query

const files = fs.readdirSync(DIR).filter((f) => f.endsWith('.json')).sort();
console.log(`importing ${files.length} book files from ${DIR}${dryRun ? '  (dry run)' : ''}`);

let nBooks = 0, nOk = 0, nBad = 0;

for (const f of files) {
  let data;
  try { data = JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8')); }
  catch (e) { console.error(`  SKIP ${f}: ${e.message}`); continue; }
  const book = data.book;
  const questions = data.questions || [];
  if (!book || !book.id) { console.error(`  SKIP ${f}: no book.id`); continue; }

  // validate first so a dry run is meaningful
  const good = [];
  let bad = 0;
  for (const q of questions) {
    const v = validateQuestion(q);
    if (v.ok) good.push(q); else { bad++; if (bad <= 2) console.error(`    bad ${q.id}: ${v.error}`); }
  }

  if (!dryRun) {
    await db.prepare(`INSERT OR REPLACE INTO books
      (id, subject, title, publisher, edition, has_answers, answer_source, cover_path, total_questions, created_at)
      VALUES (?,?,?,?,?,?,?,?,?,COALESCE((SELECT created_at FROM books WHERE id = ?), ?))`)
      .run(book.id, book.subject, book.title, book.publisher || null, book.edition || null,
           book.has_answers ? 1 : 0, book.answer_source || null, book.cover_path || null,
           good.length, book.id, new Date().toISOString());
    await db.prepare('DELETE FROM questions WHERE book_id = ?').run(book.id);
    for (const q of good) await insertQuestion(q, { authored_by: 'import' });
  }

  nBooks++; nOk += good.length; nBad += bad;
  console.log(`  ${book.id.padEnd(18)} ${String(good.length).padStart(5)} Q  (${bad} skipped)`);
}

if (!dryRun) {
  await db.prepare("UPDATE questions SET category='book' WHERE source_type='book'").run();
}
console.log(`DONE books=${nBooks} questions=${nOk} skipped=${nBad}`);
process.exit(0);
