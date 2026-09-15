import { useEffect, useState } from 'react';
import type { Question } from '../types';

// Per-question "Ask AI".
//
// This is deliberately NOT a second chat UI. It hands the question to the
// shared assistant in assets/ai-widget.js — the very same panel the floating
// "Ask AI" button opens — and lets that panel run the conversation. So there is
// one chat implementation for the whole site: the per-question experience is
// the site-wide bar, scoped to a single question, and the two can never drift
// apart.
//
// The widget is loaded from index.html with `defer`, so on the first paint
// window.dpAI may not exist yet; we poll briefly and keep the button disabled
// (rather than unmounting it) until the hook is there.

type DpAI = {
  open: (opts: Record<string, unknown>) => void;
  close: () => void;
  focused: () => boolean;
};

declare global {
  interface Window {
    dpAI?: DpAI;
  }
}

export default function AskAI({ q }: { q: Question }) {
  const [ready, setReady] = useState(() => typeof window !== 'undefined' && !!window.dpAI);

  useEffect(() => {
    if (ready) return;
    let tries = 0;
    const t = window.setInterval(() => {
      if (window.dpAI) {
        setReady(true);
        window.clearInterval(t);
      } else if (++tries > 40) {
        window.clearInterval(t); // ~20s, then stop quietly
      }
    }, 500);
    return () => window.clearInterval(t);
  }, [ready]);

  function open() {
    if (!window.dpAI) return;
    window.dpAI.open({
      ref: q.id,
      questionId: q.id, // the server grounds the prompt on our own DB row
      subject: q.subject,
      topic: q.topic || undefined,
      marks: q.marks ?? undefined,
      prompt: 'Explain how to answer this question.',
      display: 'Explain this question'
    });
  }

  return (
    <div className="askai">
      <button
        className="askai-btn"
        onClick={open}
        disabled={!ready}
        title={
          ready
            ? 'Open the AI assistant, focused on this question'
            : 'Loading the AI assistant…'
        }
      >
        <span aria-hidden="true">✨</span> Ask AI
      </button>
      <span className="askai-note">
        The same assistant as the floating button, focused on this question
      </span>
    </div>
  );
}
