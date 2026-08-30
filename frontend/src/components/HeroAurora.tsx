import { useEffect, useRef, useState } from 'react';
import { useAppState } from '../state';
import './HeroAurora.css';

const SUBJECTS = [
  { num: '2,725', label: 'Math AA HL · Past Papers', tag: 'Past papers' },
  { num: '1,827', label: 'Physics HL · Past Papers', tag: 'Past papers' },
  { num: '1,107', label: 'Computer Science HL', tag: 'Past papers' },
];

// A handful of drifting particles with pseudo-randomised positions/speeds.
const PARTICLES = Array.from({ length: 16 }, (_, i) => ({
  left: (i * 61) % 100,
  size: 4 + ((i * 7) % 6),
  delay: (i * 0.9) % 12,
  duration: 12 + ((i * 3) % 10),
}));

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export default function HeroAurora() {
  const rootRef = useRef<HTMLElement>(null);
  const [ripples, setRipples] = useState<{ id: number; x: number; y: number }[]>([]);
  const { setPendingQuery } = useAppState();
  const [q, setQ] = useState('');

  const scrollToFilters = () => {
    document.getElementById('filters')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Hand the typed query to SearchPage (mounted below on the home route) and
  // scroll down so the results are visible.
  const submitSearch = () => {
    const query = q.trim();
    if (!query) {
      scrollToFilters();
      return;
    }
    setPendingQuery(query);
    scrollToFilters();
  };

  // Pointer parallax + scroll progress → CSS variables (no re-render).
  useEffect(() => {
    const el = rootRef.current;
    if (!el || prefersReducedMotion()) return;
    let raf = 0;

    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * 2 - 1;
      const py = ((e.clientY - r.top) / r.height) * 2 - 1;
      if (raf) return;
      raf = requestAnimationFrame(() => {
        el.style.setProperty('--px', px.toFixed(3));
        el.style.setProperty('--py', py.toFixed(3));
        raf = 0;
      });
    };

    const onScroll = () => {
      const r = el.getBoundingClientRect();
      const prog = Math.min(Math.max(-r.top / (r.height * 0.8), 0), 1);
      el.style.setProperty('--scroll', prog.toFixed(3));
    };

    el.addEventListener('pointermove', onMove);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => {
      el.removeEventListener('pointermove', onMove);
      window.removeEventListener('scroll', onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  // Touch / click ripple.
  const onPointerDown = (e: React.PointerEvent) => {
    const el = rootRef.current;
    if (!el || prefersReducedMotion()) return;
    const r = el.getBoundingClientRect();
    const id = Date.now() + Math.random();
    setRipples((prev) => [...prev, { id, x: e.clientX - r.left, y: e.clientY - r.top }]);
    window.setTimeout(() => {
      setRipples((prev) => prev.filter((rp) => rp.id !== id));
    }, 700);
  };

  return (
    <section
      className="hero-aurora"
      aria-label="IB DP Study Platform hero"
      ref={rootRef}
      onPointerDown={onPointerDown}
    >
      {/* Aurora light blobs */}
      <div className="hero-aurora__blob hero-aurora__blob--violet" />
      <div className="hero-aurora__blob hero-aurora__blob--indigo" />
      <div className="hero-aurora__blob hero-aurora__blob--teal" />

      {/* Decorative pattern: dot grid */}
      <div className="hero-aurora__grid" />

      {/* Decorative pattern: rotating topographic contours */}
      <div className="hero-aurora__contours" aria-hidden="true">
        <svg viewBox="0 0 400 400">
          {[40, 70, 100, 130, 160, 188].map((rad, i) => (
            <path
              key={i}
              d={`M200,200 m-${rad + i * 2},0 a${rad + i * 2},${rad * 0.78} 0 1,0 ${
                (rad + i * 2) * 2
              },0 a${rad + i * 2},${rad * 0.78} 0 1,0 -${(rad + i * 2) * 2},0`}
            />
          ))}
        </svg>
      </div>

      {/* Decorative pattern: drifting particles */}
      <div className="hero-aurora__particles" aria-hidden="true">
        {PARTICLES.map((p, i) => (
          <span
            key={i}
            className="hero-aurora__particle"
            style={{
              left: `${p.left}%`,
              width: p.size,
              height: p.size,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.duration}s`,
            }}
          />
        ))}
      </div>

      {/* Touch ripple layer */}
      <div className="hero-aurora__ripples" aria-hidden="true">
        {ripples.map((rp) => (
          <span
            key={rp.id}
            className="hero-aurora__ripple"
            style={{ left: rp.x, top: rp.y }}
          />
        ))}
      </div>

      {/* Foreground content */}
      <div className="hero-aurora__inner">
        <span className="hero-aurora__badge">
          <span className="hero-aurora__dot" />
          IB Diploma Programme · Past Papers & Topic Practice
        </span>

        <h1 className="hero-aurora__title">IB DP Study Platform</h1>

        <p className="hero-aurora__subtitle">
          Past papers, topic questions, and smart revision — an all-in-one study system built for DP candidates.
        </p>

        <div className="hero-aurora__search">
          <input
            placeholder="Search questions, topics, or $LaTeX$ formulas"
            aria-label="Search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') submitSearch(); }}
          />
          <button className="hero-aurora__btn" type="button" onClick={submitSearch}>
            Search
          </button>
        </div>

        <div className="hero-aurora__cards">
          {SUBJECTS.map((s) => (
            <div className="hero-aurora__card" key={s.label}>
              <div className="hero-aurora__card-num">{s.num}</div>
              <div className="hero-aurora__card-label">{s.label}</div>
              <span className="hero-aurora__card-tag">{s.tag} →</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
