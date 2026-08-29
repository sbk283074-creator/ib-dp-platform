import db from '../src/db.js';
import fs from 'fs';
import path from 'path';

const SUB = 'Computer Science';
const q = (s, p = []) => db.prepare(s).all(...p);
const row = (s, p = []) => db.prepare(s).get(...p);
const ROOT = path.resolve('../..');
const FIG = path.join(ROOT, 'backend/public/figures');

console.log('=== CS past rows by paper_type (full history) ===');
console.table(q(`SELECT paper_type, COUNT(*) AS n FROM questions WHERE subject='${SUB}' AND category='past' GROUP BY paper_type ORDER BY paper_type`));
console.log('=== CS total past ===', row(`SELECT COUNT(*) AS n FROM questions WHERE subject='${SUB}' AND category='past'`));

console.log('=== Marks / answer / image coverage (all CS past) ===');
console.table(q(`SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN marks IS NULL OR marks=0 THEN 1 ELSE 0 END) AS zero_marks,
  SUM(CASE WHEN answer IS NULL OR TRIM(answer)='' THEN 1 ELSE 0 END) AS empty_answer,
  SUM(CASE WHEN question_image IS NULL OR TRIM(question_image)='' THEN 1 ELSE 0 END) AS no_qimg,
  SUM(CASE WHEN answer_image IS NULL OR TRIM(answer_image)='' THEN 1 ELSE 0 END) AS no_aimg
FROM questions WHERE subject='${SUB}' AND category='past'`));

console.log('=== newly added (review_status=new) breakdown ===');
console.table(q(`SELECT paper_type, COUNT(*) AS n FROM questions WHERE subject='${SUB}' AND category='past' AND review_status='new' GROUP BY paper_type ORDER BY paper_type`));

// distinct figure paths (JS-side split since question_image is a comma string, not JSON)
const imgs = q(`SELECT question_image, answer_image FROM questions WHERE subject='${SUB}' AND category='past'`);
const set = new Set();
for (const r of imgs) {
  for (const col of [r.question_image, r.answer_image]) {
    if (!col) continue;
    for (const v of col.split(',')) { const t = v.trim(); if (t) set.add(t); }
  }
}
let miss = 0;
for (const v of set) if (!fs.existsSync(path.join(FIG, v))) miss++;
console.log(`=== figure files: ${set.size} distinct referenced, ${miss} missing on disk ===`);

// inspect the empty-answer rows
console.log('=== rows with empty answer (both text + image) ===');
const bad = q(`SELECT id, source, paper_type, marks, question_image, answer_image FROM questions WHERE subject='${SUB}' AND category='past' AND (answer IS NULL OR TRIM(answer)='')`);
console.log(`count=${bad.length}`);
for (const b of bad.slice(0, 30)) console.log(`  ${b.id} [${b.source}] marks=${b.marks} qimg=${b.question_image?1:0} aimg=${b.answer_image?1:0}`);
