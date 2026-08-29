import { useEffect, useState } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import { AppStateProvider, useAppState } from './state';
import SearchPage from './pages/SearchPage';
import PracticePage from './pages/PracticePage';
import KnowledgePage from './pages/KnowledgePage';
import CollectionsPage from './pages/CollectionsPage';
import WrongBookPage from './pages/WrongBookPage';
import ExportPage from './pages/ExportPage';
import ProgressPage from './pages/ProgressPage';
import ImportPage from './pages/ImportPage';
import ExamsPage from './pages/ExamsPage';
import BooksPage from './pages/BooksPage';
import BookDetailPage from './pages/BookDetailPage';
import ReportsPage from './pages/ReportsPage';
import { getWrongQuestions, getExams, getReports } from './api';

const tabs = [
  { to: '/', label: 'Search', end: true },
  { to: '/practice', label: 'Practice', end: false },
  { to: '/exams', label: 'Exams', end: false },
  { to: '/knowledge', label: 'Knowledge', end: false },
  { to: '/collections', label: 'Collections', end: false },
  { to: '/wrong', label: 'Wrong Book', end: false },
  { to: '/export', label: 'Export', end: false },
  { to: '/progress', label: 'Progress', end: false },
  { to: '/import', label: 'Import', end: false },
  { to: '/books', label: 'Books', end: false },
  { to: '/reports', label: 'Reports', end: false }
];

function Shell() {
  const [wrongCount, setWrongCount] = useState(0);
  const [examCount, setExamCount] = useState(0);
  const [reportCount, setReportCount] = useState(0);
  const { favorites, collections } = useAppState();

  useEffect(() => {
    getWrongQuestions(false).then((list) => setWrongCount(list.length)).catch(() => {});
    getExams().then((list) => setExamCount(list.length)).catch(() => {});
    getReports({ status: 'open' }).then((r) => setReportCount(r.total)).catch(() => {});
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">IB DP Study Platform</div>
        <nav className="nav">
          {tabs.map((t) => (
            <NavLink key={t.to} to={t.to} end={t.end}
              className={({ isActive }) => 'navlink' + (isActive ? ' active' : '')}>
              {t.label}
              {t.to === '/wrong' && wrongCount > 0 && <span className="nav-badge">{wrongCount}</span>}
              {t.to === '/exams' && examCount > 0 && <span className="nav-badge">{examCount}</span>}
              {t.to === '/collections' && collections.length > 0 && <span className="nav-badge">{collections.length}</span>}
              {t.to === '/reports' && reportCount > 0 && <span className="nav-badge report-badge">{reportCount}</span>}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/practice" element={<PracticePage />} />
          <Route path="/exams" element={<ExamsPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/knowledge/:id" element={<KnowledgePage />} />
          <Route path="/collections" element={<CollectionsPage />} />
          <Route path="/collections/:id" element={<CollectionsPage />} />
          <Route path="/wrong" element={<WrongBookPage />} />
          <Route path="/export" element={<ExportPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/books" element={<BooksPage />} />
          <Route path="/books/:id" element={<BookDetailPage />} />
          <Route path="/reports" element={<ReportsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AppStateProvider>
      <Shell />
    </AppStateProvider>
  );
}
