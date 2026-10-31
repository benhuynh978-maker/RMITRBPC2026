// Adapter contract: export async function analyze(jpegBuffer, job) returning
// {waste_coverage_pct, drain_blockage_pct, confidence, analyzed_url?} plus optional v2 fields
// (usable, quality_reason, certainty, no_trash_in_roi, blockage_method, roi_version = job.drain_roi?.version).
// This runner has no fake image classifier: plug in a real model explicitly.
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
const base=process.env.SSC_API_URL||'http://127.0.0.1:8010';
const key=process.env.AI_API_KEY||process.env.ADMIN_API_KEY||'';
const adapterPath=process.env.AI_ADAPTER_MODULE;
if(!adapterPath)throw new Error('Set AI_ADAPTER_MODULE to a module that exports analyze(jpegBuffer, job). Use /api/test/simulate if you have no model yet.');
const {analyze}=await import(pathToFileURL(resolve(adapterPath)).href);
if(typeof analyze!=='function')throw new Error('The AI adapter must export an analyze function');
async function request(path,payload){
  const response=await fetch(base+path,{method:payload?'POST':'GET',headers:{'X-API-Key':key,...(payload?{'Content-Type':'application/json'}:{})},body:payload?JSON.stringify(payload):undefined,signal:AbortSignal.timeout(15000)});
  const data=await response.json();if(!response.ok)throw new Error(`${response.status}: ${data.error}`);return data;
}
const once=process.argv.includes('--once');
let stopping=false;process.on('SIGINT',()=>{stopping=true;});process.on('SIGTERM',()=>{stopping=true;});
do {
  try{
    const {jobs}=await request('/api/ai/jobs?status=pending&limit=20');
    for(const job of jobs){
      if(stopping)break;
      let result;
      try{
        if(!job.image_url)throw new Error('The job has no image. Use the simulate API to test the figures.');
        const image=new URL(job.image_url,base);
        // Do not turn an arbitrary image URL into a network request to internal services.
        if(image.origin!==new URL(base).origin||!/^\/api\/images\/[a-f0-9-]{36}\.jpg$/.test(image.pathname))throw new Error('The sample worker only reads uploaded images from /api/images on this server. Other image sources need their own allowlist.');
        const response=await fetch(image,{redirect:'error',signal:AbortSignal.timeout(15000)});
        if(!response.ok)throw new Error(`Could not read the image: ${response.status}`);
        result=await analyze(Buffer.from(await response.arrayBuffer()),job);
      }catch(error){
        await request('/api/ai/jobs/fail',{camera_id:job.camera_id,observation_id:job.observation_id,error:String(error.message).slice(0,1000)});
        console.error(job.observation_id,error.message);continue;
      }
      // If delivery fails, leave pending for retry; a duplicate result is idempotent.
      const outcome=await request('/api/ai/results',{...result,camera_id:job.camera_id,observation_id:job.observation_id});
      console.log(job.observation_id,outcome.observation.status,`applied=${outcome.observation.applied}`);
    }
  }catch(error){console.error(error.message);if(once)process.exitCode=1;}
  if(!once&&!stopping)await new Promise(resolve=>setTimeout(resolve,3000));
}while(!once&&!stopping);
