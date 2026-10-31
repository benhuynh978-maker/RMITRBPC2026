import type { Severity } from './roadAlert';

/** Optional readings from the server/AI. Missing readings mean unknown, never zero. */
export interface Monitoring {
  /** Trung bình % rác của các camera còn hiệu lực trên tuyến. */
  waste_coverage_pct?: number;
  /** Mức độ rác suy từ waste_coverage_pct theo ngưỡng của máy chủ. */
  waste_level?: Severity;
  /** Mức che miệng cống = trung bình % rác che miệng cống, chỉ tính camera thực sự thấy cống. */
  drain_blockage_pct?: number;
  waste_camera_count?: number;
  waste_max_pct?: number;
  flood_camera_count?: number;
  flood_max_pct?: number;
  rain_expected?: boolean;
  observed_at?: string;
}

export interface CameraImages {
  original_url?: string;
  analyzed_url?: string;
  captured_at?: string;
}
