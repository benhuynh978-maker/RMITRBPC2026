import { describe, it, expect } from 'vitest';
import {
  CaptureError, captureEndpoint, makeObservationId, resizeToJpeg, uploadCapture, waitForAnalysis,
} from '../src/services/captureService';
import type { DecodedImage, FetchImpl, ResizeEnv } from '../src/services/captureService';

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const SERVER_ID_RULE = /^[A-Za-z0-9_-]{1,80}$/; // server/input.js id()
const FIXED = new Date('2026-10-30T08:00:00.000Z');
const hangUntilAbort: FetchImpl = (_u, init) => new Promise((_res, rej) => {
  init?.signal?.addEventListener('abort', () => rej(new DOMException('aborted', 'AbortError')));
});

describe('makeObservationId', () => {
  it('matches the server id() rule and is unique over 1000 calls', () => {
    const ids = new Set<string>();
    for (let i = 0; i < 1000; i++) {
      const id = makeObservationId();
      expect(id).toMatch(SERVER_ID_RULE);
      ids.add(id);
    }
    expect(ids.size).toBe(1000);
  });
  it('is unique even with a frozen clock', () => {
    const ids = new Set(Array.from({ length: 1000 }, () => makeObservationId(1_700_000_000_000)));
    expect(ids.size).toBe(1000);
  });
});

describe('captureEndpoint', () => {
  it('maps the cameras base to the esp32 capture route and encodes the id', () => {
    expect(captureEndpoint('CAM-001', '/api/cameras')).toBe('/api/esp32/cameras/CAM-001/capture');
    expect(captureEndpoint('a b', 'http://h:8010/api/cameras/')).toBe('http://h:8010/api/esp32/cameras/a%20b/capture');
    expect(captureEndpoint('X', '/weird')).toBe('/api/esp32/cameras/X/capture');
  });
});

describe('uploadCapture', () => {
  const blob = new Blob([new Uint8Array([0xff, 0xd8, 1, 2, 0xff, 0xd9])], { type: 'image/jpeg' });
  const recorder = (res: () => Response | Promise<Response>) => {
    const calls: { url: string; init: RequestInit }[] = [];
    const fn: FetchImpl = async (url, init) => { calls.push({ url, init: init ?? {} }); return res(); };
    return { fn, calls };
  };

  it('sends exactly one POST with URL, headers and the blob', async () => {
    const { fn, calls } = recorder(() => json(202, { observation: {}, duplicate: false }));
    const r = await uploadCapture('CAM-001', blob, { fetchImpl: fn, now: () => FIXED });
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('/api/esp32/cameras/CAM-001/capture');
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBe(blob);
    const h = calls[0].init.headers as Record<string, string>;
    expect(h['Content-Type']).toBe('image/jpeg');
    expect(h['X-Captured-At']).toBe('2026-10-30T08:00:00.000Z');
    expect(h['X-Observation-Id']).toMatch(SERVER_ID_RULE);
    expect(r).toEqual({ ok: true, observationId: h['X-Observation-Id'], capturedAt: '2026-10-30T08:00:00.000Z' });
  });
  it('accepts 200 (duplicate) as success', async () => {
    const { fn } = recorder(() => json(200, { duplicate: true }));
    expect((await uploadCapture('C', blob, { fetchImpl: fn })).ok).toBe(true);
  });
  it('maps a network failure', async () => {
    const r = await uploadCapture('C', blob, { fetchImpl: async () => { throw new TypeError('Failed to fetch'); } });
    expect(r).toMatchObject({ ok: false, status: 0 });
    expect(!r.ok && r.error).toContain('Could not connect to the server');
  });
  it('maps 401, 413, 415', async () => {
    const r401 = await uploadCapture('C', blob, { fetchImpl: recorder(() => json(401, { error: 'Invalid X-API-Key' })).fn });
    expect(r401).toMatchObject({ ok: false, status: 401 });
    expect(!r401.ok && r401.error).toContain('API key');
    expect(!r401.ok && r401.error).toContain('without a key');
    const r413 = await uploadCapture('C', blob, { fetchImpl: recorder(() => json(413, { error: 'The request exceeds the size limit' })).fn });
    expect(r413).toMatchObject({ ok: false, status: 413 });
    expect(!r413.ok && r413.error).toContain('exceeds the server limit');
    const r415 = await uploadCapture('C', blob, { fetchImpl: recorder(() => json(415, { error: 'Content-Type: image/jpeg is required' })).fn });
    expect(r415).toMatchObject({ ok: false, status: 415 });
  });
  it('passes through the server JSON error for 403/409', async () => {
    const r = await uploadCapture('C', blob, { fetchImpl: recorder(() => json(409, { error: 'The camera has no road_id yet' })).fn });
    expect(r).toEqual({ ok: false, status: 409, error: 'The camera has no road_id yet' });
    const r403 = await uploadCapture('C', blob, { fetchImpl: recorder(() => json(403, { error: 'Invalid Host for keyless demo mode' })).fn });
    expect(!r403.ok && r403.error).toBe('Invalid Host for keyless demo mode');
  });
  it('falls back to a generic message when the error body is not JSON', async () => {
    const r = await uploadCapture('C', blob, { fetchImpl: recorder(() => new Response('<html>', { status: 502 })).fn });
    expect(r).toMatchObject({ ok: false, status: 502 });
    expect(!r.ok && r.error).toContain('HTTP 502');
  });
  it('times out when the server never answers', async () => {
    const r = await uploadCapture('C', blob, { fetchImpl: hangUntilAbort, timeoutMs: 20 });
    expect(r).toMatchObject({ ok: false, status: 0 });
    expect(!r.ok && r.error).toContain('did not respond');
  });
  it('reports caller abort', async () => {
    const ac = new AbortController();
    const p = uploadCapture('C', blob, { fetchImpl: hangUntilAbort, signal: ac.signal });
    ac.abort();
    const r = await p;
    expect(!r.ok && r.error).toContain('cancelled');
  });
});

describe('waitForAnalysis', () => {
  const SENT = '2026-10-30T08:00:00.000Z';
  const camera = (capturedAt: string) => ({
    camera_id: 'CAM-001',
    monitoring: { waste_coverage_pct: 7.5, drain_blockage_pct: 58, blockage_method: 'roi', certainty: 0.8, low_certainty: false, observed_at: capturedAt },
    images: { original_url: '/api/images/a.jpg', analyzed_url: '/api/images/b.jpg', captured_at: capturedAt },
  });
  /** Đồng hồ giả: sleep chỉ cộng thời gian, không chờ thật. */
  const clock = () => {
    let t = 0;
    return { now: () => t, sleep: async (ms: number) => { t += ms; } };
  };

  it('succeeds on the 3rd poll, ignoring older results', async () => {
    const c = clock();
    const responses = [
      () => json(200, { camera_id: 'CAM-001' }), // chưa có phân tích
      () => json(200, camera('2026-10-30T07:59:00.000Z')), // kết quả của ảnh cũ hơn
      () => json(200, camera('2026-10-30T08:00:00.400Z')), // khớp trong 1 giây
    ];
    let i = 0;
    const urls: string[] = [];
    const ticks: number[] = [];
    const r = await waitForAnalysis('CAM-001', SENT, {
      fetchImpl: async url => { urls.push(url); return responses[i++](); },
      ...c, onTick: ms => ticks.push(ms),
    });
    expect(i).toBe(3);
    expect(urls[0]).toBe('/api/cameras/CAM-001');
    expect(ticks).toEqual([0, 1500, 3000]);
    expect(r).toMatchObject({ ok: true, elapsedMs: 3000 });
    if (r.ok) {
      expect(r.monitoring).toMatchObject({ drain_blockage_pct: 58, blockage_method: 'roi', waste_coverage_pct: 7.5, certainty: 0.8 });
      expect(r.images.analyzed_url).toBe('/api/images/b.jpg');
    }
  });
  it('does not accept a result more than 1 s away from the sent captured_at', async () => {
    const r = await waitForAnalysis('CAM-001', SENT, {
      fetchImpl: async () => json(200, camera('2026-10-30T08:00:01.500Z')), ...clock(), timeoutMs: 6000,
    });
    expect(r).toMatchObject({ ok: false, reason: 'timeout' });
  });
  it('times out after 60 s with the documented message (fake clock)', async () => {
    const c = clock();
    let polls = 0;
    const r = await waitForAnalysis('CAM-001', SENT, { fetchImpl: async () => { polls++; return json(200, { camera_id: 'CAM-001' }); }, ...c });
    expect(r).toEqual({
      ok: false, reason: 'timeout',
      error: 'No result after 60 seconds: the AI worker may not be running, or the image is unusable (too dark). Check the worker window.',
    });
    expect(polls).toBe(40);
    expect(c.now()).toBe(60_000);
  });
  it('aborts before polling and while sleeping', async () => {
    const pre = new AbortController(); pre.abort();
    let polls = 0;
    const fetchImpl: FetchImpl = async () => { polls++; return json(200, {}); };
    expect(await waitForAnalysis('C', SENT, { fetchImpl, signal: pre.signal })).toMatchObject({ ok: false, reason: 'aborted' });
    expect(polls).toBe(0);

    const ac = new AbortController();
    const r = await waitForAnalysis('C', SENT, { fetchImpl, signal: ac.signal, now: () => 0, sleep: async () => { ac.abort(); } });
    expect(r).toMatchObject({ ok: false, reason: 'aborted' });
    expect(polls).toBe(1);
  });
  it('aborts an in-flight poll', async () => {
    const ac = new AbortController();
    const p = waitForAnalysis('C', SENT, { fetchImpl: hangUntilAbort, signal: ac.signal });
    ac.abort();
    expect(await p).toMatchObject({ ok: false, reason: 'aborted' });
  });
  it('tolerates transient errors and still succeeds', async () => {
    const seq: (() => Response | Promise<Response>)[] = [
      () => { throw new TypeError('Failed to fetch'); },
      () => new Response('boom', { status: 500 }),
      () => json(200, camera(SENT)),
    ];
    let i = 0;
    const r = await waitForAnalysis('C', SENT, { fetchImpl: async () => seq[i++](), ...clock() });
    expect(r.ok).toBe(true);
  });
  it('reports network when every poll failed or the last 3 polls in a row failed', async () => {
    const r = await waitForAnalysis('C', SENT, { fetchImpl: async () => { throw new TypeError('Failed to fetch'); }, ...clock(), timeoutMs: 6000 });
    expect(r).toMatchObject({ ok: false, reason: 'network' });
    let n = 0;
    const r2 = await waitForAnalysis('C', SENT, {
      fetchImpl: async () => { if (n++ === 0) return json(200, {}); throw new TypeError('x'); }, ...clock(), timeoutMs: 6000,
    });
    expect(r2).toMatchObject({ ok: false, reason: 'network' }); // backend chết giữa chừng
    let m = 0;
    const r3 = await waitForAnalysis('C', SENT, {
      fetchImpl: async () => { if (m++ % 2 === 0) return json(200, {}); throw new TypeError('x'); }, ...clock(), timeoutMs: 6000,
    });
    expect(r3).toMatchObject({ ok: false, reason: 'timeout' }); // lỗi xen kẽ vẫn là hết giờ
  });
  it('treats an unreadable JSON body as a failed poll, not a crash', async () => {
    const r = await waitForAnalysis('C', SENT, { fetchImpl: async () => new Response('<html>', { status: 200 }), ...clock(), timeoutMs: 3000 });
    expect(r).toMatchObject({ ok: false, reason: 'network' });
  });
});

describe('resizeToJpeg (injected environment)', () => {
  const decoded = (w: number, h: number, released: { n: number }): DecodedImage => ({
    source: {} as CanvasImageSource, width: w, height: h, release: () => { released.n++; },
  });
  const jpegOfSize = (size: number) => new Blob([new Uint8Array(size)], { type: 'image/jpeg' });
  const image = new Blob(['x'], { type: 'image/png' });

  it('rejects non-image files without decoding', async () => {
    let decodes = 0;
    const env: ResizeEnv = { decode: async () => { decodes++; throw new Error('no'); }, encode: async () => null };
    await expect(resizeToJpeg(new Blob(['x'], { type: 'text/plain' }), 1600, env)).rejects.toThrow('not an image');
    expect(decodes).toBe(0);
  });
  it('maps decode failure to the English message', async () => {
    const env: ResizeEnv = { decode: async () => { throw new Error('bad'); }, encode: async () => null };
    const err = await resizeToJpeg(image, 1600, env).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(CaptureError);
    expect((err as Error).message).toBe('Could not read this image.');
  });
  it('downsizes a 24 MP image and walks quality steps until under 4.5 MB', async () => {
    const released = { n: 0 };
    const calls: [number, number, number][] = [];
    const sizes = [6 * 1024 * 1024, 5 * 1024 * 1024, 1024 * 1024];
    const env: ResizeEnv = {
      decode: async () => decoded(6000, 4000, released),
      encode: async (_i, w, h, q) => { calls.push([w, h, q]); return jpegOfSize(sizes[calls.length - 1]); },
    };
    const r = await resizeToJpeg(image, 1600, env);
    expect(calls).toEqual([[1600, 1067, 0.9], [1600, 1067, 0.8], [1600, 1067, 0.7]]);
    expect(r).toMatchObject({ width: 1600, height: 1067 });
    expect(r.blob.size).toBe(1024 * 1024);
    expect(released.n).toBe(1);
  });
  it('shrinks further when even the lowest quality is too big, then gives up', async () => {
    const released = { n: 0 };
    const widths: number[] = [];
    const env: ResizeEnv = {
      decode: async () => decoded(4000, 3000, released),
      encode: async (_i, w) => { widths.push(w); return jpegOfSize(6 * 1024 * 1024); },
    };
    await expect(resizeToJpeg(image, 1600, env)).rejects.toThrow('too large');
    expect([...new Set(widths)]).toEqual([1600, 1200, 900]);
    expect(released.n).toBe(1);
  });
  it('handles toBlob returning null and non-JPEG output', async () => {
    const released = { n: 0 };
    const nullEnv: ResizeEnv = { decode: async () => decoded(100, 100, released), encode: async () => null };
    await expect(resizeToJpeg(image, 1600, nullEnv)).rejects.toThrow('could not compress');
    const pngEnv: ResizeEnv = { decode: async () => decoded(100, 100, released), encode: async () => new Blob([new Uint8Array(10)], { type: 'image/png' }) };
    await expect(resizeToJpeg(image, 1600, pngEnv)).rejects.toThrow('JPEG');
    expect(released.n).toBe(2);
  });
  it('never upscales small photos', async () => {
    const seen: [number, number][] = [];
    const env: ResizeEnv = { decode: async () => decoded(640, 480, { n: 0 }), encode: async (_i, w, h) => { seen.push([w, h]); return jpegOfSize(1000); } };
    const r = await resizeToJpeg(image, 1600, env);
    expect(seen).toEqual([[640, 480]]);
    expect(r).toMatchObject({ width: 640, height: 480 });
  });
});
