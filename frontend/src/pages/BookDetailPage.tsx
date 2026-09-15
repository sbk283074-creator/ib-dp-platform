import NotAvailable from '../components/NotAvailable';

/**
 * Reached only by direct URL now that the Books list is switched off. Kept as a
 * route so an old link lands on an explanation instead of a blank page.
 *
 * This page used to render every extracted question of one book via
 * `QuestionCard source="book"` — i.e. exactly the placeholder rows that were cut
 * from the rest of the UI. The old implementation is in git history.
 */
export default function BookDetailPage() {
  return <NotAvailable />;
}
