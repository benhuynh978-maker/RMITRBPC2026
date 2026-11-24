import type { Coordinate } from './roadAlert';

/**
 * Một vùng rác do AI khoanh trên ảnh của camera, đã chiếu xuống mặt đất (đa giác trên bản đồ, kèm diện tích m²).
 * Trường TÙY CHỌN của camera: hiện chỉ dữ liệu demo có; backend và AI worker chưa gửi trường này.
 * `ring` theo thứ tự GeoJSON [kinh độ, vĩ độ]. `drain` = đám rác nằm trên vùng cống, `street` = rác xung quanh.
 */
export interface TrashRegion {
  kind: 'drain' | 'street';
  area_m2: number;
  ring: Coordinate[];
}
