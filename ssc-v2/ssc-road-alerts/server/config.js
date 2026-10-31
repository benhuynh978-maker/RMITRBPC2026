// Ngưỡng mức độ rác hiệu chỉnh theo phân bố đo trên 1.819 ảnh đã gán nhãn tay
// (trung vị 0.95%, p90 9.26%, p95 15.3%, p99 29%): thang 20/50/70/90 cũ gần như
// không bao giờ chạm tới vì rác hiếm khi phủ quá 1/5 khung hình.
// Ngưỡng che cống giữ thang cũ vì phân bố thực tế trải đều 0–100 (trung vị 15%, p90 90%).
export const POLICY = Object.freeze({
  waste: Object.freeze({ low: 1, medium: 5, high: 10, critical: 20 }),
  blockage: Object.freeze({ low: 20, medium: 50, high: 70, critical: 90 }),
  // v2: không còn dùng để chặn kết quả. confidence = min(mọi detection) phản thông tin (ảnh càng
  // nhiều rác càng thấp) nên đẩy gần hết ảnh có rác vào needs_review. Giữ để tương thích /api/policy.
  minConfidence: 0.5,
  // Trạng thái cống theo camera: trung vị `windowSize` lần đo gần nhất + trễ (enter/exit) chống nhấp nháy.
  // certainty < lowCertainty chỉ gắn nhãn low_certainty, không chặn.
  drainState: Object.freeze({ windowSize: 5, minReadings: 3, clean: Object.freeze({ enter: 50, exit: 35 }), watch: Object.freeze({ enter: 20, exit: 12 }), lowCertainty: 0.5 }),
  readingMaxAgeMs: 15 * 60_000,
  maxFutureSkewMs: 5 * 60_000,
  maxObservationsPerCamera: 100,
  maxImageBytes: 5 * 1024 * 1024,
  maxJsonBytes: 64 * 1024,
});
