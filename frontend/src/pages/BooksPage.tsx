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

  useEffect(() => {
    setLoading(true);
    getBooks(filter || undefined)
      .then(setBooks)
      .catch(() => setBooks([]))
      .finally(() => setLoading(false));
  }, [filter]);

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
      {!loading && books.length === 0 && <div className="empty">No books yet.</div>}

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
              <Link key={b.id} to={`/books/${b.id}`} className="book-card">
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
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}