// CLI bulk importer for the IB DP question bank.
//
// Usage:
//   node src/import.js path/to/questions.json
//   node src/import.js path/to/questions.json --dry-run   (validate only, no writes)
//
// Accepts either a top-level JSON array, or { "questions": [ ... ] }.
// Each question: { subject, topic, question, answer, explanation, [level, subtopic,
//   paper_type, command_term, marks, difficulty, figure, source, tags, id] }
//   - `id` is optional. If provided, re-importing the same file updates that row (upsert).
//   - `tags` is an array of strings.
//
// This runs directly against the database (no server needed), so it is the
// fastest way to load hundreds/thousands of questions from a file.
import fs from 'fs';
import db from './db.js';
import { validateQuestion, insertQuestion } from './questionRepo.js';

const file = process.argv[2];
const dryRun = process.argv.includes('--dry-run');

if (!file) {
  console.error('Usage: node src/import.js <questions.json> [--dry-run]');
  process.exit(1);
}

let raw;
try {
  raw = fs.readFileSync(file, 'utf8');
} catch (e) {
  console.error(`Cannot read file: ${e.message}`);
  process.exit(1);
}

let data;
try {
  data = JSON.parse(raw);
} catch (e) {
  console.error(`Invalid JSON: ${e.message}`);
  process.exit(1);
}

const arr = Array.isArray(data) ? data : data.questions;
if (!Array.isArray(arr)) {
  console.error('JSON must be a top-level array or an object with a "questions" array.');
  process.exit(1);
}

let inserted = 0;
let errors = 0;

if (dryRun) {
  arr.forEach((item, i) => {
    const v = validateQuestion(item);
    if (v.ok) inserted++;
    else { errors++; console.error(`  [${i}] SKIP: ${v.error}${item && item.id ? ' (id=' + item.id + ')' : ''}`); }
  });
  console.log(`[import --dry-run] valid=${inserted}, errors=${errors}`);
  process.exit(errors ? 1 : 0);
}

async function main() {
  await db.init();
  await db.transaction(async () => {
    for (let i = 0; i < arr.length; i++) {
      const item = arr[i];
      const v = validateQuestion(item);
      if (!v.ok) {
        errors++;
        console.error(`  [${i}] SKIP: ${v.error}${item && item.id ? ' (id=' + item.id + ')' : ''}`);
        continue;
      }
      await insertQuestion(item, { authored_by: item.authored_by || 'import' });
      inserted++;
    }
  });
  console.log(`[import] inserted ${inserted}, errors ${errors} (from ${arr.length} entries)`);
}

main().catch((e) => {
  console.error('[import] failed:', e);
  process.exit(1);
});
