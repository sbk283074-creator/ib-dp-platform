import db from './src/db.js';
const rows = (s) => db.prepare(s).all();
console.log('category counts', JSON.stringify(rows("SELECT category, COUNT(*) c FROM questions GROUP BY category")));
console.log('review_status counts', JSON.stringify(rows("SELECT COALESCE(review_status,'NULL') rs, COUNT(*) c FROM questions GROUP BY review_status")));
// sanity: a freshly-inserted question should default category+review_status
import { insertQuestion } from './src/questionRepo.js';
const id = 'verify_' + Date.now();
insertQuestion({ id, subject:'CS', topic:'Test', question:'q', answer:'a', explanation:'e', source_type:'paper', source:'IB 真题 2020 May CS HL P2' }, { id, authored_by:'test' });
const r = db.prepare('SELECT id,category,review_status FROM questions WHERE id=?').get(id);
console.log('inserted sample', JSON.stringify(r));
db.prepare('DELETE FROM questions WHERE id=?').run(id);
console.log('OK');
