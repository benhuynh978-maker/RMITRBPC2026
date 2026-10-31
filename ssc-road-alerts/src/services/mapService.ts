import type { Camera } from '../models/camera';
import { normalizeAlerts } from './normalizeAlerts';
import { normalizeImages, normalizeMonitoring } from './normalizeMonitoring';
export function normalizeCameras(payload: unknown): Camera[] {
  const rows = (payload as {cameras?:unknown})?.cameras;
  if (!Array.isArray(rows)) throw new Error('API camera cần trả về {cameras: [...]}');
  const ids = new Set<string>();
  return rows.map(item=>{
    const p = item?.geometry?.coordinates;
    if (typeof item?.camera_id !== 'string' || !item.camera_id.trim() || ids.has(item.camera_id)) throw new Error('camera_id thiếu hoặc trùng');
    ids.add(item.camera_id);
    if (item.geometry?.type !== 'Point' || !Array.isArray(p) || p.length !== 2 || !p.every(n=>typeof n==='number'&&Number.isFinite(n)) || Math.abs(p[0])>180 || Math.abs(p[1])>90) throw new Error(`${item.camera_id}: Point không hợp lệ`);
    if (item.name !== undefined && typeof item.name !== 'string') throw new Error('Tên camera phải là chuỗi');
    if (item.status !== undefined && !['online','offline','unknown'].includes(item.status)) throw new Error('Trạng thái camera không hợp lệ');
    if (item.road_id !== undefined && (typeof item.road_id !== 'string' || !item.road_id.trim())) throw new Error('road_id camera phải là chuỗi không rỗng');
    if(item.analysis_source!==undefined&&!['simulation','ai'].includes(item.analysis_source))throw new Error('analysis_source sai');
    if(item.analysis_status!==undefined&&!['fresh','stale'].includes(item.analysis_status))throw new Error('analysis_status sai');
    return { camera_id:item.camera_id, name:item.name, status:item.status, geometry:item.geometry, road_id:item.road_id, monitoring:normalizeMonitoring(item.monitoring), images:normalizeImages(item.images),analysis_source:item.analysis_source,analysis_status:item.analysis_status } as Camera;
  });
}
async function getJson(url: string, signal: AbortSignal) {
  const controller=new AbortController();
  const abort=()=>controller.abort();
  if(signal.aborted) abort(); else signal.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(abort,10000);
  try {
    const res=await fetch(url,{signal:controller.signal,headers:{Accept:'application/json'},cache:'no-store'});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json() as unknown;
  } catch(e) {
    if(signal.aborted) throw e;
    throw new Error(controller.signal.aborted?'API quá thời gian chờ':e instanceof Error?e.message:'Không kết nối được API');
  } finally { clearTimeout(timer);signal.removeEventListener('abort',abort); }
}
export const getCameras = async (signal:AbortSignal) => normalizeCameras(await getJson(import.meta.env.VITE_CAMERAS_API_URL || '/api/cameras',signal));
export const getRoads = async (signal:AbortSignal) => normalizeAlerts(await getJson(import.meta.env.VITE_ROADS_API_URL || '/api/road-alerts',signal));
