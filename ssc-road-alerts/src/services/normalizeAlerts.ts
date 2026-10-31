import type { Coordinate, RoadAlert, Severity } from '../models/roadAlert';
import { normalizeMonitoring } from './normalizeMonitoring';
const record = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const levels: Record<string, Severity> = { '0':'normal','1':'low','2':'medium','3':'high','4':'critical',normal:'normal',low:'low',medium:'medium',high:'high',critical:'critical' };
function coordinate(x: unknown): x is Coordinate {
  return Array.isArray(x) && (x.length === 2 || x.length === 3) && x.every(n => typeof n === 'number' && Number.isFinite(n)) && Math.abs(x[0]) <= 180 && Math.abs(x[1]) <= 90;
}
/** Strict boundary validation: never silently render unknown severity as safe. */
export function normalizeAlerts(payload: unknown): RoadAlert[] {
  const rows = Array.isArray(payload) ? payload : record(payload) && payload.type === 'FeatureCollection' ? payload.features : record(payload) ? payload.roads ?? payload.data : undefined;
  if (!Array.isArray(rows)) throw new Error('JSON cần là mảng, {roads: [...]} hoặc GeoJSON FeatureCollection.');
  const ids = new Set<string>();
  return rows.map((raw, index) => {
    if (!record(raw)) throw new Error(`Đoạn ${index + 1}: dữ liệu không hợp lệ.`);
    const item = raw.type === 'Feature' ? raw.properties : raw;
    if (!record(item)) throw new Error(`Đoạn ${index + 1}: thiếu properties.`);
    const geometry = raw.geometry;
    const id = item.road_id;
    if ((typeof id !== 'string' && typeof id !== 'number') || (typeof id === 'number' && !Number.isFinite(id)) || !String(id).trim()) throw new Error(`Đoạn ${index + 1}: thiếu road_id.`);
    const road_id = String(id);
    if (ids.has(road_id)) throw new Error(`road_id bị trùng: ${road_id}`);
    ids.add(road_id);
    const key = String(item.severity).toLowerCase();
    const severity = Object.hasOwn(levels, key) ? levels[key] : undefined;
    if (!severity) throw new Error(`${road_id}: severity không được hỗ trợ.`);
    if (!record(geometry) || geometry.type !== 'LineString' || !Array.isArray(geometry.coordinates) || geometry.coordinates.length < 2 || !geometry.coordinates.every(coordinate)) throw new Error(`${road_id}: LineString cần ít nhất 2 tọa độ [kinh độ, vĩ độ] hợp lệ.`);
    const coordinates = geometry.coordinates;
    if(item.data_quality!==undefined&&!['fresh','partial','unknown','unconfigured'].includes(String(item.data_quality))) throw new Error(`${road_id}: data_quality không hợp lệ.`);
    if (coordinates.every(p => p[0] === coordinates[0][0] && p[1] === coordinates[0][1])) throw new Error(`${road_id}: đoạn đường phải có độ dài.`);
    for (const field of ['road_name','description','updated_at','alert_id']) if (item[field] !== undefined && typeof item[field] !== 'string') throw new Error(`${road_id}: ${field} phải là chuỗi.`);
    if (typeof item.updated_at === 'string' && !Number.isFinite(Date.parse(item.updated_at))) throw new Error(`${road_id}: updated_at không hợp lệ.`);
    return { road_id, severity, geometry: { type:'LineString', coordinates: geometry.coordinates }, road_name: item.road_name as string | undefined, description: item.description as string | undefined, updated_at: item.updated_at as string | undefined, alert_id: item.alert_id as string | undefined, monitoring: normalizeMonitoring(item.monitoring), data_quality:item.data_quality as RoadAlert['data_quality'] };
  });
}
export const toLeafletPositions = (coordinates: Coordinate[]): [number,number][] => coordinates.map(([lng,lat]) => [lat,lng]);
