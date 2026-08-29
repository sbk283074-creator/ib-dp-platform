import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { Question } from '../types';
import { useAppState } from '../state';
import { getQuestionNote, saveQuestionNote, patchProgress, getSimilar, createReport, setReviewStatus } from '../api';
import { REPORT_REASONS } from '../types';
import RichText from './RichText';
import Lightbox from './Lightbox';

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="badge">{children}</span>;
}

// Derive a short source tag: "AI" for AI-authored questions, "Book" for
// book-source questions, otherwise the year/session extracted from the
// past-paper source string.
function sourceBadge(q: Question): { label: string; ai: boolean; book: boolean } | null {
  // Book source has priority (questions imported from textbooks / workbooks)
  if (q.source_type === 'book' || q.book_id) {
    return { label: 'Book', ai: q.authored_by === 'ai', book: true };
  }
  if (q.authored_by === 'ai') return { label: 'AI', ai: true, book: false };
  const s = q.source || '';
  // "IB 真题 2016 May Physics HL Paper 1" -> "2016 May"
  const m = s.match(/(\d{4})\s*(May|November|Nov|N)/i);
  if (m) {
    const month = /nov/i.test(m[2]) ? 'Nov' : 'May';
    return { label: `${m[1]} ${month}`, ai: false, book: false };
  }
  // "IB CS classified — 18M.2.SL.TZO.4" -> "18M"
  const m2 = s.match(/(\d{2}[MN])/);
  if (m2) return { label: m2[1], ai: false, book: false };
  if (s) return { label: 'Past paper', ai: false, book: false };
  return null;
}

function splitImages(s: string | null | undefined): string[] {
  if (!s) return [];
  const FIG_HOST = (import.meta as any).env?.VITE_FIGURES_BASE_URL || '';
  return s.split(',').map((p) => p.trim()).filter(Boolean).map((p) => {
    // stored paths are relative to the /figures static dir (e.g. "paper_aa_hl_p1/...")
    if (/^https?:\/\//.test(p) || p.startsWith('/')) return p;
    return FIG_HOST + '/figures/' + p.replace(/^\/?figures\//, '');
  });
}

function ImageStack({ imgs, label, onZoom }: { imgs: string[]; label: string; onZoom: (src: string) => void }) {
  if (!imgs.length) return null;
  return (
    <div className="q-image-stack">
      {imgs.map((src, i) => (
        <img key={i} className="q-image zoomable" src={src} alt={`${label} ${i + 1}`}
          loading="lazy" onClick={() => onZoom(src)} />
      ))}
    </div>
  );
}

export default function QuestionCard({ q, source, onReview }: { q: Question; source?: 'paper' | 'book'; onReview?: (id: string, status: 'new' | 'done') => void }) {
  const [open, setOpen] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [newColName, setNewColName] = useState('');
  const [justSaved, setJustSaved] = useState(false);
  const [zoomSrc, setZoomSrc] = useState<string | null>(null);

  // F-progress: completion + mastery + similar
  const [completed, setCompleted] = useState<boolean>(q.status === 'completed');
  const [mastery, setMastery] = useState<number>(q.mastery_level ?? 0);
  const [savingDone, setSavingDone] = useState(false);
  const [similarOpen, setSimilarOpen] = useState(false);
  const [similar, setSimilar] = useState<Question[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);

  // F11: report (纠错) modal state
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState('wrong-crop');
  const [reportDetail, setReportDetail] = useState('');
  const [reportPage, setReportPage] = useState('');
  const [reportSent, setReportSent] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);

  // Review workflow: track whether this question is still awaiting review.
  const [review, setReview] = useState<string | null | undefined>(q.review_status);
  const [reviewBusy, setReviewBusy] = useState(false);
  async function setReviewed(status: 'new' | 'done') {
    if (reviewBusy) return;
    setReviewBusy(true);
    try {
      await setReviewStatus(q.id, status);
      setReview(status);
      onReview?.(q.id, status);
    } catch { /* ignore */ }
    setReviewBusy(false);
  }

  const { favorites, kpMap, collections, toggleFav, addToCollection, createCollection } = useAppState();
  const favorited = Boolean(favorites[q.id]);

  async function onToggleDone() {
    const next = !completed;
    setSavingDone(true);
    try {
      await patchProgress(q.id, { completed: next, mastery_level: mastery || 1 });
      setCompleted(next);
    } catch { /* ignore */ }
    setSavingDone(false);
  }
  async function onChangeMastery(level: number) {
    setMastery(level);
    try { await patchProgress(q.id, { completed: completed || level > 0, mastery_level: level }); } catch {}
  }
  async function onShowSimilar() {
    setSimilarOpen((v) => !v);
    if (!similarOpen && similar.length === 0) {
      setSimilarLoading(true);
      try { const r = await getSimilar(q.id); setSimilar(r.similar); } catch { setSimilar([]); }
      setSimilarLoading(false);
    }
  }

  async function openNote() {
    setNoteOpen((v) => !v);
    if (note === null) {
      try { const r = await getQuestionNote(q.id); setNote(r.note || ''); } catch { setNote(''); }
    }
  }
  async function saveNote() {
    if (note === null) return;
    await saveQuestionNote(q.id, note).catch(() => {});
    setJustSaved(true);
    setTimeout(() => setJustSaved(false), 1500);
  }
  async function onAddToCollection(cid: string) {
    await addToCollection(cid, q.id).catch(() => {});
    setMenuOpen(false);
  }
  async function onNewCollection() {
    const name = newColName.trim();
    if (!name) return;
    const id = await createCollection(name).catch(() => null);
    if (id) await addToCollection(id, q.id).catch(() => {});
    setNewColName('');
    setMenuOpen(false);
  }

  // F11: submit a correction report for this specific question
  async function submitReport() {
    setReportBusy(true);
    try {
      await createReport({ question_id: q.id, reason: reportReason, detail: reportDetail, page_ref: reportPage });
      setReportSent(true);
      setTimeout(() => {
        setReportOpen(false);
        setReportSent(false);
        setReportDetail('');
        setReportPage('');
        setReportReason('wrong-crop');
      }, 1500);
    } catch { /* ignore */ }
    setReportBusy(false);
  }

  return (
    <div className="card">
      <div className="card-head">
        <div className="card-tags">
          <Badge>{q.subject}</Badge>
          {(() => {
            const sb = sourceBadge(q);
            if (!sb) return null;
            if (sb.book) return <span className="badge book-badge" title={q.book_section || q.source || 'Book'}>{sb.label}</span>;
            if (sb.ai)   return <span className="badge ai-badge">AI</span>;
            return <span className="badge source-badge">{sb.label}</span>;
          })()}
          {q.topic && <Badge>{q.topic}</Badge>}
          {review === 'new' && <span className="badge new-badge" title="Newly imported — awaiting review">New</span>}
          {q.paper_type && <Badge>{q.paper_type}</Badge>}
          {q.command_term && <Badge>{q.command_term}</Badge>}
          {q.marks != null && <Badge>[{q.marks} marks]</Badge>}
          {q.difficulty != null && <Badge>D{q.difficulty}</Badge>}
          {q.usage && q.usage.length > 0 && (
            <span className="usage-badge" title={q.usage.map((u) => `${u.usage_type} · ${new Date(u.used_at).toLocaleString()}`).join('\n')}>
              ✓ used {new Date(q.usage[0].used_at).toLocaleDateString()}
            </span>
          )}
        </div>
        <div className="card-toolbar">
          <button
            className={'iconbtn' + (favorited ? ' fav' : '')}
            title={favorited ? 'Remove from favorites' : 'Add to favorites'}
            onClick={() => toggleFav(q.id)}
          >{favorited ? '★' : '☆'}</button>
          <button className="iconbtn" title="Add note" onClick={openNote}>✎</button>
          <div className="menu-wrap">
            <button className="iconbtn" title="Add to collection" onClick={() => setMenuOpen((v) => !v)}>⊕</button>
            {menuOpen && (
              <div className="menu">
                <div className="menu-title">Add to collection</div>
                {collections.length === 0 && <div className="menu-empty">No collections yet</div>}
                {collections.map((c) => (
                  <button key={c.id} className="menu-item" onClick={() => onAddToCollection(c.id)}>{c.name}</button>
                ))}
                <div className="menu-new">
                  <input
                    placeholder="New collection name"
                    value={newColName}
                    onChange={(e) => setNewColName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') onNewCollection(); }}
                  />
                  <button className="menu-item" onClick={onNewCollection} disabled={!newColName.trim()}>Create & add</button>
                </div>
              </div>
            )}
          </div>
          <button className="iconbtn" title="Report this question" onClick={() => setReportOpen(true)}>⚑</button>
          {review === 'new' && (
            <button className="iconbtn review-new" title="Newly imported — click to mark as reviewed"
              onClick={() => setReviewed('done')} disabled={reviewBusy} style={{ marginLeft: 6 }}>
              ✓ Mark reviewed
            </button>
          )}
          {review === 'done' && (
            <button className="iconbtn review-done" title="Reviewed — click to reopen for another pass"
              onClick={() => setReviewed('new')} disabled={reviewBusy}>
              ↺ Reopen
            </button>
          )}
        </div>
      </div>

      <div className="card-progress">
        <button className={'iconbtn done-btn' + (completed ? ' active' : '')} title="Mark as done / undo"
          onClick={onToggleDone} disabled={savingDone}>
          {completed ? '✓ Done' : '○ Mark done'}
        </button>
        {completed && (
          <span className="mastery-pick">
            <span className="mastery-label">Mastery</span>
            {[1,2,3,4,5].map((lv) => (
              <button key={lv} className={'mastery-dot' + (mastery === lv ? ' on' : '')}
                title={`Mastery level ${lv}`} onClick={() => onChangeMastery(lv)}>{lv}</button>
            ))}
          </span>
        )}
        <button className="iconbtn" title="Find similar questions" onClick={onShowSimilar}>≈ Similar</button>
      </div>

      {q.knowledge_point_ids && q.knowledge_point_ids.length > 0 && (
        <div className="kp-chips">
          {q.knowledge_point_ids.map((id) => (
            <Link key={id} className="kp-chip" to={`/knowledge/${id}`}>
              {kpMap[id] ? `${kpMap[id].code} ${kpMap[id].title}` : id}
            </Link>
          ))}
        </div>
      )}

      <div className="card-q">
        <ImageStack imgs={splitImages(q.question_image)} label="Question" onZoom={setZoomSrc} />
        {q.figure_image && <ImageStack imgs={splitImages(q.figure_image)} label="Figure" onZoom={setZoomSrc} />}
        {!q.question_image && q.figure && splitImages(q.figure).map((src, i) => (
          <img key={i} className="q-figure" src={src} alt={`question figure ${i + 1}`} loading="lazy" />
        ))}
        {q.question_image ? (
          <details className="text-fallback">
            <summary>Show question text</summary>
            <RichText text={q.question} />
          </details>
        ) : (
          <RichText text={q.question} />
        )}
      </div>

      <button className="linkbtn" onClick={() => setOpen((v) => !v)}>
        {open ? 'Hide answer' : 'Show answer'}
      </button>
      {open && (
        <div className="card-answer">
          <div className="answer-label">Answer</div>
          <ImageStack imgs={splitImages(q.answer_image)} label="Answer" onZoom={setZoomSrc} />
          {!q.answer_image && q.answer_figure && splitImages(q.answer_figure).map((src, i) => (
            <img key={i} className="q-figure" src={src} alt={`answer figure ${i + 1}`} loading="lazy" />
          ))}
          {q.answer_image ? (
            <details className="text-fallback">
              <summary>Show answer text</summary>
              <div className="answer-body"><RichText text={q.answer} /></div>
            </details>
          ) : (
            <div className="answer-body"><RichText text={q.answer} /></div>
          )}
          {q.explanation && (
            <>
              <div className="answer-label">Explanation</div>
              <div className="answer-body"><RichText text={q.explanation} /></div>
            </>
          )}
          {q.definition_basis && (
            <div className="definition-basis">
              <span className="db-label">Textbook basis:</span> {q.definition_basis}
            </div>
          )}
        </div>
      )}

      {noteOpen && (
        <div className="note-box">
          <textarea
            className="wb-note"
            placeholder="Add a personal note for this question…"
            value={note ?? ''}
            onChange={(e) => setNote(e.target.value)}
            onBlur={saveNote}
          />
          {justSaved && <div className="note-saved">Saved ✓</div>}
        </div>
      )}

      {zoomSrc && <Lightbox src={zoomSrc} onClose={() => setZoomSrc(null)} />}

      {similarOpen && (
        <div className="similar-box">
          <div className="similar-head">
            <span>Similar questions</span>
            <button className="linkbtn" onClick={() => setSimilarOpen(false)}>close</button>
          </div>
          {similarLoading ? <div className="muted">Finding related questions…</div> :
            similar.length === 0 ? <div className="muted">No closely related questions found.</div> :
            <ul className="similar-list">
              {similar.map((s) => (
                <li key={s.id}>
                  <span className="similar-id">{s.id}</span>
                  <span className="similar-snippet">{s.question.slice(0, 90)}{s.question.length > 90 ? '…' : ''}</span>
                  <span className="similar-tags">{(s.knowledge_point_ids || []).join(', ')}</span>
                </li>
              ))}
            </ul>
          }
        </div>
      )}

      {reportOpen && (
        <div className="report-overlay" onClick={() => !reportBusy && setReportOpen(false)}>
          <div className="report-modal" onClick={(e) => e.stopPropagation()}>
            <div className="report-head">
              <span>Report this question</span>
              <button className="linkbtn" onClick={() => setReportOpen(false)} disabled={reportBusy}>close</button>
            </div>
            <div className="report-qref">
              <b>{q.subject}{q.paper_type ? ` · ${q.paper_type}` : ''}</b>
              {q.source ? <span className="muted"> · {q.source}</span> : null}
              <span className="report-qid"> · {q.id}</span>
            </div>
            <div className="report-reasons">
              {REPORT_REASONS.map((r) => (
                <button key={r.code}
                  className={'reason-chip' + (reportReason === r.code ? ' on' : '')}
                  onClick={() => setReportReason(r.code)}>{r.label}</button>
              ))}
            </div>
            <input
              className="report-page"
              placeholder="Page reference (optional, e.g. Paper 2, page 3)"
              value={reportPage}
              onChange={(e) => setReportPage(e.target.value)}
            />
            <textarea
              className="report-detail"
              placeholder="Describe what is wrong (optional)…"
              value={reportDetail}
              onChange={(e) => setReportDetail(e.target.value)}
            />
            {reportSent ? (
              <div className="report-sent">Report sent ✓ — thank you!</div>
            ) : (
              <button className="report-submit" onClick={submitReport} disabled={reportBusy}>
                {reportBusy ? 'Sending…' : 'Submit report'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
