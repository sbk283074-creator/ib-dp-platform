import { Link } from 'react-router-dom';

/**
 * Shown in place of a feature that is deliberately switched off in the UI.
 *
 * "Books" is the current case. Questions imported from textbooks were cut out of
 * the frontend because the rows are not usable yet: `question` holds a
 * placeholder ("[See question image. Source: …]") and `answer` / `explanation`
 * are `__AI_FILL__`. Nothing was deleted — the rows are still in the database,
 * and the API still serves them to anyone who asks for them directly.
 */
export default function NotAvailable({
  title = 'Books',
  note
}: {
  title?: string;
  note?: string;
}) {
  return (
    <div className="page">
      <header className="page-head">
        <h1>📚 {title}</h1>
      </header>
      <div className="empty">
        <p><b>This feature is not available yet.</b></p>
        <p className="muted">
          {note ||
            'Textbook questions are still being prepared, so this section is switched off for now.'}
        </p>
        <p>
          <Link className="book-action" to="/">← Back to search</Link>
        </p>
      </div>
    </div>
  );
}
