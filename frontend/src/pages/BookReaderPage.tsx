import NotAvailable from '../components/NotAvailable';

/**
 * Reached only by direct URL now that the Books list is switched off. Kept as a
 * route so an old link lands on an explanation instead of a blank page.
 *
 * This page used to stream the original book PDF from the backend into the
 * browser's viewer. The old implementation is in git history.
 */
export default function BookReaderPage() {
  return <NotAvailable />;
}
