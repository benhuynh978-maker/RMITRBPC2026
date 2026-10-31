import { useEffect, useState } from 'react';

const LINKS = [
  ['problem', 'Problem'],
  ['how', 'How it works'],
  ['demo', 'Demo'],
  ['who', 'Who it\u2019s for'],
  ['evidence', 'Evidence'],
  ['limits', 'Limits'],
  ['involved', 'Get involved'],
  ['team', 'Team'],
];

export default function Nav() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <header className="nav">
      <div className="container nav-inner">
        <a className="nav-brand" href="#top" onClick={() => setOpen(false)}>
          <img src="/favicon.svg" alt="" width="28" height="28" />
          <span>CleanSight</span>
        </a>
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={open}
          aria-controls="site-menu"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="sr-only">{open ? 'Close menu' : 'Open menu'}</span>
          <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" focusable="false">
            {open ? (
              <path d="M4 4l14 14M18 4L4 18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
            ) : (
              <path d="M3 6h16M3 11h16M3 16h16" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
            )}
          </svg>
        </button>
        <nav id="site-menu" className={`nav-links${open ? ' is-open' : ''}`} aria-label="Main">
          <ul>
            {LINKS.map(([id, label]) => (
              <li key={id}>
                <a href={`#${id}`} onClick={() => setOpen(false)}>{label}</a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
