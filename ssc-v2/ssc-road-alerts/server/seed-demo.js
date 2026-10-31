// Creates a NEW demo road/camera through public APIs; never clears existing data.
const base=process.env.SSC_API_URL||'http://127.0.0.1:8010';
const key=process.env.ADMIN_API_KEY||'';
const suffix=Date.now().toString(36);
const road_id=`DEMO-ROAD-${suffix}`;const camera_id=`DEMO-CAM-${suffix}`;
async function post(path,data){const response=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':key},body:JSON.stringify(data),signal:AbortSignal.timeout(10000)});const result=await response.json();if(!response.ok)throw new Error(`${response.status}: ${result.error}`);return result;}
await post('/api/road-alerts',{road_id,road_name:'API test road — sample data',geometry:{type:'LineString',coordinates:[[106.7112,10.7874],[106.7132,10.7886],[106.7162,10.7901]]}});
await post('/api/cameras',{camera_id,road_id,name:'API test camera',geometry:{type:'Point',coordinates:[106.7132,10.7886]}});
const result=await post('/api/test/simulate',{camera_id,observation_id:`DEMO-OBS-${suffix}`,captured_at:new Date().toISOString(),waste_coverage_pct:86,drain_blockage_pct:82,confidence:0.99});
console.log(JSON.stringify({road_id,camera_id,observation:result.observation},null,2));
console.log('Frontend: choose the Server source and click Refresh data. Delete the demo camera/road separately with the DELETE API when no longer needed.');
