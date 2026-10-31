import { useCallback, useEffect, useRef, useState } from 'react';
import type { Camera } from '../models/camera';
import type { WeatherResponse } from '../models/weather';
import { getWeather } from '../services/weatherService';

export function useWeather(cameras:Camera[],enabled:boolean) {
  const signature=JSON.stringify(cameras.map(c=>[c.camera_id,c.road_id,c.geometry.coordinates]));
  const [state,setState]=useState<{signature:string;data:WeatherResponse|null}>({signature:'',data:null});
  const [loading,setLoading]=useState(false);const [error,setError]=useState('');const active=useRef<AbortController|null>(null);
  const refresh=useCallback(async()=>{
    active.current?.abort();
    if(!enabled||signature==='[]'){setLoading(false);setError('');setState({signature,data:null});return;}
    const controller=new AbortController();active.current=controller;setLoading(true);setError('');
    const timeout=setTimeout(()=>controller.abort(),240_000);
    try{const data=await getWeather(controller.signal);if(!controller.signal.aborted)setState({signature,data});}
    catch(e){if(active.current===controller){setState({signature,data:null});setError(controller.signal.aborted?'Yêu cầu thời tiết bị ngắt hoặc quá thời gian chờ':e instanceof Error?e.message:'Không tải được thời tiết');}}
    finally{clearTimeout(timeout);if(active.current===controller)setLoading(false);}
  },[signature,enabled]);
  useEffect(()=>{void refresh();const visible=()=>{if(!document.hidden)void refresh();};document.addEventListener('visibilitychange',visible);const timer=setInterval(visible,5*60_000);return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',visible);active.current?.abort();active.current=null;};},[refresh]);
  return {data:enabled&&state.signature===signature?state.data:null,loading,error,refresh};
}
