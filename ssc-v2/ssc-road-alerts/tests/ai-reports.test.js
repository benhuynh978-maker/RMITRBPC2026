import {it,expect} from 'vitest';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createApiServer} from '../server/app.js';
it('accepts a four-field AI report atomically, preserves flood separately, handles retry and rejects old/invalid data',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'ssc-reports-'));let now=Date.parse('2026-09-09T12:00:00Z');
  const weatherFetch=async()=>({ok:true,json:async()=>({hourly:{time:Array.from({length:16},(_,i)=>(now+i*3600000)/1000),rain:Array(16).fill(0.4),showers:Array(16).fill(0),precipitation_probability:Array(16).fill(80)}})});
  const server=createApiServer({dataDir:dir,clock:()=>now,weatherFetch});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base=`http://127.0.0.1:${server.address().port}`;
  const call=async(path,data)=>{const res=await fetch(base+path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});return {status:res.status,data:await res.json()};};
  try{
    await call('/api/road-alerts',{road_id:'R1',geometry:{type:'LineString',coordinates:[[106,10],[107,11]]}});
    await call('/api/cameras',{camera_id:'C1',road_id:'R1',geometry:{type:'Point',coordinates:[106,10]}});
    const report={camera_id:'C1',waste_level:'high',flood_percentage:85,image_url:'https://example.com/result.jpg'};
    const first=await call('/api/ai/reports',report);expect(first.status).toBe(200);expect(first.data.observation.applied).toBe(true);
    const repeated=await call('/api/ai/reports',{...report,observation_id:first.data.observation.observation_id});expect(repeated.data.duplicate).toBe(true);
    const camera=(await call('/api/cameras/C1')).data;expect(camera.monitoring.flood_percentage).toBe(85);expect(camera.monitoring.drain_blockage_pct).toBeUndefined();expect(camera.monitoring.waste_coverage_pct).toBeUndefined();expect(camera.images.analyzed_url).toBe(report.image_url);
    const road=(await call('/api/road-alerts/R1')).data;expect(road.severity).toBe('high');expect(road.monitoring.waste_level).toBe('high');expect(road.monitoring.drain_blockage_pct).toBe(85);
    expect((await call('/api/weather/cameras')).data.cameras[0].will_rain).toBe(true);
    const before=await readFile(join(dir,'cameras.json'),'utf8');
    expect((await call('/api/ai/reports',{...report,flood_percentage:120})).status).toBe(400);
    expect((await call('/api/ai/reports',{...report,waste_level:'a lot'})).status).toBe(400);
    expect((await call('/api/ai/reports',{...report,image_url:'javascript:alert(1)'})).status).toBe(400);
    expect(await readFile(join(dir,'cameras.json'),'utf8')).toBe(before);
    expect((await call('/api/ai/reports',{...report,camera_id:'missing'})).status).toBe(404);
    now+=1000;
    expect((await call('/api/ai/reports',{...report,captured_at:'2026-09-09T11:59:00Z'})).data.observation.applied).toBe(false);
    const next=await call('/api/ai/reports',{...report,waste_level:'normal',flood_percentage:0});expect(next.data.observation.applied).toBe(true);
    expect((await call('/api/road-alerts/R1')).data.severity).toBe('normal');
  }finally{await new Promise(resolve=>server.close(resolve));await rm(dir,{recursive:true,force:true});}
});
