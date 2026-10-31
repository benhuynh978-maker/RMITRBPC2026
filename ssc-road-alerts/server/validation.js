const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const position = p => Array.isArray(p) && p.length === 2 && p.every(n => typeof n === 'number' && Number.isFinite(n)) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90;
const severity = new Set(['normal','low','medium','high','critical']);
function validateMonitoring(value, id) {
  if (value === undefined) return;
  if (!object(value)) throw new Error(`${id}: monitoring phải là object`);
  for (const key of ['waste_coverage_pct','drain_blockage_pct','flood_percentage']) {
    const number = value[key];
    if (number !== undefined && (typeof number !== 'number' || !Number.isFinite(number) || number < 0 || number > 100)) throw new Error(`${id}: ${key} phải trong khoảng 0–100`);
  }
  if (value.flood_risk !== undefined && !severity.has(value.flood_risk)) throw new Error(`${id}: flood_risk sai`);
  if (value.waste_level !== undefined && !severity.has(value.waste_level)) throw new Error(`${id}: waste_level sai`);
  if (value.rain_expected !== undefined && typeof value.rain_expected !== 'boolean') throw new Error(`${id}: rain_expected phải là boolean`);
  if (value.observed_at !== undefined && (typeof value.observed_at !== 'string' || !Number.isFinite(Date.parse(value.observed_at)))) throw new Error(`${id}: observed_at sai`);
}

function validateImages(value, id) {
  if (value === undefined) return;
  if (!object(value)) throw new Error(`${id}: images phải là object`);
  for (const key of ['original_url','analyzed_url']) {
    const url = value[key];
    if (url !== undefined && (typeof url !== 'string' || !/^(https?:\/\/|\/(?!\/))[^\s\\]+$/i.test(url))) throw new Error(`${id}: ${key} cần URL HTTP(S) hoặc đường dẫn /...`);
  }
  if (value.captured_at !== undefined && (typeof value.captured_at !== 'string' || !Number.isFinite(Date.parse(value.captured_at)))) throw new Error(`${id}: captured_at sai`);
}
export function validateDataset(payload, kind) {
  if (!object(payload) || !Array.isArray(payload[kind])) throw new Error(`Thiếu mảng ${kind}`);
  const ids = new Set();
  for (const item of payload[kind]) {
    if (!object(item)) throw new Error('Phần tử phải là object');
    const id = item[kind === 'cameras' ? 'camera_id' : 'road_id'];
    if (typeof id !== 'string' || !id.trim() || ids.has(id)) throw new Error('ID phải là chuỗi không rỗng, không trùng');
    ids.add(id);
    validateMonitoring(item.monitoring, id);
    const g = item.geometry;
    if (!object(g)) throw new Error(`${id}: thiếu geometry`);
    if (kind === 'cameras') {
      if (g.type !== 'Point' || !position(g.coordinates)) throw new Error(`${id}: Point sai tọa độ [lng,lat]`);
      if (item.status !== undefined && !['online','offline','unknown'].includes(item.status)) throw new Error(`${id}: status sai`);
      if (item.road_id !== undefined && (typeof item.road_id !== 'string' || !item.road_id.trim())) throw new Error(`${id}: road_id camera sai`);
      validateImages(item.images, id);
      if (item.observations !== undefined) {
        if (!Array.isArray(item.observations)) throw new Error(`${id}: observations sai`);
        const observationIds=new Set();
        for(const observation of item.observations){
          if(!object(observation)||typeof observation.observation_id!=='string'||observationIds.has(observation.observation_id)||!['pending','processed','failed','needs_review'].includes(observation.status)||!Number.isFinite(Date.parse(observation.captured_at))||!Number.isFinite(Date.parse(observation.received_at)))throw new Error(`${id}: observation sai hoặc trùng`);
          observationIds.add(observation.observation_id);
        }
      }
      if(item.latest_analysis!==undefined){
        const latest=item.latest_analysis;
        // drain_blockage_pct được phép vắng mặt: camera không thấy miệng cống thì không có ý kiến về nó.
        if(!object(latest)||!severity.has(latest.severity)||!Number.isFinite(Date.parse(latest.captured_at))||!object(latest.monitoring)||!(latest.monitoring.waste_level!==undefined&&latest.monitoring.flood_percentage!==undefined||latest.monitoring.waste_coverage_pct!==undefined))throw new Error(`${id}: latest_analysis sai`);
        validateMonitoring(latest.monitoring,id);validateImages(latest.images,id);
      }
    } else {
      if (!severity.has(item.severity)) throw new Error(`${id}: severity sai`);
      if (g.type !== 'LineString' || !Array.isArray(g.coordinates) || g.coordinates.length < 2 || !g.coordinates.every(position)) throw new Error(`${id}: LineString cần ít nhất 2 điểm hợp lệ`);
      if (g.coordinates.every(p => p[0] === g.coordinates[0][0] && p[1] === g.coordinates[0][1])) throw new Error(`${id}: đoạn đường phải có độ dài`);
    }
    for (const key of ['name','road_name','description','updated_at','alert_id']) {
      if (item[key] !== undefined && typeof item[key] !== 'string') throw new Error(`${id}: ${key} phải là chuỗi`);
    }
    if (item.updated_at !== undefined && !Number.isFinite(Date.parse(item.updated_at))) throw new Error(`${id}: updated_at không hợp lệ`);
  }
  return payload;
}
