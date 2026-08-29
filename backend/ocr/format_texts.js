// One-time text-formatting pass: make sub-questions and answers line-break cleanly.
//  - question: inline subpart markers "(a) " "(i) " start on their own line
//  - answer: marking-point ticks, mark annotations (M1/A1/AG…), alternatives (OR/EITHER),
//    notes (Note:/Award …/Do not allow…) and inline subparts each start on a new line
// Usage: node format_texts.js
import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '..', 'data', 'app.db'));

function formatQuestion(s) {
  if (!s) return s;
  let t = s;
  t = t.replace(/\s+(?=\([a-f]\)\s)/g, '\n');          // (a) (b) …
  t = t.replace(/\s+(?=\([ivx]{1,3}\)\s)/g, '\n');      // (i) (ii) (iii)
  t = t.replace(/[ \t]+\n/g, '\n');
  return t.replace(/\n{3,}/g, '\n\n').trim();
}

function formatAnswer(s) {
  if (!s) return s;
  let t = s;
  t = t.replace(/[✓✔]/g, '\n');                          // marking-point ticks
  t = t.replace(/\s+(?=(?:\(?(?:[MAR]\d+|N\d+)\)?|AG|FT|OWTTE)\b)/g, '\n'); // annotations
  t = t.replace(/\s+(?=(?:EITHER|OR|Note:|METHOD\s+\d+|Hence|Award\s|Do not allow)\b)/g, '\n');
  t = t.replace(/\s+(?=\([a-f]\)\s)/g, '\n');
  t = t.replace(/\s+(?=\([ivx]{1,3}\)\s)/g, '\n');
  t = t.replace(/[ \t]+\n/g, '\n');
  return t.replace(/\n{3,}/g, '\n\n').trim();
}

const rows = db.prepare('SELECT id, question, answer FROM questions').all();
console.log(`[fmt] ${rows.length} questions`);
const upd = db.prepare('UPDATE questions SET question = ?, answer = ? WHERE id = ?');
const tx = db.transaction(() => {
  let changed = 0;
  for (const r of rows) {
    const q = formatQuestion(r.question);
    const a = formatAnswer(r.answer);
    if (q !== r.question || a !== r.answer) {
      upd.run(q, a, r.id);
      changed++;
    }
  }
  return changed;
});
const changed = tx();
console.log(`[fmt] changed ${changed} rows`);
// sample
const s = db.prepare("SELECT answer FROM questions WHERE id = 'MATH-RAW-2024-05-TZ1-Paper1-Q1a'").get();
console.log('[fmt] sample answer:\n' + s.answer.slice(0, 300));
