import Database from "better-sqlite3";
import fs from "fs";

const ROOT = process.cwd();
const DB = process.env.PT_DB || `${ROOT}/data/app.db`;
const SIDECAR = process.env.PT_SIDECAR || "/tmp/math_aa_qb_images.json";

const db = new Database(DB);
db.pragma("journal_mode = WAL");
const sidecar = JSON.parse(fs.readFileSync(SIDECAR, "utf-8"));

const upd = db.prepare(
  "UPDATE questions SET question_image=?, answer_image=? WHERE source=? AND category='questionbank'"
);

let n = 0;
const tx = db.transaction(() => {
  for (const [code, paths] of Object.entries(sidecar)) {
    const r = upd.run(paths.question_image || null, paths.answer_image || null, code);
    if (r.changes) n++;
  }
});
tx();
const withImg = db
  .prepare("SELECT COUNT(*) c FROM questions WHERE category='questionbank' AND question_image IS NOT NULL")
  .get().c;
console.log(`patched ${n} rows; questionbank rows with image: ${withImg}`);
db.close();
