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
    if (road.severity !== 'normal') { reasons.push(`Road alert: ${SEVERITY[road.severity].label}`); triggers.push('road'); }
    if (m?.waste_coverage_pct !== undefined && m.waste_coverage_pct >= config.wasteThreshold) {
      reasons.push(`Litter ${m.waste_coverage_pct}% ≥ threshold ${config.wasteThreshold}%`); triggers.push('waste');
    }
    if (m?.drain_blockage_pct !== undefined && m.drain_blockage_pct >= config.floodThreshold) {
      reasons.push(`Drain inlet coverage ${m.drain_blockage_pct}% ≥ threshold ${config.floodThreshold}%`); triggers.push('flood');
    }
    if (m?.rain_expected === true) { reasons.push('Rain forecast signal'); triggers.push('rain'); }
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
    'CleanSight — LITTER PICKUP / DRAIN INSPECTION REQUEST',
    demo ? 'SIMULATED DATA — NOT FOR REAL DISPATCH' : 'Ticket exported from the interface. Not yet sent to the receiving unit.',
    `Created at: ${new Date().toISOString()}`,
    `Requested receiving unit: ${team.trim()}`,
    `Road: ${alert.road.road_name ?? alert.road.road_id} (${alert.road.road_id})`,
    `Alert ID: ${alert.road.alert_id ?? 'Not provided by the backend'}`,
    `Priority: ${SEVERITY[alert.severity].label}`, ...alert.reasons,
    `Description: ${alert.road.description ?? 'None'}`,
    `Observed at: ${alert.road.monitoring?.observed_at ?? alert.road.updated_at ?? 'None'}`,
    `Camera: ${cameras.filter(c => c.road_id === alert.road.road_id).map(c => c.camera_id).join(', ') || 'Not linked'}`,
    `Notes: ${note.trim() || 'None'}`,
    `GeoJSON (WGS84, longitude before latitude): ${JSON.stringify(alert.road.geometry)}`,
  ].join('\n');
}
