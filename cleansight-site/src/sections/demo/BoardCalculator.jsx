import { useState } from 'react';
import Card from '../../components/Card.jsx';
import Badge from '../../components/Badge.jsx';

const MIN_BOARD_PX = 50; // below this the system refuses to calibrate
const REF_FOCAL_PX = 616; // focal-length-like constant of the reference test camera
const BOARDS = [
  { name: 'A3 board', side: 0.25 },
  { name: 'A4 backup', side: 0.15 },
];

const FIELDS = [
  { key: 'd', label: 'Distance to the farthest litter, D (m)', min: 1, max: 6, step: 0.1 },
  { key: 'fov', label: 'Camera horizontal field of view (degrees)', min: 20, max: 140, step: 1 },
  { key: 'w', label: 'Image width (pixels)', min: 320, max: 8000, step: 1 },
  { key: 'theta', label: 'Tilt angle, θ (degrees)', min: 0, max: 80, step: 1 },
];

function Chip({ name, side, s }) {
  const pass = s <= side;
  return (
    <span className={`verdict ${pass ? 'verdict-ok' : 'verdict-bad'}`}>
      {name} ({side.toFixed(2)} m side): {pass ? 'big enough' : 'too small'}
    </span>
  );
}

export default function BoardCalculator() {
  const [v, setV] = useState({ d: '3', fov: '66', w: '1920', theta: '30' });

  const nums = Object.fromEntries(Object.entries(v).map(([k, val]) => [k, val.trim() === '' ? NaN : Number(val)]));
  const errors = FIELDS.filter((f) => !(nums[f.key] >= f.min && nums[f.key] <= f.max));
  const valid = errors.length === 0;

  let fpx = 0;
  let sGeneric = 0;
  let sRef = 0;
  if (valid) {
    const cosT = Math.cos((nums.theta * Math.PI) / 180);
    fpx = nums.w / 2 / Math.tan((nums.fov * Math.PI) / 360);
    sGeneric = (MIN_BOARD_PX * nums.d) / (fpx * cosT);
    sRef = (MIN_BOARD_PX * nums.d) / (REF_FOCAL_PX * cosT);
  }

  return (
    <Card className="demo-card" title="Marker-board size calculator" badge={<Badge variant="demo">Demo data</Badge>}>
      <p className="muted">
        How big must the printed marker board be so the camera can still see it clearly from the farthest litter spot?
      </p>

      <form className="calc-form" onSubmit={(e) => e.preventDefault()} noValidate>
        {FIELDS.map((f) => {
          const bad = errors.includes(f);
          return (
            <div key={f.key} className="field">
              <label htmlFor={`calc-${f.key}`}>{f.label}</label>
              <input
                id={`calc-${f.key}`}
                type="number"
                inputMode="decimal"
                min={f.min}
                max={f.max}
                step={f.step}
                value={v[f.key]}
                aria-invalid={bad}
                aria-describedby={bad ? `calc-${f.key}-err` : undefined}
                onChange={(e) => setV({ ...v, [f.key]: e.target.value })}
              />
              {bad && (
                <span id={`calc-${f.key}-err`} className="field-error">
                  Enter a number from {f.min} to {f.max}.
                </span>
              )}
            </div>
          );
        })}
      </form>

      <div className="calc-out" aria-live="polite">
        {valid ? (
          <>
            <p className="calc-label">Minimum board side (from your camera settings)</p>
            <p className="calc-big">
              S<sub>min</sub> = {sGeneric.toFixed(3)} m <span className="calc-cm">({(sGeneric * 100).toFixed(1)} cm)</span>
            </p>
            <p className="small muted">
              S<sub>min</sub> = 50 &times; D / (f<sub>px</sub> &times; cos &theta;), where f<sub>px</sub> = (image width / 2) / tan(FOV / 2) ={' '}
              {fpx.toFixed(0)} px.
            </p>
            <div className="chip-row">
              {BOARDS.map((b) => (
                <Chip key={b.name} name={b.name} side={b.side} s={sGeneric} />
              ))}
            </div>

            <div className="calc-ref">
              <p className="calc-label">For the reference test camera (focal &asymp; 616 px)</p>
              <p className="calc-mid">
                S<sub>min</sub> = 50 &times; D / (616 &times; cos &theta;) = <strong>{sRef.toFixed(3)} m</strong>
              </p>
              <div className="chip-row">
                {BOARDS.map((b) => (
                  <Chip key={b.name} name={b.name} side={b.side} s={sRef} />
                ))}
              </div>
              <p className="small muted">
                The 616 px constant belongs to one reference camera, so it only applies to that camera. Use the result
                above for your own camera.
              </p>
            </div>
          </>
        ) : (
          <p className="muted">Fix the highlighted fields to see the result.</p>
        )}
      </div>

      <p className="callout">
        <strong>Why 50 px?</strong> We refuse to calibrate if the board is smaller than 50 px in the photo. The formula
        finds the smallest board that still appears 50 px wide at distance D.
      </p>
    </Card>
  );
}
