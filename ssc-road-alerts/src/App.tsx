import { useMemo, useState } from 'react';
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
  const selectedCamera=selection?.kind==='camera'?cameras.find(c=>c.camera_id===selection.id):undefined;
  const selectedRoad=roads.find(r=>r.road_id===(selection?.kind==='road'?selection.id:selectedCamera?.road_id));
  const alertIds=new Set(alerts.map(a=>a.road.road_id));
  const priority=new Map(alerts.map(a=>[a.road.road_id,a.severity]));
  const filtered=roads.filter(r=>(!onlyAlerts||alertIds.has(r.road_id))&&`${r.road_id} ${r.road_name??''}`.toLocaleLowerCase('vi').includes(query.toLocaleLowerCase('vi')));
  const mapRoads=filtered.map(r=>({...r,severity:priority.get(r.road_id)??r.severity}));
  const stale=mode==='api'&&!!data.errors.roads;
  function selectRoad(id:string){setSelection({kind:'road',id});setShowRoads(true);setQuery('');setOnlyAlerts(false);}
  function selectCamera(id:string){setSelection({kind:'camera',id});setShowCameras(true);}
  function changeMode(value:'api'|'demo'){setMode(value);setSelection(null);setQuery('');setOnlyAlerts(false);setDraft([]);setDrawMode('none');}
  return <div className="app">
    <header className="header"><a className="brand" href="./"><span className="brand-icon"><Route size={25}/></span><strong>SSC<span>ROAD MONITOR</span></strong></a><span className="header-title">Sustainable Society Challenge</span><div className="header-right"><span className="camera-heading"><CloudRain size={20}/>Phòng ngập từ cửa cống</span></div></header>
    <main>
      <div className="page-heading"><div><div className="eyebrow">GIÁM SÁT MÔI TRƯỜNG ĐÔ THỊ</div><h1>Thu gom kịp thời. Giảm nguy cơ ngập.</h1><p>Theo dõi rác thải, tình trạng cống và các tuyến cần xử lý trước mưa.</p></div><div className="heading-actions"><label className="source-picker">Nguồn dữ liệu<select value={mode} onChange={e=>changeMode(e.target.value as 'api'|'demo')}><option value="api">Máy chủ</option><option value="demo">Mô phỏng minh họa</option></select></label><button className="refresh" disabled={data.loading||mode==='demo'} onClick={()=>void data.refresh()}><RefreshCw size={17} className={data.loading?'spinning':''}/>{data.loading?'Đang tải…':'Cập nhật dữ liệu'}</button></div></div>
      {mode==='demo'&&<div className="notice">MÔ PHỎNG · Vị trí và chỉ số chỉ minh họa, quan sát mẫu ngày 09/09/2026. Không phải dữ liệu hiện trường; không dùng điều phối thực tế.</div>}
      {mode==='api'&&<div className="data-status" role="status">{data.loading?'Đang nhận dữ liệu…':data.updated?`Lần nhận gần nhất: ${data.updated} · Tự cập nhật mỗi 30 giây khi mở tab.`:'Chưa nhận được dữ liệu.'}{data.errors.cameras&&<span>Camera: {data.errors.cameras}. {cameras.length?'Đang giữ dữ liệu cũ.':'Chưa có dữ liệu.'}</span>}{data.errors.roads&&<span>Tuyến: {data.errors.roads}. {roads.length?'Đang giữ dữ liệu cũ.':'Chưa có dữ liệu.'}</span>}</div>}
      <section className="summary overview" aria-label="Tổng quan"><div><Route size={21}/><span>Tuyến đang giám sát</span><strong>{roads.length}</strong></div><div><TriangleAlert size={21}/><span>Tuyến cần chú ý</span><strong className="urgent-number">{alerts.length}</strong></div><div><Camera size={21}/><span>Camera trực tuyến</span><strong>{cameras.filter(c=>c.status==='online').length}<small>/ {cameras.length} camera</small></strong></div><div><CloudRain size={21}/><span>Tuyến có tín hiệu mưa</span><strong>{roads.filter(r=>r.monitoring?.rain_expected===true).length}</strong></div></section>
      {handling.announcement&&<div className="notice notification" role="status" aria-live="polite"><Bell size={19}/><span>{handling.announcement}</span><button className="secondary" onClick={handling.dismiss}>Ẩn thông báo</button></div>}
      <div className="monitor"><aside className="sidebar"><div className="list-title"><h2>Tuyến đường</h2><span>{filtered.length}</span></div><div className="road-filters"><label>Tìm tuyến<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Tên hoặc mã tuyến…"/></label><label className="check-label"><input type="checkbox" checked={onlyAlerts} onChange={e=>setOnlyAlerts(e.target.checked)}/>Chỉ tuyến cần chú ý</label></div><div className="road-list">{filtered.map(road=>{const severity=priority.get(road.road_id)??road.severity;return <button key={road.road_id} aria-pressed={selectedRoad?.road_id===road.road_id} className={`road-card ${selectedRoad?.road_id===road.road_id?'selected':''}`} onClick={()=>selectRoad(road.road_id)}><span className="road-id">{road.road_id}</span><strong>{road.road_name??road.road_id}</strong><span className="badge" style={{color:SEVERITY[severity].color,background:SEVERITY[severity].background}}>{road.data_quality==='unknown'&&severity==='normal'?'Chưa đủ dữ liệu':SEVERITY[severity].label}</span><small>Rác: {road.monitoring?.waste_level?SEVERITY[road.monitoring.waste_level].label:road.monitoring?.waste_coverage_pct===undefined?'chưa có':`${road.monitoring.waste_coverage_pct}%`} · {cameras.filter(c=>c.road_id===road.road_id).length} camera</small></button>;})}{!filtered.length&&<p className="empty">{roads.length?'Không có tuyến phù hợp bộ lọc.':'Chưa có dữ liệu tuyến. Chọn “Mô phỏng minh họa” để thử hệ thống.'}</p>}</div><div className="list-footer">Chọn tuyến để xem chỉ số và camera.</div></aside>
        <RoadMap rainForecasts={showRain?weather.data?.cameras??[]:[]} roads={showRoads?mapRoads:[]} cameras={showCameras?cameras:[]} selectedRoad={showRoads?selectedRoad:undefined} selectedCamera={showCameras?selectedCamera:undefined} onRoadSelect={selectRoad} onCameraSelect={selectCamera} drawMode={drawMode} draft={draft} onPoint={p=>setDraft(v=>drawMode==='camera'?[p]:[...v,p])}/>
      </div>
      <div className="bottom-row"><div className="legend"><span>MỨC ƯU TIÊN HIỂN THỊ</span>{[...SEVERITY_ORDER].reverse().map(level=><span className="legend-item" key={level}><i style={{background:SEVERITY[level].color}}/>{SEVERITY[level].label}</span>)}</div><span className="coordinate-note">Màu ưu tiên tổng hợp; nguy cơ ngập xem trong chi tiết.</span></div>
      <div className="layer-controls"><label className="layer-toggle"><Camera size={20}/><span>Hiện camera<small>{cameras.length} điểm đã nhận</small></span><input type="checkbox" checked={showCameras} onChange={e=>setShowCameras(e.target.checked)}/></label><label className="layer-toggle"><Route size={20}/><span>Hiện đoạn đường theo mức ưu tiên<small>{filtered.length} đoạn trong bộ lọc</small></span><input type="checkbox" checked={showRoads} onChange={e=>setShowRoads(e.target.checked)}/></label></div>
      <label className="layer-toggle rain-toggle"><CloudRain size={20}/><span>Hiện khu vực sắp mưa — 12 giờ tới<small>{weather.loading?'Đang lấy dự báo':weather.data?`${weather.data.cameras.filter(c=>c.will_rain===true&&c.status!=='unavailable').length} vị trí có tín hiệu mưa`:'Dự báo theo camera đã lưu; không dùng tọa độ bản nháp'}</small></span><input type="checkbox" checked={showRain} onChange={e=>setShowRain(e.target.checked)}/></label>
      {showRain&&<WeatherPanel data={weather.data} loading={weather.loading} error={weather.error} onRefresh={()=>void weather.refresh()} onCamera={selectCamera}/>}
      <ObservationDetail road={selectedRoad} camera={selectedCamera} cameras={cameras} onCamera={camera=>selectCamera(camera.camera_id)} onClose={()=>setSelection(null)}/>
      {handling.storageError&&<p className="notice" role="status">{handling.storageError}</p>}
      <AlertQueue alerts={alerts} cameras={cameras} records={handling.records} update={handling.update} onSelect={selectRoad} demo={mode==='demo'} stale={stale}/>
      <p className="threshold-note">Quy tắc thử nghiệm: rác ≥ {MONITORING_CONFIG.wasteThreshold}%, tỉ lệ ngập ≥ {MONITORING_CONFIG.floodThreshold}%, có tín hiệu mưa hoặc cảnh báo từ máy chủ. Chỉ số tuyến là trung bình các camera còn hiệu lực.</p>
      <CoordinateTool mode={drawMode} draft={draft} onMode={setDrawMode} onDraft={setDraft}/>
      <footer><span>SSC / Giám sát rác và nguy cơ ngập</span><span>Camera → Máy chủ / AI → Tuyến đường → Điều phối</span></footer>
    </main>
  </div>;
}
