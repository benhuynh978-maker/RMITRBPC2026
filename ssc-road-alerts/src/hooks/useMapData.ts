import { useCallback, useEffect, useRef, useState } from 'react';
import type { Camera } from '../models/camera';
import type { RoadAlert } from '../models/roadAlert';
import { getCameras,getRoads } from '../services/mapService';
import { MONITORING_CONFIG } from '../config/monitoring';
export function useMapData(enabled = true) {
 const [cameras,setCameras]=useState<Camera[]>([]);
 const [roads,setRoads]=useState<RoadAlert[]>([]);
 const [errors,setErrors]=useState({cameras:'',roads:''});
 const [loading,setLoading]=useState(false);
 const [updated,setUpdated]=useState('');
 const active=useRef<AbortController|null>(null);
 const refresh=useCallback(async()=>{
   if (!enabled) return;
   active.current?.abort();const controller=new AbortController();active.current=controller;setLoading(true);
   const [c,r]=await Promise.allSettled([getCameras(controller.signal),getRoads(controller.signal)]);
   if(controller.signal.aborted)return;
   if(c.status==='fulfilled')setCameras(c.value);
   if(r.status==='fulfilled')setRoads(r.value);
   setErrors({cameras:c.status==='rejected'?String(c.reason.message):'',roads:r.status==='rejected'?String(r.reason.message):''});
   if(c.status==='fulfilled'||r.status==='fulfilled')setUpdated(new Date().toLocaleTimeString('vi-VN'));
   setLoading(false);
 },[enabled]);
 useEffect(()=>{if(!enabled){setLoading(false);return;}void refresh();const timer=setInterval(()=>{if(!document.hidden&&!active.current?.signal.aborted)void refresh();},MONITORING_CONFIG.pollIntervalMs);return()=>{clearInterval(timer);active.current?.abort();};},[refresh,enabled]);
 return {cameras,roads,errors,loading,updated,refresh};
}
