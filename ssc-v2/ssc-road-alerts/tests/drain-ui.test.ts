import { describe, it, expect } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { normalizeDrainRoi, normalizeDrainState, normalizeDrainSummary } from '../src/services/normalizeDrain';
import { normalizeCameras } from '../src/services/mapService';
import { normalizeAlerts } from '../src/services/normalizeAlerts';
import { DRAIN_LABEL, DRAIN_ORDER, drainReasonText, drainThresholdsText, formatPct } from '../src/config/drain';
import { DrainStatusCard } from '../src/components/monitoring/DrainStatusCard';
import { DrainSummaryRow, drainSummaryText } from '../src/components/monitoring/DrainSummaryRow';
import type { Camera } from '../src/models/camera';

const roi = { polygon: [[0.1, 0.2], [0.8, 0.2], [0.5, 0.9]], source: 'manual', calibrated_at: '2026-10-20T03:00:00.000Z' };
const state = { state: 'watch', window_count: 5, updated_at: '2026-10-20T03:10:00.000Z', since: '2026-10-20T03:00:00.000Z', smoothed_blockage_pct: 37.5, needed: 3, reason: 'ok',
  roi_calibrated: true, blockage_method: 'roi', flags: { no_trash_in_roi: false, low_certainty: true }, evidence_observation_id: 'o1', evidence_captured_at: '2026-10-20T03:09:00.000Z' };
const summary = { clear: 3, watch: 2, clean: 1, unknown: 1, worst_state: 'clean', worst_camera_id: 'C1' };
const fallback = { state: 'unknown', window_count: 0, reason: 'no_data' };
const cam = { camera_id: 'C1', geometry: { type: 'Point', coordinates: [106, 10] } };
const road = { road_id: 'R1', severity: 3, geometry: { type: 'LineString', coordinates: [[106.7, 10.77], [106.71, 10.78]] } };
const camera = (extra: Partial<Camera> = {}): Camera => ({ camera_id: 'C1', geometry: { type: 'Point', coordinates: [106, 10] }, ...extra });
const html = (c: Camera) => renderToStaticMarkup(createElement(DrainStatusCard, { camera: c }));

describe('normalizeDrainRoi', () => {
  it('accepts a valid ROI and ignores extra keys', () => {
    expect(normalizeDrainRoi({ ...roi, extra: 1 })).toEqual(roi);
    expect(normalizeDrainRoi({ ...roi, source: 'ai' })?.source).toBe('ai');
  });
  it('drops malformed ROI instead of throwing', () => {
    const bad = [undefined, null, 'x', [], {}, { ...roi, polygon: roi.polygon.slice(0, 2) }, { ...roi, polygon: [...roi.polygon, [1.01, 0.5]] },
      { ...roi, polygon: [[0, 0], [1, 0], [NaN, 1]] }, { ...roi, polygon: [[0, 0], [1, 0], [0, 1, 1]] }, { ...roi, polygon: Array(65).fill([0.5, 0.5]) },
      { ...roi, source: 'robot' }, { ...roi, calibrated_at: 'yesterday' }, { ...roi, calibrated_at: undefined }];
    for (const b of bad) expect(normalizeDrainRoi(b)).toBeUndefined();
  });
  it('accepts boundary values 0, 1 and 3/64 points', () => {
    expect(normalizeDrainRoi({ ...roi, polygon: [[0, 0], [1, 0], [1, 1]] })).toBeDefined();
    expect(normalizeDrainRoi({ ...roi, polygon: Array(64).fill([0, 1]) })).toBeDefined();
  });
});

describe('normalizeDrainState', () => {
  it('keeps a valid state and drops unknown keys', () => {
    expect(normalizeDrainState({ ...state, junk: 1 })).toEqual(state);
    expect(normalizeDrainState({ state: 'clear', window_count: 0 })).toEqual({ state: 'clear', window_count: 0 });
  });
  it('is undefined when absent, unknown/no_data when malformed', () => {
    expect(normalizeDrainState(undefined)).toBeUndefined();
    expect(normalizeDrainState(null)).toBeUndefined();
    const bad = ['x', [], {}, { state: 'clean' }, { ...state, state: 'danger' }, { ...state, state: 'constructor' }, { ...state, window_count: -1 }, { ...state, window_count: 1.5 },
      { ...state, window_count: NaN }, { ...state, smoothed_blockage_pct: 100.1 }, { ...state, smoothed_blockage_pct: -1 }, { ...state, smoothed_blockage_pct: NaN },
      { ...state, reason: 'weird' }, { ...state, blockage_method: 'x' }, { ...state, since: 'nope' }, { ...state, flags: 'yes' }, { ...state, flags: { low_certainty: 'yes' } }];
    for (const b of bad) expect(normalizeDrainState(b), JSON.stringify(b)).toEqual(fallback);
  });
  it('accepts range edges 0 and 100', () => {
    expect(normalizeDrainState({ ...state, smoothed_blockage_pct: 0 })?.smoothed_blockage_pct).toBe(0);
    expect(normalizeDrainState({ ...state, smoothed_blockage_pct: 100 })?.smoothed_blockage_pct).toBe(100);
  });
  it('returns an independent fallback object each time', () => {
    const a = normalizeDrainState('x'); const b = normalizeDrainState('x');
    expect(a).not.toBe(b);
  });
});

describe('normalizeDrainSummary', () => {
  it('accepts valid summary (null worst camera allowed) and ignores extra keys', () => {
    expect(normalizeDrainSummary({ ...summary, extra: 1 })).toEqual(summary);
    expect(normalizeDrainSummary({ clear: 0, watch: 0, clean: 0, unknown: 0, worst_state: 'unknown', worst_camera_id: null })?.worst_camera_id).toBeNull();
  });
  it('drops malformed summary', () => {
    const bad = [undefined, null, 'x', [], {}, { ...summary, clear: -1 }, { ...summary, watch: 1.2 }, { ...summary, clean: NaN }, { ...summary, unknown: '1' },
      { ...summary, worst_state: 'bad' }, { ...summary, worst_camera_id: 5 }, { ...summary, worst_camera_id: undefined }];
    for (const b of bad) expect(normalizeDrainSummary(b)).toBeUndefined();
  });
});

describe('drain config helpers', () => {
  it('maps every state to the confirmed English label and never the raw code', () => {
    expect(DRAIN_LABEL).toEqual({ clear: 'Low', watch: 'Watch', clean: 'Needs cleaning', unknown: 'Unknown' });
    expect([...DRAIN_ORDER].sort()).toEqual(['clean', 'clear', 'unknown', 'watch']);
  });
  it('explains reasons', () => {
    expect(drainReasonText({ reason: 'collecting', window_count: 2, needed: 3 })).toBe('Collecting: 2/3 valid readings');
    expect(drainReasonText({ reason: 'collecting', window_count: 1 })).toBe('Collecting: 1/3 valid readings');
    expect(drainReasonText({ reason: 'stale', window_count: 4 })).toBe('Data is stale (over 15 minutes old) or the camera is disconnected');
    expect(drainReasonText({ reason: 'no_data', window_count: 0 })).toBe('No readings yet for the current drain zone');
    expect(drainReasonText({ reason: 'ok', window_count: 5 })).toBe('');
    expect(drainReasonText(undefined)).toBe('');
  });
  it('shows thresholds from the policy and formats percentages with a decimal point', () => {
    expect(drainThresholdsText()).toContain('≥ 50%');
    expect(drainThresholdsText()).toContain('< 35%');
    expect(drainThresholdsText()).toContain('≥ 20%');
    expect(drainThresholdsText()).toContain('< 12%');
    expect(formatPct(37.5)).toBe('37.5');
    expect(formatPct(40)).toBe('40');
    expect(formatPct(12.345)).toBe('12.3');
  });
});

describe('normalizeCameras / normalizeAlerts integration', () => {
  it('keeps drain_roi and drain_state from the API', () => {
    const [c] = normalizeCameras({ cameras: [{ ...cam, drain_roi: roi, drain_state: state }] });
    expect(c.drain_roi).toEqual(roi);
    expect(c.drain_state).toEqual(state);
  });
  it('camera without drain fields still normalizes with drain_state undefined', () => {
    const [c] = normalizeCameras({ cameras: [cam] });
    expect(c.camera_id).toBe('C1');
    expect(c.drain_state).toBeUndefined();
    expect(c.drain_roi).toBeUndefined();
  });
  it('malformed drain blocks do not break the list; existing validation still throws', () => {
    const rows = normalizeCameras({ cameras: [{ ...cam, drain_roi: { polygon: [] }, drain_state: { state: 'clear' } }, { ...cam, camera_id: 'C2' }] });
    expect(rows).toHaveLength(2);
    expect(rows[0].drain_roi).toBeUndefined();
    expect(rows[0].drain_state).toEqual(fallback);
    expect(() => normalizeCameras({ cameras: [{ ...cam, geometry: { type: 'Point', coordinates: [10, 106] }, drain_state: state }] })).toThrow();
  });
  it('keeps drain_summary on roads; drops a malformed one; still strict on severity', () => {
    expect(normalizeAlerts([{ ...road, drain_summary: summary }])[0].drain_summary).toEqual(summary);
    expect(normalizeAlerts([road])[0].drain_summary).toBeUndefined();
    expect(normalizeAlerts([{ ...road, drain_summary: { clear: 'x' } }])[0].drain_summary).toBeUndefined();
    expect(() => normalizeAlerts([{ ...road, severity: 'bogus', drain_summary: summary }])).toThrow();
  });
});

describe('drain components (static render)', () => {
  it('renders smoothed state with label, percent, window, ROI line, flags and method', () => {
    const out = html(camera({ drain_state: normalizeDrainState(state), drain_roi: normalizeDrainRoi(roi) }));
    expect(out).toContain('Drain status (smoothed)');
    expect(out).toContain('Watch');
    expect(out).toContain('aria-label="Drain status: Watch"');
    expect(out).toContain('37.5%');
    expect(out).toContain('Based on 5/5 latest readings (needs ≥ 3)');
    expect(out).toContain('Drain zone calibrated (drawn by hand), version');
    expect(out).toContain('Low model certainty');
    expect(out).not.toContain('No litter in the drain zone');
    expect(out).toContain('How it is calculated');
    expect(out).toContain('Reference indicator only');
    expect(out).not.toMatch(/flood (forecast|prediction)|real[- ]time/i);
  });
  it('treats missing drain_state as unknown with the no_data reason and legacy ROI warning', () => {
    const out = html(camera());
    expect(out).toContain('Unknown');
    expect(out).toContain('No readings yet for the current drain zone');
    expect(out).toContain('Drain zone not calibrated — using the old formula');
    expect(out).not.toContain('Smoothed drain inlet coverage');
  });
  it('shows the collecting reason and hides the percentage for unknown', () => {
    const out = html(camera({ drain_state: { state: 'unknown', window_count: 2, needed: 3, reason: 'collecting', smoothed_blockage_pct: 80 } }));
    expect(out).toContain('Collecting: 2/3 valid readings');
    expect(out).not.toContain('80');
  });
  it('shows the AI-proposed source and the no-trash flag', () => {
    const out = html(camera({ drain_state: { state: 'clear', window_count: 3, smoothed_blockage_pct: 0, flags: { no_trash_in_roi: true } },
      drain_roi: { polygon: [[0, 0], [1, 0], [1, 1]], source: 'ai', calibrated_at: roi.calibrated_at } }));
    expect(out).toContain('suggested by AI');
    expect(out).toContain('No litter in the drain zone in the latest reading');
    expect(out).toContain('0%');
  });
  it('summary row: compact text lists only non-zero parts, renders nothing when empty', () => {
    expect(drainSummaryText(summary as never)).toBe('Drains: 1 needs cleaning · 2 watch · 3 low · 1 unknown');
    expect(drainSummaryText({ ...summary, clear: 0, unknown: 0 } as never)).toBe('Drains: 1 needs cleaning · 2 watch');
    expect(drainSummaryText(undefined)).toBe('');
    const empty = { clear: 0, watch: 0, clean: 0, unknown: 0, worst_state: 'unknown', worst_camera_id: null } as never;
    expect(renderToStaticMarkup(createElement(DrainSummaryRow, { summary: undefined, compact: true }))).toBe('');
    expect(renderToStaticMarkup(createElement(DrainSummaryRow, { summary: empty }))).toBe('');
    expect(renderToStaticMarkup(createElement(DrainSummaryRow, { summary: summary as never, compact: true }))).toContain('Drains: 1 needs cleaning');
  });
  it('summary row: full variant shows labels and the worst camera', () => {
    const out = renderToStaticMarkup(createElement(DrainSummaryRow, { summary: summary as never }));
    expect(out).toContain('Needs cleaning');
    expect(out).toContain('Worst');
    expect(out).toContain('camera C1');
    expect(out).not.toMatch(/>clean</);
  });
});
