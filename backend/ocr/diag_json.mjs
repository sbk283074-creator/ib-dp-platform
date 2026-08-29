import db from '../src/db.js';

function check(col) {
  const rows = db.prepare(`SELECT id, ${col} FROM questions WHERE subject='Computer Science' AND category='past' LIMIT 20`).all();
  let throws = 0;
  const samples = [];
  for (const r of rows) {
    const raw = r[col];
    try { JSON.parse(raw); }
    catch (e) { throws++; if (samples.length < 3) samples.push({ id: r.id, raw, err: e.message }); }
  }
  console.log(`COLUMN ${col}: rows=${rows.length} throws=${throws}`);
  for (const s of samples) console.log('   ', s.id, 'raw=', JSON.stringify(s.raw), 'err=', s.err);
}

check('tags');
check('knowledge_point_ids');

// Also: does the DEFAULT landing query (what SearchPage sends) throw inside rowToQuestion?
import { rowToQuestion } from '../src/questionRepo.js';
const all = db.prepare(`SELECT * FROM questions WHERE id NOT IN (SELECT question_id FROM progress WHERE status='completed') ORDER BY created_at DESC LIMIT 50`).all();
let rtThrows = 0, firstErr = null;
for (const row of all) {
  try { rowToQuestion(row); } catch (e) { rtThrows++; if (!firstErr) firstErr = { id: row.id, err: e.message }; }
}
console.log(`DEFAULT landing query: rows=${all.length} rowToQuestion throws=${rtThrows}`);
if (firstErr) console.log('   first throw:', firstErr.id, firstErr.err);
