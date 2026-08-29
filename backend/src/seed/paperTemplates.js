// Paper templates mirroring real IB HL exam formats.
// Used by the exam-generation feature (F10).
// Idempotent: INSERT OR REPLACE by id.
import db from '../db.js';

export const PAPER_TEMPLATES = [
  // ---------------- Physics HL ----------------
  {
    id: 'PHY-P1', subject: 'Physics', paper_type: 'Paper 1',
    name: 'Physics HL Paper 1 — multiple choice',
    duration_min: 60, total_marks: 40, calculator: 0, num_questions: 40,
    question_mode: 'count',
    description: '40 multiple-choice questions. No calculator required (data booklet allowed).',
    sort_order: 1,
  },
  {
    id: 'PHY-P2', subject: 'Physics', paper_type: 'Paper 2',
    name: 'Physics HL Paper 2 — short/extended response',
    duration_min: 135, total_marks: 90, calculator: 1, num_questions: 0,
    question_mode: 'marks',
    description: 'Short and extended response questions (~90 marks, 2h15). Calculator required.',
    sort_order: 2,
  },
  {
    id: 'PHY-P3', subject: 'Physics', paper_type: 'Paper 3',
    name: 'Physics HL Paper 3 — data analysis + option',
    duration_min: 75, total_marks: 45, calculator: 1, num_questions: 0,
    question_mode: 'marks',
    description: 'Section A data-based questions + Section B option questions (~45 marks, 1h15).',
    sort_order: 3,
  },

  // ---------------- Math AA HL ----------------
  {
    id: 'MATH-P1', subject: 'Math AA HL', paper_type: 'Paper 1',
    name: 'Math AA HL Paper 1 — no calculator',
    duration_min: 120, total_marks: 110, calculator: 0, num_questions: 0,
    question_mode: 'marks',
    description: 'Section A + Section B, ~110 marks, 2h. Calculator not permitted.',
    sort_order: 4,
  },
  {
    id: 'MATH-P2', subject: 'Math AA HL', paper_type: 'Paper 2',
    name: 'Math AA HL Paper 2 — calculator',
    duration_min: 120, total_marks: 110, calculator: 1, num_questions: 0,
    question_mode: 'marks',
    description: 'Section A + Section B, ~110 marks, 2h. GDC required.',
    sort_order: 5,
  },
  {
    id: 'MATH-P3', subject: 'Math AA HL', paper_type: 'Paper 3',
    name: 'Math AA HL Paper 3 — problem solving',
    duration_min: 60, total_marks: 55, calculator: 1, num_questions: 0,
    question_mode: 'marks',
    description: 'Problem-solving paper, ~55 marks, 1h. GDC required.',
    sort_order: 6,
  },

  // ---------------- CS HL ----------------
  {
    id: 'CS-P1', subject: 'CS', paper_type: 'Paper 1',
    name: 'CS HL Paper 1 — core concepts + problem solving',
    duration_min: 130, total_marks: 110, calculator: 0, num_questions: 0,
    question_mode: 'marks',
    description: 'Section A + Section B, ~110 marks, 2h10. No calculator.',
    sort_order: 7,
  },
  {
    id: 'CS-P2', subject: 'CS', paper_type: 'Paper 2',
    name: 'CS HL Paper 2 — option (Java)',
    duration_min: 105, total_marks: 65, calculator: 0, num_questions: 0,
    question_mode: 'marks',
    description: 'Option paper (Java), ~65 marks, 1h45.',
    sort_order: 8,
  },
  {
    id: 'CS-P3', subject: 'CS', paper_type: 'Paper 3',
    name: 'CS HL Paper 3 — case study',
    duration_min: 75, total_marks: 30, calculator: 0, num_questions: 0,
    question_mode: 'marks',
    description: 'Case-study paper, ~30 marks, 1h15.',
    sort_order: 9,
  },
];

export async function seedPaperTemplates() {
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO paper_templates
      (id, subject, paper_type, name, duration_min, total_marks, calculator,
       num_questions, question_mode, description, sort_order)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)
  `);
  await db.transaction(async () => {
    for (const t of PAPER_TEMPLATES) {
      await stmt.run(t.id, t.subject, t.paper_type, t.name, t.duration_min, t.total_marks,
        t.calculator, t.num_questions, t.question_mode, t.description, t.sort_order);
    }
  });
  return PAPER_TEMPLATES.length;
}
