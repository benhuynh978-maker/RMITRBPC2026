/** Các mức chất lượng JPEG thử lần lượt (cao -> thấp) khi nén ảnh trước khi gửi. */
export const qualitySteps: readonly number[] = Object.freeze([0.9, 0.8, 0.7, 0.6]);

export interface FitSize { width: number; height: number }

/**
 * Thu nhỏ (w x h) để cạnh dài nhất <= maxSide, giữ nguyên tỉ lệ. Không bao giờ phóng to.
 * Kết quả luôn là số nguyên >= 1. Đầu vào không hợp lệ (<= 0, NaN, Infinity) thì ném RangeError.
 */
export function fitSize(w: number, h: number, maxSide: number): FitSize {
  if (![w, h, maxSide].every(v => Number.isFinite(v) && v > 0)) throw new RangeError('Invalid image size');
  const width = Math.max(1, Math.round(w));
  const height = Math.max(1, Math.round(h));
  const limit = Math.max(1, Math.floor(maxSide));
  const longest = Math.max(width, height);
  if (longest <= limit) return { width, height };
  const scale = limit / longest;
  // Cạnh dài chốt đúng bằng limit để không lệch do làm tròn; cạnh ngắn làm tròn theo tỉ lệ.
  return width >= height
    ? { width: limit, height: Math.max(1, Math.round(height * scale)) }
    : { width: Math.max(1, Math.round(width * scale)), height: limit };
}
