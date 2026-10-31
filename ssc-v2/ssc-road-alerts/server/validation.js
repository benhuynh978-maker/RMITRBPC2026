const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const position = p => Array.isArray(p) && p.length === 2 && p.every(n => typeof n === 'number' && Number.isFinite(n)) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90;
const severity = new Set(['normal','low','medium','high','critical']);
function validateMonitoring(value, id) {
  if (value === undefined) return;
  if (!object(value)) throw new Error(`${id}: monitoring must be an object`);
  for (const key of ['waste_coverage_pct','drain_blockage_pct','flood_percentage']) {
    const number = value[key];
    if (number !== undefined && (typeof number !== 'number' || !Number.isFinite(number) || number < 0 || number > 100)) throw new Error(`${id}: ${key} must be between 0 and 100`);
  }
  if (value.flood_risk !== undefined && !severity.has(value.flood_risk)) throw new Error(`${id}: flood_risk is invalid`);
  if (value.waste_level !== undefined && !severity.has(value.waste_level)) throw new Error(`${id}: waste_level is invalid`);
  if (value.rain_expected !== undefined && typeof value.rain_expected !== 'boolean') throw new Error(`${id}: rain_expected must be a boolean`);
  if (value.observed_at !== undefined && (typeof value.observed_at !== 'string' || !Number.isFinite(Date.parse(value.observed_at)))) throw new Error(`${id}: observed_at is invalid`);
  if (value.blockage_method !== undefined && !blockageMethods.has(value.blockage_method)) throw new Error(`${id}: blockage_method is invalid`);
  for (const key of ['no_trash_in_roi','low_certainty']) if (value[key] !== undefined && typeof value[key] !== 'boolean') throw new Error(`${id}: ${key} must be a boolean`);
  if (value.certainty !== undefined && !unit(value.certainty)) throw new Error(`${id}: certainty must be between 0 and 1`);
}
const blockageMethods = new Set(['roi','legacy']);
const unit = n => typeof n === 'number' && Number.isFinite(n) && n >= 0 && n <= 1;
const date = s => typeof s === 'string' && Number.isFinite(Date.parse(s));
/** Vùng miệng cống cố định theo camera, tọa độ chuẩn hóa [0,1] (x sang phải, y xuống dưới). */
export function validateRoi(value, id) {
  if (value === undefined || value === null) return;
  if (!object(value) || !Array.isArray(value.polygon) || value.polygon.length < 3 || value.polygon.length > 64 || !value.polygon.every(p => Array.isArray(p) && p.length === 2 && p.every(unit))) throw new Error(`${id}: drain_roi.polygon needs 3–64 [x,y] points between 0 and 1`);
  if (!['ai','manual'].includes(value.source)) throw new Error(`${id}: drain_roi.source must be ai or manual`);
  if (!date(value.calibrated_at)) throw new Error(`${id}: drain_roi.calibrated_at is invalid`);
}
function validateDrainState(value, id) {
  if (value === undefined) return;
  if (!object(value) || !['clear','watch','clean','unknown'].includes(value.state) || !Number.isInteger(value.window_count) || value.window_count < 0 || !date(value.updated_at)) throw new Error(`${id}: drain_state is invalid`);
  const pct = value.smoothed_blockage_pct;
  if (pct !== undefined && (typeof pct !== 'number' || !Number.isFinite(pct) || pct < 0 || pct > 100)) throw new Error(`${id}: drain_state.smoothed_blockage_pct is invalid`);
  if (value.state !== 'unknown' && (pct === undefined || !date(value.since))) throw new Error(`${id}: drain_state is missing smoothed_blockage_pct/since`);
}

function validateImages(value, id) {
  if (value === undefined) return;
  if (!object(value)) throw new Error(`${id}: images must be an object`);
  for (const key of ['original_url','analyzed_url']) {
    const url = value[key];
    if (url !== undefined && (typeof url !== 'string' || !/^(https?:\/\/|\/(?!\/))[^\s\\]+$/i.test(url))) throw new Error(`${id}: ${key} needs an HTTP(S) URL or a /... path`);
  }
  if (value.captured_at !== undefined && (typeof value.captured_at !== 'string' || !Number.isFinite(Date.parse(value.captured_at)))) throw new Error(`${id}: captured_at is invalid`);
}
export function validateDataset(payload, kind) {
  if (!object(payload) || !Array.isArray(payload[kind])) throw new Error(`Missing array ${kind}`);
  const ids = new Set();
  for (const item of payload[kind]) {
    if (!object(item)) throw new Error('Each element must be an object');
    const id = item[kind === 'cameras' ? 'camera_id' : 'road_id'];
    if (typeof id !== 'string' || !id.trim() || ids.has(id)) throw new Error('ID must be a non-empty, unique string');
    ids.add(id);
    validateMonitoring(item.monitoring, id);
    const g = item.geometry;
    if (!object(g)) throw new Error(`${id}: missing geometry`);
    if (kind === 'cameras') {
      if (g.type !== 'Point' || !position(g.coordinates)) throw new Error(`${id}: Point has invalid [lng,lat] coordinates`);
      if (item.status !== undefined && !['online','offline','unknown'].includes(item.status)) throw new Error(`${id}: status is invalid`);
      if (item.road_id !== undefined && (typeof item.road_id !== 'string' || !item.road_id.trim())) throw new Error(`${id}: camera road_id is invalid`);
      validateImages(item.images, id);
      validateRoi(item.drain_roi, id);
      validateDrainState(item.drain_state, id);
      if (item.observations !== undefined) {
        if (!Array.isArray(item.observations)) throw new Error(`${id}: observations is invalid`);
        const observationIds=new Set();
        for(const observation of item.observations){
          if(!object(observation)||typeof observation.observation_id!=='string'||observationIds.has(observation.observation_id)||!['pending','processed','failed','needs_review'].includes(observation.status)||!Number.isFinite(Date.parse(observation.captured_at))||!Number.isFinite(Date.parse(observation.received_at)))throw new Error(`${id}: invalid or duplicate observation`);
          observationIds.add(observation.observation_id);
        }
      }
      if(item.latest_analysis!==undefined){
        const latest=item.latest_analysis;
        // drain_blockage_pct được phép vắng mặt: camera không thấy miệng cống thì không có ý kiến về nó.
        if(!object(latest)||!severity.has(latest.severity)||!Number.isFinite(Date.parse(latest.captured_at))||!object(latest.monitoring)||!(latest.monitoring.waste_level!==undefined&&latest.monitoring.flood_percentage!==undefined||latest.monitoring.waste_coverage_pct!==undefined))throw new Error(`${id}: latest_analysis is invalid`);
        validateMonitoring(latest.monitoring,id);validateImages(latest.images,id);
      }
    } else {
      if (!severity.has(item.severity)) throw new Error(`${id}: severity is invalid`);
      if (g.type !== 'LineString' || !Array.isArray(g.coordinates) || g.coordinates.length < 2 || !g.coordinates.every(position)) throw new Error(`${id}: LineString needs at least 2 valid points`);
      if (g.coordinates.every(p => p[0] === g.coordinates[0][0] && p[1] === g.coordinates[0][1])) throw new Error(`${id}: the road segment must have a length`);
    }
    for (const key of ['name','road_name','description','updated_at','alert_id']) {
      if (item[key] !== undefined && typeof item[key] !== 'string') throw new Error(`${id}: ${key} must be a string`);
    }
    if (item.updated_at !== undefined && !Number.isFinite(Date.parse(item.updated_at))) throw new Error(`${id}: invalid updated_at`);
  }
  return payload;
}
