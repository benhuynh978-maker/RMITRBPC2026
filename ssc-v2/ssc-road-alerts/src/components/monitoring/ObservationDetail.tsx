import { useState } from 'react';
import type { Camera } from '../../models/camera';
import type { RoadAlert } from '../../models/roadAlert';
import { Metrics, formatTime } from './Metrics';
import { DrainStatusCard } from './DrainStatusCard';
import { DrainSummaryRow } from './DrainSummaryRow';
import { DrainRoiEditor } from './DrainRoiEditor';
import { DrainPhotoTest } from './DrainPhotoTest';

function ObservationImage({ url, label }: { url?: string; label: string }) {
  const [failed, setFailed] = useState(false);
  return <figure className="observation-image"><figcaption>{label}</figcaption>
    {url && !failed ? <a href={url} target="_blank" rel="noreferrer"><img src={url} alt={label} loading="lazy" onError={() => setFailed(true)}/></a> : <div className="image-placeholder">{failed ? 'Could not load the image. Check the URL or image access.' : 'No image from the camera / server yet.'}</div>}
  </figure>;
}
export function ObservationDetail({ road, camera, cameras, onCamera, onClose, onRefresh, demo = false }: {
  road?: RoadAlert; camera?: Camera; cameras: Camera[]; onCamera: (camera: Camera) => void; onClose: () => void;
  onRefresh?: () => void; demo?: boolean;
}) {
  if (!road && !camera) return null;
  const linked = road ? cameras.filter(c => c.road_id === road.road_id) : [];
  return <section className="observation-detail" aria-label="Observation details">
    <div className="section-heading"><div><span className="eyebrow">{camera ? 'CAMERA NODE' : 'ROAD SUMMARY'}</span><h2>{camera?.name ?? camera?.camera_id ?? road?.road_name ?? road?.road_id}</h2></div><button className="secondary" onClick={onClose}>Close details</button></div>
    <p>{camera ? `${camera.camera_id} · ${camera.status === 'online' ? 'Online' : camera.status === 'offline' ? 'Offline — figures may be outdated' : 'Status unknown'} · Road ${camera.road_id ?? 'not linked'}` : road?.description ?? 'No description from the server.'}</p>
    {camera?.analysis_source==='simulation'&&<p className="notice">Figures come from a simulated API, not from an AI model run.</p>}
    {camera?.analysis_status==='stale'&&<p className="notice">The analysis has expired. Do not use these figures to judge the current situation.</p>}
    {!camera&&road?.data_quality==='unknown'&&<p className="notice">No valid camera analysis yet. There is not enough data to conclude the road is safe.</p>}
    <Metrics data={camera?.monitoring ?? (!camera ? road?.monitoring : undefined)}/>
    {!camera && <DrainSummaryRow summary={road?.drain_summary}/>}
    {camera && <DrainStatusCard camera={camera}/>}
    {camera && (demo
      ? <p className="notice">Simulation mode: cameras are illustrative data, so a drain zone cannot be drawn or saved. Choose the "Server" data source to calibrate the drain zone.</p>
      : <><DrainRoiEditor key={camera.camera_id} camera={camera} onSaved={() => onRefresh?.()}/><DrainPhotoTest key={camera.camera_id} camera={camera} onDone={() => onRefresh?.()}/></>)}
    {camera ? <><div className="image-pair"><ObservationImage key={`original:${camera.camera_id}:${camera.images?.original_url}`} url={camera.images?.original_url} label="Original photo"/><ObservationImage key={`ai:${camera.camera_id}:${camera.images?.analyzed_url}`} url={camera.images?.analyzed_url} label="AI analysis result image"/></div><p className="muted">Photo: {formatTime(camera.images?.captured_at)}. Click an image to open it full size.</p></> : <div className="linked-cameras"><h3>Cameras on this road ({linked.length})</h3>{linked.map(c => <button className="secondary" key={c.camera_id} onClick={() => onCamera(c)}>{c.name ?? c.camera_id} · {c.status === 'online' ? 'Online' : c.status === 'offline' ? 'Offline' : 'Unknown'}</button>)}{!linked.length && <p>No camera is linked via road_id. Road figures are aggregated by the backend.</p>}</div>}
  </section>;
}
