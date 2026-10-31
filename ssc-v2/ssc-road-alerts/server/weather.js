// Open-Meteo hourly rain/showers/probability: https://open-meteo.com/en/docs
export const WEATHER_POLICY = Object.freeze({ horizonHours:12, cacheMs:15*60_000, retryMs:60_000,
  probabilityThreshold:50, rainMmThreshold:0.2, displayRadiusM:500, maxLocations:100, concurrency:4 });
const HOUR=3_600_000;
const number=(v,min,max)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max;
export function parseForecast(data) {
  const h=data?.hourly;
  if(!h||!Array.isArray(h.time)||!Array.isArray(h.precipitation_probability)||!Array.isArray(h.rain)||!Array.isArray(h.showers)||[h.precipitation_probability,h.rain,h.showers].some(v=>v.length!==h.time.length))throw new Error('Forecast data has an invalid format');
  return h.time.map((end,i)=>{
    if(!Number.isInteger(end)||(i>0&&end<=h.time[i-1]))throw new Error('Invalid forecast hour mark');
    return {end:end*1000,probability:number(h.precipitation_probability[i],0,100)?h.precipitation_probability[i]:null,
      rain_mm:number(h.rain[i],0,10000)&&number(h.showers[i],0,10000)?Number((h.rain[i]+h.showers[i]).toFixed(3)):null};
  });
}
export function summarizeForecast(hours,now) {
  const end=now+WEATHER_POLICY.horizonHours*HOUR;
  // Totals refer to the preceding hour, so include hourly intervals overlapping the next 12h.
  const selected=hours.filter(h=>h.end>now&&h.end-HOUR<end).map(h=>({
    interval_start:new Date(Math.max(now,h.end-HOUR)).toISOString(),interval_end:new Date(Math.min(end,h.end)).toISOString(),
    probability:h.probability,rain_mm_per_hour:h.rain_mm,likely_rain:(h.probability!==null&&h.probability>=WEATHER_POLICY.probabilityThreshold)||(h.rain_mm!==null&&h.rain_mm>=WEATHER_POLICY.rainMmThreshold),
  }));
  const expectedEnds=[];for(let t=Math.floor(now/HOUR)*HOUR+HOUR;t-HOUR<end;t+=HOUR)expectedEnds.push(t);
  const complete=expectedEnds.every(t=>hours.some(h=>h.end===t&&h.probability!==null&&h.rain_mm!==null));
  const first=selected.find(h=>h.likely_rain);
  const probabilities=selected.map(h=>h.probability).filter(v=>v!==null);
  const amounts=selected.map(h=>h.rain_mm_per_hour).filter(v=>v!==null);
  return {window_start:new Date(now).toISOString(),window_end:new Date(end).toISOString(),hourly:selected,complete,
    will_rain:first?true:complete?false:null,first_rain_at:first?.interval_start??null,
    max_probability:probabilities.length?Math.max(...probabilities):null,max_rain_mm_per_hour:amounts.length?Math.max(...amounts):null};
}
export function createWeatherService({fetchImpl=fetch,clock=Date.now}={}) {
  const cache=new Map();const pending=new Map();
  async function location(key,coords) {
    const cached=cache.get(key);const now=clock();
    if(cached&&now<cached.retryAt)return cached;
    if(pending.has(key))return pending.get(key);
    const task=(async()=>{
      try{
        const url=new URL('https://api.open-meteo.com/v1/forecast');
        url.search=new URLSearchParams({latitude:String(coords[1]),longitude:String(coords[0]),hourly:'precipitation_probability,rain,showers',forecast_hours:'15',timezone:'GMT',timeformat:'unixtime'}).toString();
        const response=await fetchImpl(url,{signal:AbortSignal.timeout(8000)});
        if(!response.ok)throw new Error(`The weather service returned HTTP ${response.status}`);
        const hours=parseForecast(await response.json());
        if(!summarizeForecast(hours,clock()).hourly.length)throw new Error('The forecast source has no data for the next 12 hours');
        const entry={hours,fetchedAt:clock(),retryAt:clock()+WEATHER_POLICY.cacheMs,error:null};cache.set(key,entry);return entry;
      }catch(error){
        const entry={hours:cached?.hours??[],fetchedAt:cached?.fetchedAt??null,retryAt:clock()+WEATHER_POLICY.retryMs,error:error.name==='TimeoutError'?'The weather API timed out':String(error.message)};
        cache.set(key,entry);return entry;
      }finally{pending.delete(key);}
    })();pending.set(key,task);return task;
  }
  async function camerasForecast(cameras) {
    const groups=new Map();
    for(const camera of cameras){const key=camera.geometry.coordinates.slice(0,2).join(',');if(!groups.has(key))groups.set(key,camera.geometry.coordinates);}
    const entries=[...groups.entries()].slice(0,WEATHER_POLICY.maxLocations);const values=new Map();let next=0;
    await Promise.all(Array.from({length:Math.min(WEATHER_POLICY.concurrency,entries.length)},async()=>{while(next<entries.length){const [key,coords]=entries[next++];values.set(key,await location(key,coords));}}));
    for(const key of cache.keys())if(!groups.has(key))cache.delete(key);
    const now=clock();
    return {provider:'Open-Meteo',attribution_url:'https://open-meteo.com/',horizon_hours:12,generated_at:new Date(now).toISOString(),policy:WEATHER_POLICY,
      cameras:cameras.map(camera=>{
        const entry=values.get(camera.geometry.coordinates.slice(0,2).join(','));
        const summary=summarizeForecast(entry?.hours??[],now);
        const status=!entry?.fetchedAt||!summary.hourly.length?'unavailable':entry.error||now-entry.fetchedAt>=WEATHER_POLICY.cacheMs?'stale':summary.complete?'fresh':'partial';
        return {camera_id:camera.camera_id,camera_name:camera.name??camera.camera_id,road_id:camera.road_id,coordinates:camera.geometry.coordinates.slice(0,2),
          status,fetched_at:entry?.fetchedAt?new Date(entry.fetchedAt).toISOString():null,error:entry?.error??(!entry?'Limit of 100 locations per request exceeded':null),display_radius_m:WEATHER_POLICY.displayRadiusM,...summary};
      })};
  }
  return {camerasForecast};
}
