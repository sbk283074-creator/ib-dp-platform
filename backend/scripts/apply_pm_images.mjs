#!/usr/bin/env node
// Apply PM image map to the database.
// Reads ocr/pm_image_map.json and updates question_image/answer_image columns.

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import Database from 'better-sqlite3';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dbPath = path.join(__dirname, '..', 'data', 'app.db');
const mapPath = path.join(__dirname, '..', 'ocr', 'pm_image_map.json');

if (!existsSync(mapPath)) {
  console.error('Map file not found:', mapPath);
  process.exit(1);
}

const map = JSON.parse(readFileSync(mapPath, 'utf-8'));
console.log(`Map has ${Object.keys(map).length} questions.`);

const db = new Database(dbPath);

// Verify files exist for each entry
let missing = 0;
let ok = 0;
for (const [qid, val] of Object.entries(map)) {
  for (const imgPath of [...(val.q || []), ...(val.a || [])]) {
    const filename = imgPath.replace('/figures/', '');
    const fullPath = path.join(__dirname, '..', 'public', 'figures', filename);
    if (!existsSync(fullPath)) {
      missing++;
    } else {
      ok++;
    }
  }
}
console.log(`File check: ${ok} files exist, ${missing} missing`);

// Prepare update statements
const updateStmt = db.prepare(
  'UPDATE questions SET question_image = ?, answer_image = ? WHERE id = ?'
);

let updated = 0;
let skipped = 0;
const txn = db.transaction(() => {
  for (const [qid, val] of Object.entries(map)) {
    const qImg = (val.q || []).filter(Boolean).join(',');
    const aImg = (val.a || []).filter(Boolean).join(',');

    // Verify question exists
    const exists = db.prepare('SELECT id FROM questions WHERE id = ?').get(qid);
    if (!exists) {
      skipped++;
      continue;
    }

    // Only update if we have at least one image
    if (qImg || aImg) {
      updateStmt.run(qImg || null, aImg || null, qid);
      updated++;
    } else {
      skipped++;
    }
  }
});

txn();
console.log(`Updated ${updated} questions, skipped ${skipped}`);
db.close();
