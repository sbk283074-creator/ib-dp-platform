import { useEffect, useState } from 'react';
import { getProgress, getProgressByKp, getProgressByTopic, getReview } from '../api';
import type { ProgressByKp, ProgressByTopic, ProgressRow, Question } from '../types';
import QuestionCard from '../components/QuestionCard';

function Bar({ accuracy }: { accuracy: number }) {
  const color = accuracy >= 70 ? '#1a7f37' : accuracy >= 40 ? '#b58105' : '#b42318';
  return (
    <div className="bar">
      <div className="bar-fill" style={{ width: `${accuracy}%`, background: color }} />
      <span className="bar-label">{accuracy}%</span>
    </div>
  );
}

export default function ProgressPage() {
  const [rows, setRows] = useState<ProgressRow[]>([]);
  const [byTopic, setByTopic] = useState<ProgressByTopic[]>([]);
  const [byKp, setByKp] = useState<ProgressByKp[]>([]);

  // Review (date-range + mastery) section
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [mastery, setMastery] = useState<number | ''>('');
  const [review, setReview] = useState<Question[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);

  useEffect(() => {
    getProgress().then(setRows).catch(() => {});
    getProgressByTopic().then(setByTopic).catch(() => {});
    getProgressByKp().then(setByKp).catch(() => {});
  }, []);

  async function runReview() {
    setReviewLoading(true);
    try {
      const r = await getReview({ from: from || undefined, to: to || undefined, mastery: mastery === '' ? undefined : Number(mastery) });
      setReview(r);
    } catch { setReview([]); }
    setReviewLoading(false);
  }

  useEffect(() => { runReview(); /* eslint-disable-next-line */ }, []);

  const attempted = rows.length;
  const correct = rows.reduce((s, r) => s + (r.correct_count ?? 0), 0);
  const wrong = rows.reduce((s, r) => s + (r.wrong_count ?? 0), 0);
  const answered = correct + wrong;
  const accuracy = answered ? Math.round((correct / answered) * 100) : 0;

  return (
    <div className="progress">
      <h3>Your progress</h3>
      <div className="stat-grid">
        <div className="stat"><div className="stat-num">{attempted}</div><div className="stat-label">Questions attempted</div></div>
        <div className="stat"><div className="stat-num correct">{correct}</div><div className="stat-label">Correct answers</div></div>
        <div className="stat"><div className="stat-num wrong">{wrong}</div><div className="stat-label">Wrong answers</div></div>
        <div className="stat"><div className="stat-num">{accuracy}%</div><div className="stat-label">Accuracy</div></div>
      </div>

      <h4>By topic</h4>
      {byTopic.length === 0 ? (
        <div className="empty"><p className="muted">No attempts recorded yet.</p></div>
      ) : (
        <div className="agg-list">
          {byTopic.map((t) => (
            <div key={t.topic} className="agg-row">
              <div className="agg-name">{t.topic}</div>
              <div className="agg-bar"><Bar accuracy={t.accuracy} /></div>
              <div className="agg-meta">{t.correct}/{t.correct + t.wrong}</div>
            </div>
          ))}
        </div>
      )}

      <h4>By knowledge point</h4>
      {byKp.length === 0 ? (
        <div className="empty"><p className="muted">No attempts linked to knowledge points yet.</p></div>
      ) : (
        <div className="agg-list">
          {byKp.map((t) => (
            <div key={t.kp} className="agg-row">
              <div className="agg-name">{t.kp}</div>
              <div className="agg-bar"><Bar accuracy={t.accuracy} /></div>
              <div className="agg-meta">{t.correct}/{t.correct + t.wrong}</div>
            </div>
          ))}
        </div>
      )}

      <h4>Review completed questions</h4>
      <p className="muted">Look back at questions you finished, filter by date or mastery level, and re-practice to strengthen recall.</p>
      <div className="review-filters">
        <label>From<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>To<input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        <label>Mastery
          <select value={mastery} onChange={(e) => setMastery(e.target.value === '' ? '' : Number(e.target.value))}>
            <option value="">All</option>
            {[1,2,3,4,5].map((m) => <option key={m} value={m}>Level {m}</option>)}
          </select>
        </label>
        <button className="primary" onClick={runReview}>Search</button>
      </div>
      <div className="results-head">{reviewLoading ? 'Loading…' : `${review.length} completed question(s)`}</div>
      {review.length === 0 && !reviewLoading ? (
        <div className="empty"><p className="muted">No completed questions in this range yet. Mark questions as done from Search to build your review log.</p></div>
      ) : (
        review.map((q) => <QuestionCard key={q.id} q={q} />)
      )}
    </div>
  );
}
