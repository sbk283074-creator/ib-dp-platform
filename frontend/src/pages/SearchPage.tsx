import { useEffect, useState } from 'react';
import { getFacets, getQuestions } from '../api';
import { useAppState } from '../state';
import type { Facets, Question, QuestionQuery } from '../types';
import QuestionCard from '../components/QuestionCard';

type Category = 'all' | 'book' | 'past' | 'topic' | 'questionbank';
const PAGE_SIZE = 50;

export default function SearchPage() {
  const [facets, setFacets] = useState<Facets>({ subjects: [], topics: [], paper_types: [], command_terms: [] });
  const [items, setItems] = useState<Question[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const { kpList } = useAppState();

  const [q, setQ] = useState('');
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [paper_type, setPaperType] = useState('');
  const [command_term, setCommandTerm] = useState('');
  const [difficulty, setDifficulty] = useState<number | ''>('');
  const [marks, setMarks] = useState<number | ''>('');
  const [knowledge_point, setKnowledgePoint] = useState('');
  const [category, setCategory] = useState<Category>('all');
  const [newComing, setNewComing] = useState(false);
  const [hideCompleted, setHideCompleted] = useState(true);

  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  useEffect(() => {
    getFacets().then(setFacets).catch(() => {});
  }, []);

  // Build the query for a given page. `resetToFirst` collapses back to page 0
  // whenever a filter changes (so the user always starts at the top).
  function buildParams(p: number): QuestionQuery {
    const params: QuestionQuery = {
      q, subject, topic, paper_type, command_term, difficulty, marks, knowledge_point,
      category, limit: PAGE_SIZE, offset: p * PAGE_SIZE,
      exclude_completed: hideCompleted
    };
    if (newComing) params.review_status = 'new';
    return params;
  }

  function load(p: number) {
    setLoading(true);
    getQuestions(buildParams(p))
      .then((r) => { setItems(r.items); setTotal(r.total); setPage(p); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  // Filter changes: restart from page 1.
  function runSearch() { load(0); }

  // Initial load with retry: if the API is briefly unreachable, keep trying
  // (every 3s, up to ~60s) instead of leaving a permanent "No questions yet".
  // Recovers on its own as soon as the backend is back online.
  useEffect(() => {
    let cancelled = false;
    let tries = 0;
    const attempt = () => {
      if (cancelled) return;
      setLoading(true);
      getQuestions(buildParams(0))
        .then((r) => {
          if (cancelled) return;
          setItems(r.items); setTotal(r.total); setPage(0); setLoading(false);
        })
        .catch(() => {
          if (cancelled) return;
          tries += 1;
          if (tries < 20) setTimeout(attempt, 3000);
          else setLoading(false);
        });
    };
    attempt();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function reset() {
    setQ(''); setSubject(''); setTopic(''); setPaperType(''); setCommandTerm('');
    setDifficulty(''); setMarks(''); setKnowledgePoint(''); setCategory('all'); setNewComing(false);
    load(0);
  }

  // When a review action removes an item from the "new coming" view, drop it
  // from the current page and decrement the running total.
  function onReview(_id: string, status: 'new' | 'done') {
    if (newComing && status === 'done') {
      setItems((prev) => prev.filter((x) => x.id !== _id));
      setTotal((t) => Math.max(0, t - 1));
    }
  }

  function gotoPage(p: number) {
    const clamped = Math.max(0, Math.min(p, totalPages - 1));
    load(clamped);
  }

  return (
    <div className="search-layout">
      <aside className="filters" id="filters">
        <h3>Filters</h3>
        <label>Search
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="keywords, $LaTeX$…" />
        </label>
        <div className="filter-group">
          <span className="filter-label">Category</span>
          <div className="seg">
            <button className={'seg-btn' + (category === 'all' ? ' on' : '')} onClick={() => { setCategory('all'); runSearch(); }}>All</button>
            <button className={'seg-btn' + (category === 'book' ? ' on' : '')} onClick={() => { setCategory('book'); runSearch(); }}>Books</button>
            <button className={'seg-btn' + (category === 'past' ? ' on' : '')} onClick={() => { setCategory('past'); runSearch(); }}>Past papers</button>
            <button className={'seg-btn' + (category === 'topic' ? ' on' : '')} onClick={() => { setCategory('topic'); runSearch(); }}>Topic questions</button>
            <button className={'seg-btn' + (category === 'questionbank' ? ' on' : '')} onClick={() => { setCategory('questionbank'); runSearch(); }}>Question bank</button>
          </div>
        </div>
        <label className="checkline">
          <input type="checkbox" checked={newComing} onChange={(e) => { setNewComing(e.target.checked); runSearch(); }} />
          New coming (unreviewed)
        </label>
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
        <label>Knowledge point
          <select value={knowledge_point} onChange={(e) => setKnowledgePoint(e.target.value)}>
            <option value="">All</option>
            {kpList.map((k) => <option key={k.id} value={k.id}>{k.code} · {k.title}</option>)}
          </select>
        </label>
        <label>Paper
          <select value={paper_type} onChange={(e) => setPaperType(e.target.value)}>
            <option value="">All</option>
            {facets.paper_types.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>Command term
          <select value={command_term} onChange={(e) => setCommandTerm(e.target.value)}>
            <option value="">All</option>
            {facets.command_terms.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>Difficulty
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value === '' ? '' : Number(e.target.value))}>
            <option value="">All</option>
            {[1, 2, 3, 4, 5].map((d) => <option key={d} value={d}>D{d}</option>)}
          </select>
        </label>
        <label>Marks
          <input type="number" value={marks} onChange={(e) => setMarks(e.target.value === '' ? '' : Number(e.target.value))} />
        </label>
        <button className="primary" onClick={runSearch}>Search</button>
        <button className="secondary" onClick={reset}>Reset</button>
        <label className="checkline">
          <input type="checkbox" checked={hideCompleted} onChange={(e) => { setHideCompleted(e.target.checked); runSearch(); }} />
          Hide completed questions
        </label>
      </aside>

      <section className="results">
        <div className="results-head">
          {loading ? 'Searching…' : `${total} question(s) · page ${page + 1} / ${totalPages}`}
        </div>
        {items.length === 0 && !loading ? (
          <div className="empty">
            <p>No questions yet.</p>
            <p className="muted">Nothing matches the current filters.</p>
          </div>
        ) : (
          items.map((qq) => <QuestionCard key={qq.id} q={qq} onReview={onReview} />)
        )}

        {total > PAGE_SIZE && (
          <div className="pager">
            <button className="secondary" disabled={page === 0} onClick={() => gotoPage(page - 1)}>‹ Prev</button>
            <span className="pager-info">Page {page + 1} / {totalPages}</span>
            <button className="secondary" disabled={page + 1 >= totalPages} onClick={() => gotoPage(page + 1)}>Next ›</button>
            <span className="pager-jump">
              Jump to{' '}
              <input
                type="number" min={1} max={totalPages} value={page + 1}
                onChange={(e) => { const v = Number(e.target.value); if (v >= 1) gotoPage(v - 1); }}
              />{' '}/ {totalPages}
            </span>
            <span className="muted">{PAGE_SIZE} per page</span>
          </div>
        )}
      </section>
    </div>
  );
}
