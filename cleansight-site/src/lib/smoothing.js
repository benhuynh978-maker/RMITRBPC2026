// Drain-state smoothing used by the "Smoothing slider" demo.
// Rules (as specified for the project):
//   Levels: Low < 20, Watch 20 to <50, Needs cleaning >= 50 (raw thresholds).
//   Smoothing: median of the last 5 readings (fewer at the start).
//   Hysteresis on the smoothed value:
//     enter Needs cleaning at >= 50, leave it below 35
//     enter Watch at >= 20, leave it below 12
//   A state is only shown after at least 3 readings.

export const STATES = ['Low', 'Watch', 'Needs cleaning'];
export const MIN_READINGS = 3;

// Deterministic PRNG (mulberry32) so the demo series and counters are stable.
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gaussian(rand) {
  const u = Math.max(rand(), 1e-9);
  const v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

// Simulated blockage-% series: a slow build-up that hovers near the thresholds,
// plus sensor-like noise and occasional outliers.
export function makeSeries(seed = 7, n = 40) {
  const rand = mulberry32(seed);
  const out = [];
  for (let i = 0; i < n; i += 1) {
    const t = i / (n - 1);
    // slow trend: 14% -> ~55% with a dip in the middle (litter partly washed away)
    const trend = 14 + 41 * t - 10 * Math.sin(Math.PI * t * 2) * (t > 0.3 && t < 0.8 ? 1 : 0.3);
    let v = trend + gaussian(rand) * 6.5;
    if (rand() < 0.1) v += (rand() < 0.5 ? -1 : 1) * (14 + rand() * 14);
    out.push(Math.round(Math.min(100, Math.max(0, v)) * 10) / 10);
  }
  return out;
}

export function median(values) {
  const s = [...values].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function medianSmooth(series, window = 5) {
  return series.map((_, i) => median(series.slice(Math.max(0, i - window + 1), i + 1)));
}

export function rawState(v) {
  if (v >= 50) return 2;
  if (v >= 20) return 1;
  return 0;
}

// Returns an array of state indices (or null while warming up).
export function hysteresisStates(smoothed) {
  const out = [];
  let state = null;
  smoothed.forEach((v, i) => {
    if (i + 1 < MIN_READINGS) {
      out.push(null);
      return;
    }
    if (state === null) {
      state = rawState(v);
    } else if (state === 0) {
      if (v >= 50) state = 2;
      else if (v >= 20) state = 1;
    } else if (state === 1) {
      if (v >= 50) state = 2;
      else if (v < 12) state = 0;
    } else if (v < 35) {
      state = v < 12 ? 0 : 1;
    }
    out.push(state);
  });
  return out;
}

// Number of times the displayed state changes between consecutive shown states.
export function countChanges(states) {
  let changes = 0;
  let prev = null;
  states.forEach((s) => {
    if (s === null) return;
    if (prev !== null && s !== prev) changes += 1;
    prev = s;
  });
  return changes;
}
