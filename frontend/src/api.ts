import type {
  AttemptPayload, CollectionDetail, CollectionSummary, ExamPaper, Facets, KnowledgePoint, KnowledgePointDetail,
  PaperTemplate, ProgressByKp, ProgressByTopic, ProgressRow, Question, WrongQuestion, Report
} from './types';

// On Netlify the app is served from the same origin, so /api and /figures are
// relative. On GitHub Pages (static frontend only) we point at the live Netlify
// backend via build-time env vars (VITE_API_BASE_URL / VITE_FIGURES_BASE_URL).
async function getJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const API_HOST = (import.meta as any).env?.VITE_API_BASE_URL || '';
  const r = await fetch(API_HOST + url, init);
  if (!r.ok) throw new Error(`request failed: ${r.status}`);
  return r.json() as Promise<T>;
}

export interface QuestionQuery {
  q?: string;
  subject?: string;
  topic?: string;
  paper_type?: string;
  command_term?: string;
  difficulty?: number | '';
  marks?: number | '';
  tag?: string;
  knowledge_point?: string;
  category?: 'all' | 'book' | 'past' | 'topic' | 'ai' | 'questionbank';
  review_status?: 'new' | 'done' | null;
  sort?: string;
  limit?: number;
  offset?: number;
  exclude_completed?: boolean;
}

export function getQuestions(params: QuestionQuery): Promise<{ total: number; items: Question[]; limit: number; offset: number }> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return;
    // 'all' is a UI-only sentinel: don't send it to the backend as a literal
    // category value (there is no category literally named "all").
    if (k === 'category' && v === 'all') return;
    qs.set(k, String(v));
  });
  return getJSON(`/api/questions?${qs.toString()}`);
}

export function getQuestion(id: string): Promise<Question> {
  return getJSON(`/api/questions/${id}`);
}

export function getFacets(): Promise<Facets> {
  return getJSON('/api/facets');
}

export function getProgress(): Promise<ProgressRow[]> {
  return getJSON('/api/progress');
}

// F6 aggregates
export function getProgressByTopic(): Promise<ProgressByTopic[]> {
  return getJSON('/api/progress/by-topic');
}
export function getProgressByKp(): Promise<ProgressByKp[]> {
  return getJSON('/api/progress/by-kp');
}

export function saveProgress(p: { question_id: string; status: string; attempts?: number }): Promise<void> {
  return getJSON('/api/progress', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(p)
  });
}

// Record one practice attempt (drives progress + wrong notebook + SRS on the server).
export function recordAttempt(p: AttemptPayload): Promise<void> {
  return getJSON('/api/attempt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(p)
  });
}

// Batch import many questions at once (idempotent by id).
export function importQuestions(questions: Partial<Question>[]): Promise<{ inserted: number; total: number; errors: any[] }> {
  return getJSON('/api/questions/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ questions })
  });
}

// ---------------------------------------------------------------------------
// F2 / F3  Knowledge points
// ---------------------------------------------------------------------------
export function getKnowledgePoints(subject?: string): Promise<KnowledgePoint[]> {
  return getJSON(`/api/knowledge-points${subject ? `?subject=${encodeURIComponent(subject)}` : ''}`);
}
export function getKnowledgePoint(id: string): Promise<KnowledgePointDetail> {
  return getJSON(`/api/knowledge-points/${id}`);
}

// ---------------------------------------------------------------------------
// F1  Favorites
// ---------------------------------------------------------------------------
export function getFavorites(): Promise<Question[]> {
  return getJSON('/api/favorites');
}
export function toggleFavorite(question_id: string): Promise<{ favorited: boolean }> {
  return getJSON('/api/favorites', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id })
  });
}
export function removeFavorite(question_id: string): Promise<void> {
  return getJSON(`/api/favorites/${question_id}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// F5  Collections
// ---------------------------------------------------------------------------
export function getCollections(): Promise<CollectionSummary[]> {
  return getJSON('/api/collections');
}
export function createCollection(name: string): Promise<{ id: string; name: string }> {
  return getJSON('/api/collections', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
}
export function getCollection(id: string): Promise<CollectionDetail> {
  return getJSON(`/api/collections/${id}`);
}
export function deleteCollection(id: string): Promise<void> {
  return getJSON(`/api/collections/${id}`, { method: 'DELETE' });
}
export function addToCollection(collection_id: string, question_id: string): Promise<void> {
  return getJSON(`/api/collections/${collection_id}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id })
  });
}
export function removeFromCollection(collection_id: string, question_id: string): Promise<void> {
  return getJSON(`/api/collections/${collection_id}/items/${question_id}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// F8  Question-level notes
// ---------------------------------------------------------------------------
export function getQuestionNote(question_id: string): Promise<{ note: string }> {
  return getJSON(`/api/question-notes/${question_id}`);
}
export function saveQuestionNote(question_id: string, note: string): Promise<void> {
  return getJSON(`/api/question-notes/${question_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note })
  });
}

// ---------------------------------------------------------------------------
// Wrong-question notebook
// ---------------------------------------------------------------------------
export function getWrongQuestions(opts: { includeMastered?: boolean; dueOnly?: boolean } = {}): Promise<WrongQuestion[]> {
  const params = new URLSearchParams();
  if (opts.includeMastered) params.set('all', '1');
  if (opts.dueOnly) params.set('due', '1');
  const qs = params.toString();
  return getJSON(`/api/wrong-questions${qs ? `?${qs}` : ''}`);
}

export function addToNotebook(question_id: string, note = ''): Promise<void> {
  return getJSON(`/api/wrong-questions/${question_id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note })
  });
}

export function updateNotebook(question_id: string, patch: { mastered?: boolean; note?: string; next_review_at?: string }): Promise<void> {
  return getJSON(`/api/wrong-questions/${question_id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch)
  });
}

export function removeFromNotebook(question_id: string): Promise<void> {
  return getJSON(`/api/wrong-questions/${question_id}`, { method: 'DELETE' });
}

export function addQuestion(q: Partial<Question> & Pick<Question, 'subject' | 'topic' | 'question' | 'answer' | 'explanation'>): Promise<{ id: string }> {
  return getJSON('/api/questions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(q)
  });
}

export function exportHtml(ids: string[]): Promise<{ html: string }> {
  return getJSON('/api/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids })
  });
}

// ---------------------------------------------------------------------------
// Books (textbooks / workbooks)
// ---------------------------------------------------------------------------
export interface Book {
  id: string;
  subject: string;
  title: string;
  publisher: string | null;
  edition: string | null;
  has_answers: number;
  answer_source: string | null;
  cover_path: string | null;
  total_questions: number;
  created_at: string | null;
}

export function getBooks(subject?: string): Promise<Book[]> {
  const q = subject ? `?subject=${encodeURIComponent(subject)}` : '';
  return getJSON(`/api/books${q}`);
}

export function getBook(id: string): Promise<{ book: Book; sections: Record<string, Question[]>; questions: Question[] }> {
  return getJSON(`/api/books/${id}`);
}

// ---------------------------------------------------------------------------
// F10  试卷生成 (mock exam paper generation)
// ---------------------------------------------------------------------------
export function getPaperTemplates(): Promise<PaperTemplate[]> {
  return getJSON('/api/paper-templates');
}
export function getExams(): Promise<ExamPaper[]> {
  return getJSON('/api/exams');
}
export function getExam(id: string): Promise<ExamPaper> {
  return getJSON(`/api/exams/${id}`);
}
export function generateExam(body: { template_id: string; include_used?: boolean; override_marks?: number; override_count?: number; authored_filter?: 'all' | 'ai' | 'real' }): Promise<ExamPaper> {
  return getJSON('/api/exams/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}
export function addExamItem(exam_id: string, question_id: string): Promise<void> {
  return getJSON(`/api/exams/${exam_id}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id })
  });
}
export function deleteExam(exam_id: string): Promise<void> {
  return getJSON(`/api/exams/${exam_id}`, { method: 'DELETE' });
}

// F-progress: get questions similar to a given one (classification / related practice).
export function getSimilar(id: string): Promise<{ similar: Question[] }> {
  return getJSON(`/api/questions/${id}/similar`);
}

// F-progress: mark a question done + set mastery level + record completion date.
export function patchProgress(id: string, patch: { completed?: boolean; mastery_level?: number }): Promise<void> {
  return getJSON(`/api/progress/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch)
  });
}

// F-progress: fetch completed questions by date range (and optional mastery filter).
export function getReview(opts: { from?: string; to?: string; mastery?: number } = {}): Promise<Question[]> {
  const qs = new URLSearchParams();
  if (opts.from) qs.set('from', opts.from);
  if (opts.to) qs.set('to', opts.to);
  if (opts.mastery) qs.set('mastery', String(opts.mastery));
  return getJSON(`/api/progress/review?${qs.toString()}`);
}

// getQuestions already supports exclude_completed via QuestionQuery (added below).

// ---------------------------------------------------------------------------
// F11  题目纠错报告 (question reports)
// ---------------------------------------------------------------------------
export function createReport(body: {
  question_id: string;
  reason: string;
  detail?: string;
  page_ref?: string;
}): Promise<{ id: string; ok: boolean }> {
  return getJSON('/api/reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

export function getReports(opts: { status?: 'open' | 'resolved' | 'dismissed' | '' } = {}): Promise<{ total: number; reports: Report[] }> {
  const qs = new URLSearchParams();
  if (opts.status) qs.set('status', opts.status);
  const s = qs.toString();
  return getJSON(`/api/reports${s ? `?${s}` : ''}`);
}

export function updateReport(id: string, patch: { status?: 'open' | 'resolved' | 'dismissed'; resolved_note?: string }): Promise<void> {
  return getJSON(`/api/reports/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch)
  });
}

// Review workflow: mark a freshly-imported question as reviewed ('done') or
// reset it back to 'new' (reopen for another pass).
export function setReviewStatus(id: string, status: 'new' | 'done'): Promise<{ ok: boolean; review_status: string }> {
  return getJSON(`/api/questions/${encodeURIComponent(id)}/review-status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  });
}
