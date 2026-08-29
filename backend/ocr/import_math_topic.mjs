// Import math topic question manifest into the questions table.
// Idempotent: DELETE existing rows by source, then INSERT new rows.
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import Database from 'better-sqlite3';

const __dirname = dirname(fileURLToPath(import.meta.url));
const MANIFEST = resolve(__dirname, '../data/math_topic_manifest.json');
const DB = resolve(__dirname, '../data/app.db');

const manifest = JSON.parse(readFileSync(MANIFEST, 'utf-8'));
console.log(`manifest records: ${manifest.length}`);

const db = new Database(DB);
const insertQuestion = db.prepare(`
  INSERT INTO questions (
    id, source, subject, level, category, topic, subtopic, paper_type,
    command_term, marks, difficulty, question, figure, answer, explanation,
    source_type, question_image, answer_image, figure_image,
    review_status, authored_by, created_at
  ) VALUES (
    @id, @source, @subject, @level, @category, @topic, @subtopic, @paper_type,
    @command_term, @marks, @difficulty, @question, @figure, @answer, @explanation,
    @source_type, @question_image, @answer_image, @figure_image,
    @review_status, @authored_by, @created_at
  )
`);
const deleteBySource = db.prepare('DELETE FROM questions WHERE source = ?');

let inserted = 0, deleted = 0, newStatus = 0;
const now = new Date().toISOString();
const tx = db.transaction(() => {
  for (const r of manifest) {
    const del = deleteBySource.run(r.source);
    deleted += del.changes;
    insertQuestion.run({
      id: r.id,
      source: r.source,
      subject: r.subject,
      level: r.level,
      category: r.category,
      topic: r.topic,
      subtopic: r.subtopic ?? null,
      paper_type: r.paper_type,
      command_term: r.command_term ?? null,
      marks: r.marks ?? null,
      difficulty: r.difficulty ?? null,
      question: r.question_text ?? '',
      figure: null,
      answer: r.answer_text ?? '',
      explanation: null,
      source_type: 'topic',
      question_image: r.question_image ?? '',
      answer_image: r.answer_image ?? '',
      figure_image: null,
      review_status: r.review_status ?? 'new',
      authored_by: 'extract_math_topic.py',
      created_at: now,
    });
    inserted++;
    if ((r.review_status ?? 'new') === 'new') newStatus++;
  }
});
try {
  tx();
} catch (e) {
  console.error('transaction failed:', e.message);
  process.exit(1);
}
console.log(`inserted: ${inserted} | deleted (by source): ${deleted} | new: ${newStatus}`);
db.close();