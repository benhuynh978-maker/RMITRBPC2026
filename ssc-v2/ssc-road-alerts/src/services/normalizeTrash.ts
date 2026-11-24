import type { Coordinate } from '../models/roadAlert';
import type { TrashRegion } from '../models/trash';

const MAX_REGIONS = 100;
const MAX_POINTS = 256;
const record = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const position = (x: unknown): x is Coordinate =>
  Array.isArray(x) && x.length === 2 && x.every(n => typeof n === 'number' && Number.isFinite(n)) && Math.abs(x[0]) <= 180 && Math.abs(x[1]) <= 90;

/**
 * Chuẩn hoá trường tùy chọn `trash_regions` của camera. Vắng mặt = không có vùng nào (không phải lỗi);
 * có mặt mà sai dạng thì ném lỗi, giống các trường khác ở biên dữ liệu.
 */
export function normalizeTrashRegions(value: unknown, id = 'camera'): TrashRegion[] | undefined {
  if (value === undefined || value === null) return undefined;
  if (!Array.isArray(value) || value.length > MAX_REGIONS) throw new Error(`${id}: trash_regions must be an array of at most ${MAX_REGIONS} regions`);
  return value.map((raw, index) => {
    if (!record(raw)) throw new Error(`${id}: trash_regions[${index}] is invalid`);
    if (raw.kind !== 'drain' && raw.kind !== 'street') throw new Error(`${id}: trash_regions[${index}].kind must be drain or street`);
    if (typeof raw.area_m2 !== 'number' || !Number.isFinite(raw.area_m2) || raw.area_m2 < 0) throw new Error(`${id}: trash_regions[${index}].area_m2 must be a number >= 0`);
    const ring = raw.ring;
    if (!Array.isArray(ring) || ring.length < 3 || ring.length > MAX_POINTS || !ring.every(position)) throw new Error(`${id}: trash_regions[${index}].ring needs 3-${MAX_POINTS} valid [lng,lat] points`);
    return { kind: raw.kind, area_m2: raw.area_m2, ring: ring as Coordinate[] };
  });
}

/** Tổng số vùng và diện tích (m²) của một camera; 0 khi không có vùng. */
export function summarizeTrashRegions(regions?: TrashRegion[]): { count: number; total_m2: number } {
  const list = regions ?? [];
  return { count: list.length, total_m2: Number(list.reduce((sum, r) => sum + r.area_m2, 0).toFixed(3)) };
}
