/** Mã trạng thái do máy chủ trả về. Lưu ý: `clean` nghĩa là "Cần dọn"; không hiển thị mã thô cho người dùng. */
export type DrainStateName = 'clear' | 'watch' | 'clean' | 'unknown';

/** Vùng miệng cống cố định theo camera, tọa độ chuẩn hóa [0,1] (x sang phải, y xuống dưới). */
export interface DrainRoi {
  polygon: [number, number][];
  source: 'ai' | 'manual';
  calibrated_at: string;
}

export interface DrainState {
  state: DrainStateName;
  window_count: number;
  updated_at?: string;
  since?: string;
  smoothed_blockage_pct?: number;
  needed?: number;
  reason?: 'ok' | 'collecting' | 'stale' | 'no_data';
  roi_calibrated?: boolean;
  blockage_method?: 'roi' | 'legacy';
  flags?: { no_trash_in_roi?: boolean; low_certainty?: boolean };
  evidence_observation_id?: string;
  evidence_captured_at?: string;
}

/** Tóm tắt theo tuyến: số camera ở mỗi trạng thái và trạng thái nặng nhất. */
export interface DrainSummary {
  clear: number;
  watch: number;
  clean: number;
  unknown: number;
  worst_state: DrainStateName;
  worst_camera_id: string | null;
}
