import { useMemo, useState } from 'react';
import Card from '../../components/Card.jsx';
import Badge from '../../components/Badge.jsx';
import samples from '../../data/samples.json';

const { width: IW, height: IH } = samples.imageSize;
const pts = (poly) => poly.map((p) => p.join(',')).join(' ');

// Shoelace formula.
function polyArea(poly) {
  let a = 0;
  for (let i = 0; i < poly.length; i += 1) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}

function Frame({ frame, large = false, decorative = false }) {
  const gid = `ph-${frame.id}-${large ? 'l' : 's'}`;
  return (
    <svg viewBox={`0 0 ${IW} ${IH}`} className="frame-svg" {...(decorative ? { "aria-hidden": true, focusable: "false" } : { role: "img", "aria-label": `${frame.title}. Placeholder image with trash and drain-zone outlines.` })}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#d9dfe0" />
          <stop offset="1" stopColor="#a9b4b7" />
        </linearGradient>
      </defs>
      {frame.image ? (
        <image href={frame.image} x="0" y="0" width={IW} height={IH} preserveAspectRatio="xMidYMid slice" />
      ) : (
        <>
          <rect width={IW} height={IH} fill={`url(#${gid})`} />
          <text x={IW / 2} y="90" textAnchor="middle" fontSize={large ? 44 : 52} fontWeight="700" fill="#4b5d62">Sample photo placeholder</text>
        </>
      )}
      <polygon points={pts(frame.drain.polygon)} fill="#0072b2" fillOpacity="0.22" stroke="#00507d" strokeWidth="6" strokeDasharray="22 12" />
      <text x={frame.drain.polygon[0][0]} y={frame.drain.polygon[0][1] - 14} fontSize="38" fontWeight="700" fill="#00324f">Drain zone</text>
      {frame.trash.map((t, i) => (
        <g key={t.id}>
          <polygon points={pts(t.polygon)} fill="#d55e00" fillOpacity="0.35" stroke="#8a3b00" strokeWidth="6" />
          <text x={t.polygon[0][0]} y={t.polygon[0][1] - 10} fontSize="34" fontWeight="700" fill="#5c2800">Trash {i + 1}</text>
        </g>
      ))}
    </svg>
  );
}

// Top-down view in metres. Board centre = origin. +Y up on screen, +X right.
function MiniMap({ frame }) {
  const X0 = -1.25, X1 = 1.25, Y0 = -0.5, Y1 = 2;
  const S = 120; // px per metre
  const w = (X1 - X0) * S;
  const h = (Y1 - Y0) * S;
  const sx = (m) => (m - X0) * S;
  const sy = (m) => (Y1 - m) * S;
  const vlines = [-1, -0.5, 0, 0.5, 1];
  const hlines = [0, 0.5, 1, 1.5, 2];
  const half = 0.125;
  return (
    <svg viewBox={`-30 -10 ${w + 40} ${h + 40}`} className="mini-svg" role="img" aria-label="Top-down map: litter polygons on a ground grid in metres, relative to the marker board">
      <rect x="0" y="0" width={w} height={h} fill="#f4f1e8" stroke="#b5c6c9" />
      {vlines.map((m) => (
        <g key={`v${m}`}>
          <line x1={sx(m)} x2={sx(m)} y1="0" y2={h} stroke="#d6e0e2" />
          <text x={sx(m)} y={h + 16} textAnchor="middle" fontSize="11" fill="#44616a">{m} m</text>
        </g>
      ))}
      {hlines.map((m) => (
        <g key={`h${m}`}>
          <line x1="0" x2={w} y1={sy(m)} y2={sy(m)} stroke="#d6e0e2" />
          <text x="-6" y={sy(m) + 4} textAnchor="end" fontSize="11" fill="#44616a">{m}</text>
        </g>
      ))}
      <text x={w - 4} y={sy(0) - 6} textAnchor="end" fontSize="11" fontWeight="700" fill="#1f4f5a">+X</text>
      <text x={sx(0) + 6} y="14" fontSize="11" fontWeight="700" fill="#1f4f5a">+Y</text>
      {/* marker board */}
      <rect x={sx(-half)} y={sy(half)} width={2 * half * S} height={2 * half * S} fill="#0b3b45" />
      <rect x={sx(-half) + 5} y={sy(half) + 5} width={2 * half * S - 10} height={2 * half * S - 10} fill="#fff" />
      <rect x={sx(-half) + 10} y={sy(half) + 10} width={2 * half * S - 20} height={2 * half * S - 20} fill="#0b3b45" />
      <text x={sx(0) + half * S + 6} y={sy(0) + 4} fontSize="11" fontWeight="700" fill="#0b3b45">Marker board</text>
      {frame.trash.map((t, i) => {
        const c = t.ground.reduce((a, p) => [a[0] + p[0] / t.ground.length, a[1] + p[1] / t.ground.length], [0, 0]);
        return (
          <g key={t.id}>
            <polygon points={t.ground.map(([gx, gy]) => `${sx(gx)},${sy(gy)}`).join(' ')} fill="#d55e00" fillOpacity="0.5" stroke="#8a3b00" strokeWidth="2" />
            <text x={sx(c[0]) + 14} y={sy(c[1]) + 4} fontSize="11" fontWeight="700" fill="#5c2800">T{i + 1}</text>
          </g>
        );
      })}
    </svg>
  );
}

export default function PhotoExplorer() {
  const [selId, setSelId] = useState(samples.frames[0].id);
  const frame = samples.frames.find((f) => f.id === selId);
  const imgArea = IW * IH;

  const items = useMemo(
    () => frame.trash.map((t, i) => ({ label: `Trash ${i + 1}`, pct: (polyArea(t.polygon) / imgArea) * 100 })),
    [frame, imgArea],
  );

  return (
    <Card
      className="demo-card demo-wide"
      title="Litter on the map"
      badge={
        <span className="badge-row">
          <Badge variant="demo">Demo data</Badge>
          <Badge variant="placeholder">Placeholder – real field photos coming</Badge>
        </span>
      }
    >
      <p className="muted">
        Pick a frame to see what the AI would report and where that litter sits on the ground relative to the marker
        board. This is how a photo becomes a point on the map: <em>trash with an address</em>.
      </p>

      <div className="thumbs" role="group" aria-label="Sample frames">
        {samples.frames.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`thumb${f.id === selId ? ' is-on' : ''}`}
            aria-pressed={f.id === selId}
            onClick={() => setSelId(f.id)}
          >
            <Frame frame={f} decorative />
            <span className="thumb-title">{f.title}</span>
          </button>
        ))}
      </div>

      <div className="explorer">
        <div className="explorer-main">
          <h4>{frame.title}</h4>
          <Frame frame={frame} large />
          <ul className="annot-key small">
            <li><span className="swatch swatch-trash" /> Trash outline</li>
            <li><span className="swatch swatch-drain" /> Drain zone</li>
          </ul>
        </div>
        <div className="explorer-side" aria-live="polite">
          <h4>Detected items</h4>
          <ul className="detect-list">
            {items.map((it) => (
              <li key={it.label}>
                <span>{it.label}</span>
                <span>{it.pct.toFixed(2)}% of the photo</span>
              </li>
            ))}
            <li className="detect-drain">
              <span>Drain blockage</span>
              <span>{frame.drain.blockagePct}%</span>
            </li>
          </ul>
          <p className="small muted">
            Trash &times; {frame.trash.length}. Area % is the outline&rsquo;s share of the photo, computed from the
            polygon points in <code>samples.json</code>.
          </p>
          <h4>Top-down view (metres from the board)</h4>
          <MiniMap frame={frame} />
        </div>
      </div>
    </Card>
  );
}
