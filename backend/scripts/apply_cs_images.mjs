// Wire CS image map into the database.
// question_image / answer_image columns added in db.js.
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const db = new Database(path.join(ROOT, 'data', 'app.db'));
const map = JSON.parse(fs.readFileSync(path.join(ROOT, 'ocr', 'cs_image_map.json'), 'utf-8'));

const norm = (t) => t.replace(/O/g, '0');

// DB ids look like CS-18M-2-SL-TZO-4 -> normalized code 18M.2.SL.TZ0.4
function codeFromId(id) {
  const parts = id.split('-').slice(1); // [18M, 2, SL, TZO, 4]
  return norm(parts.join('.'));
}

const rows = db.prepare("SELECT id FROM questions WHERE subject='CS'").all();
const upd = db.prepare("UPDATE questions SET question_image=?, answer_image=? WHERE id=?");
let matched = 0, missing = [];
db.transaction(() => {
  for (const r of rows) {
    const code = codeFromId(r.id);
    const m = map[code];
    if (!m) { missing.push({ id: r.id, code }); continue; }
    upd.run((m.q || []).join(','), (m.a || []).join(','), r.id);
    matched++;
  }
})();

console.log(`[cs-img] updated ${matched}/${rows.length} CS questions`);
if (missing.length) console.log('[cs-img] MISSING:', missing);

// verification: any DB question with image?
const withImg = db.prepare("SELECT count(*) c FROM questions WHERE subject='CS' AND question_image IS NOT NULL AND question_image <> ''").get().c;
const withAns = db.prepare("SELECT count(*) c FROM questions WHERE subject='CS' AND answer_image IS NOT NULL AND answer_image <> ''").get().c;
console.log(`[cs-img] CS rows with question_image: ${withImg}, with answer_image: ${withAns}`);

// verify all image files exist on disk
let missingFiles = [];
for (const r of db.prepare("SELECT id, question_image, answer_image FROM questions WHERE subject='CS'").all()) {
  for (const f of [...(r.question_image || '').split(','), ...(r.answer_image || '').split(',')]) {
    if (!f) continue;
    const p = path.join(__dirname, '..', 'public', f);
    if (!fs.existsSync(p)) missingFiles.push(`${r.id}: ${f}`);
  }
}
if (missingFiles.length) console.log('[cs-img] MISSING FILES:', missingFiles);
else console.log('[cs-img] all files present');