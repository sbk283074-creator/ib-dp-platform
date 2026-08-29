export interface Question {
  id: string;
  subject: string;
  level: string | null;
  topic: string | null;
  subtopic: string | null;
  paper_type: string | null;
  command_term: string | null;
  marks: number | null;
  difficulty: number | null;
  definition_basis?: string | null;
  question: string;
  figure: string | null;
  answer: string;
  answer_figure: string | null;
  explanation: string;
  source: string | null;
  tags: string[];
  authored_by: string;
  created_at: string;
  knowledge_point_ids: string[];
  question_image: string | null;
  answer_image: string | null;
  figure_image: string | null;
  // F10: usage records (exam / wrong_book)
  usage?: QuestionUsage[];
  // F-progress: mastery + completion date (joined from progress table when present)
  mastery_level?: number | null;
  completed_at?: string | null;
  status?: string | null;
  // Book source
  book_id?: string | null;
  book_section?: string | null;
  book_page?: number | null;
  in_book_order?: number | null;
  source_type?: 'paper' | 'book' | null;
  // Category: book / past / topic / ai (ai is hidden from the UI filter).
  category?: string | null;
  // Review workflow: null = legacy, 'new' = awaiting review, 'done' = reviewed.
  review_status?: string | null;
}

// F10: a usage record — a trace left when a question was used in a paper or added to the wrong book.
export interface QuestionUsage {
  question_id: string;
  usage_type: 'exam' | 'wrong_book' | string;
  ref_id: string | null;
  used_at: string;
}

// F10: paper templates mirroring real IB formats (per subject / paper).
export interface PaperTemplate {
  id: string;
  subject: string;
  paper_type: string;
  name: string;
  duration_min: number | null;
  total_marks: number | null;
  calculator: number;
  num_questions: number;
  question_mode: 'marks' | 'count';
  description: string;
  sort_order: number;
}

// F10: a generated mock exam paper.
export interface ExamPaper {
  id: string;
  template_id: string | null;
  subject: string;
  paper_type: string;
  name: string;
  created_at: string;
  duration_min: number | null;
  total_marks: number | null;
  num_questions: number;
  note: string;
  item_count?: number;      // list view
  items?: Question[];       // detail view
  total_marks_actual?: number;
}

export interface Facets {
  subjects: string[];
  topics: string[];
  paper_types: string[];
  command_terms: string[];
}

export interface ProgressRow {
  question_id: string;
  status: string;
  attempts: number;
  correct_count: number;
  wrong_count: number;
  last_result: string | null;
  last_seen: string;
  mastery_level: number;
  completed_at: string | null;
}

// F6: progress aggregates
export interface ProgressByTopic {
  topic: string;
  attempted: number;
  correct: number;
  wrong: number;
  accuracy: number;
}
export interface ProgressByKp {
  kp: string;
  attempted: number;
  correct: number;
  wrong: number;
  accuracy: number;
}

// F2/F3: knowledge point
export interface Reference {
  type: 'textbook' | 'formula' | 'guide' | string;
  label: string;
  chapter?: number | string;
  pages?: string;
  note?: string;
}
export interface KnowledgePoint {
  id: string;
  subject: string;
  code: string | null;
  theme: string | null;
  title: string;
  description: string | null;
  references: Reference[];
}
export interface KnowledgePointDetail {
  kp: KnowledgePoint;
  questions: Question[];
}

// F1: favorites are just Question[]
// F5: collections
export interface CollectionSummary {
  id: string;
  name: string;
  item_count: number;
}
export interface CollectionDetail {
  collection: { id: string; name: string };
  items: Question[];
}

// 错题本 (wrong-question notebook).
export interface WrongQuestion extends Question {
  times_wrong: number;
  added_at: string;
  last_wrong_at: string;
  mastered: number; // 0 = still learning, 1 = mastered
  note: string;
  srs_level: number;
  next_review_at: string | null;
}

export interface AttemptPayload {
  question_id: string;
  result: 'correct' | 'incorrect';
}

// F11: question report (纠错报告) — a user flagging a specific question.
export interface Report {
  id: string;
  question_id: string;
  reason: string;
  detail: string;
  page_ref: string;
  status: 'open' | 'resolved' | 'dismissed';
  created_at: string;
  resolved_at: string | null;
  resolved_note: string;
  // joined question fields (so the admin page can show the reported question)
  subject?: string | null;
  topic?: string | null;
  paper_type?: string | null;
  source?: string | null;
  source_type?: string | null;
  question_image?: string | null;
  answer_image?: string | null;
}

export const REPORT_REASONS: { code: string; label: string }[] = [
  { code: 'wrong-crop', label: 'Wrong crop' },
  { code: 'merged', label: 'Two questions merged' },
  { code: 'split', label: 'One question split' },
  { code: 'missing-part', label: 'Missing subpart/figure' },
  { code: 'wrong-answer', label: 'Wrong answer image' },
  { code: 'wrong-mapping', label: 'Wrong question linked' },
  { code: 'other', label: 'Other' }
];
