// Node importer for Math AA questions.pdf scan.
// Reads the manifest JSON produced by extract_math_aa_qb.py and inserts rows into
// the questions table under category='questionbank'. Idempotent: skips rows whose
// stable id already exists, and de-duplicates against existing Math past rows by
// parsed question identity (year/month/tz/paper/level/qnum).
import Database from "better-sqlite3";
import fs from "fs";

const ROOT = process.cwd();
const DB = process.env.PT_DB || `${ROOT}/data/app.db`;
const MANIFEST = process.env.PT_MANIFEST || "/tmp/math_aa_qb_dryrun.json";

const db = new Database(DB);
db.pragma("journal_mode = WAL");

// ---- build existing Math past identity set (for dedup) ----
const existing = db
  .prepare("SELECT id FROM questions WHERE category='past' AND subject LIKE '%Math%'")
  .all();
const existIdSet = new Set(existing.map((r) => r.id));
const skipIdent = new Set();
const idRe = /MATH_(AASL|AAHL)_P(\d)_(\d{4})(May|Nov)_TZ(\d)_q(\d+)/;
for (const { id } of existing) {
  const m = idRe.exec(id);
  if (m) {
    const lvl = m[1] === "AASL" ? "SL" : "HL";
    skipIdent.add(`${m[3]}|${m[4]}|${m[5]}|Paper ${m[2]}|${lvl}|${m[6]}`);
  }
}

function identity(rec) {
  if (!rec.year) return null;
  const lvl = rec.level === "SL" ? "SL" : "HL";
  return `${rec.year}|${rec.month}|${rec.tz}|${rec.paper_type}|${lvl}|${rec.marks != null ? "" : ""}${rec.code}`;
}

// Build identity from the IB code (more reliable than marks).
function codeIdentity(code) {
  // e.g. 21M.1.AHL.TZ1.11  or  20N.2.AHL.TZ0.H_3
  const m = /^(\d{2})([MN])\.(\d)\.(SL|AHL|HL)\.TZ(\d)\.([A-Za-z0-9_]+)$/.exec(code);
  if (!m) return null;
  const year = 2000 + parseInt(m[1], 10);
  const month = m[2] === "M" ? "May" : "Nov";
  const paper = `Paper ${parseInt(m[3], 10)}`;
  const lvl = m[4] === "SL" ? "SL" : "HL";
  const tz = parseInt(m[5], 10);
  const qnum = (m[6].match(/\d+/) || ["0"])[0];
  return `${year}|${month}|${tz}|${paper}|${lvl}|${qnum}`;
}

const manifest = JSON.parse(fs.readFileSync(MANIFEST, "utf-8"));
const records = manifest.records;

const insert = db.prepare(
  `INSERT INTO questions
   (id, subject, level, topic, subtopic, paper_type, marks, question, answer,
    source, category, review_status, tags, question_image, answer_image)
   VALUES (@id,@subject,@level,@topic,@subtopic,@paper_type,@marks,@question,@answer,
           @source,@category,@review_status,@tags,@question_image,@answer_image)`
);

let inserted = 0;
let skippedDup = 0;
let skippedEmpty = 0;
let skippedExist = 0;

const tx = db.transaction(() => {
  for (const r of records) {
    if (!r.question || !r.question.trim()) {
      skippedEmpty++;
      continue;
    }
    if (existIdSet.has(r.id)) {
      skippedExist++;
      continue;
    }
    const ident = codeIdentity(r.code);
    if (ident && skipIdent.has(ident)) {
      skippedDup++;
      continue;
    }
    insert.run({
      id: r.id,
      subject: r.subject,
      level: r.level,
      topic: r.topic,
      subtopic: r.subtopic,
      paper_type: r.paper_type,
      marks: r.marks,
      question: r.question,
      answer: r.answer || "",
      source: r.source,
      category: "questionbank",
      review_status: "new",
      tags: JSON.stringify(["questionbank"]),
      question_image: null,
      answer_image: null,
    });
    inserted++;
  }
});
tx();

const total = db.prepare("SELECT COUNT(*) c FROM questions WHERE category='questionbank'").get().c;
console.log(
  `inserted=${inserted} skippedDup=${skippedDup} skippedEmpty=${skippedEmpty} skippedExist=${skippedExist} total_questionbank=${total}`
);
db.close();
