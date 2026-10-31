import {describe,it,expect} from 'vitest';
import {mkdtemp,rm,readFile,writeFile,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createApiServer} from '../server/app.js';
import {POLICY} from '../server/config.js';

async function fixture(run,options={}){
  const dir=await mkdtemp(join(tmpdir(),'ssc-ingest-'));
  let now=Date.parse('2026-09-09T12:00:00Z');
  let server=createApiServer({dataDir:dir,clock:()=>now,...options});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let base=`http://127.0.0.1:${server.address().port}`;
  const request=async(path,method='GET',data,headers={})=>{
    const res=await fetch(base+path,{method,headers:{...(data!==undefined?{'Content-Type':'application/json'}:{}),...headers},body:data!==undefined?JSON.stringify(data):undefined});
    return {status:res.status,data:await res.json()};
  };
  const road={road_id:'R1',road_name:'Test road',geometry:{type:'LineString',coordinates:[[106.7,10.77],[106.71,10.78]]}};
  const camera={camera_id:'C1',road_id:'R1',geometry:{type:'Point',coordinates:[106.7,10.77]}};
  const seed=async()=>{expect((await request('/api/road-alerts','POST',road)).status).toBe(201);expect((await request('/api/cameras','POST',camera)).status).toBe(201);};
  const observation=(observation_id='O1',captured_at=new Date(now).toISOString())=>({camera_id:'C1',observation_id,captured_at,image_url:'/images/capture.jpg'});
  const result=(observation_id='O1',waste=82)=>({camera_id:'C1',observation_id,waste_coverage_pct:waste,drain_blockage_pct:waste,confidence:0.95});
  try{await run({request,seed,road,camera,observation,result,dir,base,advance:ms=>{now+=ms;},restart:async()=>{
    await new Promise(resolve=>server.close(resolve));server=createApiServer({dataDir:dir,clock:()=>now,...options});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));base=`http://127.0.0.1:${server.address().port}`;
  }});}finally{await new Promise(resolve=>server.close(resolve));await rm(dir,{recursive:true,force:true});}
}
describe('JSON-backed ingestion and AI workflow',()=>{
  it('creates coordinates, persists pending jobs across restart, applies AI and serves client geometry',()=>fixture(async({seed,request,observation,result,restart})=>{
    await seed();
    expect((await request('/api/esp32/observations','POST',observation())).status).toBe(202);
    await restart();expect((await request('/api/ai/jobs')).data.jobs).toHaveLength(1);
    expect((await request('/api/ai/results','POST',result())).data.observation.applied).toBe(true);
    const r=(await request('/api/road-alerts')).data.roads[0];
    expect(r.severity).toBe('critical');expect(r.geometry.coordinates[0]).toEqual([106.7,10.77]);expect(r.monitoring.waste_coverage_pct).toBe(82);expect(r.data_quality).toBe('fresh');
    expect((await request('/api/cameras')).data.cameras[0].images.original_url).toBe('/images/capture.jpg');
    await restart();expect((await request('/api/road-alerts/R1')).data.alert_id).toBe(r.alert_id);
  }));
  it('is idempotent, rejects conflicts, ignores out-of-order results and keeps incident ID',()=>fixture(async({seed,request,observation,result,advance})=>{
    await seed();const first=observation();await request('/api/esp32/observations','POST',first);
    expect((await request('/api/esp32/observations','POST',first)).data.duplicate).toBe(true);
    expect((await request('/api/esp32/observations','POST',{...first,image_url:'/different.jpg'})).status).toBe(409);
    await request('/api/ai/results','POST',result());
    const originalId=(await request('/api/road-alerts/R1')).data.alert_id;
    expect((await request('/api/ai/results','POST',result())).data.duplicate).toBe(true);
    expect((await request('/api/ai/results','POST',result('O1',1))).status).toBe(409);
    advance(1000);await request('/api/esp32/observations','POST',observation('O2'));await request('/api/ai/results','POST',result('O2',88));
    expect((await request('/api/road-alerts/R1')).data.alert_id).toBe(originalId);
    await request('/api/esp32/observations','POST',observation('OLD','2026-09-09T11:59:00Z'));
    expect((await request('/api/ai/results','POST',result('OLD',0))).data.observation.applied).toBe(false);
    expect((await request('/api/road-alerts/R1')).data.monitoring.waste_coverage_pct).toBe(88);
  }));
  it('no longer holds low-confidence results, retries failed jobs, expires stale data and renews incidents',()=>fixture(async({seed,request,observation,result,advance})=>{
    await seed();await request('/api/esp32/observations','POST',observation());
    // v2: confidence thấp không còn chuyển needs_review (min-of-detections phản thông tin) — vẫn processed và áp dụng.
    const low=(await request('/api/ai/results','POST',{...result(),confidence:0.2})).data.observation;
    expect(low.status).toBe('processed');expect(low.applied).toBe(true);
    expect((await request('/api/road-alerts/R1')).data.monitoring.waste_coverage_pct).toBe(82);
    expect((await request('/api/ai/jobs/retry','POST',{camera_id:'C1',observation_id:'O1'})).status).toBe(409);
    advance(1000);await request('/api/esp32/observations','POST',observation('O2'));
    await request('/api/ai/jobs/fail','POST',{camera_id:'C1',observation_id:'O2',error:'Model unavailable'});
    expect((await request('/api/ai/jobs?status=failed')).data.jobs).toHaveLength(1);
    await request('/api/ai/jobs/retry','POST',{camera_id:'C1',observation_id:'O2'});
    await request('/api/ai/results','POST',result('O2'));
    const first=(await request('/api/road-alerts/R1')).data.alert_id;
    advance(POLICY.readingMaxAgeMs+1);
    const stale=(await request('/api/road-alerts/R1')).data;
    expect(stale.monitoring).toBeUndefined();expect(stale.data_quality).toBe('unknown');
    expect((await request('/api/cameras/C1')).data.status).toBe('offline');
    await request('/api/esp32/observations','POST',observation('NEW'));await request('/api/ai/results','POST',result('NEW'));
    expect((await request('/api/road-alerts/R1')).data.alert_id).not.toBe(first);
  }));
  it('averages fresh cameras, applies weather, and manual alerts expire without erasing AI',()=>fixture(async({seed,request,camera,observation,result,advance})=>{
    await seed();await request('/api/cameras','POST',{...camera,camera_id:'C2'});
    await request('/api/test/simulate','POST',{...observation(),...result()});
    await request('/api/test/simulate','POST',{...observation('OTHER'),...result('OTHER',5),camera_id:'C2'});
    const merged=(await request('/api/road-alerts/R1')).data.monitoring;
    expect(merged.waste_coverage_pct).toBe(43.5);expect(merged.waste_camera_count).toBe(2);expect(merged.waste_max_pct).toBe(82);
    const weather={rain_expected:true,observed_at:'2026-09-09T12:00:00Z'};
    expect((await request('/api/road-alerts/R1/weather','PUT',weather)).data.severity).toBe('critical');
    await request('/api/road-alerts/R1/weather','PUT',{...weather,rain_expected:false});
    expect((await request('/api/road-alerts/R1/alert','POST',{severity:'critical',description:'Test',ttl_seconds:1})).data.severity).toBe('critical');
    advance(1001);expect((await request('/api/road-alerts/R1')).data.severity).toBe('critical');
    expect((await request('/api/road-alerts/R1','DELETE')).status).toBe(409);
  }));
  it('serializes concurrent writes and rejects bad inputs without corrupting JSON',()=>fixture(async({seed,request,camera,observation,result,dir})=>{
    await seed();const created=await Promise.all(Array.from({length:10},(_,i)=>request('/api/cameras','POST',{...camera,camera_id:`P${i}`})));
    expect(created.every(r=>r.status===201)).toBe(true);expect((await request('/api/cameras')).data.cameras).toHaveLength(11);
    expect((await request('/api/cameras','POST',camera)).status).toBe(409);
    expect((await request('/api/cameras','POST',{...camera,camera_id:'BAD',road_id:'missing'})).status).toBe(404);
    expect((await request('/api/cameras/C1','PATCH',{geometry:{type:'Point',coordinates:[10,106]}})).status).toBe(400);
    expect((await request('/api/esp32/observations','POST',{...observation(),captured_at:'2030-01-01T00:00:00Z'})).status).toBe(400);
    expect((await request('/api/ai/results','POST',result())).status).toBe(404);
    expect((await request('/api/test/simulate','POST',{...observation(),...result(),waste_coverage_pct:101})).status).toBe(400);
    expect((await request('/api/ai/jobs')).data.jobs).toHaveLength(0);
    await writeFile(join(dir,'cameras.json'),'{corrupt');
    expect((await request('/api/cameras/C1','PATCH',{name:'changed'})).status).toBe(500);
    expect(await readFile(join(dir,'cameras.json'),'utf8')).toBe('{corrupt');
  }));
  it('stores JPEG bytes once on retry and serves them under generated safe paths',()=>fixture(async({seed,base,request,dir})=>{
    await seed();const image=Buffer.from([255,216,1,2,3,255,217]);
    const headers={'Content-Type':'image/jpeg','X-Observation-Id':'JPEG1','X-Captured-At':'2026-09-09T12:00:00Z'};
    const capture=()=>fetch(base+'/api/esp32/cameras/C1/capture',{method:'POST',headers,body:image});
    const first=await capture();expect(first.status).toBe(202);const data=await first.json();
    expect(Buffer.from(await (await fetch(base+data.observation.image_url)).arrayBuffer())).toEqual(image);
    expect((await (await capture()).json()).duplicate).toBe(true);
    expect(await readdir(join(dir,'images'))).toHaveLength(1);
    expect((await request('/api/esp32/observations','POST',{camera_id:'C1',observation_id:'BAD',captured_at:headers['X-Captured-At'],image_url:'javascript:alert(1)'})).status).toBe(400);
  }));
  it('enforces separate API keys, origin policy and test switch',()=>fixture(async({request,road,base})=>{
    expect((await request('/api/road-alerts','POST',road)).status).toBe(401);
    expect((await request('/api/road-alerts','POST',road,{'X-API-Key':'device'})).status).toBe(401);
    // CORS mở có chủ đích (server/readme.md): Origin bất kỳ được phản chiếu, chỉ X-API-Key bảo vệ ghi.
    expect((await fetch(base+'/api/health',{headers:{Origin:'https://untrusted.example'}})).headers.get('access-control-allow-origin')).toBe('https://untrusted.example');
    expect((await request('/api/road-alerts','POST',road,{'X-API-Key':'admin'})).status).toBe(201);
    expect((await request('/api/ai/jobs','GET',undefined,{'X-API-Key':'ai'})).status).toBe(200);
    expect((await request('/api/ai/jobs')).status).toBe(401);
    expect((await request('/api/test/simulate','POST',{}, {'X-API-Key':'admin'})).status).toBe(404);
  },{apiKey:'admin',deviceKey:'device',aiKey:'ai',enableTestApi:false}));
  it('bounds pending jobs and request size, and prunes only terminal history',()=>fixture(async({seed,request,observation,dir,base})=>{
    await seed();const data=JSON.parse(await readFile(join(dir,'cameras.json'),'utf8'));
    data.cameras[0].observations=Array.from({length:POLICY.maxObservationsPerCamera},(_,i)=>({camera_id:'C1',road_id:'R1',observation_id:`Q${i}`,status:'pending',captured_at:'2026-09-09T12:00:00Z',received_at:'2026-09-09T12:00:00Z'}));
    await writeFile(join(dir,'cameras.json'),JSON.stringify(data));
    expect((await request('/api/esp32/observations','POST',observation('OVERFLOW'))).status).toBe(429);
    await request('/api/ai/jobs/fail','POST',{camera_id:'C1',observation_id:'Q0',error:'Test failed frame'});
    expect((await request('/api/esp32/observations','POST',observation('ADMITTED'))).status).toBe(202);
    expect((await request('/api/ai/jobs?status=all&limit=200')).data.jobs).toHaveLength(POLICY.maxObservationsPerCamera);
    expect((await request('/api/cameras/C1','PATCH',{name:'a'.repeat(POLICY.maxJsonBytes)})).status).toBe(413);
    const invalid=await fetch(base+'/api/cameras',{method:'POST',headers:{'Content-Type':'application/json'},body:'{not-json'});
    expect(invalid.status).toBe(400);
    expect((await request('/api/cameras')).status).toBe(200);
  }));
});
