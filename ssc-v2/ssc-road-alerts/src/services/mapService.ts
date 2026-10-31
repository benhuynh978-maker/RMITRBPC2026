import type { Camera } from '../models/camera';
import { normalizeAlerts } from './normalizeAlerts';
import { normalizeDrainRoi, normalizeDrainState } from './normalizeDrain';
import { normalizeImages, normalizeMonitoring } from './normalizeMonitoring';
export function normalizeCameras(payload: unknown): Camera[] {
  const rows = (payload as {cameras?:unknown})?.cameras;
  if (!Array.isArray(rows)) throw new Error('The camera API must return {cameras: [...]}');
  const ids = new Set<string>();
  return rows.map(item=>{
    const p = item?.geometry?.coordinates;
    if (typeof item?.camera_id !== 'string' || !item.camera_id.trim() || ids.has(item.camera_id)) throw new Error('camera_id is missing or duplicated');
    ids.add(item.camera_id);
    if (item.geometry?.type !== 'Point' || !Array.isArray(p) || p.length !== 2 || !p.every(n=>typeof n==='number'&&Number.isFinite(n)) || Math.abs(p[0])>180 || Math.abs(p[1])>90) throw new Error(`${item.camera_id}: invalid Point`);
    if (item.name !== undefined && typeof item.name !== 'string') throw new Error('Camera name must be a string');
    if (item.status !== undefined && !['online','offline','unknown'].includes(item.status)) throw new Error('Invalid camera status');
    if (item.road_id !== undefined && (typeof item.road_id !== 'string' || !item.road_id.trim())) throw new Error('Camera road_id must be a non-empty string');
    if(item.analysis_source!==undefined&&!['simulation','ai'].includes(item.analysis_source))throw new Error('Invalid analysis_source');
    if(item.analysis_status!==undefined&&!['fresh','stale'].includes(item.analysis_status))throw new Error('Invalid analysis_status');
    return { camera_id:item.camera_id, name:item.name, status:item.status, geometry:item.geometry, road_id:item.road_id, monitoring:normalizeMonitoring(item.monitoring), images:normalizeImages(item.images),analysis_source:item.analysis_source,analysis_status:item.analysis_status,drain_roi:normalizeDrainRoi(item.drain_roi),drain_state:normalizeDrainState(item.drain_state) } as Camera;
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
    throw new Error(controller.signal.aborted?'The API timed out':e instanceof Error?e.message:'Could not connect to the API');
  } finally { clearTimeout(timer);signal.removeEventListener('abort',abort); }
}
export const getCameras = async (signal:AbortSignal) => normalizeCameras(await getJson(import.meta.env.VITE_CAMERAS_API_URL || '/api/cameras',signal));
export const getRoads = async (signal:AbortSignal) => normalizeAlerts(await getJson(import.meta.env.VITE_ROADS_API_URL || '/api/road-alerts',signal));
