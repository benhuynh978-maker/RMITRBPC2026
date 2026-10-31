import {
  TIMING_S,
  TIMING_TARGET_S,
  HEIGHT_POINTS,
  HEIGHT_REF_M,
  HEIGHT_REFUSED_DISTANCES_M,
  POSITION_ROWS,
  BOARD_SIDE_M,
} from '../../data/evidence.js';

const GRID = '#e1e9eb';
const AXIS = '#44616a';
const INK = '#0b3b45';

function median(arr) {
  const s = [...arr].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/* ---------- 1. Upload and analysis time ---------- */
export function TimingChart() {
  const W = 480, H = 270;
  const P = { l: 44, r: 14, t: 14, b: 34 };
  const pw = W - P.l - P.r, ph = H - P.t - P.b;
  const YMAX = 24;
  const y = (v) => P.t + (1 - v / YMAX) * ph;
  const n = TIMING_S.length;
  const bw = pw / n;
  const med = median(TIMING_S);
  return (
    <figure className="chart-fig">
      <p className="scroll-hint" aria-hidden="true">Swipe sideways to see the whole chart</p>
      <div className="chart-scroll" tabIndex={0} role="group" aria-label="Chart, scrollable on small screens">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-labelledby="ct-t ct-d">
        <title id="ct-t">Time per photo for 21 photos</title>
        <desc id="ct-d">
          Bars show seconds from upload to finished analysis for each of 21 photos. All bars are between 8.8 and 12.3
          seconds, well under the 20 second limit. The median is {med.toFixed(1)} seconds.
        </desc>
        {[0, 5, 10, 15, 20].map((v) => (
          <g key={v}>
            <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} stroke={GRID} />
            <text x={P.l - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill={AXIS}>{v}</text>
          </g>
        ))}
        <text x="12" y={P.t + ph / 2} fontSize="11" fill={AXIS} transform={`rotate(-90 12 ${P.t + ph / 2})`} textAnchor="middle">Seconds per photo</text>
        {TIMING_S.map((v, i) => (
          <g key={i}>
            <rect x={P.l + i * bw + 2} y={y(v)} width={bw - 4} height={y(0) - y(v)} rx="2" fill="#12909a" />
            <text x={P.l + i * bw + bw / 2} y={H - 18} textAnchor="middle" fontSize="9" fill={AXIS}>{i + 1}</text>
          </g>
        ))}
        <text x={P.l + pw / 2} y={H - 4} textAnchor="middle" fontSize="11" fill={AXIS}>Photo number</text>
        <line x1={P.l} x2={W - P.r} y1={y(TIMING_TARGET_S)} y2={y(TIMING_TARGET_S)} stroke="#d55e00" strokeWidth="2.5" strokeDasharray="8 5" />
        <text x={W - P.r - 2} y={y(TIMING_TARGET_S) - 5} textAnchor="end" fontSize="11" fontWeight="700" fill="#8a3b00" stroke="#fff" strokeWidth="3" paintOrder="stroke">Limit: {TIMING_TARGET_S} s</text>
        <line x1={P.l} x2={W - P.r} y1={y(med)} y2={y(med)} stroke={INK} strokeWidth="2" />
        <text x={W - P.r - 2} y={y(med) - 5} textAnchor="end" fontSize="11" fontWeight="700" fill={INK} stroke="#fff" strokeWidth="3" paintOrder="stroke">Median: {med.toFixed(1)} s</text>
      </svg>
      </div>
      <figcaption>Time per photo, upload to finished analysis (21 photos). Dark line: median. Dashed line: 20 s limit.</figcaption>
    </figure>
  );
}

/* ---------- 2. Camera height from the marker ---------- */
export function HeightChart() {
  const W = 480, H = 290;
  const P = { l: 52, r: 14, t: 14, b: 40 };
  const pw = W - P.l - P.r, ph = H - P.t - P.b;
  const X0 = 0.5, X1 = 5.5, Y0 = 1.5, Y1 = 2.2;
  const x = (v) => P.l + ((v - X0) / (X1 - X0)) * pw;
  const y = (v) => P.t + (1 - (v - Y0) / (Y1 - Y0)) * ph;
  const lo = HEIGHT_REF_M * 0.9, hi = HEIGHT_REF_M * 1.1;
  const errs = HEIGHT_POINTS.map(([, h]) => (Math.abs(h - HEIGHT_REF_M) / HEIGHT_REF_M) * 100);
  const meanErr = errs.reduce((a, b) => a + b, 0) / errs.length;
  const maxErr = Math.max(...errs);
  return (
    <figure className="chart-fig">
      <p className="scroll-hint" aria-hidden="true">Swipe sideways to see the whole chart</p>
      <div className="chart-scroll" tabIndex={0} role="group" aria-label="Chart, scrollable on small screens">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-labelledby="ch-t ch-d">
        <title id="ch-t">Estimated camera height versus board distance</title>
        <desc id="ch-d">
          Eight height estimates from board distances of 1, 1.5, 2 and 3 metres all fall between 1.73 and 1.85 metres,
          inside the plus or minus 10 percent band around the tape-measured 1.90 metres. At 4 and 5 metres the board
          was too small in the photo and the system refused to calibrate. Computed mean error {meanErr.toFixed(1)}%,
          maximum {maxErr.toFixed(1)}%.
        </desc>
        <rect x={x(3.5)} y={P.t} width={x(5.5) - x(3.5)} height={ph} fill="#ece9f7" />
        <text x={(x(3.5) + x(5.5)) / 2} y={P.t + 16} textAnchor="middle" fontSize="11" fontWeight="700" fill="#473b86">Refused: board &lt; 50 px</text>
        <rect x={P.l} y={y(hi)} width={pw} height={y(lo) - y(hi)} fill="#d6efe9" opacity="0.8" />
        {[1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2].map((v) => (
          <g key={v}>
            <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} stroke={GRID} />
            <text x={P.l - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill={AXIS}>{v.toFixed(1)}</text>
          </g>
        ))}
        {[1, 2, 3, 4, 5].map((v) => (
          <text key={v} x={x(v)} y={H - 20} textAnchor="middle" fontSize="11" fill={AXIS}>{v} m</text>
        ))}
        <text x={P.l + pw / 2} y={H - 4} textAnchor="middle" fontSize="11" fill={AXIS}>Distance from camera to board</text>
        <text x="12" y={P.t + ph / 2} fontSize="11" fill={AXIS} transform={`rotate(-90 12 ${P.t + ph / 2})`} textAnchor="middle">Estimated camera height (m)</text>
        <line x1={P.l} x2={W - P.r} y1={y(HEIGHT_REF_M)} y2={y(HEIGHT_REF_M)} stroke="#00695c" strokeWidth="2.5" />
        <text x={P.l + 6} y={y(HEIGHT_REF_M) - 6} fontSize="11" fontWeight="700" fill="#00695c">Tape measure: 1.90 m (band &plusmn;10%)</text>
        {HEIGHT_POINTS.map(([d, h], i) => (
          <circle key={i} cx={x(d) + (i % 2 ? 5 : -5)} cy={y(h)} r="5.5" fill="#0e7480" stroke="#fff" strokeWidth="1.5" />
        ))}
        {HEIGHT_REFUSED_DISTANCES_M.map((d) => (
          <g key={d} stroke="#473b86" strokeWidth="2.5" strokeLinecap="round">
            <path d={`M${x(d) - 6} ${y(1.6) - 6} l12 12 M${x(d) + 6} ${y(1.6) - 6} l-12 12`} />
          </g>
        ))}
      </svg>
      </div>
      <figcaption>
        Estimated camera height at each board distance (dots). X marks: board refused at 4 m and 5 m. From these points:
        mean error {meanErr.toFixed(1)}%, max {maxErr.toFixed(1)}% against the 1.90 m tape measure.
      </figcaption>
    </figure>
  );
}

/* ---------- 3. Litter position on the map ---------- */
export function positionStats() {
  const errs = POSITION_ROWS.map(([ty, tx, my, mx]) => Math.hypot(my - ty, mx - tx));
  const dy = POSITION_ROWS.map(([ty, , my]) => my - ty);
  return {
    errs,
    median: median(errs),
    max: Math.max(...errs),
    within20: errs.filter((e) => e <= 0.2).length,
    within40: errs.filter((e) => e > 0.2 && e <= 0.4).length,
    biasY: dy.reduce((a, b) => a + b, 0) / dy.length,
    n: errs.length,
  };
}

export function PositionChart() {
  const st = positionStats();
  const S = 210; // px per metre
  const X0 = -0.75, X1 = 1.25, Y0 = -0.25, Y1 = 2.0;
  const P = { l: 40, r: 10, t: 12, b: 34 };
  const W = (X1 - X0) * S + P.l + P.r;
  const H = (Y1 - Y0) * S + P.t + P.b;
  const sx = (m) => P.l + (m - X0) * S;
  const sy = (m) => P.t + (Y1 - m) * S;
  const half = BOARD_SIDE_M / 2;
  const trueKeys = new Map();
  POSITION_ROWS.forEach(([ty, tx]) => trueKeys.set(`${ty},${tx}`, [ty, tx]));
  return (
    <figure className="chart-fig chart-fig-narrow">
      <p className="scroll-hint" aria-hidden="true">Swipe sideways to see the whole chart</p>
      <div className="chart-scroll" tabIndex={0} role="group" aria-label="Chart, scrollable on small screens">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-labelledby="cp-t cp-d">
        <title id="cp-t">Top-down view: measured versus true positions of a point object</title>
        <desc id="cp-d">
          Crosses mark the nine true positions around the marker board. Dots mark the {st.n} measured positions. Most dots
          sit within 0.2 metres of their cross, with a small shift along the board's +Y axis (away from the camera).
        </desc>
        {[-0.5, 0, 0.5, 1].map((m) => (
          <g key={`x${m}`}>
            <line x1={sx(m)} x2={sx(m)} y1={P.t} y2={H - P.b} stroke={GRID} />
            <text x={sx(m)} y={H - P.b + 15} textAnchor="middle" fontSize="11" fill={AXIS}>{m}</text>
          </g>
        ))}
        {[0, 0.5, 1, 1.5, 2].map((m) => (
          <g key={`y${m}`}>
            <line x1={P.l} x2={W - P.r} y1={sy(m)} y2={sy(m)} stroke={GRID} />
            <text x={P.l - 6} y={sy(m) + 4} textAnchor="end" fontSize="11" fill={AXIS}>{m}</text>
          </g>
        ))}
        <text x={P.l + (W - P.l - P.r) / 2} y={H - 4} textAnchor="middle" fontSize="11" fill={AXIS}>X (m), board&rsquo;s +X axis</text>
        <text x="11" y={P.t + (H - P.t - P.b) / 2} fontSize="11" fill={AXIS} transform={`rotate(-90 11 ${P.t + (H - P.t - P.b) / 2})`} textAnchor="middle">Y (m), board&rsquo;s +Y axis</text>
        <rect x={sx(-half)} y={sy(half)} width={2 * half * S} height={2 * half * S} fill={INK} />
        <text x={sx(0)} y={sy(-half) + 14} textAnchor="middle" fontSize="10" fontWeight="700" fill={INK}>Board</text>
        {POSITION_ROWS.map(([ty, tx, my, mx], i) => (
          <line key={`l${i}`} x1={sx(tx)} y1={sy(ty)} x2={sx(mx)} y2={sy(my)} stroke="#8aa3a8" strokeWidth="1" />
        ))}
        {[...trueKeys.values()].map(([ty, tx], i) => (
          <path key={`t${i}`} d={`M${sx(tx) - 6} ${sy(ty)} h12 M${sx(tx)} ${sy(ty) - 6} v12`} stroke="#00695c" strokeWidth="2.5" strokeLinecap="round" />
        ))}
        {POSITION_ROWS.map(([, , my, mx], i) => (
          <circle key={`m${i}`} cx={sx(mx)} cy={sy(my)} r="4" fill="#d55e00" stroke="#fff" strokeWidth="1" />
        ))}
      </svg>
      </div>
      <figcaption>
        <span className="key-inline"><span className="key-plus" aria-hidden="true">+</span> true position (9)</span>{' '}
        <span className="key-inline"><span className="key-dot" style={{ background: '#d55e00' }} /> measured ({st.n} shots)</span>.
        Computed from the points: median error {(st.median * 100).toFixed(1)} cm, max{' '}
        {(st.max * 100).toFixed(1)} cm, {st.within20} within 0.20 m, {st.within40} within 0.20&ndash;0.40 m, mean shift
        along +Y {(st.biasY * 100).toFixed(1)} cm.
      </figcaption>
    </figure>
  );
}
