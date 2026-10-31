import type { DrainRoi, DrainState, DrainStateName, DrainSummary } from '../models/drain';

/**
 * Chuẩn hóa khối drain_* từ API theo chính sách KHOAN DUNG (khác phần còn lại của normalizeAlerts/normalizeCameras):
 * dữ liệu hỏng không làm hỏng cả danh sách, nhưng cũng không bao giờ được hiểu thành "an toàn".
 * - drain_roi / drain_summary hỏng -> undefined.
 * - drain_state hỏng -> unknown/no_data. Vắng mặt (undefined/null) -> undefined.
 */
const record = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const STATES: readonly string[] = ['clear', 'watch', 'clean', 'unknown'];
const REASONS: readonly string[] = ['ok', 'collecting', 'stale', 'no_data'];
const finite = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const unit = (x: unknown): x is number => finite(x) && x >= 0 && x <= 1;
const percent = (x: unknown): x is number => finite(x) && x >= 0 && x <= 100;
const count = (x: unknown): x is number => finite(x) && Number.isInteger(x) && x >= 0;
const isoDate = (x: unknown): x is string => typeof x === 'string' && Number.isFinite(Date.parse(x));
const isState = (x: unknown): x is DrainStateName => typeof x === 'string' && STATES.includes(x);
const isString = (x: unknown): x is string => typeof x === 'string';
const isBool = (x: unknown): x is boolean => typeof x === 'boolean';
const isReason = (x: unknown): boolean => typeof x === 'string' && REASONS.includes(x);
const isMethod = (x: unknown): boolean => x === 'roi' || x === 'legacy';
const optional = (x: unknown, ok: (v: unknown) => boolean): boolean => x === undefined || ok(x);

/** Giá trị an toàn khi khối drain_state hỏng: không bao giờ hiểu là "Thấp". */
export const unknownDrainState = (): DrainState => ({ state: 'unknown', window_count: 0, reason: 'no_data' });

export function normalizeDrainRoi(raw: unknown): DrainRoi | undefined {
  if (!record(raw) || !Array.isArray(raw.polygon)) return undefined;
  const { polygon, source, calibrated_at } = raw;
  if (polygon.length < 3 || polygon.length > 64) return undefined;
  if (!polygon.every(p => Array.isArray(p) && p.length === 2 && unit(p[0]) && unit(p[1]))) return undefined;
  if ((source !== 'ai' && source !== 'manual') || !isoDate(calibrated_at)) return undefined;
  return { polygon: polygon.map(p => [p[0], p[1]] as [number, number]), source, calibrated_at };
}

/** undefined = không có cờ; null = cờ hỏng. */
function normalizeFlags(raw: unknown): DrainState['flags'] | null {
  if (raw === undefined) return undefined;
  if (!record(raw) || !optional(raw.no_trash_in_roi, isBool) || !optional(raw.low_certainty, isBool)) return null;
  return { no_trash_in_roi: raw.no_trash_in_roi as boolean | undefined, low_certainty: raw.low_certainty as boolean | undefined };
}

function validState(raw: Record<string, unknown>): boolean {
  return isState(raw.state) && count(raw.window_count)
    && optional(raw.updated_at, isoDate) && optional(raw.since, isoDate) && optional(raw.evidence_captured_at, isoDate)
    && optional(raw.smoothed_blockage_pct, percent) && optional(raw.needed, count)
    && optional(raw.reason, isReason) && optional(raw.blockage_method, isMethod)
    && optional(raw.roi_calibrated, isBool) && optional(raw.evidence_observation_id, isString);
}

const COPIED = ['updated_at', 'since', 'smoothed_blockage_pct', 'needed', 'reason', 'roi_calibrated', 'blockage_method', 'evidence_observation_id', 'evidence_captured_at'] as const;

export function normalizeDrainState(raw: unknown): DrainState | undefined {
  if (raw === undefined || raw === null) return undefined;
  if (!record(raw) || !validState(raw)) return unknownDrainState();
  const flags = normalizeFlags(raw.flags);
  if (flags === null) return unknownDrainState();
  const out: DrainState = { state: raw.state as DrainStateName, window_count: raw.window_count as number };
  // Chỉ sao chép các khóa đã được validState kiểm tra; khóa lạ bị bỏ.
  for (const key of COPIED) if (raw[key] !== undefined) Object.assign(out, { [key]: raw[key] });
  if (flags) out.flags = flags;
  return out;
}

export function normalizeDrainSummary(raw: unknown): DrainSummary | undefined {
  if (!record(raw)) return undefined;
  const { clear, watch, clean, unknown, worst_state, worst_camera_id } = raw;
  if (![clear, watch, clean, unknown].every(count) || !isState(worst_state)) return undefined;
  if (worst_camera_id !== null && typeof worst_camera_id !== 'string') return undefined;
  return { clear: clear as number, watch: watch as number, clean: clean as number, unknown: unknown as number, worst_state, worst_camera_id };
}
