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
const DRAIN = POLICY.drainState;
const DRAIN_RANK = { unknown:0, clear:1, watch:2, clean:3 };
export const roiVersion = camera => camera.drain_roi?.calibrated_at ?? null;
const lowCertainty = result => typeof result.certainty === 'number' && result.certainty < DRAIN.lowCertainty;
const median = values => { const s=[...values].sort((a,b)=>a-b), m=s.length>>1; return s.length%2 ? s[m] : (s[m-1]+s[m])/2; };
/** Trễ: vào clean ở ≥50 nhưng chỉ ra khi <35; vào watch ở ≥20, ra khi <12. Không có trạng thái trước → ngưỡng thường. */
export function nextDrainState(previous, v) {
  const { clean, watch } = DRAIN;
  if (previous === 'clean') return v >= clean.exit ? 'clean' : v >= watch.exit ? 'watch' : 'clear';
  if (previous === 'watch') return v >= clean.enter ? 'clean' : v < watch.exit ? 'clear' : 'watch';
  return v >= clean.enter ? 'clean' : v >= watch.enter ? 'watch' : 'clear';
}
/** Tính lại drain_state lưu trữ: trung vị các lần đo dùng được, cùng phiên bản ROI và cùng tuyến hiện tại. */
export function computeDrainState(camera, now) {
  const version = roiVersion(camera);
  const readings = (camera.observations ?? []).filter(o => o.status === 'processed' && o.result?.usable !== false && typeof o.result?.drain_blockage_pct === 'number'
    && (o.result.roi_version ?? null) === version && o.road_id === camera.road_id).sort((a,b) => Date.parse(b.captured_at) - Date.parse(a.captured_at));
  const newest = readings[0];
  const recent = newest ? readings.filter(o => Date.parse(newest.captured_at) - Date.parse(o.captured_at) <= POLICY.readingMaxAgeMs).slice(0, DRAIN.windowSize) : [];
  const previous = camera.drain_state;
  const at = new Date(now).toISOString();
  const common = { window_count:recent.length, updated_at:at, ...(newest ? { evidence_observation_id:newest.observation_id, evidence_captured_at:newest.captured_at } : {}),
    roi_calibrated:!!camera.drain_roi, blockage_method:newest?.result.blockage_method ?? (camera.drain_roi ? 'roi' : 'legacy'),
    flags:{ no_trash_in_roi:newest?.result.no_trash_in_roi === true, low_certainty:recent.some(o => lowCertainty(o.result)) } };
  if (recent.length < DRAIN.minReadings) return { state:'unknown', ...common, since:previous?.state === 'unknown' ? previous.since : at, reason:'collecting', needed:DRAIN.minReadings };
  const value = Number(median(recent.map(o => o.result.drain_blockage_pct)).toFixed(2));
  const state = nextDrainState(previous?.state, value);
  return { state, smoothed_blockage_pct:value, ...common, since:previous?.state === state ? previous.since : at, reason:'ok' };
}
/** Trạng thái hiển thị: không ghi lại kho; bằng chứng quá hạn hoặc camera mất kết nối → unknown/stale. */
export function presentDrainState(camera, now) {
  const s = camera.drain_state;
  if (!s) return { state:'unknown', reason:'no_data', window_count:0, roi_calibrated:!!camera.drain_roi };
  if (fresh(s.evidence_captured_at ?? s.updated_at, now) && (!camera.last_seen_at || fresh(camera.last_seen_at, now))) return s;
  const { smoothed_blockage_pct, since, needed, ...rest } = s;
  return { ...rest, state:'unknown', reason:'stale' };
}
const withWasteLevel = monitoring => monitoring?.waste_level !== undefined || typeof monitoring?.waste_coverage_pct !== 'number'
  ? monitoring : {...monitoring, waste_level: wasteLevel(monitoring.waste_coverage_pct)};
export function publicCamera(camera, now = Date.now()) {
  const { observations, latest_analysis, drain_state, ...metadata } = camera;
  return {
    ...metadata,
    status: camera.last_seen_at ? (fresh(camera.last_seen_at,now) ? 'online' : 'offline') : camera.status ?? 'unknown',
    ...(latest_analysis ? { monitoring:withWasteLevel(latest_analysis.monitoring), images:latest_analysis.images, analysis_source:latest_analysis.simulated?'simulation':'ai', analysis_status: fresh(latest_analysis.captured_at,now) ? 'fresh' : 'stale' } : {}),
    pending_count: (observations ?? []).filter(o => o.status === 'pending').length,
    drain_state: presentDrainState(camera, now),
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
  const warnings = linked.length && readings.length < linked.length ? ` ${linked.length-readings.length}/${linked.length} cameras have no valid analysis yet.` : '';
  // Bổ sung, không ảnh hưởng severity: đếm trạng thái cống đã làm mượt; worst = trạng thái đã biết khẩn nhất (clean > watch > clear).
  const drains = linked.map(c => ({ camera_id:c.camera_id, ...presentDrainState(c, now) }));
  const worst = drains.filter(d => d.state !== 'unknown').sort((a,b) => DRAIN_RANK[b.state]-DRAIN_RANK[a.state] || (b.smoothed_blockage_pct??0)-(a.smoothed_blockage_pct??0) || a.camera_id.localeCompare(b.camera_id))[0];
  const drain_summary = { clear:0, watch:0, clean:0, unknown:0, worst_state:worst?.state ?? 'unknown', worst_camera_id:worst?.camera_id ?? null };
  for (const d of drains) drain_summary[d.state]++;
  return {...base, severity, monitoring, drain_summary,
    alert_id:severity !== 'normal' ? (incidentIds.join(':') || base.alert_id) : undefined,
    description:(readings.some(a=>a.simulated)?'[Simulated data via the test API] ':'')+(manual?.description ?? base.description ?? 'Risk level aggregated from cameras.') + warnings,
    data_quality:quality, camera_count:linked.length, analyzed_camera_count:readings.length,
    manual_alert:manual, weather:weather && fresh(weather.observed_at,now) ? weather : undefined,
  };
}
