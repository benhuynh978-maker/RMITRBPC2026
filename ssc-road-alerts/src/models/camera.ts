import type { Coordinate } from './roadAlert';
import type { CameraImages, Monitoring } from './monitoring';
export interface Camera {
  camera_id: string;
  name?: string;
  status?: 'online' | 'offline' | 'unknown';
  geometry: { type: 'Point'; coordinates: Coordinate };
  road_id?: string;
  monitoring?: Monitoring;
  images?: CameraImages;
  analysis_source?: 'simulation' | 'ai';
  analysis_status?: 'fresh' | 'stale';
}
