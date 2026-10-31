import { randomUUID } from 'node:crypto';
import { createJsonStore } from './store.js';
import { validateDataset } from './validation.js';
import { requireValue, ApiError } from './errors.js';
import { fields, id, timestamp, percent, imageUrl } from './input.js';
import { POLICY } from './config.js';
import { aggregateRoad, publicCamera, evaluateSeverity, LEVELS, computeDrainState, roiVersion } from './aggregation.js';

const entityFields = {
  cameras:['camera_id','road_id','name','status','geometry','drain_roi'],
  roads:['road_id','road_name','description','geometry','severity'],
};
const find = (rows, key, value) => {
  const entity=rows.find(row=>row[key]===value);
  requireValue(entity, `${key} does not exist: ${value}`,404);
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
    if (entityId) requireValue(payload[key]===undefined || payload[key]===entityId,'The ID cannot be changed');
    else id(payload[key],key);
    return store.transaction(async tx=>{
      const rows=await tx.read(kind);
      const old=entityId?find(rows,key,entityId):undefined;
      requireValue(old || !rows.some(row=>row[key]===payload[key]),'The ID already exists',409);
      const entity={...(kind==='roads'?{severity:'normal'}:{status:'unknown'}),...old,...payload};
      if(kind==='cameras'&&payload.drain_roi!==undefined){
        const roi=payload.drain_roi;
        if(roi===null)delete entity.drain_roi;
        else {
          requireValue(typeof roi==='object'&&!Array.isArray(roi),'drain_roi must be an object or null');
          fields(roi,['polygon','source','calibrated_at']);
          // Chỉ chặn ở đường ghi: worker từ chối ROI diện tích 0, còn đặt trong validateRoi sẽ làm file cũ không đọc được.
          const area=Array.isArray(roi.polygon)?Math.abs(roi.polygon.reduce((s,[x,y],i,p)=>{const [x2,y2]=p[(i+1)%p.length];return s+x*y2-x2*y;},0))/2:NaN;
          requireValue(!(area<1e-9),'drain_roi.polygon has zero area');
          // calibrated_at là phiên bản ROI: server tự đặt, tăng ngặt mỗi lần polygon đổi; bỏ qua giá trị client gửi.
          const same=old?.drain_roi&&JSON.stringify(old.drain_roi.polygon)===JSON.stringify(roi.polygon);
          entity.drain_roi={polygon:roi.polygon,source:roi.source,calibrated_at:same?old.drain_roi.calibrated_at:new Date(Math.max(clock(),old?.drain_roi?Date.parse(old.drain_roi.calibrated_at)+1:0)).toISOString()};
        }
        // Số đo bằng ROI khác không so sánh được với ROI mới.
        if(roiVersion(entity)!==(old?roiVersion(old):null))delete entity.drain_state;
      }
      validate(kind,[entity]);
      if(kind==='cameras'&&entity.road_id) find(await tx.read('roads'),'road_id',entity.road_id);
      if(kind==='cameras'&&old&&old.road_id!==entity.road_id) {
        requireValue(!(old.observations??[]).some(o=>o.status==='pending'),'The camera still has pending AI jobs; finish them before changing the road',409);
        delete entity.latest_analysis;delete entity.drain_state;
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
      if(kind==='roads') requireValue(!(await tx.read('cameras')).some(c=>c.road_id===entityId),'The road still has linked cameras; move or delete the cameras first',409);
      await tx.write(kind,rows.filter(row=>row[key]!==entityId));
      return {deleted:entityId};
    });
  }
  async function enqueue(payload, {saveImage, contentHash, simulated=false} = {}) {
    fields(payload,['camera_id','observation_id','captured_at','image_url']);
    id(payload.camera_id,'camera_id');id(payload.observation_id,'observation_id');
    const captured=timestamp(payload.captured_at,clock());
    const url=payload.image_url===undefined?undefined:imageUrl(payload.image_url);
    requireValue(url || saveImage || simulated,'image_url or a JPEG upload is required');
    const fingerprint=JSON.stringify([captured,contentHash??url??'demo']);
    return store.transaction(async tx=>{
      const cameras=await tx.read('cameras');const camera=find(cameras,'camera_id',payload.camera_id);
      requireValue(camera.road_id,'The camera has no road_id yet',409);
      find(await tx.read('roads'),'road_id',camera.road_id);
      camera.observations??=[];
      const duplicate=camera.observations.find(o=>o.observation_id===payload.observation_id);
      if(duplicate){requireValue(duplicate.fingerprint===fingerprint,'observation_id was already used with different content',409);return {observation:duplicate,duplicate:true};}
      if(camera.observations.length>=POLICY.maxObservationsPerCamera){
        const finished=camera.observations.findIndex(o=>o.status!=='pending');
        requireValue(finished>=0,'The camera queue is full; the AI must process the pending images',429);
        camera.observations.splice(finished,1);
      }
      const observation={camera_id:camera.camera_id,road_id:camera.road_id,observation_id:payload.observation_id,
        captured_at:captured,received_at:iso(),status:'pending',image_url:saveImage?await saveImage():url,simulated,fingerprint};
      camera.observations.push(observation);camera.last_seen_at=iso();
      await tx.write('cameras',cameras);
      return {observation,duplicate:false};
    });
  }
  const unit=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
  /** Dạng chuẩn, thứ tự khóa cố định; áp cho cả kết quả cũ đã lưu (thiếu trường mới) để so idempotency. */
  const canonical=r=>({
    ...(r.waste_coverage_pct!==undefined?{waste_coverage_pct:r.waste_coverage_pct}:{}),
    ...(r.drain_blockage_pct!==undefined?{drain_blockage_pct:r.drain_blockage_pct}:{}),
    confidence:r.confidence,...(r.analyzed_url!==undefined?{analyzed_url:r.analyzed_url}:{}),
    usable:r.usable??true,...(r.quality_reason!==undefined?{quality_reason:r.quality_reason}:{}),certainty:r.certainty??null,
    ...(r.no_trash_in_roi!==undefined?{no_trash_in_roi:r.no_trash_in_roi}:{}),blockage_method:r.blockage_method??'legacy',roi_version:r.roi_version??null,
  });
  function resultInput(payload) {
    fields(payload,['camera_id','observation_id','waste_coverage_pct','drain_blockage_pct','confidence','analyzed_url','usable','quality_reason','certainty','no_trash_in_roi','blockage_method','roi_version']);
    id(payload.camera_id,'camera_id');id(payload.observation_id,'observation_id');
    requireValue(payload.usable===undefined||typeof payload.usable==='boolean','usable must be a boolean');
    const usable=payload.usable!==false;
    // Ảnh không dùng được (thiếu sáng...) được phép bỏ trống cả hai phần trăm.
    if(usable||payload.waste_coverage_pct!==undefined)percent(payload.waste_coverage_pct,'waste_coverage_pct');
    // Bỏ trống khi camera không nhìn thấy miệng cống nào — khác hẳn "thấy cống và cống sạch = 0%".
    if(payload.drain_blockage_pct!==undefined)percent(payload.drain_blockage_pct,'drain_blockage_pct');
    requireValue(unit(payload.confidence),'confidence must be a number from 0 to 1');
    if(payload.analyzed_url!==undefined)imageUrl(payload.analyzed_url);
    requireValue(payload.quality_reason===undefined||!usable,'quality_reason is only allowed when usable=false');
    requireValue(payload.quality_reason===undefined||typeof payload.quality_reason==='string'&&payload.quality_reason.length>=1&&payload.quality_reason.length<=64,'quality_reason must be a string of 1–64 characters');
    requireValue(payload.certainty===undefined||payload.certainty===null||unit(payload.certainty),'certainty must be a number from 0 to 1 or null');
    requireValue(payload.no_trash_in_roi===undefined||typeof payload.no_trash_in_roi==='boolean','no_trash_in_roi must be a boolean');
    requireValue(payload.blockage_method===undefined||['roi','legacy'].includes(payload.blockage_method),'blockage_method must be roi or legacy');
    requireValue(payload.roi_version===undefined||payload.roi_version===null||typeof payload.roi_version==='string'&&payload.roi_version.length>=1&&payload.roi_version.length<=64,'roi_version must be a string of 1–64 characters or null');
    const {camera_id,observation_id,...result}=payload;
    return canonical(result);
  }
  async function applyResult(payload) {
    const result=resultInput(payload);
    return store.transaction(async tx=>{
      const cameras=await tx.read('cameras'); const camera=find(cameras,'camera_id',payload.camera_id);
      const observation=find(camera.observations??[],'observation_id',payload.observation_id);
      if(observation.result){requireValue(JSON.stringify(canonical(observation.result))===JSON.stringify(result),'A different result was already received for this observation',409);return {observation,duplicate:true};}
      requireValue(observation.status==='pending','The job is not in pending state; use the retry API',409);
      observation.result=result;observation.processed_at=iso();observation.applied=false;
      // v2: confidence không còn chặn (xem POLICY.minConfidence); certainty thấp chỉ là nhãn.
      observation.status='processed';observation.usable=result.usable;
      observation.low_certainty=typeof result.certainty==='number'&&result.certainty<POLICY.drainState.lowCertainty;
      const current=clock()-Date.parse(observation.captured_at)<=POLICY.readingMaxAgeMs&&observation.road_id===camera.road_id;
      if(result.usable){
        const previous=camera.latest_analysis;
        const newer=!previous||Date.parse(observation.captured_at)>Date.parse(previous.captured_at);
        if(newer&&current){
          const severity=evaluateSeverity(result.waste_coverage_pct,result.drain_blockage_pct);
          const sameEpisode=previous&&previous.severity!=='normal'&&clock()-Date.parse(previous.captured_at)<=POLICY.readingMaxAgeMs;
          camera.latest_analysis={observation_id:observation.observation_id,captured_at:observation.captured_at,simulated:observation.simulated,
            severity,incident_id:severity==='normal'?undefined:sameEpisode?previous.incident_id:randomUUID(),
            monitoring:{waste_coverage_pct:result.waste_coverage_pct,drain_blockage_pct:result.drain_blockage_pct,observed_at:observation.captured_at,
              blockage_method:result.blockage_method,low_certainty:observation.low_certainty,
              ...(result.certainty!==null?{certainty:result.certainty}:{}),...(result.no_trash_in_roi!==undefined?{no_trash_in_roi:result.no_trash_in_roi}:{})},
            images:{original_url:observation.image_url,analyzed_url:result.analyzed_url,captured_at:observation.captured_at}};
          observation.applied=true;
        }
        if(current)camera.drain_state=computeDrainState(camera,clock());
      }
      await tx.write('cameras',cameras);
      return {observation,duplicate:false};
    });
  }
  async function jobs({status='pending',camera_id,limit=50}={}) {
    requireValue(['pending','processed','needs_review','failed','all'].includes(status),'Invalid job status');
    requireValue(Number.isInteger(limit)&&limit>=1&&limit<=200,'limit must be 1–200');
    // drain_roi = ROI hiện tại của camera lúc GET; worker gửi lại drain_roi.version làm roi_version.
    const roi=c=>c.drain_roi?{polygon:c.drain_roi.polygon,version:c.drain_roi.calibrated_at}:null;
    return (await store.read('cameras')).filter(c=>!camera_id||c.camera_id===camera_id)
      .flatMap(c=>(c.observations??[]).filter(o=>status==='all'||o.status===status).map(({fingerprint,...o})=>({...o,drain_roi:roi(c)})))
      .sort((a,b)=>a.received_at.localeCompare(b.received_at)).slice(0,limit);
  }
  async function jobAction(payload, retry=false) {
    fields(payload,retry?['camera_id','observation_id']:['camera_id','observation_id','error']);
    if(!retry)requireValue(typeof payload.error==='string'&&payload.error.length>0&&payload.error.length<=1000,'error must be a string of 1–1000 characters');
    return store.transaction(async tx=>{
      const cameras=await tx.read('cameras');const camera=find(cameras,'camera_id',payload.camera_id);
      const observation=find(camera.observations??[],'observation_id',payload.observation_id);
      requireValue(retry?['failed','needs_review'].includes(observation.status):observation.status==='pending','The job state does not allow this action',409);
      if(retry){observation.status='pending';delete observation.error;delete observation.result;delete observation.processed_at;delete observation.applied;}
      else {observation.status='failed';observation.error=payload.error;}
      await tx.write('cameras',cameras);return observation;
    });
  }
  async function roadAction(roadId, action, payload) {
    if(action==='alert'){
      fields(payload,['severity','description','ttl_seconds']);
      requireValue(LEVELS.slice(1).includes(payload.severity),'severity must be low, medium, high or critical');
      requireValue(typeof payload.description==='string'&&payload.description.trim().length>0&&payload.description.length<=2000,'description must be 1–2000 characters');
      const ttl=payload.ttl_seconds??3600;
      requireValue(Number.isInteger(ttl)&&ttl>=1&&ttl<=86400,'ttl_seconds must be 1–86400');
    }
    if(action==='weather'){
      fields(payload,['rain_expected','observed_at']);
      requireValue(typeof payload.rain_expected==='boolean','rain_expected must be a boolean');
      timestamp(payload.observed_at,clock());
    }
    return store.transaction(async tx=>{
      const roads=await tx.read('roads'); const road=find(roads,'road_id',roadId);
      if(action==='alert')road.manual_alert={...payload,alert_id:randomUUID(),created_at:iso(),expires_at:new Date(clock()+(payload.ttl_seconds??3600)*1000).toISOString()};
      if(action==='clear')delete road.manual_alert;
      if(action==='weather'){
        const observed=timestamp(payload.observed_at,clock());
        requireValue(!road.weather||Date.parse(observed)>=Date.parse(road.weather.observed_at),'The weather data is older than the current one',409);
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
    requireValue(LEVELS.includes(payload.waste_level),'waste_level must be normal, low, medium, high or critical');
    percent(payload.flood_percentage,'flood_percentage');imageUrl(payload.image_url);
    if(payload.observation_id!==undefined)id(payload.observation_id,'observation_id');
    if(payload.captured_at!==undefined)timestamp(payload.captured_at,clock());
    const result={waste_level:payload.waste_level,flood_percentage:payload.flood_percentage,image_url:payload.image_url};
    return store.transaction(async tx=>{
      const cameras=await tx.read('cameras');const camera=find(cameras,'camera_id',payload.camera_id);
      requireValue(camera.road_id,'The camera is not linked to a road',409);
      find(await tx.read('roads'),'road_id',camera.road_id);
      camera.observations??=[];
      const existing=payload.observation_id&&camera.observations.find(o=>o.observation_id===payload.observation_id);
      if(existing){requireValue(existing.report===true&&JSON.stringify(existing.result)===JSON.stringify(result)&&(!payload.captured_at||existing.captured_at===timestamp(payload.captured_at,clock())),'The observation ID was already used with different content',409);return {observation:existing,duplicate:true};}
      const observation_id=payload.observation_id??randomUUID();const captured_at=payload.captured_at?timestamp(payload.captured_at,clock()):iso();
      if(camera.observations.length>=POLICY.maxObservationsPerCamera){const index=camera.observations.findIndex(o=>o.status!=='pending');requireValue(index>=0,'The queue is full',429);camera.observations.splice(index,1);}
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
