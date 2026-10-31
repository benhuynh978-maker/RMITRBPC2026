function HeroIllustration() {
  return (
    <svg
      className="hero-art"
      viewBox="0 0 520 420"
      role="img"
      aria-labelledby="hero-art-title hero-art-desc"
    >
      <title id="hero-art-title">Illustration: a camera watches a street drain and a map pin marks the litter</title>
      <desc id="hero-art-desc">
        A stylised street map with two crossing roads. A pole-mounted camera on the left looks at a drain grate with
        a few pieces of litter beside it. A map pin above the drain marks the spot.
      </desc>
      <defs>
        <linearGradient id="ha-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#eaf6f7" />
          <stop offset="1" stopColor="#d3e9ec" />
        </linearGradient>
        <linearGradient id="ha-cone" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#e0892b" stopOpacity="0.45" />
          <stop offset="1" stopColor="#e0892b" stopOpacity="0.08" />
        </linearGradient>
      </defs>
      <rect width="520" height="420" rx="24" fill="url(#ha-bg)" />
      {/* city blocks */}
      <g fill="#f4f1e8" stroke="#c4d6d9" strokeWidth="1.5">
        <rect x="24" y="24" width="190" height="130" rx="10" />
        <rect x="306" y="24" width="190" height="130" rx="10" />
        <rect x="24" y="266" width="190" height="130" rx="10" />
        <rect x="306" y="266" width="190" height="130" rx="10" />
      </g>
      <g fill="#cfe3d3">
        <rect x="44" y="44" width="60" height="40" rx="8" />
        <rect x="326" y="296" width="70" height="46" rx="8" />
      </g>
      {/* roads */}
      <g stroke="#ffffff" strokeLinecap="round">
        <path d="M0 210 H520" strokeWidth="64" />
        <path d="M260 0 V420" strokeWidth="64" />
      </g>
      <g stroke="#a9bfc4" strokeWidth="3" strokeDasharray="14 12" fill="none">
        <path d="M10 210 H228" />
        <path d="M292 210 H510" />
        <path d="M260 10 V178" />
        <path d="M260 242 V410" />
      </g>
      {/* alert-coloured road segments (colour + line style) */}
      <path d="M292 210 H500" stroke="#d55e00" strokeWidth="8" strokeLinecap="round" opacity="0.9" />
      <path d="M260 20 V176" stroke="#e69f00" strokeWidth="8" strokeLinecap="round" strokeDasharray="16 10" opacity="0.95" />
      {/* camera view cone */}
      <path d="M92 206 L318 150 L318 262 Z" fill="url(#ha-cone)" />
      {/* camera pole */}
      <g>
        <rect x="76" y="212" width="8" height="82" rx="3" fill="#0b3b45" />
        <rect x="64" y="288" width="32" height="8" rx="3" fill="#0b3b45" />
        <rect x="66" y="196" width="40" height="22" rx="6" fill="#0b3b45" />
        <circle cx="100" cy="207" r="6" fill="#e0892b" />
        <circle cx="100" cy="207" r="2.4" fill="#0b3b45" />
        <rect x="68" y="176" width="26" height="14" rx="3" fill="#12909a" />
        <path d="M81 190 V196" stroke="#0b3b45" strokeWidth="3" />
      </g>
      {/* drain grate */}
      <g>
        <rect x="316" y="200" width="64" height="34" rx="5" fill="#2d4a52" />
        <g stroke="#9db6bb" strokeWidth="3" strokeLinecap="round">
          <path d="M326 207 V227" />
          <path d="M337 207 V227" />
          <path d="M348 207 V227" />
          <path d="M359 207 V227" />
          <path d="M370 207 V227" />
        </g>
      </g>
      {/* litter */}
      <g>
        <path d="M300 238 l16 -6 l6 14 l-16 6 z" fill="#e0892b" stroke="#8a4b05" strokeWidth="1.5" />
        <rect x="334" y="238" width="18" height="12" rx="3" fill="#7aa6c2" stroke="#2f5e7e" strokeWidth="1.5" transform="rotate(-12 343 244)" />
        <ellipse cx="376" cy="246" rx="11" ry="7" fill="#f4f1e8" stroke="#6b7f84" strokeWidth="1.5" />
        <circle cx="395" cy="226" r="6" fill="#c9d6a0" stroke="#68773a" strokeWidth="1.5" />
      </g>
      {/* map pin with drop */}
      <g transform="translate(348 78)">
        <ellipse cx="0" cy="104" rx="26" ry="7" fill="#0b2a31" opacity="0.18" />
        <path d="M0 98 C-30 62 -38 46 -38 28 a38 38 0 0 1 76 0 C38 46 30 62 0 98 z" fill="#0b3b45" stroke="#fff" strokeWidth="4" />
        <path d="M0 8 C-14 24 -20 33 -20 42 a20 20 0 0 0 40 0 C20 33 14 24 0 8 z" fill="#12909a" />
        <path d="M0 52 c0 -12 6 -20 18 -25 c-1 14 -8 23 -18 25 z" fill="#e0892b" />
      </g>
      {/* label chips */}
      <g fontFamily="system-ui, sans-serif" fontSize="13" fontWeight="700">
        <rect x="24" y="320" width="150" height="30" rx="15" fill="#ffffff" stroke="#c4d6d9" />
        <text x="99" y="340" textAnchor="middle" fill="#0b3b45">Camera (prototype)</text>
        <rect x="402" y="150" width="104" height="30" rx="15" fill="#ffffff" stroke="#c4d6d9" />
        <text x="454" y="170" textAnchor="middle" fill="#0b3b45">Litter + drain</text>
      </g>
    </svg>
  );
}

export default function Hero() {
  return (
    <section id="top" className="hero" aria-labelledby="hero-title">
      <div className="container hero-inner">
        <div className="hero-copy">
          <p className="hero-eyebrow">Street-litter mapping with computer vision</p>
          <h1 id="hero-title">
            <span className="hero-brand">CleanSight</span>
            <span className="hero-slogan">Trash with an address</span>
          </h1>
          <p className="hero-value">
            A fixed camera photographs a street drain on a schedule, AI looks for litter and drain blockage, and the
            city map shows where to collect and which drains need cleaning first.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary" href="#demo">See it in action</a>
            <a className="btn btn-ghost" href="#involved">Get involved</a>
          </div>
          <p className="hero-sub">Collect in the right place, at the right time, and warn early of local flooding.</p>
        </div>
        <div className="hero-visual">
          <HeroIllustration />
        </div>
      </div>
    </section>
  );
}
