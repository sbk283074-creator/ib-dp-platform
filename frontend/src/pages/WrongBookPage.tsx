import { useEffect, useState } from 'react';
import { getWrongQuestions, recordAttempt, removeFromNotebook, updateNotebook } from '../api';
import type { WrongQuestion } from '../types';
import RichText from '../components/RichText';

function nextReviewLabel(w: WrongQuestion): string {
  if (!w.next_review_at) return 'due now';
  const t = new Date(w.next_review_at).getTime();
  if (t <= Date.now()) return 'due now';
  return 'next: ' + new Date(w.next_review_at).toLocaleDateString();
}

export default function WrongBookPage() {
  const [items, setItems] = useState<WrongQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [showMastered, setShowMastered] = useState(false);
  const [dueOnly, setDueOnly] = useState(false);

  const [review, setReview] = useState<WrongQuestion[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [reviewCorrect, setReviewCorrect] = useState(0);

  async function load() {
    setLoading(true);
    try {
      const list = await getWrongQuestions({ includeMastered: showMastered, dueOnly });
      setItems(list);
    } catch { /* ignore */ }
    setLoading(false);
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [showMastered, dueOnly]);

  async function markMastered(it: WrongQuestion) {
    await updateNotebook(it.id, { mastered: true }).catch(() => {});
    await load();
  }
  async function remove(it: WrongQuestion) {
    await removeFromNotebook(it.id).catch(() => {});
    await load();
  }
  async function saveNote(it: WrongQuestion, note: string) {
    await updateNotebook(it.id, { note }).catch(() => {});
  }

  function startReview(pool: WrongQuestion[]) {
    if (pool.length === 0) return;
    setReview(pool);
    setIdx(0);
    setRevealed(false);
    setReviewCorrect(0);
  }

  async function reviewMark(result: 'correct' | 'incorrect') {
    if (!review) return;
    const q = review[idx];
    await recordAttempt({ question_id: q.id, result }).catch(() => {});
    if (result === 'correct') setReviewCorrect((c) => c + 1);
    if (idx + 1 >= review.length) { setRevealed(true); return; }
    setIdx(idx + 1);
    setRevealed(false);
  }

  function exitReview() { setReview(null); load(); }

  if (review) {
    const q = review[idx];
    const done = idx >= review.length;
    if (done) {
      return (
        <div className="practice-end">
          <h2>Review complete</h2>
          <p>You got <b>{reviewCorrect}</b> / {review.length} right this round.</p>
          <p className="muted">Correct answers pushed each question's next review further out (spaced repetition).</p>
          <button className="primary" onClick={exitReview}>Back to notebook</button>
        </div>
      );
    }
    return (
      <div className="practice">
        <div className="practice-progress">Review {idx + 1} / {review.length} · score {reviewCorrect}</div>
        <div className="card">
          <div className="card-meta">
            <span className="badge">{q.subject}</span>
            {q.topic && <span className="badge">{q.topic}</span>}
            {q.marks != null && <span className="badge">[{q.marks} marks]</span>}
            <span className="badge warn">wrong ×{q.times_wrong}</span>
          </div>
          <div className="card-q"><RichText text={q.question} /></div>
          {revealed && (
            <div className="card-answer">
              <div className="answer-label">Answer</div>
              <div className="answer-body"><RichText text={q.answer} /></div>
              <div className="answer-label">Explanation</div>
              <div className="answer-body"><RichText text={q.explanation} /></div>
            </div>
          )}
        </div>
        <div className="practice-controls">
          {!revealed
            ? <button className="primary" onClick={() => setRevealed(true)}>Reveal answer</button>
            : (
              <>
                <button className="secondary" onClick={() => reviewMark('incorrect')}>Still wrong</button>
                <button className="primary" onClick={() => reviewMark('correct')}>Got it</button>
              </>
            )}
        </div>
      </div>
    );
  }

  const dueCount = items.filter((it) => !it.mastered && nextReviewLabel(it) === 'due now').length;

  return (
    <div className="wrongbook">
      <div className="wrongbook-head">
        <h3>Wrong Book</h3>
        <div className="wrongbook-actions">
          <label className="inline-check">
            <input type="checkbox" checked={showMastered} onChange={(e) => setShowMastered(e.target.checked)} />
            Show mastered
          </label>
          <label className="inline-check">
            <input type="checkbox" checked={dueOnly} onChange={(e) => setDueOnly(e.target.checked)} />
            Due only
          </label>
          <button className="primary" disabled={dueCount === 0} onClick={() => startReview(items.filter((it) => !it.mastered && nextReviewLabel(it) === 'due now'))}>
            Review due ({dueCount})
          </button>
          <button className="secondary" disabled={items.length === 0} onClick={() => startReview(items.filter((it) => !it.mastered))}>Review all</button>
        </div>
      </div>

      {loading ? <p className="muted">Loading…</p> :
        items.length === 0 ? (
          <div className="empty">
            <p>No wrong questions yet.</p>
            <p className="muted">When you answer a question incorrectly in Practice, it is added here automatically. Due questions are scheduled with spaced repetition.</p>
          </div>
        ) : (
          <div className="wb-list">
            {items.map((it) => (
              <div key={it.id} className={'wb-card' + (it.mastered ? ' mastered' : '')}>
                <div className="wb-card-meta">
                  <span className="badge">{it.subject}</span>
                  {it.topic && <span className="badge">{it.topic}</span>}
                  {it.marks != null && <span className="badge">[{it.marks} marks]</span>}
                  <span className={'badge ' + (it.mastered ? 'ok' : 'warn')}>
                    {it.mastered ? 'mastered' : `wrong ×${it.times_wrong}`}
                  </span>
                  {!it.mastered && <span className="badge srs">SR L{it.srs_level} · {nextReviewLabel(it)}</span>}
                  <span className="wb-date">{new Date(it.added_at).toLocaleDateString()}</span>
                </div>
                <div className="wb-q"><RichText text={it.question} /></div>
                <details className="wb-details">
                  <summary>Show answer & explanation</summary>
                  <div className="answer-label">Answer</div>
                  <div className="answer-body"><RichText text={it.answer} /></div>
                  <div className="answer-label">Explanation</div>
                  <div className="answer-body"><RichText text={it.explanation} /></div>
                </details>
                <textarea
                  className="wb-note"
                  placeholder="Add a note (why you got it wrong, key idea…)"
                  defaultValue={it.note}
                  onBlur={(e) => saveNote(it, e.target.value)}
                />
                <div className="wb-card-actions">
                  {it.mastered
                    ? <button className="secondary" onClick={() => updateNotebook(it.id, { mastered: false }).then(load).catch(() => {})}>Unmark</button>
                    : <button className="secondary" onClick={() => markMastered(it)}>Mark mastered</button>}
                  <button className="danger" onClick={() => remove(it)}>Remove</button>
                </div>
              </div>
            ))}
          </div>
        )}
    </div>
  );
}
