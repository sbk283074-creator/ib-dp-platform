import { useState } from 'react';
import type { Question } from '../types';
import { getAIStatus, askAI } from '../api';
import type { AIStatus } from '../api';

// Self-contained "Ask AI tutor" affordance for a single question.
// Privacy: only { message, questionId, complexity, length } leaves the browser;
// the question text is fetched server-side and the API key never reaches the client.
//
// UX intent: the student picks HOW HARD the question is (complexity) and HOW LONG
// an answer they want (length); the server picks the best-fit free model. They can
// still override manually. Live per-model quotas (requests + tokens remaining) are
// shown so the choice is informed, not a black box.

type Complexity = 'simple' | 'standard' | 'deep';
type Length = 'short' | 'medium' | 'long';

const COMPLEXITY_LABELS: Record<Complexity, string> = {
  simple: 'Quick / simple',
  standard: 'Standard IB question',
  deep: 'Hard / multi-step'
};
const LENGTH_LABELS: Record<Length, string> = {
  short: 'Short answer',
  medium: 'Normal explanation',
  long: 'Full worked solution'
};

export default function AskAI({ q }: { q: Question }) {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [complexity, setComplexity] = useState<Complexity>('standard');
  const [length, setLength] = useState<Length>('medium');
  const [model, setModel] = useState(''); // '' = follow intent (Auto)
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [answeredBy, setAnsweredBy] = useState<string | null>(null);
  const [cached, setCached] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const pool = status?.pool || [];
  const labelFor = (id?: string | null) =>
    id ? pool.find((m) => m.id === id)?.label || id : null;

  // The model the server will use: explicit override wins, else the intent pick.
  const recommended =
    status?.intentMatrix?.recommend[complexity]?.[length] || null;
  const effectiveId = model || recommended?.model || '';
  const recommendedLabel = labelFor(recommended?.model);

  async function ensureStatus() {
    if (status !== null) return;
    try {
      setStatus(await getAIStatus());
    } catch {
      setStatus({ configured: false, model: null });
    }
  }

  async function onToggle() {
    await ensureStatus();
    setOpen((v) => !v);
  }

  async function send() {
    const msg = input.trim();
    if (!msg || busy) return;
    setBusy(true);
    setNotice(null);
    setAnswer(null);
    setAnsweredBy(null);
    setCached(false);
    try {
      const r = await askAI({
        message: msg,
        questionId: q.id,
        subject: q.subject,
        topic: q.topic,
        marks: q.marks ?? null,
        complexity,
        length,
        ...(model ? { model } : {})
      });
      if (!r.ok) {
        setNotice(r.message || 'The AI could not respond right now.');
        return;
      }
      setAnswer(r.answer || '');
      setAnsweredBy(labelFor(r.model));
      setCached(Boolean(r.cached));
      // Refresh pool health so quotas reflect the real remaining budget.
      getAIStatus().then(setStatus).catch(() => {});
    } catch {
      setNotice('Network error — please try again.');
    } finally {
      setBusy(false);
    }
  }

  // If we already know the server has no key, render nothing (no broken button).
  if (status && !status.configured) return null;

  const quotaLine =
    status?.aggregate &&
    `pool: ${status.aggregate.availableNow}/${status.aggregate.models} free · ` +
      `${status.aggregate.rpdRemaining.toLocaleString()} req left today` +
      (status.aggregate.tpd === null ? ' · unlimited tokens available' : '');

  return (
    <div className="askai">
      <button className="iconbtn" title="Ask the AI tutor about this question" onClick={onToggle}>
        Ask AI
      </button>

      {open && (
        <div
          className="askai-panel"
          style={{ marginTop: 8, border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, background: '#f8fafc' }}
        >
          <div style={{ fontSize: 13, color: '#475569', marginBottom: 8 }}>
            Ask the AI tutor about this {q.subject} question. Tell it how hard your question is and how
            long an answer you want — it picks the best free model for that. Your message is sent to the
            server only and is not stored.
          </div>

          {/* ── Intent selectors ─────────────────────────────────────────── */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
            <label style={{ fontSize: 12, color: '#64748b', display: 'flex', flexDirection: 'column', gap: 2 }}>
              Question difficulty
              <select
                className="wb-note"
                style={{ width: 'auto', minHeight: 0, padding: '4px 8px', fontSize: 12 }}
                value={complexity}
                onChange={(e) => setComplexity(e.target.value as Complexity)}
              >
                {(['simple', 'standard', 'deep'] as Complexity[]).map((c) => (
                  <option key={c} value={c}>
                    {COMPLEXITY_LABELS[c]}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: 12, color: '#64748b', display: 'flex', flexDirection: 'column', gap: 2 }}>
              Answer length
              <select
                className="wb-note"
                style={{ width: 'auto', minHeight: 0, padding: '4px 8px', fontSize: 12 }}
                value={length}
                onChange={(e) => setLength(e.target.value as Length)}
              >
                {(['short', 'medium', 'long'] as Length[]).map((l) => (
                  <option key={l} value={l}>
                    {LENGTH_LABELS[l]}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* ── Recommendation callout ───────────────────────────────────── */}
          {recommended && (
            <div
              style={{
                fontSize: 12,
                background: '#ecfdf5',
                border: '1px solid #a7f3d0',
                borderRadius: 6,
                padding: '6px 8px',
                color: '#065f46',
                marginBottom: 8
              }}
            >
              <strong>Recommended: {recommendedLabel}</strong> — {recommended.reason}
            </div>
          )}

          {/* ── Manual model override ────────────────────────────────────── */}
          {pool.length > 0 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
              <label style={{ fontSize: 12, color: '#64748b' }} htmlFor={`aimodel-${q.id}`}>
                Model
              </label>
              <select
                id={`aimodel-${q.id}`}
                className="wb-note"
                style={{ width: 'auto', minHeight: 0, padding: '4px 8px', fontSize: 12 }}
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                <option value="">Auto (use recommendation)</option>
                {pool.map((m) => (
                  <option key={m.id} value={m.id} disabled={!m.available}>
                    {m.label}
                    {m.available ? '' : ' (capped)'}
                    {m.id === recommended?.model ? ' ★' : ''}
                  </option>
                ))}
              </select>
              {quotaLine && (
                <span className="muted" style={{ fontSize: 11 }}>
                  {quotaLine}
                </span>
              )}
            </div>
          )}

          <textarea
            className="wb-note"
            style={{ width: '100%', minHeight: 56 }}
            placeholder="e.g. Can you explain the method step by step?"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send();
            }}
          />
          <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              className="report-submit"
              style={{ padding: '6px 12px' }}
              onClick={send}
              disabled={busy || !input.trim()}
            >
              {busy ? 'Thinking…' : 'Ask'}
            </button>
            {cached && <span className="muted" style={{ fontSize: 12 }}>cached answer</span>}
            {!cached && answeredBy && (
              <span className="muted" style={{ fontSize: 12 }}>answered by {answeredBy}</span>
            )}
          </div>

          {notice && <div className="muted" style={{ marginTop: 8, color: '#b45309' }}>{notice}</div>}

          {answer && (
            <div className="answer-body" style={{ marginTop: 10, whiteSpace: 'pre-wrap', color: '#0f172a' }}>
              {answer}
            </div>
          )}

          {/* ── Capability + live quota panel ────────────────────────────── */}
          {pool.length > 0 && (
            <details style={{ marginTop: 10 }}>
              <summary style={{ fontSize: 12, color: '#475569', cursor: 'pointer' }}>
                Models, capabilities &amp; remaining quota
              </summary>
              <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {pool.map((m) => {
                  const isRecommended = m.id === recommended?.model;
                  const reqLeft = m.remaining === null ? '∞' : m.remaining.toLocaleString();
                  const tokLeft = m.tpdRemaining === null ? '∞' : m.tpdRemaining.toLocaleString();
                  return (
                    <div
                      key={m.id}
                      style={{
                        border: isRecommended ? '1px solid #a7f3d0' : '1px solid #e2e8f0',
                        borderRadius: 6,
                        padding: '6px 8px',
                        background: isRecommended ? '#f0fdf4' : '#ffffff'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                        <span style={{ fontWeight: 600, color: '#0f172a' }}>
                          {m.label}
                          {isRecommended ? ' ★' : ''}
                          {!m.available ? ' · capped' : ''}
                        </span>
                        <span className="muted" style={{ fontSize: 11 }}>
                          {reqLeft} req · {tokLeft} tokens left
                        </span>
                      </div>
                      {m.caps && (
                        <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>
                          <span style={{ color: '#64748b' }}>{m.caps.vendor} · {m.caps.size}</span>
                          <br />
                          <strong>Best for:</strong> {m.caps.bestFor}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <div style={{ fontSize: 11, color: '#64748b', marginTop: 6 }}>
                Requests = how many questions/day; tokens = how long the answers can be. “∞” means that
                model has no cap on that dimension. Quotas reset at 00:00 UTC.
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
