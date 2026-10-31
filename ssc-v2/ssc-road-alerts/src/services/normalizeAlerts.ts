import type { Coordinate, RoadAlert, Severity } from '../models/roadAlert';
import { normalizeMonitoring } from './normalizeMonitoring';
import { normalizeDrainSummary } from './normalizeDrain';
const record = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const levels: Record<string, Severity> = { '0':'normal','1':'low','2':'medium','3':'high','4':'critical',normal:'normal',low:'low',medium:'medium',high:'high',critical:'critical' };
function coordinate(x: unknown): x is Coordinate {
  return Array.isArray(x) && (x.length === 2 || x.length === 3) && x.every(n => typeof n === 'number' && Number.isFinite(n)) && Math.abs(x[0]) <= 180 && Math.abs(x[1]) <= 90;
}
/** Strict boundary validation: never silently render unknown severity as safe. */
export function normalizeAlerts(payload: unknown): RoadAlert[] {
  const rows = Array.isArray(payload) ? payload : record(payload) && payload.type === 'FeatureCollection' ? payload.features : record(payload) ? payload.roads ?? payload.data : undefined;
  if (!Array.isArray(rows)) throw new Error('JSON must be an array, {roads: [...]} or a GeoJSON FeatureCollection.');
  const ids = new Set<string>();
  return rows.map((raw, index) => {
    if (!record(raw)) throw new Error(`Segment ${index + 1}: invalid data.`);
    const item = raw.type === 'Feature' ? raw.properties : raw;
    if (!record(item)) throw new Error(`Segment ${index + 1}: missing properties.`);
    const geometry = raw.geometry;
    const id = item.road_id;
    if ((typeof id !== 'string' && typeof id !== 'number') || (typeof id === 'number' && !Number.isFinite(id)) || !String(id).trim()) throw new Error(`Segment ${index + 1}: missing road_id.`);
    const road_id = String(id);
    if (ids.has(road_id)) throw new Error(`Duplicate road_id: ${road_id}`);
    ids.add(road_id);
    const key = String(item.severity).toLowerCase();
    const severity = Object.hasOwn(levels, key) ? levels[key] : undefined;
    if (!severity) throw new Error(`${road_id}: unsupported severity.`);
    if (!record(geometry) || geometry.type !== 'LineString' || !Array.isArray(geometry.coordinates) || geometry.coordinates.length < 2 || !geometry.coordinates.every(coordinate)) throw new Error(`${road_id}: LineString needs at least 2 valid [longitude, latitude] coordinates.`);
    const coordinates = geometry.coordinates;
    if(item.data_quality!==undefined&&!['fresh','partial','unknown','unconfigured'].includes(String(item.data_quality))) throw new Error(`${road_id}: invalid data_quality.`);
    if (coordinates.every(p => p[0] === coordinates[0][0] && p[1] === coordinates[0][1])) throw new Error(`${road_id}: the road segment must have a length.`);
    for (const field of ['road_name','description','updated_at','alert_id']) if (item[field] !== undefined && typeof item[field] !== 'string') throw new Error(`${road_id}: ${field} must be a string.`);
    if (typeof item.updated_at === 'string' && !Number.isFinite(Date.parse(item.updated_at))) throw new Error(`${road_id}: invalid updated_at.`);
    return { road_id, severity, geometry: { type:'LineString', coordinates: geometry.coordinates }, road_name: item.road_name as string | undefined, description: item.description as string | undefined, updated_at: item.updated_at as string | undefined, alert_id: item.alert_id as string | undefined, monitoring: normalizeMonitoring(item.monitoring), data_quality:item.data_quality as RoadAlert['data_quality'], drain_summary: normalizeDrainSummary(item.drain_summary) };
  });
}
export const toLeafletPositions = (coordinates: Coordinate[]): [number,number][] => coordinates.map(([lng,lat]) => [lat,lng]);
