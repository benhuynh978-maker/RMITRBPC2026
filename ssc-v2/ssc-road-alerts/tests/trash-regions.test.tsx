import { describe, it, expect } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { normalizeTrashRegions, summarizeTrashRegions } from '../src/services/normalizeTrash';
import { normalizeCameras } from '../src/services/mapService';
import { TrashRegionSummary } from '../src/components/monitoring/TrashRegionSummary';
import { demoCameras, demoRoads } from '../src/mocks/monitoring';
import city from '../src/mocks/city.json';
import type { Camera } from '../src/models/camera';

const ring = [[106.7, 10.77], [106.70001, 10.77], [106.70001, 10.77001]];
const region = { kind: 'street', area_m2: 0.5, ring };
const cam = (extra: object): Camera => ({ camera_id: 'C1', geometry: { type: 'Point', coordinates: [106.7, 10.77] }, ...extra }) as Camera;

describe('trash_regions (optional litter outlines)', () => {
  it('is optional: absent stays undefined, empty list is allowed', () => {
    expect(normalizeTrashRegions(undefined)).toBeUndefined();
    expect(normalizeTrashRegions(null)).toBeUndefined();
    expect(normalizeTrashRegions([])).toEqual([]);
    expect(normalizeTrashRegions([region])).toEqual([region]);
  });
  it('rejects malformed regions instead of drawing them', () => {
    for (const bad of [
      'x', [1], [{ ...region, kind: 'other' }], [{ ...region, area_m2: -1 }], [{ ...region, area_m2: NaN }], [{ ...region, area_m2: '1' }],
      [{ ...region, ring: ring.slice(0, 2) }], [{ ...region, ring: [[200, 10], [1, 1], [2, 2]] }], [{ ...region, ring: [[1, 100], [1, 1], [2, 2]] }],
      [{ ...region, ring: [[1, 1], [1, 'a'], [2, 2]] }], Array.from({ length: 101 }, () => region),
    ]) expect(() => normalizeTrashRegions(bad)).toThrow();
  });
  it('sums regions per camera and survives the camera normalizer', () => {
    expect(summarizeTrashRegions(undefined)).toEqual({ count: 0, total_m2: 0 });
    expect(summarizeTrashRegions([region, { ...region, area_m2: 0.25 }] as never)).toEqual({ count: 2, total_m2: 0.75 });
    expect(normalizeCameras({ cameras: [cam({ trash_regions: [region] })] })[0].trash_regions).toEqual([region]);
    expect(() => normalizeCameras({ cameras: [cam({ trash_regions: [{ kind: 'street' }] })] })).toThrow();
    expect(normalizeCameras({ cameras: [cam({})] })[0].trash_regions).toBeUndefined();
  });
  it('detail summary: hidden without the field, explicit when empty, counts and m² otherwise', () => {
    const html = (c: Camera) => renderToStaticMarkup(createElement(TrashRegionSummary, { camera: c }));
    expect(html(cam({}))).toBe('');
    expect(html(cam({ trash_regions: [] }))).toContain('No litter outlined');
    const text = html(cam({ trash_regions: [region, { ...region, kind: 'drain', area_m2: 1.5 }] }));
    expect(text).toContain('<strong>2</strong> regions');
    expect(text).toContain('2 m²');
    expect(text).toContain('(on the drain zone)');
  });
});

describe('the simulated city used by the "Demo simulation" source', () => {
  it('is flagged simulated and has the scale of a city deployment', () => {
    expect(city.simulated).toBe(true);
    expect(demoCameras).toHaveLength(100);
    expect(demoRoads.length).toBeGreaterThanOrEqual(25);
    expect(new Set(demoCameras.map(c => c.camera_id)).size).toBe(100);
    expect(new Set(demoRoads.map(r => r.road_id)).size).toBe(demoRoads.length);
  });
  it('links every camera to a road and uses only generic names (no real streets, no competition names)', () => {
    const roadIds = new Set(demoRoads.map(r => r.road_id));
    expect(demoCameras.every(c => c.road_id && roadIds.has(c.road_id))).toBe(true);
    expect(demoRoads.every(r => /^Road R-\d\d \(sample\)$/.test(r.road_name ?? ''))).toBe(true);
    expect(demoCameras.every(c => /^Drain inlet \d{3}$/.test(c.name ?? ''))).toBe(true);
    expect(JSON.stringify(city)).not.toMatch(/SSC|Sustainable|Challenge|RMIT|RBPC/i);
  });
  it('marks every analysed camera as a simulation, and roads say so through the backend description', () => {
    expect(demoCameras.filter(c => c.monitoring).every(c => c.analysis_source === 'simulation')).toBe(true);
    expect(demoRoads.filter(r => r.data_quality !== 'unknown').every(r => r.description?.startsWith('[Simulated data via the test API]'))).toBe(true);
  });
  it('keeps the backend aggregation consistent: drain_summary matches the cameras on each road', () => {
    for (const road of demoRoads) {
      const linked = demoCameras.filter(c => c.road_id === road.road_id);
      const s = road.drain_summary!;
      expect(s.clear + s.watch + s.clean + s.unknown).toBe(linked.length);
      for (const k of ['clear', 'watch', 'clean', 'unknown'] as const) expect(s[k]).toBe(linked.filter(c => c.drain_state?.state === k).length);
    }
  });
  it('covers every situation a customer would see, and litter outlines have areas', () => {
    const states = new Set<string | undefined>(demoCameras.map(c => (c.status === 'offline' ? 'offline' : c.drain_state?.state)));
    for (const k of ['clear', 'watch', 'clean', 'unknown', 'offline']) expect(states.has(k)).toBe(true);
    expect(new Set(demoRoads.map(r => r.severity)).size).toBeGreaterThanOrEqual(4);
    const withRegions = demoCameras.filter(c => c.trash_regions?.length);
    expect(withRegions.length).toBeGreaterThan(80);
    expect(withRegions.every(c => c.trash_regions!.every(r => r.area_m2 > 0 && r.ring.length >= 3))).toBe(true);
  });
});
