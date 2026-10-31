// Sao chép NGUYÊN VĂN từ ssc-v2/ssc-road-alerts/src/lib/roiGeometry.ts.
/**
 * Hình học thuần cho vùng miệng cống (ROI): toạ độ chuẩn hoá [0,1], x sang phải, y xuống dưới.
 * Quy tắc hợp lệ phải khớp server (server/service.js, server/validation.js) và ssc-v2/inference/calibrate_roi.py.
 */
export type RoiPoint = [number, number];

export const ROI_MIN_POINTS = 3;
export const ROI_MAX_POINTS = 64;
/** Server từ chối đa giác có diện tích < ngưỡng này. */
export const ROI_MIN_AREA = 1e-9;

const COLLINEAR_EPS = 1e-12;

export interface PolygonCheck {
  ok: boolean;
  errors: string[];
}

export type ParseResult = { ok: true; points: RoiPoint[] } | { ok: false; error: string };

const isFiniteNumber = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n);

/** Diện tích (shoelace, đơn vị chuẩn hoá), không phụ thuộc chiều quay. */
export function polygonArea(points: ReadonlyArray<readonly [number, number]>): number {
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    sum += x1 * y2 - x2 * y1;
  }
  return Math.abs(sum) / 2;
}

export function clampPoint01(point: readonly [number, number]): RoiPoint {
  const c = (n: number) => (Number.isFinite(n) ? Math.min(1, Math.max(0, n)) : 0);
  return [c(point[0]), c(point[1])];
}

type P = readonly [number, number];
const cross = (o: P, a: P, b: P) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
const sign = (v: number) => (Math.abs(v) <= COLLINEAR_EPS ? 0 : v > 0 ? 1 : -1);
const onSegment = (a: P, b: P, p: P) =>
  Math.min(a[0], b[0]) - COLLINEAR_EPS <= p[0] && p[0] <= Math.max(a[0], b[0]) + COLLINEAR_EPS &&
  Math.min(a[1], b[1]) - COLLINEAR_EPS <= p[1] && p[1] <= Math.max(a[1], b[1]) + COLLINEAR_EPS;

/** Hai đoạn ab và cd có chung điểm nào không (kể cả chạm nhau / chồng nhau trên một đường thẳng). */
function segmentsIntersect(a: P, b: P, c: P, d: P): boolean {
  const d1 = sign(cross(a, b, c));
  const d2 = sign(cross(a, b, d));
  const d3 = sign(cross(c, d, a));
  const d4 = sign(cross(c, d, b));
  if (d1 * d2 < 0 && d3 * d4 < 0) return true;
  return (d1 === 0 && onSegment(a, b, c)) || (d2 === 0 && onSegment(a, b, d)) ||
    (d3 === 0 && onSegment(c, d, a)) || (d4 === 0 && onSegment(c, d, b));
}

/**
 * Đa giác có tự cắt không: kiểm tra mọi cặp cạnh không kề nhau (chạm cộng tuyến cũng tính là cắt).
 * Cạnh kề nhau chỉ bị coi là lỗi khi gập ngược lại đè lên nhau (mũi nhọn có góc 0°).
 */
export function polygonSelfIntersects(points: ReadonlyArray<readonly [number, number]>): boolean {
  const n = points.length;
  if (n < 3) return false;
  for (let i = 0; i < n; i++) {
    const a = points[i], b = points[(i + 1) % n];
    // Cạnh kề: gập ngược cộng tuyến
    const c = points[(i + 2) % n];
    if (sign(cross(a, b, c)) === 0) {
      const dot = (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]);
      if (dot < 0) return true;
    }
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue; // cạnh cuối kề cạnh đầu
      const p = points[j], q = points[(j + 1) % n];
      if (segmentsIntersect(a, b, p, q)) return true;
    }
  }
  return false;
}

/** Kiểm tra đa giác theo đúng luật server, cộng thêm kiểm tra tự cắt phía client. */
export function isValidPolygon(points: unknown): PolygonCheck {
  const errors: string[] = [];
  if (!Array.isArray(points)) return { ok: false, errors: ['Invalid polygon'] };
  if (points.length < ROI_MIN_POINTS) errors.push(`At least ${ROI_MIN_POINTS} points are required`);
  if (points.length > ROI_MAX_POINTS) errors.push(`At most ${ROI_MAX_POINTS} points are allowed`);
  const shapeOk = points.every(p => Array.isArray(p) && p.length === 2 && isFiniteNumber(p[0]) && isFiniteNumber(p[1]));
  if (!shapeOk) {
    errors.push('Each point must be [x, y] with two finite numbers');
    return { ok: false, errors };
  }
  const pts = points as RoiPoint[];
  if (!pts.every(([x, y]) => x >= 0 && x <= 1 && y >= 0 && y <= 1)) errors.push('Coordinates must be between 0 and 1');
  if (pts.length >= ROI_MIN_POINTS) {
    if (!(polygonArea(pts) >= ROI_MIN_AREA)) errors.push('The polygon has zero area — adjust the points');
    // Độc lập với diện tích: hình số 8 đối xứng có diện tích shoelace bằng 0 nhưng vẫn là lỗi tự cắt.
    if (polygonSelfIntersects(pts)) errors.push('The polygon intersects itself — adjust the points');
  }
  return { ok: errors.length === 0, errors };
}

const NUMBER_RE = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;

/**
 * 'x1,y1 x2,y2 ...' -> điểm (khớp parse_polygon_arg của calibrate_roi.py).
 * Chỉ nhận số thập phân dùng dấu chấm; chấp nhận khoảng trắng/xuống dòng thừa.
 * Đã kiểm tra số điểm và khoảng 0–1; diện tích/tự cắt do isValidPolygon báo sau.
 */
export function parsePolygonString(text: string): ParseResult {
  const tokens = text.trim().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return { ok: false, error: 'The point string is empty — expected format "x,y x,y x,y"' };
  const points: RoiPoint[] = [];
  for (const token of tokens) {
    const parts = token.split(',');
    if (parts.length !== 2) {
      return { ok: false, error: `Invalid point "${token}": expected x,y (decimals use a dot, points are separated by spaces)` };
    }
    const [sx, sy] = parts;
    for (const s of parts) {
      if (!NUMBER_RE.test(s)) return { ok: false, error: `Invalid point "${token}": "${s}" is not a number (use a dot for decimals)` };
    }
    const x = Number(sx), y = Number(sy);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return { ok: false, error: `Invalid point "${token}": number too large` };
    points.push([x, y]);
  }
  if (points.length < ROI_MIN_POINTS) return { ok: false, error: `At least ${ROI_MIN_POINTS} points are required, the string has only ${points.length}` };
  if (points.length > ROI_MAX_POINTS) return { ok: false, error: `At most ${ROI_MAX_POINTS} points are allowed, the string has ${points.length}` };
  const bad = points.findIndex(([x, y]) => x < 0 || x > 1 || y < 0 || y > 1);
  if (bad >= 0) return { ok: false, error: `Point ${bad + 1} (${tokens[bad]}) is outside the 0–1 range` };
  return { ok: true, points };
}

const round4 = (n: number) => {
  const r = Math.round(n * 10000) / 10000;
  return String(r === 0 ? 0 : r); // tránh "-0"
};

/** Ngược lại với parsePolygonString; dán lại được vào calibrate_roi.py --polygon. */
export function formatPolygonString(points: ReadonlyArray<readonly [number, number]>): string {
  return points.map(([x, y]) => `${round4(x)},${round4(y)}`).join(' ');
}

export interface Size { w: number; h: number }

/** Tỉ lệ khung hình hai ảnh lệch nhau quá `tol` (tương đối). Kích thước không hợp lệ -> false (chưa biết). */
export function aspectMismatch(a: Size, b: Size, tol = 0.02): boolean {
  const ok = (s: Size) => isFiniteNumber(s.w) && isFiniteNumber(s.h) && s.w > 0 && s.h > 0;
  if (!ok(a) || !ok(b)) return false;
  const ra = a.w / a.h, rb = b.w / b.h;
  return Math.abs(ra - rb) / rb > tol;
}
