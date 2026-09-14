import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getBooks, Book } from '../api';

const SUBJECT_COLORS: Record<string, string> = {
  CS: '#7c3aed',
  Physics: '#2563eb',
  Math: '#0d9488',
  'Math AA HL': '#0d9488',
};

export default function BooksPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [filter, setFilter] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getBooks(filter || undefined)
      .then((list) => {
        if (cancelled) return;
        setBooks(list);
        setError(null);
      })
      .catch((e) => {
        if (cancelled) return;
        // Deliberately NOT `.catch(() => setBooks([]))`. An unreachable backend
        // and an empty library are different facts; collapsing them into the
        // empty state is what made a dead API look like "No books yet."
        setBooks([]);
        setError(e?.message || String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter, reloadKey]);

  const subjects = Array.from(new Set(books.map((b) => b.subject))).sort();
  const grouped: Record<string, Book[]> = {};
  books.forEach((b) => ((grouped[b.subject] ||= []).push(b)));

  return (
    <div className="page">
      <header className="page-head">
        <h1>📚 Books</h1>
        <div className="muted small">Curated exercise sets from IB textbooks, workbooks, and specimen papers.</div>
      </header>

      <div className="filter-bar">
        <div className="seg">
          <button className={'seg-btn' + (filter === '' ? ' active' : '')} onClick={() => setFilter('')}>All subjects</button>
          {subjects.map((s) => (
            <button key={s} className={'seg-btn' + (filter === s ? ' active' : '')} onClick={() => setFilter(s)}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="empty">Loading…</div>}

      {!loading && error && (
        <div className="load-error">
          <p><b>Could not load books.</b></p>
          <p>The request to the API failed, so this list is empty <i>for that reason</i> — not because there are no books.</p>
          <p><code>{error}</code></p>
          <p className="muted">
            Most likely the backend is not running. Start it on port 3001 — the frontend proxies
            /api and /figures there (see start.command).
          </p>
          <p><button className="book-action" onClick={() => setReloadKey((k) => k + 1)}>Retry</button></p>
        </div>
      )}

      {!loading && !error && books.length === 0 && <div className="empty">No books yet.</div>}

      {!loading && subjects.map((s) => (
        <section key={s} className="book-group">
          <h2 className="book-group-title">
            <span
              className="book-subject-dot"
              style={{ background: SUBJECT_COLORS[s] || '#6b7280' }}
            />
            {s}
          </h2>
          <div className="book-grid">
            {grouped[s].map((b) => (
              <div key={b.id} className="book-card">
                <div className="book-card-head">
                  <span className="book-publisher">{b.publisher || 'Publisher'}</span>
                  <span className="book-count">{b.total_questions} Q</span>
                </div>
                <div className="book-title">{b.title}</div>
                <div className="book-edition">{b.edition || ''}</div>
                <div className="book-foot">
                  {b.has_answers ? (
                    <span className="book-badge has-ans">Has answers</span>
                  ) : (
                    <span className="book-badge no-ans">AI answers</span>
                  )}
                  {b.answer_source && <span className="muted small">· {b.answer_source}</span>}
                </div>
                <div className="book-actions">
                  <Link className="book-action primary" to={`/books/${b.id}/read`}>
                    📖 Read full book
                  </Link>
                  <Link className="book-action" to={`/books/${b.id}`}>
                    ✏️ Practice questions
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}