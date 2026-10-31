import {describe,it,expect} from 'vitest';
import {mkdtemp,rm,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createApiServer} from '../server/app.js';
import {POLICY} from '../server/config.js';
import {nextDrainState} from '../server/aggregation.js';

const polygon=[[0.2,0.5],[0.8,0.5],[0.8,0.9],[0.2,0.9]];
async function fixture(run){
  const dir=await mkdtemp(join(tmpdir(),'ssc-drain-'));
  let now=Date.parse('2026-09-09T12:00:00Z');
  const server=createApiServer({dataDir:dir,clock:()=>now});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base=`http://127.0.0.1:${server.address().port}`;
  const request=async(path,method='GET',data)=>{
    const res=await fetch(base+path,{method,headers:data!==undefined?{'Content-Type':'application/json'}:{},body:data!==undefined?JSON.stringify(data):undefined});
    return {status:res.status,data:await res.json()};
  };
  const road={road_id:'R1',geometry:{type:'LineString',coordinates:[[106.7,10.77],[106.71,10.78]]}};
  const seed=async(...ids)=>{
    expect((await request('/api/road-alerts','POST',road)).status).toBe(201);
    for(const camera_id of ids.length?ids:['C1'])expect((await request('/api/cameras','POST',{camera_id,road_id:'R1',geometry:{type:'Point',coordinates:[106.7,10.77]}})).status).toBe(201);
  };
  let seq=0;
  /** Một ảnh mới + kết quả AI, cách nhau 1 phút theo đồng hồ giả. */
  const reading=async(pct,extra={},camera_id='C1')=>{
    now+=60_000;const observation_id=`O${++seq}`;
    expect((await request('/api/esp32/observations','POST',{camera_id,observation_id,captured_at:new Date(now).toISOString(),image_url:'/images/x.jpg'})).status).toBe(202);
    const payload={camera_id,observation_id,waste_coverage_pct:5,...(pct===undefined?{}:{drain_blockage_pct:pct}),confidence:0.9,...extra};
    const res=await request('/api/ai/results','POST',payload);
    return {...res,payload,observation_id};
  };
  const state=async(camera_id='C1')=>(await request(`/api/cameras/${camera_id}`)).data.drain_state;
  try{await run({request,seed,reading,state,dir,advance:ms=>{now+=ms;},iso:()=>new Date(now).toISOString()});}
  finally{await new Promise(resolve=>server.close(resolve));await rm(dir,{recursive:true,force:true});}
}

describe('drain ROI, drain_state and v2 result contract',()=>{
  it('validates drain_roi, sets calibrated_at on the server, removes with null and resets drain_state on change',()=>fixture(async({seed,request,reading,state,iso,advance,dir})=>{
    await seed();
    const bad=[{polygon:[[0.1,0.1],[0.2,0.2],[0.3,0.3]],source:'manual'},{polygon:polygon.slice(0,2),source:'manual'},{polygon:Array(65).fill([0.5,0.5]),source:'manual'},{polygon:[[0,0],[1.5,0],[1,1]],source:'manual'},
      {polygon:[[0,0],[1,0],[NaN,1]],source:'manual'},{polygon:[[0,0],[1,0],[1]],source:'manual'},{polygon,source:'robot'},{polygon},{polygon:'x',source:'ai'},
      {polygon,source:'ai',extra:1},[polygon],'roi',5];
    for(const drain_roi of bad)expect((await request('/api/cameras/C1','PATCH',{drain_roi})).status,JSON.stringify(drain_roi)).toBe(400);
    const set=await request('/api/cameras/C1','PATCH',{drain_roi:{polygon,source:'ai',calibrated_at:'2000-01-01T00:00:00Z'}});
    expect(set.status).toBe(200);expect(set.data.drain_roi).toEqual({polygon,source:'ai',calibrated_at:iso()});
    const version=set.data.drain_roi.calibrated_at;
    expect((await request('/api/cameras/C1')).data.drain_roi.calibrated_at).toBe(version);
    for(let i=0;i<3;i++)await reading(60,{blockage_method:'roi',roi_version:version});
    expect((await state()).state).toBe('clean');
    // Cùng polygon, chỉ đổi source → giữ phiên bản và trạng thái.
    advance(1000);
    const relabel=await request('/api/cameras/C1','PATCH',{drain_roi:{polygon,source:'manual'}});
    expect(relabel.data.drain_roi).toEqual({polygon,source:'manual',calibrated_at:version});expect(relabel.data.drain_state.state).toBe('clean');
    // Polygon đổi (kể cả cùng mili giây) → phiên bản mới tăng ngặt, xóa drain_state đã lưu.
    const moved=await request('/api/cameras/C1','PATCH',{drain_roi:{polygon:[[0,0],[1,0],[1,1]],source:'manual'}});
    expect(Date.parse(moved.data.drain_roi.calibrated_at)).toBeGreaterThan(Date.parse(version));
    expect(moved.data.drain_state).toEqual({state:'unknown',reason:'no_data',window_count:0,roi_calibrated:true});
    expect(JSON.parse(await readFile(join(dir,'cameras.json'),'utf8')).cameras[0].drain_state).toBeUndefined();
    const again=await request('/api/cameras/C1','PATCH',{drain_roi:{polygon:[[0,0],[1,0],[1,1],[0,1]],source:'manual'}});
    expect(Date.parse(again.data.drain_roi.calibrated_at)).toBeGreaterThan(Date.parse(moved.data.drain_roi.calibrated_at));
    const removed=await request('/api/cameras/C1','PATCH',{drain_roi:null});
    expect(removed.status).toBe(200);expect(removed.data.drain_roi).toBeUndefined();expect(removed.data.drain_state.roi_calibrated).toBe(false);
    // Camera tạo mới có thể kèm ROI ngay.
    const created=await request('/api/cameras','POST',{camera_id:'C2',road_id:'R1',geometry:{type:'Point',coordinates:[106.7,10.77]},drain_roi:{polygon,source:'manual'}});
    expect(created.status).toBe(201);expect(created.data.drain_roi.calibrated_at).toBe(iso());
    // Đổi tuyến cũng xóa drain_state (giống latest_analysis).
    for(let i=0;i<3;i++)await reading(10);
    expect((await state()).state).toBe('clear');
    await request('/api/road-alerts','POST',{road_id:'R2',geometry:{type:'LineString',coordinates:[[106,10],[107,11]]}});
    expect((await request('/api/cameras/C1','PATCH',{road_id:'R2'})).data.drain_state.reason).toBe('no_data');
  }));

  it('includes the current drain_roi {polygon, version} or null in jobs',()=>fixture(async({seed,request})=>{
    await seed('C1','C2');
    const roi=(await request('/api/cameras/C2','PATCH',{drain_roi:{polygon,source:'ai'}})).data.drain_roi;
    await request('/api/esp32/observations','POST',{camera_id:'C1',observation_id:'J1',captured_at:'2026-09-09T12:00:00Z',image_url:'/a.jpg'});
    await request('/api/esp32/observations','POST',{camera_id:'C2',observation_id:'J2',captured_at:'2026-09-09T12:00:00Z',image_url:'/b.jpg'});
    const jobs=(await request('/api/ai/jobs')).data.jobs;
    expect(jobs.find(j=>j.camera_id==='C1').drain_roi).toBeNull();
    expect(jobs.find(j=>j.camera_id==='C2').drain_roi).toEqual({polygon,version:roi.calibrated_at});
    expect(jobs.every(j=>j.fingerprint===undefined)).toBe(true);
  }));

  it('accepts the new result fields, keeps unusable frames out of state and rejects bad combinations',()=>fixture(async({seed,request,reading,state,dir})=>{
    await seed();
    const version=(await request('/api/cameras/C1','PATCH',{drain_roi:{polygon,source:'ai'}})).data.drain_roi.calibrated_at;
    const full=await reading(40,{usable:true,certainty:0.9,no_trash_in_roi:false,blockage_method:'roi',roi_version:version});
    expect(full.status).toBe(200);
    expect(full.data.observation.result).toEqual({waste_coverage_pct:5,drain_blockage_pct:40,confidence:0.9,usable:true,certainty:0.9,no_trash_in_roi:false,blockage_method:'roi',roi_version:version});
    expect((await request('/api/ai/results','POST',full.payload)).data.duplicate).toBe(true);
    expect((await request('/api/ai/results','POST',{...full.payload,certainty:0.8})).status).toBe(409);
    const camera=(await request('/api/cameras/C1')).data;
    expect(camera.monitoring).toMatchObject({drain_blockage_pct:40,blockage_method:'roi',no_trash_in_roi:false,low_certainty:false,certainty:0.9});
    const dark=await reading(undefined,{usable:false,quality_reason:'thieu_sang',waste_coverage_pct:undefined,roi_version:version});
    expect(dark.status).toBe(200);
    expect(dark.data.observation).toMatchObject({status:'processed',usable:false,applied:false});
    expect(dark.data.observation.result).toEqual({confidence:0.9,usable:false,quality_reason:'thieu_sang',certainty:null,blockage_method:'legacy',roi_version:version});
    expect((await request('/api/cameras/C1')).data.monitoring.drain_blockage_pct).toBe(40);
    expect((await state()).window_count).toBe(1);
    // Ảnh không dùng được mà vẫn gửi phần trăm: không tính vào trạng thái.
    await reading(99,{usable:false,roi_version:version});
    expect((await state()).window_count).toBe(1);
    // roi_version lệch (ROI cũ / chưa gửi) không được tính.
    await reading(80,{blockage_method:'roi',roi_version:'2026-01-01T00:00:00.000Z'});
    await reading(80);
    expect(await state()).toMatchObject({state:'unknown',reason:'collecting',window_count:1,needed:POLICY.drainState.minReadings,roi_calibrated:true});
    const before=await readFile(join(dir,'cameras.json'),'utf8');
    for(const extra of [{quality_reason:'thieu_sang'},{usable:false,quality_reason:''},{usable:false,quality_reason:'x'.repeat(65)},{usable:'no'},{certainty:1.5},{certainty:'0.5'},
      {no_trash_in_roi:'false'},{blockage_method:'mask'},{roi_version:5},{roi_version:''},{waste_coverage_pct:undefined},{confidence:undefined},{usable:false,confidence:undefined},{unknown_field:1}]){
      const payload={camera_id:'C1',observation_id:'O1',waste_coverage_pct:5,confidence:0.9,...extra};
      expect((await request('/api/ai/results','POST',payload)).status,JSON.stringify(extra)).toBe(400);
    }
    expect(await readFile(join(dir,'cameras.json'),'utf8')).toBe(before);
  }));

  it('labels low certainty without holding the result back',()=>fixture(async({seed,request,reading,state})=>{
    await seed();
    const low=await reading(60,{certainty:0.2});
    expect(low.data.observation).toMatchObject({status:'processed',applied:true,usable:true,low_certainty:true});
    expect((await request('/api/cameras/C1')).data.monitoring).toMatchObject({drain_blockage_pct:60,low_certainty:true,certainty:0.2});
    await reading(60,{certainty:null});await reading(60);
    expect(await state()).toMatchObject({state:'clean',flags:{low_certainty:true,no_trash_in_roi:false}});
    expect((await request('/api/ai/jobs?status=needs_review')).data.jobs).toHaveLength(0);
  }));

  it('smooths with median-of-5 and hysteresis; a single outlier does not flip the state',()=>fixture(async({seed,reading,state,advance})=>{
    await seed('C1','C2');
    await reading(55);expect(await state()).toMatchObject({state:'unknown',reason:'collecting',window_count:1,needed:3});
    expect((await state()).smoothed_blockage_pct).toBeUndefined();
    await reading(55);expect((await state()).window_count).toBe(2);
    await reading(55);
    const clean=await state();expect(clean).toMatchObject({state:'clean',smoothed_blockage_pct:55,window_count:3,reason:'ok',roi_calibrated:false,blockage_method:'legacy'});
    const trace=[];
    for(const v of [45,45,45,30,30,30,10,10,10]){const r=await reading(v);const s=await state();trace.push(s.state);expect(s.evidence_observation_id).toBe(r.observation_id);}
    expect(trace).toEqual(['clean','clean','clean','clean','clean','watch','watch','watch','clear']);
    expect((await state()).smoothed_blockage_pct).toBe(10);
    expect((await state()).window_count).toBe(5);
    const out=[];for(const v of [55,55,20,55,55]){await reading(v,{},'C2');out.push((await state('C2')).state);}
    expect(out).toEqual(['unknown','unknown','clean','clean','clean']);
    // since giữ nguyên khi trạng thái không đổi.
    const s1=await state('C2');await reading(55,{},'C2');expect((await state('C2')).since).toBe(s1.since);
    // Khoảng trống dài: chỉ số đo trong 15 phút quanh lần mới nhất mới vào cửa sổ.
    advance(POLICY.readingMaxAgeMs+1);await reading(55,{},'C2');
    expect(await state('C2')).toMatchObject({state:'unknown',reason:'collecting',window_count:1});
  }));

  it('covers every hysteresis transition',()=>{
    expect([undefined,'unknown','clear'].map(p=>[nextDrainState(p,50),nextDrainState(p,20),nextDrainState(p,19.99)])).toEqual(Array(3).fill(['clean','watch','clear']));
    expect([nextDrainState('watch',50),nextDrainState('watch',12),nextDrainState('watch',11.99)]).toEqual(['clean','watch','clear']);
    expect([nextDrainState('clean',35),nextDrainState('clean',34.99),nextDrainState('clean',12),nextDrainState('clean',11.99)]).toEqual(['clean','watch','watch','clear']);
  });

  it('presents stale state as unknown at read time without writing storage; old or other-road results do not recompute',()=>fixture(async({seed,request,reading,state,advance,dir})=>{
    await seed();
    for(let i=0;i<3;i++)await reading(70);
    expect((await state()).state).toBe('clean');
    advance(POLICY.readingMaxAgeMs+1);
    const before=await readFile(join(dir,'cameras.json'),'utf8');
    const stale=await state();
    expect(stale).toMatchObject({state:'unknown',reason:'stale',window_count:3});
    expect(stale.smoothed_blockage_pct).toBeUndefined();expect(stale.since).toBeUndefined();
    expect((await request('/api/road-alerts/R1')).data.drain_summary).toMatchObject({unknown:1,worst_state:'unknown',worst_camera_id:null});
    expect(await readFile(join(dir,'cameras.json'),'utf8')).toBe(before);
    expect(JSON.parse(before).cameras[0].drain_state.state).toBe('clean');
    // Kết quả cho ảnh quá hạn được lưu nhưng không tính lại trạng thái.
    await request('/api/esp32/observations','POST',{camera_id:'C1',observation_id:'LATE',captured_at:'2026-09-09T12:01:00Z',image_url:'/late.jpg'});
    expect((await request('/api/ai/results','POST',{camera_id:'C1',observation_id:'LATE',waste_coverage_pct:1,drain_blockage_pct:0,confidence:0.9})).data.observation.applied).toBe(false);
    expect(JSON.parse(await readFile(join(dir,'cameras.json'),'utf8')).cameras[0].drain_state).toEqual(JSON.parse(before).cameras[0].drain_state);
  }));

  it('summarizes drain states per road without changing severity',()=>fixture(async({seed,request,reading})=>{
    await seed('C1','C2','C3');
    expect((await request('/api/road-alerts/R1')).data.drain_summary).toEqual({clear:0,watch:0,clean:0,unknown:3,worst_state:'unknown',worst_camera_id:null});
    for(let i=0;i<3;i++){await reading(25,{},'C1');await reading(80,{},'C2');}
    await reading(90,{},'C3');
    const road=(await request('/api/road-alerts/R1')).data;
    expect(road.drain_summary).toEqual({clear:0,watch:1,clean:1,unknown:1,worst_state:'clean',worst_camera_id:'C2'});
    // Severity vẫn theo trung bình số thô mới nhất của các camera (25, 80, 90 → 65 → medium).
    expect(road.monitoring.drain_blockage_pct).toBe(65);expect(road.severity).toBe('medium');
  }));

  it('keeps old-style payloads working: legacy method, null ROI version, counted for uncalibrated cameras',()=>fixture(async({seed,request,reading,state})=>{
    await seed();
    const old=await reading(82,{waste_coverage_pct:82,confidence:0.95});
    expect(old.data.observation).toMatchObject({status:'processed',applied:true,usable:true,low_certainty:false});
    expect(old.data.observation.result).toEqual({waste_coverage_pct:82,drain_blockage_pct:82,confidence:0.95,usable:true,certainty:null,blockage_method:'legacy',roi_version:null});
    // Gửi lại với giá trị mặc định ghi rõ vẫn là cùng một kết quả.
    expect((await request('/api/ai/results','POST',{...old.payload,usable:true,certainty:null,blockage_method:'legacy',roi_version:null})).data.duplicate).toBe(true);
    const road=(await request('/api/road-alerts/R1')).data;
    expect(road.severity).toBe('critical');expect(road.monitoring.waste_coverage_pct).toBe(82);
    await reading(82);await reading(82);
    expect(await state()).toMatchObject({state:'clean',roi_calibrated:false,blockage_method:'legacy',smoothed_blockage_pct:82});
    // Camera đã hiệu chỉnh ROI: payload kiểu cũ (roi_version null) không còn tính.
    await request('/api/cameras/C1','PATCH',{drain_roi:{polygon,source:'manual'}});
    await reading(82);
    expect(await state()).toMatchObject({state:'unknown',reason:'collecting',window_count:0,roi_calibrated:true});
  }));

  it('accepts results stored before v2 when resent identically',()=>fixture(async({seed,request,dir})=>{
    await seed();
    await request('/api/esp32/observations','POST',{camera_id:'C1',observation_id:'LEGACY',captured_at:'2026-09-09T12:00:00Z',image_url:'/l.jpg'});
    const data=JSON.parse(await readFile(join(dir,'cameras.json'),'utf8'));
    Object.assign(data.cameras[0].observations[0],{status:'needs_review',result:{waste_coverage_pct:3,drain_blockage_pct:4,confidence:0.2},processed_at:'2026-09-09T12:00:00Z',applied:false});
    await writeFile(join(dir,'cameras.json'),JSON.stringify(data));
    const payload={camera_id:'C1',observation_id:'LEGACY',waste_coverage_pct:3,drain_blockage_pct:4,confidence:0.2};
    expect((await request('/api/ai/results','POST',payload)).data.duplicate).toBe(true);
    expect((await request('/api/ai/results','POST',{...payload,confidence:0.3})).status).toBe(409);
    expect((await request('/api/ai/jobs/retry','POST',{camera_id:'C1',observation_id:'LEGACY'})).status).toBe(200);
  }));
});
