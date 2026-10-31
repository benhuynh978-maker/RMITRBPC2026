// Ngưỡng đưa tuyến vào hàng đợi cần chú ý. Mức rác bám theo thang đã hiệu chỉnh của
// máy chủ (1/5/10/20 — xem server/config.js); tỉ lệ ngập giữ thang 0–100 như cũ.
export const MONITORING_CONFIG = {
  wasteThreshold: 10,
  floodThreshold: 70,
  pollIntervalMs: 30_000,
};
