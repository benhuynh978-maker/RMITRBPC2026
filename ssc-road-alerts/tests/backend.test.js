import {it,expect} from 'vitest';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createApiServer} from '../server/app.js';
it('serves datasets, rereads edited files and refuses malformed content',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'ssc-api-'));
 const server=createApiServer({dataDir:dir});
 try {
  await writeFile(join(dir,'cameras.json'),'{"cameras":[]}');
  await writeFile(join(dir,'road-alerts.json'),'{"roads":[]}');
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url=`http://127.0.0.1:${server.address().port}`;
  expect((await (await fetch(url+'/api/cameras')).json()).cameras).toEqual([]);
  const camera={camera_id:'C1',geometry:{type:'Point',coordinates:[106,10]}};
  await writeFile(join(dir,'cameras.json'),JSON.stringify({cameras:[camera]}));
  expect((await (await fetch(url+'/api/cameras')).json()).cameras).toEqual([{...camera,status:'unknown',pending_count:0}]);
  expect((await (await fetch(url+'/api/road-alerts')).json()).roads).toEqual([]);
  expect((await fetch(url+'/api/cameras',{method:'POST'})).status).toBe(415);
  await writeFile(join(dir,'cameras.json'),'{bad');
  expect((await fetch(url+'/api/cameras')).status).toBe(500);
  // Aggregate road readings require the camera file; do not report safe values from corruption.
  expect((await fetch(url+'/api/road-alerts')).status).toBe(500);
  expect((await fetch(url+'/not-found')).status).toBe(404);
 } finally { await new Promise(resolve=>server.close(resolve));await rm(dir,{recursive:true,force:true}); }
});
