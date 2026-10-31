import type { Monitoring } from './monitoring';
import type { DrainSummary } from './drain';
export type Severity = 'normal' | 'low' | 'medium' | 'high' | 'critical';
/** GeoJSON uses longitude BEFORE latitude. */
export type Coordinate = [number, number] | [number, number, number];
export interface RoadAlert {
  road_id: string;
  severity: Severity;
  geometry: { type: 'LineString'; coordinates: Coordinate[] };
  road_name?: string;
  description?: string;
  updated_at?: string;
  alert_id?: string;
  monitoring?: Monitoring;
  data_quality?: 'fresh' | 'partial' | 'unknown' | 'unconfigured';
  drain_summary?: DrainSummary;
}
export interface AlertResult {
  roads: RoadAlert[];
  source: 'api' | 'mock' | 'fallback';
  receivedAt: string;
  warning?: string;
}
export type DataMode = 'mock' | 'api' | 'auto';
