import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { DrainPhotoTest } from '../src/components/monitoring/DrainPhotoTest';

const noop = () => undefined;
const roi = { polygon: [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]], source: 'manual', calibrated_at: '2026-10-30T00:00:00.000Z' };

describe('DrainPhotoTest (static render smoke)', () => {
  it('renders the form without a ROI, with the legacy-formula notice', () => {
    const html = renderToStaticMarkup(<DrainPhotoTest camera={{ camera_id: 'CAM-001' }} onDone={noop} />);
    expect(html).toContain('Send a test photo and see the result');
    expect(html).toContain('Choose a photo with the SAME framing as the image used to draw the drain zone. The photo is stored on the v2 server running on this machine.');
    expect(html).toContain('This camera has no drain zone: the result will use the old formula (less reliable when the drain is fully covered).');
    expect(html).toContain('type="file"');
    expect(html).toContain('accept="image/*"');
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Send and analyse<\/button>/);
    expect(html).not.toContain('role="alert"');
    expect(html).not.toContain('role="status"');
    expect(html).not.toContain('<img'); // no image selected yet
  });
  it('omits the notice when the camera has a ROI', () => {
    const html = renderToStaticMarkup(<DrainPhotoTest camera={{ camera_id: 'CAM-001', drain_roi: roi }} onDone={noop} />);
    expect(html).not.toContain('This camera has no drain zone');
    expect(html).toContain('Send and analyse');
  });
  it('has a labelled file input and avoids forbidden wording', () => {
    const html = renderToStaticMarkup(<DrainPhotoTest camera={{ camera_id: 'CAM-001' }} onDone={noop} />);
    const id = /<input[^>]*id="([^"]+)"[^>]*type="file"/.exec(html)?.[1] ?? /<input[^>]*type="file"[^>]*id="([^"]+)"/.exec(html)?.[1];
    expect(id).toBeTruthy();
    expect(html).toContain(`for="${id}"`);
    expect(html.toLowerCase()).not.toMatch(/flood (forecast|prediction)/);
    expect(html.toLowerCase()).not.toMatch(/real[- ]time/);
  });
});
