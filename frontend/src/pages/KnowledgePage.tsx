import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getKnowledgePoint, getKnowledgePoints } from '../api';
import type { KnowledgePoint, KnowledgePointDetail, Question } from '../types';
import QuestionCard from '../components/QuestionCard';

export default function KnowledgePage() {
  const { id } = useParams();
  const [list, setList] = useState<KnowledgePoint[]>([]);
  const [detail, setDetail] = useState<KnowledgePointDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getKnowledgePoints().then(setList).catch(() => {});
  }, []);

  useEffect(() => {
    if (!id) { setDetail(null); return; }
    setLoading(true);
    getKnowledgePoint(id).then((d) => { setDetail(d); setLoading(false); }).catch(() => setLoading(false));
  }, [id]);

  const grouped = useMemo(() => {
    const g: Record<string, KnowledgePoint[]> = {};
    for (const k of list) {
      const theme = k.theme || 'Other';
      (g[theme] ||= []).push(k);
    }
    return g;
  }, [list]);

  if (id && detail) {
    const kp = detail.kp;
    return (
      <div className="kp-detail">
        <Link className="backlink" to="/knowledge">← All knowledge points</Link>
        <h3>{kp.code} · {kp.title}</h3>
        <div className="kp-theme">{kp.theme}</div>
        {kp.description && <p className="kp-desc">{kp.description}</p>}

        {kp.references && kp.references.length > 0 && (
          <div className="kp-refs">
            <h4>References</h4>
            <ul>
              {kp.references.map((r, i) => (
                <li key={i}>
                  <span className={`ref-type ref-${r.type}`}>{r.type}</span>
                  <b>{r.label}</b>
                  {r.chapter != null && <> · ch. {r.chapter}</>}
                  {r.pages && <> · p. {r.pages}</>}
                  {r.note && <> — {r.note}</>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <h4>Linked questions ({detail.questions.length})</h4>
        {detail.questions.length === 0 ? (
          <div className="empty"><p className="muted">No questions linked to this point yet. Import questions with knowledge_point_ids to populate it.</p></div>
        ) : (
          <div className="results">
            {detail.questions.map((q: Question) => <QuestionCard key={q.id} q={q} />)}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="knowledge">
      <h3>Knowledge points</h3>
      <p className="muted">The IB CS (2025) syllabus tree. Each point links to its textbook/formula references and any questions you add.</p>
      {Object.entries(grouped).map(([theme, kps]) => (
        <div key={theme} className="kp-group">
          <h4 className="kp-group-title">{theme}</h4>
          <div className="kp-grid">
            {kps.map((k) => (
              <Link key={k.id} to={`/knowledge/${k.id}`} className="kp-card">
                <div className="kp-card-code">{k.code}</div>
                <div className="kp-card-title">{k.title}</div>
                {k.description && <div className="kp-card-desc">{k.description}</div>}
              </Link>
            ))}
          </div>
        </div>
      ))}
      {loading && <p className="muted">Loading…</p>}
    </div>
  );
}
