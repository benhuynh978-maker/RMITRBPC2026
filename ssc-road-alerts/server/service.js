import { randomUUID } from 'node:crypto';
import { createJsonStore } from './store.js';
import { validateDataset } from './validation.js';
import { requireValue, ApiError } from './errors.js';
import { fields, id, timestamp, percent, imageUrl } from './input.js';
import { POLICY } from './config.js';
import { aggregateRoad, publicCamera, evaluateSeverity, LEVELS } from './aggregation.js';

const entityFields = {
  cameras:['camera_id','road_id','name','status','geometry'],
  roads:['road_id','road_name','description','geometry','severity'],
};
const find = (rows, key, value) => {
  const entity=rows.find(row=>row[key]===value);
  requireValue(entity, `${key} không tồn tại: ${value}`,404);
  return entity;
};
const validate = (kind, rows) => {
  try { validateDataset({[kind]:rows},kind); } catch (error) { throw new ApiError(400,error.message); }
};
export function createService(dataDir, clock = Date.now) {
  const store=createJsonStore(dataDir);
  const iso=()=>new Date(clock()).toISOString();
  async function list(kind) {
    if (kind==='cameras') return (await store.read(kind)).map(c=>publicCamera(c,clock()));
    return store.transaction(async tx=>{
      const roads=await tx.read('roads');
      const cameras=await tx.read('cameras');
      return roads.map(r=>aggregateRoad(r,cameras,clock()));
    });
  }
  async function save(kind, payload, entityId) {
    fields(payload,entityFields[kind]);
    const key=kind==='cameras'?'camera_id':'road_id';
    if (entityId) requireValue(payload[key]===undefined || payload[key]===entityId,'Không được đổi ID');
    else id(payload[key],key);
    return store.transaction(async tx=>{
      const rows=await tx.read(kind);
      const old=entityId?find(rows,key,entityId):undefined;
      requireValue(old || !rows.some(row=>row[key]===payload[key]),'ID đã tồn tại',409);
      const entity={...(kind==='roads'?{severity:'normal'}:{status:'unknown'}),...old,...payload};
      validate(kind,[entity]);
      if(kind==='cameras'&&entity.road_id) find(await tx.read('roads'),'road_id',entity.road_id);
      if(kind==='cameras'&&old&&old.road_id!==entity.road_id) {
        requireValue(!(old.observations??[]).some(o=>o.status==='pending'),'Camera còn tác vụ AI đang chờ; xử lý xong trước khi đổi tuyến',409);
        delete entity.latest_analysis;
      }
      if(old) rows[rows.indexOf(old)]=entity; else rows.push(entity);
      const relatedCameras=kind==='roads'?await tx.read('cameras'):undefined;
      await tx.write(kind,rows);
      return kind==='cameras'?publicCamera(entity,clock()):aggregateRoad(entity,relatedCameras,clock());
    });
  }
  async function remove(kind, entityId) {
    return store.transaction(async tx=>{
      const rows=await tx.read(kind); const key=kind==='cameras'?'camera_id':'road_id';
      find(rows,key,entityId);
      if(kind==='roads') requireValue(!(await tx.read('cameras')).some(c=>c.road_id===entityId),'Tuyến còn camera liên kết; chuyển hoặc xóa camera trước',409);
      await tx.write(kind,rows.filter(row=>row[key]!==entityId));
      return {deleted:entityId};
    });
  }
  async function enqueue(payload, {saveImage, contentHash, simulated=false} = {}) {
    fields(payload,['camera_id','observation_id','captured_at','image_url']);
    id(payload.camera_id,'camera_id');id(payload.observation_id,'observation_id');
    const captured=timestamp(payload.captured_at,clock());
    const url=payload.image_url===undefined?undefined:imageUrl(payload.image_url);
    requireValue(url || saveImage || simulated,'Cần image_url hoặc upload ảnh JPEG');
    const fingerprint=JSON.stringify([captured,contentHash??url??'demo']);
    return store.transaction(async tx=>{
      const cameras=await tx.read('cameras');const camera=find(cameras,'camera_id',payload.camera_id);
      requireValue(camera.road_id,'Camera chưa được gắn road_id',409);
      find(await tx.read('roads'),'road_id',camera.road_id);
      camera.observations??=[];
      const duplicate=camera.observations.find(o=>o.observation_id===payload.observation_id);
      if(duplicate){requireValue(duplicate.fingerprint===fingerprint,'observation_id đã dùng với nội dung khác',409);return {observation:duplicate,duplicate:true};}
      if(camera.observations.length>=POLICY.maxObservationsPerCamera){
        const finished=camera.observations.findIndex(o=>o.status!=='pending');
        requireValue(finished>=0,'Hàng đợi camera đã đầy; cần AI xử lý các ảnh đang chờ',429);
        camera.observations.splice(finished,1);
      }
      const observation={camera_id:camera.camera_id,road_id:camera.road_id,observation_id:payload.observation_id,
        captured_at:captured,received_at:iso(),status:'pending',image_url:saveImage?await saveImage():url,simulated,fingerprint};
      camera.observations.push(observation);camera.last_seen_at=iso();
      await tx.write('cameras',cameras);
      return {observation,duplicate:false};
    });
  }
  function resultInput(payload) {
    fields(payload,['camera_id','observation_id','waste_coverage_pct','drain_blockage_pct','confidence','analyzed_url']);
    id(payload.camera_id,'camera_id');id(payload.observation_id,'observation_id');
    const normalized={waste_coverage_pct:percent(payload.waste_coverage_pct,'waste_coverage_pct')};
    // Bỏ trống khi camera không nhìn thấy miệng cống nào — khác hẳn "thấy cống và cống sạch = 0%".
    if(payload.drain_blockage_pct!==undefined)normalized.drain_blockage_pct=percent(payload.drain_blockage_pct,'drain_blockage_pct');
    requireValue(typeof payload.confidence==='number'&&Number.isFinite(payload.confidence)&&payload.confidence>=0&&payload.confidence<=1,'confidence cần số 0–1');
    return {...normalized,confidence:payload.confidence,...(payload.analyzed_url!==undefined?{analyzed_url:imageUrl(payload.analyzed_url)}:{})};
  }
  async function applyResult(payload) {
    const result=resultInput(payload);
    return store.transaction(async tx=>{
      const cameras=await tx.read('cameras'); const camera=find(cameras,'camera_id',payload.camera_id);
      const observation=find(camera.observations??[],'observation_id',payload.observation_id);
      if(observation.result){requireValue(JSON.stringify(observation.result)===JSON.stringify(result),'Đã nhận kết quả khác cho observation này',409);return {observation,duplicate:true};}
      requireValue(observation.status==='pending','Tác vụ không ở trạng thái pending; dùng API retry',409);
      observation.result=result;observation.processed_at=iso();observation.applied=false;
      if(result.confidence<POLICY.minConfidence){observation.status='needs_review';}
      else {
        observation.status='processed';
        const previous=camera.latest_analysis;
        const newer=!previous||Date.parse(observation.captured_at)>Date.parse(previous.captured_at);
        const current=clock()-Date.parse(observation.captured_at)<=POLICY.readingMaxAgeMs;
        if(newer&&current&&observation.road_id===camera.road_id){
          const severity=evaluateSeverity(result.waste_coverage_pct,result.drain_blockage_pct);
          const sameEpisode=previous&&previous.severity!=='normal'&&clock()-Date.parse(previous.captured_at)<=POLICY.readingMaxAgeMs;
          camera.latest_analysis={observation_id:observation.observation_id,captured_at:observation.captured_at,simulated:observation.simulated,
            severity,incident_id:severity==='normal'?undefined:sameEpisode?previous.incident_id:randomUUID(),
            monitoring:{waste_coverage_pct:result.waste_coverage_pct,drain_blockage_pct:result.drain_blockage_pct,observed_at:observation.captured_at},
            images:{original_url:observation.image_url,analyzed_url:result.analyzed_url,captured_at:observation.captured_at}};
          observation.applied=true;
        }
      }
      await tx.write('cameras',cameras);
      return {observation,duplicate:false};
    });
  }
  async function jobs({status='pending',camera_id,limit=50}={}) {
    requireValue(['pending','processed','needs_review','failed','all'].includes(status),'status tác vụ không hợp lệ');
    requireValue(Number.isInteger(limit)&&limit>=1&&limit<=200,'limit cần 1–200');
    return (await store.read('cameras')).filter(c=>!camera_id||c.camera_id===camera_id)
      .flatMap(c=>c.observations??[]).filter(o=>status==='all'||o.status===status)
      .sort((a,b)=>a.received_at.localeCompare(b.received_at)).slice(0,limit).map(({fingerprint,...o})=>o);
  }
  async function jobAction(payload, retry=false) {
    fields(payload,retry?['camera_id','observation_id']:['camera_id','observation_id','error']);
    if(!retry)requireValue(typeof payload.error==='string'&&payload.error.length>0&&payload.error.length<=1000,'error cần chuỗi 1–1000 ký tự');
    return store.transaction(async tx=>{
      const cameras=await tx.read('cameras');const camera=find(cameras,'camera_id',payload.camera_id);
      const observation=find(camera.observations??[],'observation_id',payload.observation_id);
      requireValue(retry?['failed','needs_review'].includes(observation.status):observation.status==='pending','Trạng thái tác vụ không cho phép thao tác này',409);
      if(retry){observation.status='pending';delete observation.error;delete observation.result;delete observation.processed_at;delete observation.applied;}
      else {observation.status='failed';observation.error=payload.error;}
      await tx.write('cameras',cameras);return observation;
    });
  }
  async function roadAction(roadId, action, payload) {
    if(action==='alert'){
      fields(payload,['severity','description','ttl_seconds']);
      requireValue(LEVELS.slice(1).includes(payload.severity),'severity cần low, medium, high hoặc critical');
      requireValue(typeof payload.description==='string'&&payload.description.trim().length>0&&payload.description.length<=2000,'description cần 1–2000 ký tự');
      const ttl=payload.ttl_seconds??3600;
      requireValue(Number.isInteger(ttl)&&ttl>=1&&ttl<=86400,'ttl_seconds cần 1–86400');
    }
    if(action==='weather'){
      fields(payload,['rain_expected','observed_at']);
      requireValue(typeof payload.rain_expected==='boolean','rain_expected phải là boolean');
      timestamp(payload.observed_at,clock());
    }
    return store.transaction(async tx=>{
      const roads=await tx.read('roads'); const road=find(roads,'road_id',roadId);
      if(action==='alert')road.manual_alert={...payload,alert_id:randomUUID(),created_at:iso(),expires_at:new Date(clock()+(payload.ttl_seconds??3600)*1000).toISOString()};
      if(action==='clear')delete road.manual_alert;
      if(action==='weather'){
        const observed=timestamp(payload.observed_at,clock());
        requireValue(!road.weather||Date.parse(observed)>=Date.parse(road.weather.observed_at),'Dữ liệu thời tiết cũ hơn bản hiện tại',409);
        const same=road.weather?.rain_expected===payload.rain_expected&&clock()-Date.parse(road.weather.observed_at)<=POLICY.readingMaxAgeMs;
        road.weather={...payload,observed_at:observed,event_id:same?road.weather.event_id:randomUUID()};
      }
      road.updated_at=iso();
      const cameras=await tx.read('cameras');
      await tx.write('roads',roads);return aggregateRoad(road,cameras,clock());
    });
  }
  async function simulate(payload){
    fields(payload,['camera_id','observation_id','captured_at','waste_coverage_pct','drain_blockage_pct','confidence','image_url','analyzed_url']);
    const result={camera_id:payload.camera_id,observation_id:payload.observation_id,waste_coverage_pct:payload.waste_coverage_pct,drain_blockage_pct:payload.drain_blockage_pct,confidence:payload.confidence??0.99,...(payload.analyzed_url?{analyzed_url:payload.analyzed_url}:{})};
    resultInput(result); // Do not enqueue a job if simulated metrics are invalid.
    await enqueue({camera_id:payload.camera_id,observation_id:payload.observation_id,captured_at:payload.captured_at,image_url:payload.image_url},{simulated:true});
    return applyResult(result);
  }
  async function aiReport(payload) {
    fields(payload,['camera_id','waste_level','flood_percentage','image_url','observation_id','captured_at']);
    id(payload.camera_id,'camera_id');
    requireValue(LEVELS.includes(payload.waste_level),'waste_level cần normal, low, medium, high hoặc critical');
    percent(payload.flood_percentage,'flood_percentage');imageUrl(payload.image_url);
    if(payload.observation_id!==undefined)id(payload.observation_id,'observation_id');
    if(payload.captured_at!==undefined)timestamp(payload.captured_at,clock());
    const result={waste_level:payload.waste_level,flood_percentage:payload.flood_percentage,image_url:payload.image_url};
    return store.transaction(async tx=>{
      const cameras=await tx.read('cameras');const camera=find(cameras,'camera_id',payload.camera_id);
      requireValue(camera.road_id,'Camera chưa gắn tuyến',409);
      find(await tx.read('roads'),'road_id',camera.road_id);
      camera.observations??=[];
      const existing=payload.observation_id&&camera.observations.find(o=>o.observation_id===payload.observation_id);
      if(existing){requireValue(existing.report===true&&JSON.stringify(existing.result)===JSON.stringify(result)&&(!payload.captured_at||existing.captured_at===timestamp(payload.captured_at,clock())),'Mã quan sát đã dùng với nội dung khác',409);return {observation:existing,duplicate:true};}
      const observation_id=payload.observation_id??randomUUID();const captured_at=payload.captured_at?timestamp(payload.captured_at,clock()):iso();
      if(camera.observations.length>=POLICY.maxObservationsPerCamera){const index=camera.observations.findIndex(o=>o.status!=='pending');requireValue(index>=0,'Hàng đợi đầy',429);camera.observations.splice(index,1);}
      const previous=camera.latest_analysis;
      const applied=(!previous||Date.parse(captured_at)>Date.parse(previous.captured_at))&&clock()-Date.parse(captured_at)<=POLICY.readingMaxAgeMs;
      const observation={camera_id:camera.camera_id,road_id:camera.road_id,observation_id,captured_at,received_at:iso(),processed_at:iso(),status:'processed',report:true,result,applied,image_url:payload.image_url};
      if(applied){
        const severity=LEVELS[Math.max(LEVELS.indexOf(payload.waste_level),LEVELS.indexOf(evaluateSeverity(undefined,payload.flood_percentage)))];
        const sameEpisode=previous&&previous.severity!=='normal'&&clock()-Date.parse(previous.captured_at)<=POLICY.readingMaxAgeMs;
        camera.latest_analysis={observation_id,captured_at,severity,incident_id:severity==='normal'?undefined:sameEpisode?previous.incident_id:randomUUID(),
          monitoring:{waste_level:payload.waste_level,flood_percentage:payload.flood_percentage,observed_at:captured_at},
          images:{analyzed_url:payload.image_url,captured_at}};
      }
      camera.observations.push(observation);camera.last_seen_at=iso();await tx.write('cameras',cameras);
      return {observation,duplicate:false};
    });
  }
  return {list,save,remove,enqueue,applyResult,jobs,jobAction,roadAction,simulate,aiReport};
}
