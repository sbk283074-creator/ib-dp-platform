import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getBook, getBookAvailability, getBookFileUrl, Book } from '../api';

/**
 * Full-book viewer — entry 1 of the Books feature.
 * Shows the WHOLE book (every page), not just the extracted questions, by
 * streaming the original PDF from the backend into the browser's PDF viewer.
 */
export default function BookReaderPage() {
  const { id } = useParams<{ id: string }>();
  const [book, setBook] = useState<Book | null>(null);
  const [hasFile, setHasFile] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      getBook(id).then((r) => r.book).catch(() => null),
      getBookAvailability(id).then((r) => r.has_file).catch(() => false)
    ])
      .then(([b, ok]) => { setBook(b); setHasFile(ok); })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="page"><div className="empty">Loading…</div></div>;
  if (!book) return <div className="page"><div className="empty">Book not found.</div></div>;

  return (
    <div className="page reader-page">
      <header className="page-head">
        <Link to="/books" className="back-link">← Books</Link>
        <h1>📖 {book.title}</h1>
        <div className="muted small">
          {book.publisher} · {book.edition} · {book.subject}
          {book.total_questions ? <> · {book.total_questions} extracted questions</> : null}
        </div>
        <div className="reader-actions">
          <Link to={`/books/${book.id}`} className="btn-secondary">✏️ Practice questions</Link>
          {hasFile && (
            <a className="btn-secondary" href={getBookFileUrl(book.id)} target="_blank" rel="noreferrer">
              Open in new tab
            </a>
          )}
        </div>
      </header>

      {hasFile ? (
        <iframe
          className="book-reader"
          title={book.title}
          src={`${getBookFileUrl(book.id)}#view=FitH`}
        />
      ) : (
        <div className="empty">
          The full PDF for this book is not available from this server.
          <div className="muted small" style={{ marginTop: 8 }}>
            The extracted questions are still available under “Practice questions”.
          </div>
        </div>
      )}
    </div>
  );
}
