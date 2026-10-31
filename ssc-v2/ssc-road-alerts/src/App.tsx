import { useEffect, useMemo, useState } from 'react';
import { Bell, Camera, CloudRain, RefreshCw, Route, TriangleAlert } from 'lucide-react';
import { RoadMap } from './components/map/RoadMap';
import { useMapData } from './hooks/useMapData';
import { useAlertHandling } from './hooks/useAlertHandling';
import type { DraftPoint, DrawMode } from './components/map/CoordinatePicker';
import { ObservationDetail } from './components/monitoring/ObservationDetail';
import { AlertQueue } from './components/monitoring/AlertQueue';
import { CoordinateTool } from './components/monitoring/CoordinateTool';
import { buildMonitoringAlerts } from './services/monitoringService';
import { demoCameras, demoRoads } from './mocks/monitoring';
import { SEVERITY, SEVERITY_ORDER } from './config/severity';
import { MONITORING_CONFIG } from './config/monitoring';
import { useWeather } from './hooks/useWeather';
import { mergeWeather } from './services/weatherService';
import { WeatherPanel } from './components/monitoring/WeatherPanel';
import { DrainSummaryRow } from './components/monitoring/DrainSummaryRow';

export default function App() {
  const [mode,setMode]=useState<'api'|'demo'>('api');
  const data=useMapData(mode==='api');
  const sourceRoads=mode==='demo'?demoRoads:data.roads;
  const cameras=mode==='demo'?demoCameras:data.cameras;
  const weather=useWeather(cameras,mode==='api');
  const roads=useMemo(()=>mergeWeather(sourceRoads,weather.data),[sourceRoads,weather.data]);
  const [showRain,setShowRain]=useState(false);
  const alerts=useMemo(()=>buildMonitoringAlerts(roads),[roads]);
  const handling=useAlertHandling(alerts,mode);
  const [showCameras,setShowCameras]=useState(true);
  const [showRoads,setShowRoads]=useState(true);
  const [selection,setSelection]=useState<{kind:'road'|'camera';id:string}|null>(null);
  const [query,setQuery]=useState('');
  const [onlyAlerts,setOnlyAlerts]=useState(false);
  const [drawMode,setDrawMode]=useState<DrawMode>('none');
  const [draft,setDraft]=useState<DraftPoint[]>([]);
  useEffect(()=>{ if(!selection) return; const t=setTimeout(()=>document.querySelector('section[aria-label="Observation details"]')?.scrollIntoView({behavior:'smooth',block:'start'}),50); return ()=>clearTimeout(t); },[selection?.kind,selection?.id]); // after selecting, scroll to the detail block
  const selectedCamera=selection?.kind==='camera'?cameras.find(c=>c.camera_id===selection.id):undefined;
  const selectedRoad=roads.find(r=>r.road_id===(selection?.kind==='road'?selection.id:selectedCamera?.road_id));
  const alertIds=new Set(alerts.map(a=>a.road.road_id));
  const priority=new Map(alerts.map(a=>[a.road.road_id,a.severity]));
  const filtered=roads.filter(r=>(!onlyAlerts||alertIds.has(r.road_id))&&`${r.road_id} ${r.road_name??''}`.toLocaleLowerCase('en').includes(query.toLocaleLowerCase('en')));
  const mapRoads=filtered.map(r=>({...r,severity:priority.get(r.road_id)??r.severity}));
  const stale=mode==='api'&&!!data.errors.roads;
  function selectRoad(id:string){setSelection({kind:'road',id});setShowRoads(true);setQuery('');setOnlyAlerts(false);}
  function selectCamera(id:string){setSelection({kind:'camera',id});setShowCameras(true);}
  function changeMode(value:'api'|'demo'){setMode(value);setSelection(null);setQuery('');setOnlyAlerts(false);setDraft([]);setDrawMode('none');}
  return <div className="app">
    <header className="header"><a className="brand" href="./"><span className="brand-icon"><Route size={25}/></span><strong>CleanSight<span>Road Monitor</span></strong></a><div className="header-right"><span className="camera-heading"><CloudRain size={20}/>Flood prevention starts at the drain</span></div></header>
    <main>
      <div className="page-heading"><div><div className="eyebrow">URBAN ENVIRONMENT MONITORING</div><h1>Collect on time. Reduce flood risk.</h1><p>Track litter, drain condition and the roads that need attention before rain.</p></div><div className="heading-actions"><label className="source-picker">Data source<select value={mode} onChange={e=>changeMode(e.target.value as 'api'|'demo')}><option value="api">Server</option><option value="demo">Demo simulation</option></select></label><button className="refresh" disabled={data.loading||mode==='demo'} onClick={()=>void data.refresh()}><RefreshCw size={17} className={data.loading?'spinning':''}/>{data.loading?'Loading…':'Refresh data'}</button></div></div>
      {mode==='demo'&&<div className="notice">SIMULATION · Locations and figures are illustrative, sample observation of 09/09/2026. Not field data; do not use for real dispatch.</div>}
      {mode==='api'&&<div className="data-status" role="status">{data.loading?'Receiving data…':data.updated?`Last received: ${data.updated} · Auto-refreshes every 30 seconds while the tab is open.`:'No data received yet.'}{data.errors.cameras&&<span>Cameras: {data.errors.cameras}. {cameras.length?'Keeping previous data.':'No data yet.'}</span>}{data.errors.roads&&<span>Roads: {data.errors.roads}. {roads.length?'Keeping previous data.':'No data yet.'}</span>}</div>}
      <section className="summary overview" aria-label="Overview"><div><Route size={21}/><span>Roads monitored</span><strong>{roads.length}</strong></div><div><TriangleAlert size={21}/><span>Roads needing attention</span><strong className="urgent-number">{alerts.length}</strong></div><div><Camera size={21}/><span>Cameras online</span><strong>{cameras.filter(c=>c.status==='online').length}<small>/ {cameras.length} cameras</small></strong></div><div><CloudRain size={21}/><span>Roads with rain signal</span><strong>{roads.filter(r=>r.monitoring?.rain_expected===true).length}</strong></div></section>
      {handling.announcement&&<div className="notice notification" role="status" aria-live="polite"><Bell size={19}/><span>{handling.announcement}</span><button className="secondary" onClick={handling.dismiss}>Dismiss</button></div>}
      <div className="monitor"><aside className="sidebar"><div className="list-title"><h2>Roads</h2><span>{filtered.length}</span></div><div className="road-filters"><label>Search roads<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Road name or ID…"/></label><label className="check-label"><input type="checkbox" checked={onlyAlerts} onChange={e=>setOnlyAlerts(e.target.checked)}/>Only roads needing attention</label></div><div className="road-list">{filtered.map(road=>{const severity=priority.get(road.road_id)??road.severity;return <button key={road.road_id} aria-pressed={selectedRoad?.road_id===road.road_id} className={`road-card ${selectedRoad?.road_id===road.road_id?'selected':''}`} onClick={()=>selectRoad(road.road_id)}><span className="road-id">{road.road_id}</span><strong>{road.road_name??road.road_id}</strong><span className="badge" style={{color:SEVERITY[severity].color,background:SEVERITY[severity].background}}>{road.data_quality==='unknown'&&severity==='normal'?'Not enough data':SEVERITY[severity].label}</span><small>Litter: {road.monitoring?.waste_level?SEVERITY[road.monitoring.waste_level].label:road.monitoring?.waste_coverage_pct===undefined?'n/a':`${road.monitoring.waste_coverage_pct}%`} · {cameras.filter(c=>c.road_id===road.road_id).length} cameras</small><DrainSummaryRow summary={road.drain_summary} compact/></button>;})}{!filtered.length&&<p className="empty">{roads.length?'No roads match the filter.':'No road data yet. Choose “Demo simulation” to try the system.'}</p>}</div><div className="list-footer">Select a road to see its figures and cameras.</div></aside>
        <RoadMap rainForecasts={showRain?weather.data?.cameras??[]:[]} roads={showRoads?mapRoads:[]} cameras={showCameras?cameras:[]} selectedRoad={showRoads?selectedRoad:undefined} selectedCamera={showCameras?selectedCamera:undefined} onRoadSelect={selectRoad} onCameraSelect={selectCamera} drawMode={drawMode} draft={draft} onPoint={p=>setDraft(v=>drawMode==='camera'?[p]:[...v,p])}/>
      </div>
      <div className="bottom-row"><div className="legend"><span>DISPLAYED PRIORITY</span>{[...SEVERITY_ORDER].reverse().map(level=><span className="legend-item" key={level}><i style={{background:SEVERITY[level].color}}/>{SEVERITY[level].label}</span>)}</div><span className="coordinate-note">Colour shows combined priority; drain status is in the details.</span></div>
      <div className="layer-controls"><label className="layer-toggle"><Camera size={20}/><span>Show cameras<small>{cameras.length} points received</small></span><input type="checkbox" checked={showCameras} onChange={e=>setShowCameras(e.target.checked)}/></label><label className="layer-toggle"><Route size={20}/><span>Show road segments by priority<small>{filtered.length} segments in filter</small></span><input type="checkbox" checked={showRoads} onChange={e=>setShowRoads(e.target.checked)}/></label></div>
      <label className="layer-toggle rain-toggle"><CloudRain size={20}/><span>Show areas with rain forecast (next 12 hours)<small>{weather.loading?'Loading forecast':weather.data?`${weather.data.cameras.filter(c=>c.will_rain===true&&c.status!=='unavailable').length} locations with rain signal`:'Forecast for saved cameras; draft coordinates are not used'}</small></span><input type="checkbox" checked={showRain} onChange={e=>setShowRain(e.target.checked)}/></label>
      {showRain&&<WeatherPanel data={weather.data} loading={weather.loading} error={weather.error} onRefresh={()=>void weather.refresh()} onCamera={selectCamera}/>}
      <ObservationDetail road={selectedRoad} camera={selectedCamera} cameras={cameras} onCamera={camera=>selectCamera(camera.camera_id)} onClose={()=>setSelection(null)} onRefresh={()=>void data.refresh()} demo={mode==='demo'}/>
      {handling.storageError&&<p className="notice" role="status">{handling.storageError}</p>}
      <AlertQueue alerts={alerts} cameras={cameras} records={handling.records} update={handling.update} onSelect={selectRoad} demo={mode==='demo'} stale={stale}/>
      <p className="threshold-note">Trial rules: litter ≥ {MONITORING_CONFIG.wasteThreshold}%, drain coverage ≥ {MONITORING_CONFIG.floodThreshold}%, a rain signal or a server alert. Road figures are the average of cameras with valid data.</p>
      <CoordinateTool mode={drawMode} draft={draft} onMode={setDrawMode} onDraft={setDraft}/>
      <footer><span>CleanSight · Road Monitor</span><span>Camera → Server / AI → Road → Dispatch</span></footer>
    </main>
  </div>;
}
