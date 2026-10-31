import {
  DEMO_API_URL,
  DEMO_HEALTH_TIMEOUT_MS,
  DEMO_MAX_FILE_BYTES,
  DEMO_MAX_SIDE_PX,
  DEMO_REQUEST_TIMEOUT_MS,
} from './config.js';

/** Error with a stable `code`; the page maps each code to a translated message (tryAi.live.errors.*). */
export class DemoError extends Error {
  constructor(code, { status = 0, retryAfter = null } = {}) {
    super(code);
    this.name = 'DemoError';
    this.code = code;
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

// Codes the service can return, folded into the ones the page has a message for.
const SERVER_CODES = {
  invalid_image: 'invalid_image',
  unsupported_type: 'unsupported_type',
  too_big: 'too_big',
  too_large: 'too_large',
  too_small: 'too_small',
  too_dark: 'too_dark',
  rate_limited: 'rate_limited',
  busy_global: 'busy',
  busy: 'busy',
  not_ready: 'not_ready',
};

export const demoEnabled = () => DEMO_API_URL !== '';

/** AbortSignal that fires on timeout or when `outer` aborts. `timedOut()` tells the two apart. */
function makeSignal(ms, outer) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, ms);
  const onOuter = () => controller.abort();
  if (outer) {
    if (outer.aborted) controller.abort();
    else outer.addEventListener('abort', onOuter, { once: true });
  }
  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    done() {
      clearTimeout(timer);
      outer?.removeEventListener('abort', onOuter);
    },
  };
}

const FETCH_BASE = { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer' };

/** true only when the service answers and its model is ready. Never throws. */
export async function checkHealth(outer) {
  if (!demoEnabled()) return false;
  const s = makeSignal(DEMO_HEALTH_TIMEOUT_MS, outer);
  try {
    const res = await fetch(`${DEMO_API_URL}/api/health`, { ...FETCH_BASE, signal: s.signal });
    if (!res.ok) return false;
    const data = await res.json();
    return data?.status === 'ok' && data?.ready === true;
  } catch {
    return false;
  } finally {
    s.done();
  }
}

/**
 * Validate and shrink a photo in the browser: longest side <= DEMO_MAX_SIDE_PX, re-encoded as JPEG.
 * Re-encoding through a canvas also drops EXIF (including GPS) and applies the camera rotation.
 * createImageBitmap is used instead of an <img> so the page's CSP does not need `blob:` in img-src.
 */
export async function prepareImage(file) {
  if (!file || !['image/jpeg', 'image/png'].includes(file.type)) throw new DemoError('unsupported_type');
  if (file.size > DEMO_MAX_FILE_BYTES) throw new DemoError('too_big');
  let bitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch {
    throw new DemoError('invalid_image');
  }
  try {
    const scale = Math.min(1, DEMO_MAX_SIDE_PX / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new DemoError('invalid_image');
    ctx.fillStyle = '#ffffff'; // PNG transparency becomes white instead of black
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(bitmap, 0, 0, width, height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9));
    if (!blob) throw new DemoError('invalid_image');
    return blob;
  } finally {
    bitmap.close?.();
  }
}

function validResult(data) {
  return (
    data &&
    typeof data.waste_pct === 'number' &&
    Number.isFinite(data.waste_pct) &&
    Number.isInteger(data.level_index) &&
    data.level_index >= -1 &&
    data.level_index <= 3 &&
    (data.drain_pct === null || (typeof data.drain_pct === 'number' && Number.isFinite(data.drain_pct))) &&
    typeof data.annotated_jpg === 'string' &&
    data.annotated_jpg.startsWith('data:image/jpeg;base64,')
  );
}

/** Send the prepared JPEG and return `{ wastePct, levelIndex, drainPct, annotatedSrc }`. Throws DemoError. */
export async function analyzePhoto(blob, outer) {
  const s = makeSignal(DEMO_REQUEST_TIMEOUT_MS, outer);
  try {
    let res;
    try {
      res = await fetch(`${DEMO_API_URL}/api/analyze`, {
        ...FETCH_BASE,
        method: 'POST',
        headers: { 'Content-Type': 'image/jpeg' },
        body: blob,
        signal: s.signal,
      });
    } catch {
      if (outer?.aborted) throw new DemoError('aborted');
      if (s.timedOut()) throw new DemoError('timeout');
      throw new DemoError('network');
    }
    let data = null;
    try {
      data = await res.json();
    } catch {
      /* body is not JSON: handled below */
    }
    if (!res.ok) {
      const retry = Number.parseInt(res.headers.get('Retry-After') ?? '', 10);
      throw new DemoError(SERVER_CODES[data?.code] ?? 'server', {
        status: res.status,
        retryAfter: Number.isFinite(retry) && retry > 0 ? retry : null,
      });
    }
    if (!validResult(data)) throw new DemoError('server', { status: res.status });
    return {
      wastePct: data.waste_pct,
      levelIndex: data.level_index,
      drainPct: data.drain_pct,
      annotatedSrc: data.annotated_jpg,
    };
  } finally {
    s.done();
  }
}
