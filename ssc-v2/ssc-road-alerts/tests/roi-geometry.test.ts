import { describe, it, expect } from 'vitest';
import {
  aspectMismatch, clampPoint01, formatPolygonString, isValidPolygon, parsePolygonString, polygonArea, polygonSelfIntersects,
} from '../src/lib/roiGeometry';
import type { RoiPoint } from '../src/lib/roiGeometry';

const square: RoiPoint[] = [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]];

describe('polygonArea', () => {
  it('computes square, triangle and is winding independent', () => {
    expect(polygonArea(square)).toBeCloseTo(0.25, 12);
    expect(polygonArea([[0, 0], [1, 0], [0, 1]])).toBeCloseTo(0.5, 12);
    expect(polygonArea([...square].reverse())).toBeCloseTo(0.25, 12);
  });
  it('is 0 for collinear or empty input', () => {
    expect(polygonArea([[0, 0], [0.5, 0.5], [1, 1]])).toBe(0);
    expect(polygonArea([])).toBe(0);
  });
});

describe('isValidPolygon', () => {
  it('accepts a square in both windings and a valid L-shape', () => {
    expect(isValidPolygon(square)).toEqual({ ok: true, errors: [] });
    expect(isValidPolygon([...square].reverse()).ok).toBe(true);
    const l: RoiPoint[] = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.4], [0.3, 0.4], [0.3, 0.8], [0.1, 0.8]];
    expect(isValidPolygon(l)).toEqual({ ok: true, errors: [] });
  });
  it('rejects too few / too many points', () => {
    expect(isValidPolygon([[0, 0], [1, 1]]).ok).toBe(false);
    expect(isValidPolygon([]).ok).toBe(false);
    const many: RoiPoint[] = Array.from({ length: 65 }, (_, i) => [0.5 + 0.4 * Math.cos(i / 65 * 2 * Math.PI), 0.5 + 0.4 * Math.sin(i / 65 * 2 * Math.PI)]);
    const r = isValidPolygon(many);
    expect(r.ok).toBe(false);
    expect(r.errors.join(' ')).toContain('64');
    expect(isValidPolygon(many.slice(0, 64)).ok).toBe(true);
  });
  it('rejects NaN, Infinity, out-of-range and malformed points', () => {
    expect(isValidPolygon([[0, 0], [1, 0], [Number.NaN, 1]]).ok).toBe(false);
    expect(isValidPolygon([[0, 0], [1, 0], [Infinity, 1]]).ok).toBe(false);
    expect(isValidPolygon([[0, 0], [1, 0], [1.5, 1]]).errors).toContain('Coordinates must be between 0 and 1');
    expect(isValidPolygon([[0, 0], [1, 0], [0, -0.1]]).ok).toBe(false);
    expect(isValidPolygon([[0, 0], [1, 0], [0.5]]).ok).toBe(false);
    expect(isValidPolygon('nope').ok).toBe(false);
    expect(isValidPolygon(null).ok).toBe(false);
  });
  it('rejects zero-area collinear polygons', () => {
    const r = isValidPolygon([[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]]);
    expect(r.ok).toBe(false);
    expect(r.errors[0]).toContain('zero area');
  });
  it('rejects a bow-tie but allows boundary values 0 and 1', () => {
    const r = isValidPolygon([[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]);
    expect(r.ok).toBe(false);
    expect(r.errors).toContain('The polygon intersects itself — adjust the points');
    expect(isValidPolygon([[0, 0], [1, 0], [1, 1], [0, 1]]).ok).toBe(true);
  });
});

describe('polygonSelfIntersects', () => {
  it('treats touching as intersecting', () => {
    // đỉnh cuối trùng đỉnh thứ 2 (hai cạnh không kề chạm nhau tại một điểm)
    expect(polygonSelfIntersects([[0, 0], [0.5, 0.5], [1, 0], [1, 1], [0.5, 0.5]])).toBe(true);
    // hai cạnh không kề cùng nằm trên một đường thẳng và chồng lên nhau
    expect(polygonSelfIntersects([[0, 0], [0.6, 0], [0.6, 0.3], [0.4, 0.3], [0.4, 0], [0.9, 0], [0.9, 0.5], [0, 0.5]])).toBe(true);
  });
  it('detects a spike folding back on itself and ignores simple shapes', () => {
    expect(polygonSelfIntersects([[0.1, 0.1], [0.8, 0.1], [0.4, 0.1], [0.4, 0.8]])).toBe(true);
    expect(polygonSelfIntersects(square)).toBe(false);
    expect(polygonSelfIntersects([[0, 0], [1, 0], [0, 1]])).toBe(false);
  });
});

describe('clampPoint01', () => {
  it('clamps into [0,1] and maps NaN to 0', () => {
    expect(clampPoint01([-0.2, 1.7])).toEqual([0, 1]);
    expect(clampPoint01([0.3, 0.6])).toEqual([0.3, 0.6]);
    expect(clampPoint01([Number.NaN, 0.5])).toEqual([0, 0.5]);
  });
});

describe('parsePolygonString / formatPolygonString', () => {
  it('parses with extra whitespace and newlines', () => {
    const r = parsePolygonString('  0.25,0.25\n0.75,0.25\t 0.75,0.75   0.25,0.75 \n');
    expect(r).toEqual({ ok: true, points: square });
  });
  it('round-trips via format (4 decimals)', () => {
    const pts: RoiPoint[] = [[0.123456, 0.5], [1, 0.0001], [0, 0], [0.5, 1]];
    const text = formatPolygonString(pts);
    expect(text).toBe('0.1235,0.5 1,0.0001 0,0 0.5,1');
    expect(parsePolygonString(text)).toEqual({ ok: true, points: [[0.1235, 0.5], [1, 0.0001], [0, 0], [0.5, 1]] });
  });
  it('never emits -0', () => {
    expect(formatPolygonString([[-0.00001, 0.5]])).toBe('0,0.5');
  });
  it('reports bad tokens in English', () => {
    const bad = (s: string) => { const r = parsePolygonString(s); expect(r.ok).toBe(false); return r.ok ? '' : r.error; };
    expect(bad('')).toContain('empty');
    expect(bad('0.1,0.1 0.5 0.9,0.9')).toContain('"0.5"');
    expect(bad('0.1,0.1 0.5,0.5,0.7 0.9,0.9')).toContain('0.5,0.5,0.7');
    expect(bad('0,1,0,2 0.5,0.5 0.9,0.9')).toContain('expected x,y');
    expect(bad('0.1,0.1 a,0.5 0.9,0.9')).toContain('is not a number');
    expect(bad('0.1,0.1 0.5,0.5 nan,0.9')).toContain('is not a number');
    expect(bad('0.1,0.1 0.5,0.5 inf,0.9')).toContain('is not a number');
    expect(bad('0.1,0.1 0.5,0.5 1e999,0.9')).toContain('too large');
    expect(bad('0.1,0.1 0.5,0.5')).toContain('At least 3');
    expect(bad('0.1,0.1 0.5,0.5 1.5,0.9')).toContain('outside the 0–1 range');
    expect(bad(Array(65).fill('0.5,0.5').join(' '))).toContain('At most 64');
  });
  it('rejects comma decimals', () => {
    expect(parsePolygonString('0,1;0,2 0,3;0,4 0,5;0,6').ok).toBe(false);
  });
  it('accepts exponent and leading-dot numbers', () => {
    expect(parsePolygonString('.5,1e-1 0.5,0.9 0.9,5e-1')).toEqual({ ok: true, points: [[0.5, 0.1], [0.5, 0.9], [0.9, 0.5]] });
  });
});

describe('aspectMismatch', () => {
  it('uses relative ratio tolerance', () => {
    expect(aspectMismatch({ w: 1600, h: 1200 }, { w: 800, h: 600 })).toBe(false);
    expect(aspectMismatch({ w: 1600, h: 900 }, { w: 800, h: 600 })).toBe(true);
    expect(aspectMismatch({ w: 810, h: 600 }, { w: 800, h: 600 })).toBe(false);
    expect(aspectMismatch({ w: 830, h: 600 }, { w: 800, h: 600 })).toBe(true);
    expect(aspectMismatch({ w: 830, h: 600 }, { w: 800, h: 600 }, 0.05)).toBe(false);
  });
  it('is false for unknown/invalid sizes', () => {
    expect(aspectMismatch({ w: 0, h: 0 }, { w: 800, h: 600 })).toBe(false);
    expect(aspectMismatch({ w: 800, h: 600 }, { w: Number.NaN, h: 600 })).toBe(false);
  });
});
