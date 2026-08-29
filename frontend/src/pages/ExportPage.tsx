import { useEffect, useState } from 'react';
import { exportHtml, getFacets, getQuestions, getQuestion } from '../api';
import QuestionCard from '../components/QuestionCard';
import type { Facets, Question, QuestionQuery } from '../types';

export default function ExportPage() {
  const [facets, setFacets] = useState<Facets>({ subjects: [], topics: [], paper_types: [], command_terms: [] });
  const [items, setItems] = useState<Question[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [html, setHtml] = useState('');
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [category, setCategory] = useState<'all' | 'book' | 'past' | 'topic' | 'questionbank'>('all');
  const [detail, setDetail] = useState<Question | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    getFacets().then(setFacets).catch(() => {});
  }, []);

  function load() {
    const params: QuestionQuery = { subject, topic, category, limit: 200, offset: 0 };
    getQuestions(params).then((r) => setItems(r.items)).catch(() => {});
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function openDetail(id: string) {
    setDetailLoading(true);
    setDetail(null);
    try {
      const q = await getQuestion(id);
      setDetail(q);
    } finally {
      setDetailLoading(false);
    }
  }

  async function generate() {
    const r = await exportHtml(Array.from(selected));
    setHtml(r.html);
  }

  function printPreview() {
    const w = window.open('');
    if (!w) return;
    w.document.write(html);
    w.document.close();
  }

  return (
    <div className="export-layout">
      <aside className="filters">
        <h3>Select questions</h3>
        <label>Subject
          <select value={subject} onChange={(e) => setSubject(e.target.value)}>
            <option value="">All</option>
            {facets.subjects.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>Topic
          <select value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="">All</option>
            {facets.topics.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <div className="filter-group">
          <span className="filter-label">Category</span>
          <div className="seg">
            <button className={'seg-btn' + (category === 'all' ? ' on' : '')} onClick={() => setCategory('all')}>All</button>
            <button className={'seg-btn' + (category === 'book' ? ' on' : '')} onClick={() => setCategory('book')}>Books</button>
            <button className={'seg-btn' + (category === 'past' ? ' on' : '')} onClick={() => setCategory('past')}>Past papers</button>
            <button className={'seg-btn' + (category === 'topic' ? ' on' : '')} onClick={() => setCategory('topic')}>Topic questions</button>
            <button className={'seg-btn' + (category === 'questionbank' ? ' on' : '')} onClick={() => setCategory('questionbank')}>Question bank</button>
          </div>
        </div>
        <button className="secondary" onClick={load}>Load list</button>
        <div className="export-actions">
          <button className="primary" disabled={selected.size === 0} onClick={generate}>
            Generate worksheet ({selected.size})
          </button>
          {html && <button className="secondary" onClick={printPreview}>Print / PDF</button>}
        </div>
        {items.length === 0 && <div className="empty"><p className="muted">No questions to select yet.</p></div>}
      </aside>

      <section className="results">
        {items.map((q) => (
          <div key={q.id} className="export-row">
            <input
              type="checkbox"
              checked={selected.has(q.id)}
              onChange={() => toggle(q.id)}
              onClick={(e) => e.stopPropagation()}
              aria-label={`Select ${q.id}`}
            />
            <div className="export-row-body" onClick={() => openDetail(q.id)}>
              <span className="export-row-meta">{q.subject} · {q.topic}{q.marks != null ? ` · [${q.marks}]` : ''}</span>
              <span className="export-row-q">{q.question.slice(0, 90)}{q.question.length > 90 ? '…' : ''}</span>
              <span className="export-row-hint">Click to view details</span>
            </div>
          </div>
        ))}
        {html && (
          <div className="export-preview">
            <h4>Preview</h4>
            <iframe title="worksheet" srcDoc={html} className="export-iframe" />
          </div>
        )}
      </section>

      {detail !== null && (
        <div className="modal-overlay" onClick={() => setDetail(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <strong>Question detail</strong>
              <button className="icon-btn" onClick={() => setDetail(null)} aria-label="Close">×</button>
            </div>
            <div className="modal-body">
              {detailLoading
                ? <p className="muted">Loading…</p>
                : <QuestionCard q={detail} />}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
