import { useEffect, useState } from 'react';
import { getReports, updateReport } from '../api';
import type { Report } from '../types';
import { REPORT_REASONS } from '../types';
import Lightbox from '../components/Lightbox';

const reasonLabel = (code: string) => REPORT_REASONS.find((r) => r.code === code)?.label || code;
const splitImgs = (s: string | null | undefined) =>
  s ? s.split(',').map((p) => p.trim()).filter(Boolean) : [];

type Filter = '' | 'open' | 'resolved' | 'dismissed';

export default function ReportsPage() {
  const [filter, setFilter] = useState<Filter>('open');
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [zoom, setZoom] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load(f: Filter) {
    setLoading(true);
    try {
      const r = await getReports({ status: f });
      setReports(r.reports);
    } catch {
      setReports([]);
    }
    setLoading(false);
  }

  useEffect(() => { load(filter); }, [filter]);

  async function act(r: Report, status: 'open' | 'resolved' | 'dismissed') {
    setBusy(r.id);
    try {
      await updateReport(r.id, { status });
      await load(filter);
    } catch { /* ignore */ }
    setBusy(null);
  }

  const openCount = reports.filter((r) => r.status === 'open').length;

  return (
    <div className="reports-page">
      <h2>Question Reports {openCount > 0 && <span className="nav-badge">{openCount}</span>}</h2>
      <div className="reports-filter">
        {(['open', 'resolved', 'dismissed', ''] as Filter[]).map((f) => (
          <button key={f || 'all'} className={'filter-chip' + (filter === f ? ' on' : '')}
            onClick={() => setFilter(f)}>{f === '' ? 'All' : f[0].toUpperCase() + f.slice(1)}</button>
        ))}
      </div>

      {loading ? (
        <div className="muted">Loading…</div>
      ) : reports.length === 0 ? (
        <div className="muted">No reports here. 🎉</div>
      ) : (
        <ul className="reports-list">
          {reports.map((r) => {
            const qImgs = splitImgs(r.question_image);
            const aImgs = splitImgs(r.answer_image);
            return (
              <li key={r.id} className={'report-item status-' + r.status}>
                <div className="report-meta">
                  <span className="report-reason">{reasonLabel(r.reason)}</span>
                  <span className={'report-status status-' + r.status}>{r.status}</span>
                  <span className="muted">{new Date(r.created_at).toLocaleString()}</span>
                </div>
                <div className="report-subj">
                  <b>{r.subject}{r.paper_type ? ` · ${r.paper_type}` : ''}</b>
                  {r.topic ? <span> · {r.topic}</span> : null}
                  {r.source ? <span className="muted"> · {r.source}</span> : null}
                </div>
                {r.page_ref && <div className="report-pageref">📄 {r.page_ref}</div>}
                {r.detail && <div className="report-detail-text">{r.detail}</div>}

                <div className="report-imgs">
                  {qImgs.map((src, i) => (
                    <img key={'q' + i} className="report-img zoomable" src={src} alt="question"
                      loading="lazy" onClick={() => setZoom(src)} />
                  ))}
                  {aImgs.map((src, i) => (
                    <img key={'a' + i} className="report-img zoomable" src={src} alt="answer"
                      loading="lazy" onClick={() => setZoom(src)} />
                  ))}
                  {qImgs.length === 0 && aImgs.length === 0 && (
                    <div className="muted">No image on file for this question.</div>
                  )}
                </div>

                <div className="report-qid">question_id: {r.question_id}</div>

                {r.resolved_note && <div className="report-resolved-note">↳ {r.resolved_note}</div>}

                {r.status === 'open' ? (
                  <div className="report-actions">
                    <button className="linkbtn resolve" disabled={busy === r.id} onClick={() => act(r, 'resolved')}>Resolve</button>
                    <button className="linkbtn dismiss" disabled={busy === r.id} onClick={() => act(r, 'dismissed')}>Dismiss</button>
                  </div>
                ) : (
                  <div className="report-actions">
                    <button className="linkbtn" disabled={busy === r.id} onClick={() => act(r, 'open')}>Reopen</button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {zoom && <Lightbox src={zoom} onClose={() => setZoom(null)} />}
    </div>
  );
}
