import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { DrainRoiEditor, DrainRoiPanel } from '../src/components/monitoring/DrainRoiEditor';
import type { RoiCamera } from '../src/components/monitoring/DrainRoiEditor';

const base: RoiCamera = { camera_id: 'CAM-001', name: 'Cam' };
const withImage: RoiCamera = { ...base, images: { original_url: '/api/images/a.jpg' } };
const withRoi: RoiCamera = { ...withImage, drain_roi: { polygon: [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]], source: 'manual', calibrated_at: '2026-10-30T00:00:00.000Z' } };
const noop = () => undefined;

describe('DrainRoiEditor (static render smoke)', () => {
  it('renders open by default (demo-friendly) with or without images/ROI', () => {
    for (const camera of [base, withImage, withRoi]) {
      const html = renderToStaticMarkup(<DrainRoiEditor camera={camera} onSaved={noop} />);
      expect(html).toContain('<details');
      expect(html).toContain(' open');
      expect(html).toContain('Draw / calibrate the drain inlet zone (ROI)');
      expect(html).toContain('roi-body'); // open by default, so the body renders immediately
    }
  });
  it('panel: camera photo radio is disabled without original_url and enabled with it', () => {
    const without = renderToStaticMarkup(<DrainRoiPanel camera={base} onSaved={noop} />);
    expect(without).toMatch(/<input[^>]*type="radio"[^>]*disabled=""/);
    expect(without).toContain('Upload an image from this device');
    expect(without).toContain('type="file"');
    const withUrl = renderToStaticMarkup(<DrainRoiPanel camera={withImage} onSaved={noop} />);
    expect(withUrl).not.toContain('type="file"');
    expect(withUrl).toContain('src="/api/images/a.jpg"');
  });
  it('panel: save disabled initially, remove button only when a saved ROI exists, legend present', () => {
    const none = renderToStaticMarkup(<DrainRoiPanel camera={withImage} onSaved={noop} />);
    expect(none).toMatch(/<button[^>]*disabled=""[^>]*>Save drain zone<\/button>/);
    expect(none).not.toContain('Remove drain zone');
    expect(none).toContain('0 points (3–64)');
    expect(none).toContain('Current ROI: none');
    const roi = renderToStaticMarkup(<DrainRoiPanel camera={withRoi} onSaved={noop} />);
    expect(roi).toContain('Remove drain zone');
    expect(roi).toContain('Current ROI (dashed)');
    expect(roi).not.toMatch(/<button[^>]*disabled=""[^>]*>Start from saved ROI/);
    expect(roi.toLowerCase()).not.toMatch(/flood (forecast|prediction)/);
    expect(roi.toLowerCase()).not.toMatch(/real[- ]time/);
  });
});
