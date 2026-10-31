import type { RoiPoint } from '../lib/roiGeometry';

export type RoiSource = 'manual' | 'ai';

export interface RoiPayload {
  drain_roi: { polygon: RoiPoint[]; source: RoiSource } | null;
}

export type RoiResult =
  | { ok: true; camera: unknown }
  | { ok: false; status: number; error: string; needsKey?: boolean };

export type FetchImpl = (input: string, init?: RequestInit) => Promise<Response>;

export const ROI_REQUEST_TIMEOUT_MS = 10_000;

// Khoá quản trị chỉ nằm trong bộ nhớ của trang: không localStorage/sessionStorage, không env, không log.
let adminKey: string | null = null;
export function setAdminKey(key: string | null): void {
  const trimmed = key?.trim();
  adminKey = trimmed ? trimmed : null;
}
export const hasAdminKey = (): boolean => adminKey !== null;

/** Thân PATCH để lưu ROI. Không gửi calibrated_at (server tự đặt). */
export function buildRoiPayload(polygon: ReadonlyArray<readonly [number, number]>, source: RoiSource = 'manual'): RoiPayload {
  return { drain_roi: { polygon: polygon.map(([x, y]): RoiPoint => [x, y]), source } };
}

const cameraUrl = (cameraId: string) =>
  `${import.meta.env.VITE_CAMERAS_API_URL || '/api/cameras'}/${encodeURIComponent(cameraId)}`;

async function readJson(res: Response): Promise<unknown> {
  try { return await res.json(); } catch { return undefined; }
}

async function patchCamera(
  cameraId: string,
  body: RoiPayload,
  fetchImpl: FetchImpl,
  timeoutMs: number,
): Promise<RoiResult> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  const sentKey = adminKey;
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'application/json' };
    if (sentKey) headers['X-API-Key'] = sentKey;
    const res = await fetchImpl(cameraUrl(cameraId), {
      method: 'PATCH',
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
      cache: 'no-store',
    });
    const data = await readJson(res);
    if (res.ok) {
      if (data === undefined) return { ok: false, status: res.status, error: 'The server returned unreadable data; reload the page to check the drain zone.' };
      return { ok: true, camera: data };
    }
    const serverMessage = (data as { error?: unknown } | null | undefined)?.error;
    const message = typeof serverMessage === 'string' && serverMessage.trim() ? serverMessage : undefined;
    if (res.status === 401) {
      // Khoá đã gửi mà vẫn 401 -> khoá sai, bỏ đi để người dùng nhập lại.
      if (sentKey && adminKey === sentKey) adminKey = null;
      return {
        ok: false, status: 401, needsKey: true,
        error: sentKey ? 'Wrong admin key. Please enter it again.' : 'The server requires an admin key.',
      };
    }
    if (res.status === 404) return { ok: false, status: 404, error: 'The camera is no longer on the server' };
    return { ok: false, status: res.status, error: message ?? `The server rejected the request (HTTP ${res.status})` };
  } catch {
    if (timedOut) {
      return { ok: false, status: 0, error: `The server did not respond within ${Math.round(timeoutMs / 1000)} seconds. It is unclear whether the drain zone was saved — reload the page to check, then try again.` };
    }
    return { ok: false, status: 0, error: 'Could not connect to the server. Check that the backend is running and try again.' };
  } finally {
    clearTimeout(timer);
  }
}

export function saveDrainRoi(
  cameraId: string,
  polygon: ReadonlyArray<readonly [number, number]>,
  source: RoiSource = 'manual',
  fetchImpl: FetchImpl = (input, init) => fetch(input, init),
  timeoutMs: number = ROI_REQUEST_TIMEOUT_MS,
): Promise<RoiResult> {
  return patchCamera(cameraId, buildRoiPayload(polygon, source), fetchImpl, timeoutMs);
}

export function removeDrainRoi(
  cameraId: string,
  fetchImpl: FetchImpl = (input, init) => fetch(input, init),
  timeoutMs: number = ROI_REQUEST_TIMEOUT_MS,
): Promise<RoiResult> {
  return patchCamera(cameraId, { drain_roi: null }, fetchImpl, timeoutMs);
}
