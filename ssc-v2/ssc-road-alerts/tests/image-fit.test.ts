import { describe, it, expect } from 'vitest';
import { fitSize, qualitySteps } from '../src/lib/imageFit';

describe('fitSize', () => {
  it('shrinks landscape and portrait to the longest side, keeping aspect', () => {
    expect(fitSize(6000, 4000, 1600)).toEqual({ width: 1600, height: 1067 });
    expect(fitSize(4000, 6000, 1600)).toEqual({ width: 1067, height: 1600 });
    expect(fitSize(1000, 1000, 500)).toEqual({ width: 500, height: 500 });
  });
  it('never upscales', () => {
    expect(fitSize(800, 600, 1600)).toEqual({ width: 800, height: 600 });
    expect(fitSize(1600, 900, 1600)).toEqual({ width: 1600, height: 900 });
  });
  it('returns integers >= 1 even for extreme aspect ratios', () => {
    expect(fitSize(10000, 3, 1600)).toEqual({ width: 1600, height: 1 });
    for (const [w, h] of [[5333, 3001], [1601, 1599], [4032, 3024]] as const) {
      const f = fitSize(w, h, 1600);
      expect(Number.isInteger(f.width) && Number.isInteger(f.height)).toBe(true);
      expect(Math.max(f.width, f.height)).toBeLessThanOrEqual(1600);
      expect(Math.min(f.width, f.height)).toBeGreaterThanOrEqual(1);
    }
  });
  it('rejects invalid input', () => {
    expect(() => fitSize(0, 10, 100)).toThrow(RangeError);
    expect(() => fitSize(10, NaN, 100)).toThrow(RangeError);
    expect(() => fitSize(10, 10, 0)).toThrow(RangeError);
  });
  it('quality steps descend from 0.9 to 0.6', () => {
    expect([...qualitySteps]).toEqual([0.9, 0.8, 0.7, 0.6]);
  });
});
