import { divIcon } from 'leaflet';
import { renderToStaticMarkup } from 'react-dom/server';
import { Camera, TriangleAlert } from 'lucide-react';
import { Marker, Popup, Polyline } from 'react-leaflet';
import { toLeafletPositions } from '../../services/normalizeAlerts';
import type { Camera as CameraModel } from '../../models/camera';
import type { RoadAlert } from '../../models/roadAlert';
import { roadMidpoint } from '../../services/roadMidpoint';
import { SEVERITY } from '../../config/severity';
const cameraIcon=divIcon({className:'map-point camera-point',html:renderToStaticMarkup(<Camera size={21}/>),iconSize:[38,38],iconAnchor:[19,19]});
const roadIcon=divIcon({className:'map-point warning-point',html:renderToStaticMarkup(<TriangleAlert size={21}/>),iconSize:[38,38],iconAnchor:[19,19]});
export function CameraLayer({cameras,onSelect}:{cameras:CameraModel[];onSelect?:(id:string)=>void}) {
 return <>{cameras.map(c=><Marker key={c.camera_id} icon={cameraIcon} position={[c.geometry.coordinates[1],c.geometry.coordinates[0]]} title={c.name||c.camera_id} eventHandlers={{click:()=>onSelect?.(c.camera_id)}}><Popup><strong>{c.name||c.camera_id}</strong><p>ID: {c.camera_id}</p><p>Status: {c.status==='online'?'Online':c.status==='offline'?'Offline':'Unknown'}</p><button onClick={()=>onSelect?.(c.camera_id)}>View figures and images</button></Popup></Marker>)}</>;
}
export function RoadPointLayer({roads,onSelect}:{roads:RoadAlert[];onSelect?:(id:string)=>void}) {
 return <>{roads.filter(r=>r.severity!=='normal').map(r=>{const [lng,lat]=roadMidpoint(r.geometry.coordinates);return <Marker key={r.road_id} icon={roadIcon} position={[lat,lng]} title={r.road_name||r.road_id} eventHandlers={{click:()=>onSelect?.(r.road_id)}}><Popup><strong>{r.road_name||r.road_id}</strong><p>ID: {r.road_id} · {SEVERITY[r.severity].label}</p><p>{r.description}</p><button onClick={()=>onSelect?.(r.road_id)}>View road details</button></Popup></Marker>;})}</>;
}
export function RoadAlertLayer({roads,selectedId,onSelect}:{roads:RoadAlert[];selectedId?:string;onSelect?:(id:string)=>void}) {
 return <>{roads.map(road=><Polyline key={road.road_id} positions={toLeafletPositions(road.geometry.coordinates)} pathOptions={{color:road.data_quality==='unknown'&&road.severity==='normal'?'#8296a1':SEVERITY[road.severity].color,dashArray:road.data_quality==='unknown'?'6 8':undefined,weight:road.road_id===selectedId?10:6,opacity:0.9}} eventHandlers={{click:()=>onSelect?.(road.road_id)}}><Popup><strong>{road.road_name??road.road_id}</strong><p>Priority: {road.data_quality==='unknown'&&road.severity==='normal'?'Not enough data':SEVERITY[road.severity].label}</p><button onClick={()=>onSelect?.(road.road_id)}>View road details</button></Popup></Polyline>)}</>;
}
