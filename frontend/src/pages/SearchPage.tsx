import { useEffect, useState } from 'react';
import { getFacets, getQuestions } from '../api';
import type { QuestionQuery } from '../api';
import { useAppState } from '../state';
import type { Facets, Question } from '../types';
import QuestionCard from '../components/QuestionCard';

// Book-imported questions (category='book') are hidden from the UI: their rows
// carry placeholder text ("[See question image. Source: …]") and no usable
// answer, so they are not listed anywhere. The rows stay in the DB — this is a
// UI-only exclusion, nothing is deleted.
//
// There is deliberately no "All" option any more: an absent `category` means
// "no filter", which is exactly what would bring the books back. Every option
// below is a real, non-book category, so the exclusion holds by construction.
type Category = 'past' | 'topic' | 'questionbank' | 'mock';
const PAGE_SIZE = 50;

export default function SearchPage() {
  const [facets, setFacets] = useState<Facets>({ subjects: [], topics: [], paper_types: [], command_terms: [] });
  const [items, setItems] = useState<Question[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const { kpList, pendingQuery, setPendingQuery } = useAppState();

  const [q, setQ] = useState('');
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [paper_type, setPaperType] = useState('');
  const [command_term, setCommandTerm] = useState('');
  const [difficulty, setDifficulty] = useState<number | ''>('');
  const [marks, setMarks] = useState<number | ''>('');
  const [knowledge_point, setKnowledgePoint] = useState('');
  const [category, setCategory] = useState<Category>('past');
  const [hideCompleted, setHideCompleted] = useState(true);

  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  useEffect(() => {
    getFacets().then(setFacets).catch(() => {});
  }, []);

  // If the hero search bar handed us a query, run that search instead of the
  // default (empty) initial load, and clear the pending flag so it isn't reused.
  useEffect(() => {
    if (!pendingQuery) return;
    const query = pendingQuery.trim();
    setPendingQuery('');
    setQ(query);
    setLoading(true);
    getQuestions({
      q: query, subject: '', topic: '', paper_type: '', command_term: '',
      difficulty: '', marks: '', knowledge_point: '', category: 'past',
      limit: PAGE_SIZE, offset: 0, exclude_completed: hideCompleted,
    })
      .then((r) => { setItems(r.items); setTotal(r.total); setPage(0); })
      .catch(() => {})
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Build the query for a given page. `over` lets a click handler pass the value
  // it is ABOUT to set: setState is async, so a handler that calls
  // setCategory('past') and then reads `category` still sees the old value, and
  // the filter would only take effect on the *second* click.
  function buildParams(p: number, over?: Partial<QuestionQuery>): QuestionQuery {
    const params: QuestionQuery = {
      q, subject, topic, paper_type, command_term, difficulty, marks, knowledge_point,
      category, limit: PAGE_SIZE, offset: p * PAGE_SIZE,
      exclude_completed: hideCompleted,
      ...over
    };
    return params;
  }

  function load(p: number, over?: Partial<QuestionQuery>) {
    setLoading(true);
    getQuestions(buildParams(p, over))
      .then((r) => { setItems(r.items); setTotal(r.total); setPage(p); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  // Filter changes: restart from page 1.
  function runSearch() { load(0); }

  // Selecting a category must send the category being selected, not the one
  // still sitting in state.
  function pickCategory(c: Category) { setCategory(c); load(0, { category: c }); }

  // Initial load with retry: if the API is briefly unreachable, keep trying
  // (every 3s, up to ~60s) instead of leaving a permanent "No questions yet".
  // Recovers on its own as soon as the backend is back online.
  useEffect(() => {
    if (pendingQuery) return; // hero-driven search handles the first load instead
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
    setDifficulty(''); setMarks(''); setKnowledgePoint(''); setCategory('past');
    // Same async-state trap as pickCategory: send the cleared values explicitly
    // instead of relying on the state that has not been applied yet.
    load(0, {
      q: '', subject: '', topic: '', paper_type: '', command_term: '',
      difficulty: '', marks: '', knowledge_point: '', category: 'past'
    });
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
            <button className={'seg-btn' + (category === 'past' ? ' on' : '')} onClick={() => pickCategory('past')}>Past papers</button>
            <button className={'seg-btn' + (category === 'mock' ? ' on' : '')} onClick={() => pickCategory('mock')}>Mock papers</button>
            <button className={'seg-btn' + (category === 'topic' ? ' on' : '')} onClick={() => pickCategory('topic')}>Topic questions</button>
            <button className={'seg-btn' + (category === 'questionbank' ? ' on' : '')} onClick={() => pickCategory('questionbank')}>Question bank</button>
          </div>
        </div>
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
          <input type="checkbox" checked={hideCompleted} onChange={(e) => { const v = e.target.checked; setHideCompleted(v); load(0, { exclude_completed: v }); }} />
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
          items.map((qq) => <QuestionCard key={qq.id} q={qq} />)
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
