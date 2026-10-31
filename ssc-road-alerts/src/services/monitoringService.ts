import { MONITORING_CONFIG } from '../config/monitoring';
import { SEVERITY } from '../config/severity';
import type { Camera } from '../models/camera';
import type { RoadAlert, Severity } from '../models/roadAlert';

export interface MonitoringAlert {
  key: string;
  road: RoadAlert;
  severity: Severity;
  reasons: string[];
}
/** Road-level readings are authoritative server aggregates, not averages guessed from cameras. */
export function buildMonitoringAlerts(roads: RoadAlert[], config = MONITORING_CONFIG): MonitoringAlert[] {
  return roads.flatMap(road => {
    const m = road.monitoring;
    const reasons: string[] = [];
    const triggers: string[] = [];
    if (road.severity !== 'normal') { reasons.push(`Cảnh báo tuyến: ${SEVERITY[road.severity].label}`); triggers.push('road'); }
    if (m?.waste_coverage_pct !== undefined && m.waste_coverage_pct >= config.wasteThreshold) {
      reasons.push(`Rác ${m.waste_coverage_pct}% ≥ ngưỡng ${config.wasteThreshold}%`); triggers.push('waste');
    }
    if (m?.drain_blockage_pct !== undefined && m.drain_blockage_pct >= config.floodThreshold) {
      reasons.push(`Tỉ lệ ngập ${m.drain_blockage_pct}% ≥ ngưỡng ${config.floodThreshold}%`); triggers.push('flood');
    }
    if (m?.rain_expected === true) { reasons.push('Có tín hiệu dự báo mưa'); triggers.push('rain'); }
    if (!reasons.length) return [];
    const severity = [road.severity, ...(triggers.some(t => t !== 'road') ? ['medium' as const] : [])]
      .sort((a, b) => SEVERITY[b].rank - SEVERITY[a].rank)[0];
    // Poll timestamps and small metric fluctuations must not create duplicate notifications.
    const key = JSON.stringify([road.road_id, road.alert_id ?? '', road.severity, severity, ...triggers]);
    return [{ key, road, severity, reasons }];
  }).sort((a, b) => SEVERITY[b.severity].rank - SEVERITY[a.severity].rank || a.road.road_id.localeCompare(b.road.road_id));
}

export interface HandlingRecord {
  acknowledged_at?: string;
  prepared_at?: string;
  team?: string;
  note?: string;
}
export function handoffText(alert: MonitoringAlert, cameras: Camera[], team: string, note: string, demo: boolean): string {
  return [
    'SSC — PHIẾU ĐỀ NGHỊ THU GOM RÁC / KIỂM TRA CỐNG',
    demo ? 'DỮ LIỆU MÔ PHỎNG — KHÔNG DÙNG ĐIỀU PHỐI THỰC TẾ' : 'Phiếu xuất từ giao diện. Chưa gửi đến đơn vị tiếp nhận.',
    `Lập lúc: ${new Date().toISOString()}`,
    `Đơn vị đề nghị tiếp nhận: ${team.trim()}`,
    `Tuyến: ${alert.road.road_name ?? alert.road.road_id} (${alert.road.road_id})`,
    `Mã đợt cảnh báo: ${alert.road.alert_id ?? 'Chưa có từ backend'}`,
    `Ưu tiên: ${SEVERITY[alert.severity].label}`, ...alert.reasons,
    `Mô tả: ${alert.road.description ?? 'Chưa có'}`,
    `Quan sát lúc: ${alert.road.monitoring?.observed_at ?? alert.road.updated_at ?? 'Chưa có'}`,
    `Camera: ${cameras.filter(c => c.road_id === alert.road.road_id).map(c => c.camera_id).join(', ') || 'Chưa liên kết'}`,
    `Ghi chú: ${note.trim() || 'Không có'}`,
    `GeoJSON (WGS84, kinh độ trước vĩ độ): ${JSON.stringify(alert.road.geometry)}`,
  ].join('\n');
}
