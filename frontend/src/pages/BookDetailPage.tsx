import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getBook, Book, Question } from '../api';
import QuestionCard from '../components/QuestionCard';

export default function BookDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [book, setBook] = useState<Book | null>(null);
  const [sections, setSections] = useState<Record<string, Question[]>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getBook(id)
      .then((res) => {
        setBook(res.book);
        setSections(res.sections);
        setOrder(Object.keys(res.sections));
      })
      .catch((e) => setError(e.message || String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="page"><div className="empty">Loading…</div></div>;
  if (error) return <div className="page"><div className="empty">Error: {error}</div></div>;
  if (!book) return <div className="page"><div className="empty">Book not found.</div></div>;

  return (
    <div className="page">
      <header className="page-head">
        <Link to="/books" className="back-link">← Books</Link>
        <h1>{book.title}</h1>
        <div className="muted small">
          {book.publisher} · {book.edition} · {book.subject} · {book.total_questions} questions
          {book.answer_source && <> · Answers: <b>{book.answer_source}</b></>}
        </div>
      </header>

      <div className="book-toc">
        <h3>Sections</h3>
        <ul>
          {order.map((sec, i) => (
            <li key={sec}>
              <a href={`#sec-${i}`}>{sec}</a>
              <span className="muted small"> · {sections[sec].length} Q</span>
            </li>
          ))}
        </ul>
      </div>

      {order.map((sec, i) => (
        <section key={sec} id={`sec-${i}`} className="book-section">
          <h2 className="book-section-title">{sec}</h2>
          <div className="card-stack">
            {sections[sec].map((q) => (
              <QuestionCard key={q.id} q={q} source="book" />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}