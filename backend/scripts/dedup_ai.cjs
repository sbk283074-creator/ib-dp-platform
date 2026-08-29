// Re-run AI deduplication (excluding import).
const Database = require('better-sqlite3');
const db = new Database('data/app.db');
const norm = (s) => (s || '').replace(/\s+/g, ' ').replace(/\[\s*\d+\s*\]/g, '[N]').trim();
const rows = db.prepare("SELECT id, question FROM questions WHERE authored_by = 'ai' AND book_id IS NULL").all();
const byText = {};
rows.forEach((r) => { const k = norm(r.question); (byText[k] = byText[k] || []).push(r.id); });
const dups = Object.values(byText).filter((v) => v.length > 1);
const delIds = []; let kept = 0;
dups.forEach((v) => { kept++; v.slice(1).forEach((id) => delIds.push(id)); });
console.log('AI 重复组:', dups.length, '| 待删:', delIds.length, '| 保留:', kept);
const ph = delIds.map(() => '?').join(',');
const tx = db.transaction(() => {
  if (delIds.length) {
    db.prepare(`DELETE FROM progress WHERE question_id IN (${ph})`).run(...delIds);
    db.prepare(`DELETE FROM questions WHERE id IN (${ph})`).run(...delIds);
  }
});
tx();
console.log('TOTAL after:', db.prepare('SELECT COUNT(*) c FROM questions').get().c);
console.log('AI 剩余:', db.prepare("SELECT COUNT(*) c FROM questions WHERE authored_by = 'ai'").get().c);
console.log('books:');
db.prepare("SELECT book_id, COUNT(*) c FROM questions WHERE source_type = 'book' GROUP BY book_id").all()
  .forEach((r) => console.log(' ', r.book_id, r.c));
db.close();
