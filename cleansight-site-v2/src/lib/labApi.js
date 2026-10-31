import { DEMO_API_URL, DEMO_REQUEST_TIMEOUT_MS } from './config.js';
import { DemoError } from './demoApi.js';

// Cùng khoá với trang Board lab (public/lab/board/lab.js): một tab dùng chung một phiên.
const SESSION_KEY = 'cleansight_lab_session';
const SESSION_RE = /^[A-Za-z0-9_-]{16,64}$/;
let memorySession = '';

/** Mã phiên ngẫu nhiên của tab này. Máy chủ giữ trạng thái của phiên trong RAM nên nhiều giám khảo không đè nhau. */
export function labSessionId() {
  if (memorySession) return memorySession;
  let id = '';
  try {
    id = window.sessionStorage.getItem(SESSION_KEY) || '';
  } catch {
    id = '';
  }
  if (!SESSION_RE.test(id)) {
    const bytes = new Uint8Array(18);
    window.crypto.getRandomValues(bytes);
    id = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    try {
      window.sessionStorage.setItem(SESSION_KEY, id);
    } catch {
      /* sessionStorage bị chặn: phiên chỉ nằm trong bộ nhớ trang */
    }
  }
  memorySession = id;
  return id;
}

/** POST JSON tới dịch vụ phòng thử. Trả { status, data, retryAfter }; lỗi mạng/hết hạn ném DemoError. */
export async function labPost(path, body, outer) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, DEMO_REQUEST_TIMEOUT_MS);
  const onOuter = () => controller.abort();
  if (outer) {
    if (outer.aborted) controller.abort();
    else outer.addEventListener('abort', onOuter, { once: true });
  }
  try {
    let res;
    try {
      res = await fetch(`${DEMO_API_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Lab-Session': labSessionId() },
        body: JSON.stringify(body),
        signal: controller.signal,
        cache: 'no-store',
        credentials: 'omit',
        referrerPolicy: 'no-referrer',
      });
    } catch {
      if (outer?.aborted) throw new DemoError('aborted');
      if (timedOut) throw new DemoError('timeout');
      throw new DemoError('network');
    }
    let data = null;
    try {
      data = await res.json();
    } catch {
      /* phản hồi không phải JSON */
    }
    return { status: res.status, data, retryAfter: res.headers.get('Retry-After') };
  } finally {
    clearTimeout(timer);
    outer?.removeEventListener('abort', onOuter);
  }
}

/** Câu thông báo lỗi (tiếng Anh, trang lab chỉ có tiếng Anh) cho một phản hồi không thành công hoặc DemoError. */
export function labErrorText(err) {
  if (err instanceof DemoError) {
    if (err.code === 'timeout') return 'The measurement took too long. Please try again.';
    if (err.code === 'network') return 'Could not reach the live demo. It is open daily 18:00–23:00 Vietnam time (UTC+7) until 30 November 2026.';
    return 'The live demo ran into a problem. Please try again.';
  }
  const { status, data, retryAfter } = err;
  const base = (data && typeof data.error === 'string' && data.error) || (status === 429 ? 'Too many requests.' : 'The live demo ran into a problem. Please try again.');
  return status === 429 && retryAfter ? `${base} Please wait about ${retryAfter} seconds.` : base;
}
