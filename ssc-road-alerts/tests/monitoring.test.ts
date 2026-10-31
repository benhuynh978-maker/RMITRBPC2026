import { describe, it, expect } from 'vitest';
import { normalizeAlerts } from '../src/services/normalizeAlerts';
import { normalizeCameras } from '../src/services/mapService';
import { buildMonitoringAlerts, handoffText } from '../src/services/monitoringService';
import { demoRoads, demoCameras } from '../src/mocks/monitoring';
import type { RoadAlert } from '../src/models/roadAlert';
const road: RoadAlert = { road_id:'R1', severity:'normal', geometry:{type:'LineString',coordinates:[[106.7,10.77],[106.71,10.78]]} };

describe('SSC monitoring contract and prioritization', () => {
  it('keeps legacy responses compatible, with missing metrics unknown', () => {
    expect(normalizeAlerts({roads:[road]})[0].monitoring).toBeUndefined();
    expect(buildMonitoringAlerts([road])).toEqual([]);
  });
  it('notifies exactly at configured threshold and for rain, never treats false as rain', () => {
    expect(buildMonitoringAlerts([{...road,monitoring:{waste_coverage_pct:9.9,rain_expected:false}}])).toEqual([]);
    expect(buildMonitoringAlerts([{...road,monitoring:{waste_coverage_pct:10}}])[0].severity).toBe('medium');
    expect(buildMonitoringAlerts([{...road,monitoring:{rain_expected:true}}])[0].reasons).toContain('Có tín hiệu dự báo mưa');
    expect(buildMonitoringAlerts([{...road,monitoring:{drain_blockage_pct:70}}])).toHaveLength(1);
    expect(buildMonitoringAlerts([{...road,severity:'high'}])[0].severity).toBe('high');
  });
  it('sorts urgent incidents first and preserves monitoring through both adapters', () => {
    const alerts=buildMonitoringAlerts(normalizeAlerts({roads:[...demoRoads].reverse()}));
    expect(alerts[0].severity).toBe('critical');
    expect(alerts).toHaveLength(2);
    expect(normalizeCameras({cameras:demoCameras})[0].road_id).toBe('DEMO-R1');
  });
  it('does not notify again on polling timestamps; new incident or escalation has a new key', () => {
    const original={...road,severity:'high' as const,alert_id:'A1'};
    const key=buildMonitoringAlerts([original])[0].key;
    expect(buildMonitoringAlerts([{...original,updated_at:'2026-09-09T12:00:00Z'}])[0].key).toBe(key);
    expect(buildMonitoringAlerts([{...original,alert_id:'A2'}])[0].key).not.toBe(key);
    expect(buildMonitoringAlerts([{...original,severity:'critical'}])[0].key).not.toBe(key);
  });
  it('rejects invalid metrics, time, degenerate lines and unsafe image URLs', () => {
    expect(()=>normalizeAlerts([{...road,monitoring:{waste_coverage_pct:101}}])).toThrow();
    expect(()=>normalizeAlerts([{...road,monitoring:{rain_expected:'false'}}])).toThrow();
    expect(()=>normalizeAlerts([{...road,monitoring:{waste_level:'constructor'}}])).toThrow();
    expect(()=>normalizeAlerts([{...road,geometry:{type:'LineString',coordinates:[[106,10],[106,10]]}}])).toThrow();
    for (const url of ['javascript:alert(1)','//example.com/x.jpg','/\\example.com/x.jpg']) expect(()=>normalizeCameras({cameras:[{...demoCameras[0],images:{original_url:url}}]})).toThrow();
    expect(()=>normalizeCameras({cameras:[{...demoCameras[0],images:{captured_at:'invalid'}}]})).toThrow();
    expect(normalizeCameras({cameras:[{...demoCameras[0],images:{original_url:'/images/original.jpg',analyzed_url:'https://example.com/ai.jpg'}}]})[0].images?.original_url).toBe('/images/original.jpg');
  });
  it('exports a traceable handoff without pretending delivery, including demo disclaimer', () => {
    const text=handoffText(buildMonitoringAlerts(demoRoads)[0],demoCameras,'Đội vệ sinh A','Kiểm tra cống',true);
    expect(text).toContain('KHÔNG DÙNG ĐIỀU PHỐI THỰC TẾ');
    expect(text).toContain('DEMO-C1');
    expect(text).toContain('LineString');
    expect(text).toContain('Đội vệ sinh A');
  });
});
