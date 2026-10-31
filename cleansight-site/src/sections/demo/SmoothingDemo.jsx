import { useEffect, useMemo, useState } from 'react';
import Card from '../../components/Card.jsx';
import Badge from '../../components/Badge.jsx';
import {
  STATES,
  makeSeries,
  medianSmooth,
  rawState,
  hysteresisStates,
  countChanges,
} from '../../lib/smoothing.js';

// DEMO DATA: simulated series, fixed seed so the counters never change between visits.
const SEED = 7;
const N = 40;
const W = 640;
const H = 250;
const PAD = { l: 58, r: 112, t: 12, b: 26 };
const PW = W - PAD.l - PAD.r;
const PH = H - PAD.t - PAD.b;
const x = (i) => PAD.l + (i / (N - 1)) * PW;
const y = (v) => PAD.t + (1 - v / 100) * PH;
const LETTER = ['L', 'W', 'C'];
const FILL = ['#0072b2', '#e69f00', '#d55e00'];
const TEXT_ON = ['#ffffff', '#1a1200', '#ffffff'];

const path = (vals) => vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');

function StateStrip({ label, states, shown, y0 }) {
  const cw = PW / N;
  return (
    <g>
      <text x={PAD.l - 6} y={y0 + 13} textAnchor="end" fontSize="10" fill="#44616a">{label}</text>
      {states.map((s, i) => {
        const visible = i < shown;
        const cx = PAD.l + i * cw;
        return (
          <g key={i}>
            <rect
              x={cx + 0.5}
              y={y0}
              width={cw - 1}
              height="18"
              rx="2"
              fill={visible && s !== null ? FILL[s] : '#e8eef0'}
              opacity={visible ? 1 : 0.45}
            />
            {visible && (
              <text x={cx + cw / 2} y={y0 + 13} textAnchor="middle" fontSize="10" fontWeight="700" fill={s === null ? '#44616a' : TEXT_ON[s]}>
                {s === null ? '–' : LETTER[s]}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
}

export default function SmoothingDemo() {
  const raw = useMemo(() => makeSeries(SEED, N), []);
  const smooth = useMemo(() => medianSmooth(raw), [raw]);
  const rawStates = useMemo(() => raw.map(rawState), [raw]);
  const smStates = useMemo(() => hysteresisStates(smooth), [smooth]);

  const [shown, setShown] = useState(N);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return undefined;
    const id = setInterval(() => {
      setShown((s) => {
        if (s >= N) {
          setPlaying(false);
          return N;
        }
        return s + 1;
      });
    }, 220);
    return () => clearInterval(id);
  }, [playing]);

  const rawChanges = countChanges(rawStates.slice(0, shown));
  const smChanges = countChanges(smStates.slice(0, shown));
  const curRaw = shown > 0 ? rawStates[shown - 1] : null;
  const curSm = shown > 0 ? smStates[shown - 1] : null;

  const togglePlay = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (shown >= N) setShown(1);
    setPlaying(true);
  };

  return (
    <Card className="demo-card demo-wide" title="Smoothing: fewer false alarms" badge={<Badge variant="demo">Demo data</Badge>}>
      <p className="muted">
        A single photo can be noisy (a shadow, a passing leaf). This simulated series of {N} photos shows the raw
        drain-blockage % next to a smoothed version, and the drain state each one would show.
      </p>

      <div className="smooth-controls">
        <button type="button" className="btn btn-dark btn-sm" onClick={togglePlay}>
          {playing ? 'Pause' : shown >= N ? 'Replay' : 'Play'}
        </button>
        <label className="range-label">
          <span>Photos revealed: <strong>{shown}</strong> of {N}</span>
          <input
            type="range"
            min="1"
            max={N}
            value={shown}
            onChange={(e) => {
              setPlaying(false);
              setShown(Number(e.target.value));
            }}
          />
        </label>
      </div>

      <p className="scroll-hint" aria-hidden="true">Swipe sideways to see the whole chart</p>
      <div className="chart-scroll chart-scroll-wide" tabIndex={0} role="group" aria-label="Chart, scrollable on small screens">
      <svg viewBox={`0 0 ${W} ${H + 66}`} className="chart" role="img" aria-labelledby="sm-title sm-desc">
        <title id="sm-title">Simulated drain-blockage percentage over {N} photos</title>
        <desc id="sm-desc">
          Raw readings jump around the 20 and 50 percent thresholds. The median-of-5 line is steadier. Below the chart,
          two strips show the state each method would display.
        </desc>
        {[0, 20, 50, 100].map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke={v === 20 || v === 50 ? '#8aa3a8' : '#e1e9eb'} strokeDasharray={v === 20 || v === 50 ? '5 4' : undefined} />
            <text x={PAD.l - 6} y={y(v) + 4} textAnchor="end" fontSize="10" fill="#44616a">{v}%</text>
          </g>
        ))}
        <text x={W - PAD.r + 5} y={y(20) + 3} fontSize="10" fill="#44616a">Watch from 20</text>
        <text x={W - PAD.r + 5} y={y(50) + 3} fontSize="10" fill="#44616a">Needs cleaning</text><text x={W - PAD.r + 5} y={y(50) + 15} fontSize="10" fill="#44616a">from 50</text>
        <text x={PAD.l} y={H - 8} fontSize="10" fill="#44616a">photo 1</text>
        <text x={W - PAD.r} y={H - 8} textAnchor="end" fontSize="10" fill="#44616a">photo {N}</text>
        {shown > 1 && <path d={path(raw.slice(0, shown))} fill="none" stroke="#6b7f84" strokeWidth="1.5" />}
        {raw.slice(0, shown).map((v, i) => (
          <circle key={i} cx={x(i)} cy={y(v)} r="2.6" fill="#6b7f84" />
        ))}
        {shown > 1 && <path d={path(smooth.slice(0, shown))} fill="none" stroke="#0e7480" strokeWidth="3.2" strokeLinejoin="round" />}
        <StateStrip label="Raw" states={rawStates} shown={shown} y0={H + 2} />
        <StateStrip label="Smoothed" states={smStates} shown={shown} y0={H + 26} />
        <text x={PAD.l} y={H + 60} fontSize="10" fill="#44616a">L = Low, W = Watch, C = Needs cleaning, &ndash; = not enough readings yet (needs 3)</text>
      </svg>
      </div>

      <ul className="series-key" aria-label="Chart key">
        <li><span className="key-dot" style={{ background: '#6b7f84' }} /> Raw reading (dots)</li>
        <li><span className="key-line" style={{ background: '#0e7480' }} /> Median of last 5 (smoothed)</li>
      </ul>

      <div className="counters" aria-live="polite">
        <div className="counter">
          <span className="counter-n">{rawChanges}</span>
          <span className="counter-l">state changes, raw thresholds</span>
          <span className="small muted">Now: {curRaw === null ? '–' : STATES[curRaw]}</span>
        </div>
        <div className="counter counter-good">
          <span className="counter-n">{smChanges}</span>
          <span className="counter-l">state changes, smoothed</span>
          <span className="small muted">Now: {curSm === null ? 'waiting for 3 readings' : STATES[curSm]}</span>
        </div>
      </div>
      <p className="small muted">
        Counters above are computed from this simulated series: state changes in raw {rawChanges} vs smoothed {smChanges}.
        Rules: Low below 20, Watch 20 to under 50, Needs cleaning 50 and above. Smoothed state uses a median of 5 and
        hysteresis (enter Needs cleaning at 50, leave at 35; enter Watch at 20, leave at 12) and shows a state only after
        3 readings.
      </p>

      <p className="callout">
        <strong>From our offline study:</strong> in our simulation on 76 drains &times; 20 photos, smoothing cut state
        flip-flops from 84 to 2. We did not show that it improves accuracy.
      </p>
    </Card>
  );
}
