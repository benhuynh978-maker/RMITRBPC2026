import { useEffect, useState } from 'react';
import { MapContainer, useMap, ZoomControl } from 'react-leaflet';
import { LocateFixed } from 'lucide-react';
import type { RoadAlert } from '../../models/roadAlert';
import { toLeafletPositions } from '../../services/normalizeAlerts';
import { CameraLayer, RoadPointLayer, RoadAlertLayer } from './PointLayers';
import type { Camera } from '../../models/camera';
import { CoordinatePicker, type DrawMode, type DraftPoint } from './CoordinatePicker';
import { basemaps } from '../../config/basemaps';
import { BasemapLayer, type TileHealth } from './BasemapLayer';
import { RainLayer } from './RainLayer';
import type { CameraForecast } from '../../models/weather';
function Viewport({roads,cameras,reset}:{roads:RoadAlert[];cameras:Camera[];reset:number}) {
 const map=useMap();
 const bounds=JSON.stringify([...roads.flatMap(r=>toLeafletPositions(r.geometry.coordinates)),...cameras.map(c=>[c.geometry.coordinates[1],c.geometry.coordinates[0]])]);
 useEffect(()=>{ const points=JSON.parse(bounds) as [number,number][]; if(points.length) map.fitBounds(points,{padding:[60,60],maxZoom:16,animate:false}); },[bounds,reset,map]);
 useEffect(()=>{ const observer=new ResizeObserver(()=>map.invalidateSize());observer.observe(map.getContainer());return()=>observer.disconnect();},[map]);
 return null;
}
function SelectedViewport({road,camera}:{road?:RoadAlert;camera?:Camera}) {
 const map=useMap();
 const coordinates=JSON.stringify(camera ? [[camera.geometry.coordinates[1],camera.geometry.coordinates[0]]] : road ? toLeafletPositions(road.geometry.coordinates) : []);
 useEffect(()=>{const points=JSON.parse(coordinates) as [number,number][]; if(points.length)map.fitBounds(points,{padding:[70,70],maxZoom:18,animate:false});},[coordinates,map]);
 return null;
}
export function RoadMap({roads,cameras,drawMode,draft,onPoint,selectedRoad,selectedCamera,onRoadSelect,onCameraSelect,rainForecasts=[]}:{rainForecasts?:CameraForecast[];roads:RoadAlert[];cameras:Camera[];drawMode:DrawMode;draft:DraftPoint[];onPoint:(p:DraftPoint)=>void;selectedRoad?:RoadAlert;selectedCamera?:Camera;onRoadSelect?:(id:string)=>void;onCameraSelect?:(id:string)=>void}) {
 const [reset,setReset]=useState(0);
 const [choice,setChoice]=useState('fallback');
 const [source,setSource]=useState(1);
 const [attempt,setAttempt]=useState(0);
 const [health,setHealth]=useState<TileHealth>('loading');
 const provider=basemaps[source];
 function restart(nextChoice=choice) {
   setChoice(nextChoice); setSource(nextChoice==='fallback'?1:0);
   setAttempt(v=>v+1); setHealth('loading');
 }
 function onHealth(next:TileHealth) {
   if(next==='unavailable' && choice==='auto' && source===0) {
     setSource(1); setAttempt(v=>v+1); setHealth('loading');
   } else setHealth(next);
 }
 return <section className="map-shell" aria-label="Road alert map">
   <MapContainer center={[10.773,106.700]} zoom={15} maxZoom={19} zoomControl={false} className="road-map">
     <BasemapLayer key={`${source}-${attempt}`} provider={provider} onHealth={onHealth}/>
     <ZoomControl position="bottomright"/>
     <RainLayer forecasts={rainForecasts}/>
     <Viewport roads={roads} cameras={cameras} reset={reset}/>
     <SelectedViewport road={selectedRoad} camera={selectedCamera}/>
     <RoadAlertLayer roads={roads} selectedId={selectedRoad?.road_id} onSelect={drawMode==='none'?onRoadSelect:undefined}/>
     <CameraLayer cameras={cameras} onSelect={drawMode==='none'?onCameraSelect:undefined}/><RoadPointLayer roads={roads} onSelect={drawMode==='none'?onRoadSelect:undefined}/><CoordinatePicker mode={drawMode} points={draft} onPoint={onPoint}/>
   </MapContainer>
   <div className="map-label"><span className="live-dot"/> ROAD MAP</div>
   <button className="map-fit" onClick={()=>{setReset(v=>v+1);}}><LocateFixed size={17}/>Fit all points</button>
   <div className="basemap-control"><label>Basemap<select value={choice} onChange={e=>restart(e.target.value)}><option value="auto">Auto-switch source</option>{basemaps.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label><button onClick={()=>restart()}>Retry basemap</button></div>
   <div className={`tile-status ${health==='unavailable'||health==='partial'?'tile-warning':''}`} role="status">
     {health==='unavailable'?'Could not load the basemap. Check the network/DNS or choose another source; alert segments are still shown.':health==='partial'?'Some map tiles failed to load. You can retry or choose another source.':health==='loading'?`Loading ${provider.label}…`:`Basemap: ${provider.label}${choice==='auto'&&source===1?' · Switched source because the primary did not respond.':''}`}
   </div>
 </section>;
}
