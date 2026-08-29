import { useEffect } from 'react';

export default function Lightbox({ src, onClose }: { src: string; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  return (
    <div className="lightbox" onClick={onClose} role="dialog" aria-modal="true">
      <img
        className="lightbox-img"
        src={src}
        alt="Enlarged question"
        onClick={(e) => e.stopPropagation()}
      />
      <button className="lightbox-close" title="Close (Esc)" onClick={onClose}>✕</button>
    </div>
  );
}
