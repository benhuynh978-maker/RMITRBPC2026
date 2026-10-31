import { POLICY } from './config.js';
export const LEVELS = ['normal','low','medium','high','critical'];
const rankOf = (value, thresholds) => value >= thresholds.critical ? 4 : value >= thresholds.high ? 3 : value >= thresholds.medium ? 2 : value >= thresholds.low ? 1 : 0;
export const wasteLevel = pct => LEVELS[rankOf(pct, POLICY.waste)];
export const floodLevel = pct => LEVELS[rankOf(pct, POLICY.blockage)];
/** Rác và ngập dùng hai thang ngưỡng khác nhau; ngập có thể vắng mặt khi camera không thấy miệng cống. */
export function evaluateSeverity(waste, flood) {
  const ranks = [rankOf(waste ?? 0, POLICY.waste)];
  if (typeof flood === 'number') ranks.push(rankOf(flood, POLICY.blockage));
  return LEVELS[Math.max(...ranks)];
}
const fresh = (time, now) => Number.isFinite(Date.parse(time)) && now - Date.parse(time) <= POLICY.readingMaxAgeMs && Date.parse(time) <= now + POLICY.maxFutureSkewMs;
const withWasteLevel = monitoring => monitoring?.waste_level !== undefined || typeof monitoring?.waste_coverage_pct !== 'number'
  ? monitoring : {...monitoring, waste_level: wasteLevel(monitoring.waste_coverage_pct)};
export function publicCamera(camera, now = Date.now()) {
  const { observations, latest_analysis, ...metadata } = camera;
  return {
    ...metadata,
    status: camera.last_seen_at ? (fresh(camera.last_seen_at,now) ? 'online' : 'offline') : camera.status ?? 'unknown',
    ...(latest_analysis ? { monitoring:withWasteLevel(latest_analysis.monitoring), images:latest_analysis.images, analysis_source:latest_analysis.simulated?'simulation':'ai', analysis_status: fresh(latest_analysis.captured_at,now) ? 'fresh' : 'stale' } : {}),
    pending_count: (observations ?? []).filter(o => o.status === 'pending').length,
  };
}
export function aggregateRoad(road, cameras, now = Date.now()) {
  const {manual_alert,weather,...base} = road;
  const linked = cameras.filter(c => c.road_id === road.road_id);
  const readings = linked.map(c=>c.latest_analysis).filter(a=>a && fresh(a.captured_at,now));
  const rain = weather && fresh(weather.observed_at,now) ? weather.rain_expected : undefined;
  const manual = manual_alert && Date.parse(manual_alert.expires_at) > now ? manual_alert : undefined;
  let monitoring = linked.length ? undefined : base.monitoring;
  let severity = linked.length ? 'normal' : base.severity;
  if (readings.length) {
    const numbers = key => readings.map(a=>a.monitoring[key]).filter(v=>typeof v==='number');
    const mean = list => list.length ? Number((list.reduce((sum,v)=>sum+v,0)/list.length).toFixed(2)) : undefined;
    const wasteValues = numbers('waste_coverage_pct');
    // Camera không nhìn thấy miệng cống nào thì bỏ trống trường này, không gửi 0 — số 0 đó sẽ
    // kéo trung bình xuống dù camera ấy không hề có ý kiến gì về tình trạng cống.
    const floodValues = [...numbers('drain_blockage_pct'), ...numbers('flood_percentage')];
    const waste = mean(wasteValues);
    const flood = mean(floodValues);
    const reported = readings.map(a=>a.monitoring.waste_level).filter(v=>LEVELS.includes(v))
      .sort((a,b)=>LEVELS.indexOf(b)-LEVELS.indexOf(a))[0];
    severity = LEVELS[Math.max(LEVELS.indexOf(evaluateSeverity(waste,flood)), LEVELS.indexOf(reported??'normal'))];
    if(rain&&LEVELS.indexOf(severity)>=2)severity=LEVELS[Math.min(4,LEVELS.indexOf(severity)+1)];
    monitoring = {
      waste_coverage_pct: waste,
      waste_level: waste === undefined ? reported : LEVELS[Math.max(LEVELS.indexOf(wasteLevel(waste)), LEVELS.indexOf(reported??'normal'))],
      drain_blockage_pct: flood,
      // Trung bình dễ đọc nhưng giấu mất điểm nặng cục bộ, nên kèm số camera đã tính và giá trị cao nhất.
      waste_camera_count: wasteValues.length,
      waste_max_pct: wasteValues.length ? Math.max(...wasteValues) : undefined,
      flood_camera_count: floodValues.length,
      flood_max_pct: floodValues.length ? Math.max(...floodValues) : undefined,
      observed_at: readings.map(a=>a.captured_at).sort()[0],
    };
  }
  if (rain !== undefined) monitoring = {...monitoring, rain_expected:rain};
  if (rain && LEVELS.indexOf(severity) < 2) severity = 'medium';
  if (manual && LEVELS.indexOf(manual.severity) > LEVELS.indexOf(severity)) severity = manual.severity;
  const incidentIds = readings.filter(a=>a.incident_id).map(a=>a.incident_id).sort();
  if (manual) incidentIds.push(manual.alert_id);
  if (rain) incidentIds.push(weather.event_id);
  const quality = linked.length ? (readings.length === linked.length ? 'fresh' : readings.length ? 'partial' : 'unknown') : 'unconfigured';
  const warnings = linked.length && readings.length < linked.length ? ` ${linked.length-readings.length}/${linked.length} camera chưa có phân tích còn hiệu lực.` : '';
  return {...base, severity, monitoring,
    alert_id:severity !== 'normal' ? (incidentIds.join(':') || base.alert_id) : undefined,
    description:(readings.some(a=>a.simulated)?'[Dữ liệu mô phỏng qua API test] ':'')+(manual?.description ?? base.description ?? 'Tổng hợp mức rủi ro theo camera.') + warnings,
    data_quality:quality, camera_count:linked.length, analyzed_camera_count:readings.length,
    manual_alert:manual, weather:weather && fresh(weather.observed_at,now) ? weather : undefined,
  };
}
