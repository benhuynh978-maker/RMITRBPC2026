import type { CameraImages, Monitoring } from '../models/monitoring';
import type { Severity } from '../models/roadAlert';

const levels = ['normal', 'low', 'medium', 'high', 'critical'];
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Chỉ số/ảnh phải là object');
  return value as Record<string, unknown>;
}
function date(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== 'string' || !Number.isFinite(Date.parse(value))) throw new Error('Thời gian quan sát không hợp lệ');
  return value;
}
export function normalizeMonitoring(value: unknown): Monitoring | undefined {
  if (value === undefined) return undefined;
  const data = object(value);
  const result: Monitoring = {};
  for (const key of ['waste_coverage_pct', 'drain_blockage_pct', 'waste_max_pct', 'flood_max_pct'] as const) {
    const percent = data[key];
    if (percent !== undefined) {
      if (typeof percent !== 'number' || !Number.isFinite(percent) || percent < 0 || percent > 100) throw new Error(`${key} phải trong khoảng 0–100`);
      result[key] = percent;
    }
  }
  for (const key of ['waste_camera_count', 'flood_camera_count'] as const) {
    const count = data[key];
    if (count !== undefined) {
      if (typeof count !== 'number' || !Number.isInteger(count) || count < 0) throw new Error(`${key} phải là số nguyên không âm`);
      result[key] = count;
    }
  }
  if(data.waste_level!==undefined){
    if(typeof data.waste_level!=='string'||!levels.includes(data.waste_level))throw new Error('waste_level không hợp lệ');
    result.waste_level=data.waste_level as Severity;
  }
  if (data.rain_expected !== undefined) {
    if (typeof data.rain_expected !== 'boolean') throw new Error('rain_expected phải là boolean');
    result.rain_expected = data.rain_expected;
  }
  result.observed_at = date(data.observed_at);
  return result;
}
export function normalizeImages(value: unknown): CameraImages | undefined {
  if (value === undefined) return undefined;
  const data = object(value);
  const result: CameraImages = { captured_at: date(data.captured_at) };
  for (const key of ['original_url', 'analyzed_url'] as const) {
    const url = data[key];
    if (url !== undefined) {
      if (typeof url !== 'string' || !/^(https?:\/\/|\/(?!\/))[^\s\\]+$/i.test(url)) throw new Error(`${key} cần URL HTTP(S) hoặc đường dẫn /...`);
      result[key] = url;
    }
  }
  return result;
}
