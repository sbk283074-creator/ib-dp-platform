import { useMemo } from 'react';
import katex from 'katex';

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
}

function renderMixed(text: string): string {
  if (!text) return '';
  const parts = text.split(/(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g);
  return parts
    .map((p) => {
      if (/^\$\$[\s\S]+?\$\$$/.test(p)) {
        try {
          return katex.renderToString(p.slice(2, -2), { displayMode: true, throwOnError: false });
        } catch {
          return escapeHtml(p);
        }
      }
      if (/^\$[^$\n]+?\$/.test(p)) {
        try {
          return katex.renderToString(p.slice(1, -1), { displayMode: false, throwOnError: false });
        } catch {
          return escapeHtml(p);
        }
      }
      return escapeHtml(p);
    })
    .join('');
}

export default function RichText({ text, className }: { text?: string | null; className?: string }) {
  const html = useMemo(() => renderMixed(text ?? ''), [text]);
  return <span className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
