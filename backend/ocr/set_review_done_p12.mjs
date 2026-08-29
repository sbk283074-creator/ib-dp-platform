// One-off: move Math AA HL Paper 1 & 2 rows from review_status='new' to 'done'
// ("finished checking"). Does NOT touch the `successful` tag. Idempotent.
// Run AFTER stopping the backend (avoids WAL lock contention).
import db from '../src/db.js';

const before = db.prepare(
  "SELECT COUNT(*) AS c FROM questions WHERE (source LIKE 'AA HL P1%' OR source LIKE 'AA HL P2%') AND review_status='new'"
).get().c;
const total = db.prepare(
  "SELECT COUNT(*) AS c FROM questions WHERE source LIKE 'AA HL P1%' OR source LIKE 'AA HL P2%'"
).get().c;

db.prepare(
  "UPDATE questions SET review_status='done' WHERE (source LIKE 'AA HL P1%' OR source LIKE 'AA HL P2%') AND review_status='new'"
).run();

const afterNew = db.prepare(
  "SELECT COUNT(*) AS c FROM questions WHERE (source LIKE 'AA HL P1%' OR source LIKE 'AA HL P2%') AND review_status='new'"
).get().c;
const afterDone = db.prepare(
  "SELECT COUNT(*) AS c FROM questions WHERE (source LIKE 'AA HL P1%' OR source LIKE 'AA HL P2%') AND review_status='done'"
).get().c;
const stillSuccessful = db.prepare(
  "SELECT COUNT(*) AS c FROM questions WHERE (source LIKE 'AA HL P1%' OR source LIKE 'AA HL P2%') AND tags LIKE '%successful%'"
).get().c;

console.log(`P1+P2 rows total: ${total}`);
console.log(`was 'new': ${before}  -> now 'new': ${afterNew}, now 'done': ${afterDone}`);
console.log(`still carrying 'successful' tag: ${stillSuccessful} (untouched)`);
