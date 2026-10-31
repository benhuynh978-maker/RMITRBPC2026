import { describe, it, expect, afterEach, vi } from 'vitest';
import { buildRoiPayload, hasAdminKey, removeDrainRoi, saveDrainRoi, setAdminKey } from '../src/services/roiService';
import type { FetchImpl } from '../src/services/roiService';

const poly: [number, number][] = [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const recorder = (res: () => Response | Promise<Response>) => {
  const calls: { url: string; init: RequestInit }[] = [];
  const fn: FetchImpl = async (url, init) => { calls.push({ url, init: init ?? {} }); return res(); };
  return { fn, calls };
};

afterEach(() => setAdminKey(null));

describe('buildRoiPayload', () => {
  it('has exactly polygon and source, no calibrated_at', () => {
    const p = buildRoiPayload(poly, 'manual');
    expect(p).toEqual({ drain_roi: { polygon: poly, source: 'manual' } });
    expect(Object.keys(p.drain_roi!)).toEqual(['polygon', 'source']);
    expect(JSON.stringify(p)).not.toContain('calibrated_at');
    expect(buildRoiPayload(poly).drain_roi!.source).toBe('manual');
  });
  it('copies the polygon rather than aliasing it', () => {
    const p = buildRoiPayload(poly);
    expect(p.drain_roi!.polygon).not.toBe(poly);
    expect(p.drain_roi!.polygon[0]).not.toBe(poly[0]);
  });
});

describe('roiService', () => {
  it('PATCHes the encoded camera url with the payload and returns the camera', async () => {
    const camera = { camera_id: 'CAM 1/x', drain_roi: { polygon: poly, source: 'manual', calibrated_at: '2026-10-30T00:00:00Z' } };
    const { fn, calls } = recorder(() => json(200, camera));
    const r = await saveDrainRoi('CAM 1/x', poly, 'manual', fn);
    expect(r).toEqual({ ok: true, camera });
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('/api/cameras/CAM%201%2Fx');
    expect(calls[0].init.method).toBe('PATCH');
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ drain_roi: { polygon: poly, source: 'manual' } });
    const headers = calls[0].init.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['X-API-Key']).toBeUndefined();
  });
  it('removeDrainRoi sends drain_roi: null', async () => {
    const { fn, calls } = recorder(() => json(200, { camera_id: 'C' }));
    expect((await removeDrainRoi('C', fn)).ok).toBe(true);
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ drain_roi: null });
  });
  it('401 -> needsKey; then with a key the X-API-Key header is sent', async () => {
    const first = await saveDrainRoi('C', poly, 'manual', recorder(() => json(401, { error: 'Invalid X-API-Key' })).fn);
    expect(first).toMatchObject({ ok: false, status: 401, needsKey: true });
    expect(hasAdminKey()).toBe(false);
    setAdminKey('  secret  ');
    expect(hasAdminKey()).toBe(true);
    const { fn, calls } = recorder(() => json(200, { camera_id: 'C' }));
    expect((await saveDrainRoi('C', poly, 'manual', fn)).ok).toBe(true);
    expect((calls[0].init.headers as Record<string, string>)['X-API-Key']).toBe('secret');
  });
  it('a rejected key is forgotten and reported as wrong', async () => {
    setAdminKey('wrong');
    const r = await removeDrainRoi('C', recorder(() => json(401, { error: 'Invalid X-API-Key' })).fn);
    expect(r).toMatchObject({ ok: false, needsKey: true });
    expect(r.ok ? '' : r.error).toContain('Wrong admin key');
    expect(hasAdminKey()).toBe(false);
  });
  it('setAdminKey(null/blank) clears the key', () => {
    setAdminKey('k'); setAdminKey(''); expect(hasAdminKey()).toBe(false);
    setAdminKey('k'); setAdminKey(null); expect(hasAdminKey()).toBe(false);
  });
  it('never touches web storage', () => {
    const spy = vi.fn();
    vi.stubGlobal('localStorage', { setItem: spy, getItem: spy });
    vi.stubGlobal('sessionStorage', { setItem: spy, getItem: spy });
    setAdminKey('secret');
    expect(spy).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
  it('passes 400 messages through, maps 404, falls back when body is not JSON', async () => {
    const bad = await saveDrainRoi('C', poly, 'manual', recorder(() => json(400, { error: 'drain_roi.polygon has zero area' })).fn);
    expect(bad).toEqual({ ok: false, status: 400, error: 'drain_roi.polygon has zero area' });
    const missing = await saveDrainRoi('C', poly, 'manual', recorder(() => json(404, { error: 'not found' })).fn);
    expect(missing).toEqual({ ok: false, status: 404, error: 'The camera is no longer on the server' });
    const conflict = await saveDrainRoi('C', poly, 'manual', recorder(() => json(409, { error: 'The camera still has pending AI jobs' })).fn);
    expect(conflict).toMatchObject({ status: 409, error: 'The camera still has pending AI jobs' });
    const html = await saveDrainRoi('C', poly, 'manual', recorder(() => new Response('<html>', { status: 502 })).fn);
    expect(html).toMatchObject({ ok: false, status: 502 });
    expect(html.ok ? '' : html.error).toContain('502');
  });
  it('maps network failure', async () => {
    const r = await saveDrainRoi('C', poly, 'manual', async () => { throw new TypeError('Failed to fetch'); });
    expect(r).toMatchObject({ ok: false, status: 0 });
    expect(r.ok ? '' : r.error).toContain('Could not connect to the server');
  });
  it('aborts after the timeout', async () => {
    const hang: FetchImpl = (_url, init) => new Promise((_res, rej) => {
      init?.signal?.addEventListener('abort', () => rej(new DOMException('aborted', 'AbortError')));
    });
    const r = await saveDrainRoi('C', poly, 'manual', hang, 30);
    expect(r).toMatchObject({ ok: false, status: 0 });
    expect(r.ok ? '' : r.error).toContain('did not respond');
  });
});
