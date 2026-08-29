// Cleanup pass: strip [N/A] / bare subpart-marker noise that leaked into QUESTION text
// from classified prompt-repeat parsing (examiners-report tails mis-split as question heads).
// Also collapses explanation fields that consist only of [N/A] markers.
// Usage: node clean_na.js
import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '..', 'data', 'app.db'));

const BARE_MARKER = /^[a-z]{1,4}(?:\.{1,2}[ivxlc]{1,4}){0,4}\.?\s*$/;   // "a." "b.i." "bc..i." "c.ii."

function cleanQuestion(s) {
  if (!s) return s;
  const lines = s.split('\n').filter((ln) => {
    const t = ln.trim();
    if (t === '[N/A]') return false;
    if (BARE_MARKER.test(t)) return false;
    return true;
  });
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

function cleanExplanation(s) {
  if (!s || !s.includes('[N/A]')) return s;
  const lines = s.split('\n').filter((ln) => {
    const t = ln.trim();
    if (t === '[N/A]') return false;
    if (BARE_MARKER.test(t)) return false;
    return true;
  });
  const out = lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
  if (!out) return '(No examiner report available.)';
  return out;
}

const rows = db.prepare('SELECT id, question, explanation FROM questions').all();
console.log(`[clean] ${rows.length} rows to inspect`);
const upd = db.prepare('UPDATE questions SET question = ?, explanation = ? WHERE id = ?');
const tx = db.transaction(() => {
  let n = 0;
  for (const r of rows) {
    const q = cleanQuestion(r.question);
    const e = cleanExplanation(r.explanation);
    if (q !== r.question || e !== r.explanation) {
      upd.run(q, e, r.id);
      n++;
    }
  }
  return n;
});
const changed = tx();
console.log(`[clean] changed ${changed} rows`);

const left = db.prepare("SELECT COUNT(*) c FROM questions WHERE question LIKE '%[N/A]%'").get().c;
const leftA = db.prepare("SELECT COUNT(*) c FROM questions WHERE answer LIKE '%[N/A]%'").get().c;
console.log(`[clean] questions still with [N/A]: ${left} | answers: ${leftA}`);
const s = db.prepare("SELECT question FROM questions WHERE id = 'MATH-CLS-Topic1-P1-007'").get();
console.log('[clean] sample after:\n' + s.question.slice(0, 160));
