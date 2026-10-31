import { fitSize, qualitySteps } from '../lib/imageFit';

/** Ảnh sau nén phải nhỏ hơn mức này (server chặn ở 5 MB: POLICY.maxImageBytes trong server/config.js). */
export const MAX_UPLOAD_BYTES = Math.floor(4.5 * 1024 * 1024);
export const DEFAULT_MAX_SIDE = 1600;
export const UPLOAD_TIMEOUT_MS = 20_000;
export const POLL_INTERVAL_MS = 1500;
export const WAIT_TIMEOUT_MS = 60_000;
/** Sai lệch tối đa khi so captured_at đã gửi với captured_at trong kết quả (server chuẩn hoá bằng toISOString). */
const MATCH_TOLERANCE_MS = 1000;
const POLL_REQUEST_TIMEOUT_MS = 8000;

export type FetchImpl = (input: string, init?: RequestInit) => Promise<Response>;

/** Lỗi có thông báo tiếng Việt an toàn để hiện thẳng cho người dùng. */
export class CaptureError extends Error {
  constructor(message: string) { super(message); this.name = 'CaptureError'; }
}

// ---------------------------------------------------------------- Nén / đổi cỡ ảnh

export interface ResizedJpeg { blob: Blob; width: number; height: number }

/** Ảnh đã giải mã. `release` giải phóng bộ nhớ (ImageBitmap.close / thu hồi object URL). */
export interface DecodedImage { source: CanvasImageSource; width: number; height: number; release: () => void }

/** Phần phụ thuộc trình duyệt, tách ra để test được logic vòng lặp nén trong Node. */
export interface ResizeEnv {
  decode: (file: Blob) => Promise<DecodedImage>;
  /** Vẽ `image` lên canvas width x height rồi xuất JPEG; null nếu trình duyệt không xuất được. */
  encode: (image: DecodedImage, width: number, height: number, quality: number) => Promise<Blob | null>;
}

async function decodeWithBitmap(file: Blob): Promise<DecodedImage> {
  // 'from-image': áp EXIF orientation để ảnh chụp dọc từ điện thoại không bị xoay nghiêng.
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  return { source: bitmap, width: bitmap.width, height: bitmap.height, release: () => bitmap.close() };
}

function decodeWithElement(file: Blob): Promise<DecodedImage> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    const release = () => URL.revokeObjectURL(url);
    img.onload = () => {
      if (img.naturalWidth > 0 && img.naturalHeight > 0) resolve({ source: img, width: img.naturalWidth, height: img.naturalHeight, release });
      else { release(); reject(new Error('empty image')); }
    };
    img.onerror = () => { release(); reject(new Error('decode failed')); };
    img.src = url;
  });
}

const browserEnv: ResizeEnv = {
  async decode(file) {
    if (typeof createImageBitmap === 'function') {
      try { return await decodeWithBitmap(file); } catch { /* trình duyệt cũ / định dạng lạ: thử bằng thẻ <img> */ }
    }
    return decodeWithElement(file);
  },
  encode(image, width, height, quality) {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return Promise.resolve(null);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(image.source, 0, 0, width, height);
    return new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
  },
};

/**
 * Giải mã ảnh người dùng chọn, thu nhỏ cạnh dài về <= maxSide và nén JPEG dưới MAX_UPLOAD_BYTES.
 * Thử lần lượt qualitySteps; nếu vẫn quá lớn thì giảm cỡ thêm tối đa 2 lần. Ném CaptureError khi thất bại.
 */
export async function resizeToJpeg(file: Blob, maxSide: number = DEFAULT_MAX_SIDE, env: ResizeEnv = browserEnv): Promise<ResizedJpeg> {
  if (file.type && !file.type.startsWith('image/')) throw new CaptureError('The selected file is not an image.');
  let decoded: DecodedImage;
  try { decoded = await env.decode(file); } catch { throw new CaptureError('Could not read this image.'); }
  try {
    let side = maxSide;
    for (let shrink = 0; shrink < 3; shrink++, side = Math.floor(side * 0.75)) {
      let size;
      try { size = fitSize(decoded.width, decoded.height, side); } catch { throw new CaptureError('Could not read this image.'); }
      for (const quality of qualitySteps) {
        let blob: Blob | null;
        try { blob = await env.encode(decoded, size.width, size.height, quality); } catch { blob = null; }
        if (!blob) throw new CaptureError('The browser could not compress this image. Try another image or browser.');
        if (blob.type && blob.type !== 'image/jpeg') throw new CaptureError('The browser could not produce a JPEG. Try another browser.');
        if (blob.size > 0 && blob.size < MAX_UPLOAD_BYTES) return { blob, width: size.width, height: size.height };
      }
    }
    throw new CaptureError('The image is too large even after compression. Choose a smaller one.');
  } finally {
    decoded.release();
  }
}

// ---------------------------------------------------------------- Mã quan sát

let idCounter = 0;
function randomChunk(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const buf = new Uint32Array(2);
    crypto.getRandomValues(buf);
    return Array.from(buf, n => n.toString(36).padStart(7, '0')).join('');
  }
  return Math.random().toString(36).slice(2, 16).padEnd(14, '0');
}
/**
 * Mã quan sát hợp lệ với id() của server (^[A-Za-z0-9_-]{1,80}$) và duy nhất:
 * 'web-' + thời gian base36 + bộ đếm trong phiên + 14 ký tự ngẫu nhiên.
 */
export function makeObservationId(nowMs: number = Date.now()): string {
  idCounter = (idCounter + 1) % 1_679_616; // 36^4
  return `web-${Math.max(0, Math.floor(nowMs)).toString(36)}-${idCounter.toString(36)}-${randomChunk()}`;
}

// ---------------------------------------------------------------- URL

/** Gốc API camera, cùng quy ước với mapService.ts. */
export const camerasBase = (): string => import.meta.env.VITE_CAMERAS_API_URL || '/api/cameras';

/** Đường dẫn nhận ảnh của thiết bị: cùng gốc với API camera, thay đoạn cuối `/cameras` bằng `/esp32/cameras`. */
export function captureEndpoint(cameraId: string, base: string = camerasBase()): string {
  const trimmed = base.replace(/\/+$/, '');
  const root = /\/cameras$/.test(trimmed) ? trimmed.replace(/\/cameras$/, '/esp32/cameras') : '/api/esp32/cameras';
  return `${root}/${encodeURIComponent(cameraId)}/capture`;
}
const cameraEndpoint = (cameraId: string, base: string = camerasBase()) => `${base.replace(/\/+$/, '')}/${encodeURIComponent(cameraId)}`;

// ---------------------------------------------------------------- Gửi ảnh

export type UploadResult =
  | { ok: true; observationId: string; capturedAt: string }
  | { ok: false; status: number; error: string };

export interface UploadOptions {
  fetchImpl?: FetchImpl;
  now?: () => Date;
  timeoutMs?: number;
  signal?: AbortSignal;
}

async function readJson(res: Response): Promise<unknown> {
  try { return await res.json(); } catch { return undefined; }
}

/** Gửi MỘT ảnh JPEG lên route capture của backend. Không tự thử lại (tránh tạo trùng tác vụ). */
export async function uploadCapture(cameraId: string, blob: Blob, opts: UploadOptions = {}): Promise<UploadResult> {
  const { fetchImpl = (input, init) => fetch(input, init), now = () => new Date(), timeoutMs = UPLOAD_TIMEOUT_MS, signal } = opts;
  const sentAt = now();
  const observationId = makeObservationId(sentAt.getTime());
  // Dùng giờ trình duyệt. Server chỉ chặn mốc quá 5 phút trong tương lai (POLICY.maxFutureSkewMs).
  const capturedAt = sentAt.toISOString();

  const controller = new AbortController();
  let timedOut = false;
  const onAbort = () => controller.abort();
  if (signal?.aborted) controller.abort(); else signal?.addEventListener('abort', onAbort, { once: true });
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  try {
    const res = await fetchImpl(captureEndpoint(cameraId), {
      method: 'POST',
      headers: { 'Content-Type': 'image/jpeg', 'X-Observation-Id': observationId, 'X-Captured-At': capturedAt, Accept: 'application/json' },
      body: blob,
      signal: controller.signal,
      cache: 'no-store',
    });
    if (res.ok) return { ok: true, observationId, capturedAt };
    const data = await readJson(res);
    const serverMessage = (data as { error?: unknown } | null | undefined)?.error;
    const message = typeof serverMessage === 'string' && serverMessage.trim() ? serverMessage : undefined;
    switch (res.status) {
      case 401: return { ok: false, status: 401, error: 'The backend has a device API key set (or the request did not come from this machine), so the page cannot send images. Run the backend without a key to test.' };
      case 413: return { ok: false, status: 413, error: 'The image exceeds the server limit (5 MB). Choose a smaller one.' };
      case 415: return { ok: false, status: 415, error: 'The server rejected the image format (JPEG required). Try another image.' };
      case 404: return { ok: false, status: 404, error: message ?? 'The camera is no longer on the server.' };
      default: return { ok: false, status: res.status, error: res.status >= 500 ? `Server error (HTTP ${res.status}). Check the backend window.` : message ?? `The server rejected the request (HTTP ${res.status}).` };
    }
  } catch {
    if (signal?.aborted) return { ok: false, status: 0, error: 'Image sending cancelled.' };
    if (timedOut) return { ok: false, status: 0, error: `The server did not respond after ${Math.round(timeoutMs / 1000)} seconds. It is unclear whether the image arrived; check the backend and try again.` };
    return { ok: false, status: 0, error: 'Could not connect to the server. Check that the backend is running and try again.' };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

// ---------------------------------------------------------------- Chờ kết quả

export interface AnalysisMonitoring {
  waste_coverage_pct?: number;
  drain_blockage_pct?: number;
  blockage_method?: 'roi' | 'legacy';
  certainty?: number;
  no_trash_in_roi?: boolean;
  low_certainty?: boolean;
  observed_at?: string;
}
export interface AnalysisImages { original_url?: string; analyzed_url?: string; captured_at: string }

export type WaitResult =
  | { ok: true; monitoring: AnalysisMonitoring; images: AnalysisImages; elapsedMs: number }
  | { ok: false; reason: 'timeout' | 'aborted' | 'network'; error: string };

export interface WaitOptions {
  fetchImpl?: FetchImpl;
  intervalMs?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
  onTick?: (elapsedMs: number) => void;
  /** Đồng hồ (ms) và hàm ngủ có thể thay khi test. */
  now?: () => number;
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
  /** Gốc API camera; mặc định camerasBase(). */
  base?: string;
}

const abortableSleep = (ms: number, signal?: AbortSignal): Promise<void> => new Promise(resolve => {
  if (signal?.aborted) { resolve(); return; }
  const done = () => { clearTimeout(timer); signal?.removeEventListener('abort', done); resolve(); };
  const timer = setTimeout(done, ms);
  signal?.addEventListener('abort', done, { once: true });
});

const num = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined);

/** Đọc phần monitoring/images công khai; chỉ trả khi captured_at của ảnh khớp mốc đã gửi (trong 1 giây). */
function matchAnalysis(data: unknown, capturedAtMs: number): { monitoring: AnalysisMonitoring; images: AnalysisImages } | null {
  const cam = data as { monitoring?: Record<string, unknown> | null; images?: Record<string, unknown> | null } | null;
  const images = cam?.images;
  const monitoring = cam?.monitoring;
  if (!images || typeof images !== 'object' || !monitoring || typeof monitoring !== 'object') return null;
  const at = typeof images.captured_at === 'string' ? Date.parse(images.captured_at) : NaN;
  if (!Number.isFinite(at) || Math.abs(at - capturedAtMs) > MATCH_TOLERANCE_MS) return null; // kết quả của ảnh cũ hơn/khác
  const m: AnalysisMonitoring = {};
  const waste = num(monitoring.waste_coverage_pct); if (waste !== undefined) m.waste_coverage_pct = waste;
  const drain = num(monitoring.drain_blockage_pct); if (drain !== undefined) m.drain_blockage_pct = drain;
  const cert = num(monitoring.certainty); if (cert !== undefined) m.certainty = cert;
  if (monitoring.blockage_method === 'roi' || monitoring.blockage_method === 'legacy') m.blockage_method = monitoring.blockage_method;
  if (typeof monitoring.no_trash_in_roi === 'boolean') m.no_trash_in_roi = monitoring.no_trash_in_roi;
  if (typeof monitoring.low_certainty === 'boolean') m.low_certainty = monitoring.low_certainty;
  if (typeof monitoring.observed_at === 'string') m.observed_at = monitoring.observed_at;
  const out: AnalysisImages = { captured_at: images.captured_at as string };
  if (typeof images.original_url === 'string') out.original_url = images.original_url;
  if (typeof images.analyzed_url === 'string') out.analyzed_url = images.analyzed_url;
  return { monitoring: m, images: out };
}

/**
 * Hỏi GET <camera> định kỳ cho tới khi images.captured_at khớp mốc `capturedAt` đã gửi.
 * Lỗi mạng thoáng qua được bỏ qua (thử tiếp tới hết hạn); nếu MỌI lần hỏi đều lỗi thì báo 'network'.
 * Kết quả "không dùng được" (quá tối) không bao giờ cập nhật camera nên sẽ hết hạn với reason 'timeout'.
 */
export async function waitForAnalysis(cameraId: string, capturedAt: string, opts: WaitOptions = {}): Promise<WaitResult> {
  const {
    fetchImpl = (input, init) => fetch(input, init),
    intervalMs = POLL_INTERVAL_MS, timeoutMs = WAIT_TIMEOUT_MS, signal, onTick,
    now = () => Date.now(), sleep = abortableSleep, base,
  } = opts;
  const target = Date.parse(capturedAt);
  const url = cameraEndpoint(cameraId, base);
  const start = now();
  let attempts = 0;
  let failures = 0;
  let streak = 0;
  let lastError = '';
  const aborted = (): WaitResult => ({ ok: false, reason: 'aborted', error: 'Waiting for the result was cancelled.' });

  for (;;) {
    if (signal?.aborted) return aborted();
    const elapsed = now() - start;
    if (elapsed >= timeoutMs) break;
    onTick?.(elapsed);

    attempts++;
    const controller = new AbortController();
    const onAbort = () => controller.abort();
    signal?.addEventListener('abort', onAbort, { once: true });
    const timer = setTimeout(() => controller.abort(), Math.min(POLL_REQUEST_TIMEOUT_MS, Math.max(1000, timeoutMs - elapsed)));
    try {
      const res = await fetchImpl(url, { signal: controller.signal, headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const found = matchAnalysis(await res.json() as unknown, target);
      if (found) return { ok: true, ...found, elapsedMs: now() - start };
      streak = 0;
    } catch (e) {
      if (signal?.aborted) return aborted();
      failures++; streak++;
      lastError = e instanceof Error ? e.message : String(e);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
    }
    if (signal?.aborted) return aborted();
    const remaining = timeoutMs - (now() - start);
    if (remaining <= 0) break;
    await sleep(Math.min(intervalMs, remaining), signal);
  }

  if (attempts > 0 && (failures === attempts || streak >= 3)) { // mọi lần hỏi lỗi, hoặc 3 lần cuối liên tiếp lỗi (backend chết giữa chừng)
    return { ok: false, reason: 'network', error: `Could not read the result from the server${lastError ? ` (${lastError})` : ''}. Check that the backend is running.` };
  }
  return {
    ok: false, reason: 'timeout',
    error: `No result after ${Math.round(timeoutMs / 1000)} seconds: the AI worker may not be running, or the image is unusable (too dark). Check the worker window.`,
  };
}
