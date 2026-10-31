import { CircleMarker, Polyline, useMapEvents } from 'react-leaflet';
export type DraftPoint=[number,number];
export type DrawMode='none'|'camera'|'road';
export function CoordinatePicker({mode,points,onPoint}:{mode:DrawMode;points:DraftPoint[];onPoint:(p:DraftPoint)=>void}) {
 useMapEvents({click:e=>{if(mode!=='none')onPoint([Number(e.latlng.lng.toFixed(7)),Number(e.latlng.lat.toFixed(7))]);}});
 if(mode==='none')return null;
 const positions=points.map(([lng,lat]):[number,number]=>[lat,lng]);
 return <>{positions.map((p,i)=><CircleMarker key={i} center={p} radius={5} pathOptions={{color:'#263f50',fillColor:'#fff',fillOpacity:1}}/>)}{mode==='road'&&positions.length>1&&<Polyline positions={positions} pathOptions={{color:'#263f50',weight:3,dashArray:'5 7'}}/>}</>;
}
