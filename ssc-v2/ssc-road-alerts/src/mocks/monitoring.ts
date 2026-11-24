import type { Camera } from '../models/camera';
import type { RoadAlert } from '../models/roadAlert';
import { normalizeAlerts } from '../services/normalizeAlerts';
import { normalizeCameras } from '../services/mapService';
import city from './city.json';

/**
 * Dữ liệu cho chế độ "Demo simulation": MỘT THÀNH PHỐ MÔ PHỎNG (khoảng 100 camera, gom thành các tuyến), KHÔNG phải hiện trường thật.
 * city.json có đúng dạng mà backend trả về (/api/road-alerts và /api/cameras, kể cả trạng thái cống đã làm mượt và tổng hợp theo tuyến),
 * do research/cleansight_customer_demo/make_dashboard_data.py sinh ra bằng chính mã tổng hợp của backend; xem README ở thư mục đó.
 * Dữ liệu đi qua đúng các hàm chuẩn hoá của dashboard như dữ liệu từ máy chủ. Trường `trash_regions` (vùng rác m²) là trường tùy chọn mới.
 */
/** Thời điểm mô phỏng của bộ dữ liệu (ISO, UTC). */
export const demoAsOf: string = city.as_of;
export const demoRoads: RoadAlert[] = normalizeAlerts({ roads: city.roads });
export const demoCameras: Camera[] = normalizeCameras({ cameras: city.cameras });
