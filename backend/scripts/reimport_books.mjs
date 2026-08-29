// Re-import book JSONs produced by ocr/extract_books.py.
// For each book: upsert the books row, DELETE all existing questions with that
// book_id (so stale ids from the previous extraction disappear), then insert
// the fresh set in one transaction.
//
// Usage: node scripts/reimport_books.mjs <book_json_path> [more.json ...]
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import db from '../src/db.js';
import { validateQuestion, insertQuestion } from '../src/questionRepo.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const files = process.argv.slice(2);
if (!files.length) {
  console.error('Usage: node scripts/reimport_books.mjs <book.json> [...]');
  process.exit(1);
}

for (const file of files) {
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  const book = data.book;
  const questions = data.questions || [];
  if (!book || !book.id) { console.error(`skip ${file}: no book.id`); continue; }

  const before = db.prepare('SELECT COUNT(*) n FROM questions WHERE book_id = ?').get(book.id).n;
  const tx = db.transaction(() => {
    db.prepare(`INSERT OR REPLACE INTO books
      (id, subject, title, publisher, edition, has_answers, answer_source, cover_path, total_questions, created_at)
      VALUES (?,?,?,?,?,?,?,?,?,COALESCE((SELECT created_at FROM books WHERE id = ?), ?))`)
      .run(book.id, book.subject, book.title, book.publisher || null, book.edition || null,
           book.has_answers ? 1 : 0, book.answer_source || null, book.cover_path || null,
           questions.length, book.id, new Date().toISOString());
    db.prepare('DELETE FROM questions WHERE book_id = ?').run(book.id);
    let ok = 0, bad = 0;
    for (const q of questions) {
      const v = validateQuestion(q);
      if (!v.ok) { bad++; if (bad <= 3) console.error(`  SKIP ${q.id}: ${v.error}`); continue; }
      insertQuestion(q, { authored_by: 'import' });
      ok++;
    }
    console.log(`${book.id}: before=${before} deleted=${before} inserted=${ok} skipped=${bad}`);
  });
  tx();
}
db.close();
console.log('done');
