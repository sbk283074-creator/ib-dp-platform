import NotAvailable from '../components/NotAvailable';

/**
 * The Books section is switched off in the UI for now.
 *
 * The questions imported from textbooks are not usable yet — their `question`
 * field holds a placeholder and their answers are `__AI_FILL__` — so the list
 * only ever showed broken cards. The rows are still in the database and the API
 * still serves them; this is a frontend-only switch, nothing was deleted.
 *
 * The previous implementation (a book grid grouped by subject, with "Read full
 * book" / "Practice questions" actions) is in git history if it is ever needed
 * back.
 */
export default function BooksPage() {
  return <NotAvailable />;
}
