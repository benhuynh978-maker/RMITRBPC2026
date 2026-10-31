import type { WeatherResponse } from '../models/weather';
import type { RoadAlert } from '../models/roadAlert';
export async function getWeather(signal:AbortSignal):Promise<WeatherResponse>{
  const response=await fetch('/api/weather/cameras',{signal,headers:{Accept:'application/json'}});
  if(!response.ok)throw new Error(`Không tải được thời tiết (HTTP ${response.status})`);
  const data=await response.json();
  if(!Array.isArray(data.cameras)||data.horizon_hours!==12)throw new Error('Dữ liệu thời tiết không hợp lệ');
  for(const c of data.cameras){
    if(typeof c.camera_id!=='string'||!['fresh','partial','stale','unavailable'].includes(c.status)||!Array.isArray(c.coordinates)||c.coordinates.length!==2||!c.coordinates.every((n:unknown)=>typeof n==='number'&&Number.isFinite(n))||Math.abs(c.coordinates[0])>180||Math.abs(c.coordinates[1])>90||!Array.isArray(c.hourly)||![true,false,null].includes(c.will_rain)||!Number.isFinite(Date.parse(c.window_end)))throw new Error('Vị trí dự báo không hợp lệ');
  }
  return data;
}
export function mergeWeather(roads:RoadAlert[],weather:WeatherResponse|null,now=Date.now()):RoadAlert[]{
  return roads.map(road=>{
    const rainy=weather?.cameras.some(c=>c.road_id===road.road_id&&(c.status==='fresh'||c.status==='partial')&&c.will_rain===true&&c.fetched_at&&now-Date.parse(c.fetched_at)<15*60_000&&Date.parse(c.window_end)>now);
    return rainy?{...road,monitoring:{...road.monitoring,rain_expected:true}}:road;
  });
}
