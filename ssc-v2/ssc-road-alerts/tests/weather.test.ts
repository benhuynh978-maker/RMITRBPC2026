import {describe,it,expect,vi} from 'vitest';
// @ts-expect-error Backend is native JavaScript.
import {createWeatherService,summarizeForecast,parseForecast,WEATHER_POLICY} from '../server/weather.js';
import {mergeWeather} from '../src/services/weatherService';
import type { WeatherResponse } from '../src/models/weather';
const HOUR=3_600_000;
const start=Date.parse('2026-09-09T12:00:00Z');
const camera={camera_id:'C1',road_id:'R1',geometry:{type:'Point',coordinates:[106.7,10.77]}};
function payload(now=start){return {hourly:{time:Array.from({length:16},(_,i)=>(Math.floor(now/HOUR)*HOUR+i*HOUR)/1000),precipitation_probability:Array(16).fill(65),rain:Array(16).fill(0.3),showers:Array(16).fill(0.1)}};}
describe('Camera-based weather forecasts',()=>{
  it('queries lat/lon in the correct order, deduplicates cameras and concurrent requests, caches 15 minutes',async()=>{
    let now=start;const fetchImpl=vi.fn(async()=>({ok:true,json:async()=>payload(now)}));
    const weather=createWeatherService({fetchImpl,clock:()=>now});
    const cameras=[camera,{...camera,camera_id:'C2'}];
    const [response]=await Promise.all([weather.camerasForecast(cameras),weather.camerasForecast(cameras)]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const url=String((fetchImpl.mock.calls as unknown as [URL][])[0][0]);
    expect(url).toContain('latitude=10.77');expect(url).toContain('longitude=106.7');
    expect(response.cameras[0].will_rain).toBe(true);expect(response.cameras[0].status).toBe('fresh');
    expect(response.cameras[0].hourly).toHaveLength(12);
    now+=1000;await weather.camerasForecast(cameras);expect(fetchImpl).toHaveBeenCalledTimes(1);
    now+=WEATHER_POLICY.cacheMs;await weather.camerasForecast(cameras);expect(fetchImpl).toHaveBeenCalledTimes(2);
    await weather.camerasForecast([{...camera,geometry:{type:'Point',coordinates:[107,11]}}]);expect(fetchImpl).toHaveBeenCalledTimes(3);
  });
  it('clips the next 12 hours across midnight and does not use past-hour rain',()=>{
    const now=Date.parse('2026-09-09T23:30:00Z');
    const p=payload(now);p.hourly.precipitation_probability.fill(0);p.hourly.rain.fill(0);p.hourly.showers.fill(0);
    p.hourly.precipitation_probability[0]=100;
    const result=summarizeForecast(parseForecast(p),now);
    expect(result.will_rain).toBe(false);expect(result.hourly).toHaveLength(13);
    expect(result.window_end).toBe('2026-09-10T11:30:00.000Z');
    expect(result.hourly[0].interval_start).toBe(new Date(now).toISOString());
    expect(result.hourly.at(-1).interval_end).toBe(result.window_end);
  });
  it('treats missing measurements as unknown, not no-rain, and rejects malformed series',()=>{
    const p=payload();p.hourly.precipitation_probability.fill(0);p.hourly.rain.fill(0);p.hourly.showers.fill(0);
    (p.hourly.rain as (number|null)[])[3]=null;
    expect(summarizeForecast(parseForecast(p),start).will_rain).toBeNull();
    expect(()=>parseForecast({hourly:{time:[]}})).toThrow();
    p.hourly.time[1]=p.hourly.time[0];expect(()=>parseForecast(p)).toThrow();
  });
  it('returns stale cache on provider failure and uses retry backoff; first failure is unavailable',async()=>{
    let now=start;let fail=false;
    const fetchImpl=vi.fn(async()=>{if(fail)throw new Error('Provider unavailable');return {ok:true,json:async()=>payload()};});
    const weather=createWeatherService({fetchImpl,clock:()=>now});await weather.camerasForecast([camera]);
    now+=WEATHER_POLICY.cacheMs+1;fail=true;
    const data=await weather.camerasForecast([camera]);expect(data.cameras[0].status).toBe('stale');
    expect(data.cameras[0].fetched_at).toBe(new Date(start).toISOString());
    await weather.camerasForecast([camera]);expect(fetchImpl).toHaveBeenCalledTimes(2);
    const offline=createWeatherService({fetchImpl,clock:()=>now});expect((await offline.camerasForecast([camera])).cameras[0].status).toBe('unavailable');
  });
  it('does not turn stale forecasts into operational rain alerts or erase manual rain',async()=>{
    const weather=createWeatherService({fetchImpl:async()=>({ok:true,json:async()=>payload()}),clock:()=>start});
    const response:WeatherResponse=await weather.camerasForecast([camera]);
    const roads=[{road_id:'R1',severity:'normal' as const,geometry:{type:'LineString' as const,coordinates:[[106,10],[107,11]] as [number,number][]}}];
    expect(mergeWeather(roads,response,start)[0].monitoring?.rain_expected).toBe(true);
    expect(mergeWeather(roads,response,start+16*60_000)[0].monitoring).toBeUndefined();
    response.cameras[0].status='stale';expect(mergeWeather(roads,response,start)[0].monitoring).toBeUndefined();
    expect(mergeWeather([{...roads[0],monitoring:{rain_expected:true}}],null,start)[0].monitoring?.rain_expected).toBe(true);
  });
});
