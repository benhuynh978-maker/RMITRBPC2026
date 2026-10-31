import { useState } from 'react';
import { Crosshair } from 'lucide-react';
import type { DraftPoint, DrawMode } from '../map/CoordinatePicker';

export function CoordinateTool({ mode, draft, onMode, onDraft }: {
  mode:DrawMode; draft:DraftPoint[]; onMode:(mode:DrawMode)=>void; onDraft:(points:DraftPoint[])=>void;
}) {
  const [id,setId]=useState('CAM-001');
  const [copied,setCopied]=useState('');
  const valid=id.trim()&&(mode==='camera'?draft.length===1:mode==='road'&&draft.length>=2&&draft.some(p=>p[0]!==draft[0][0]||p[1]!==draft[0][1]));
  const payload=valid?(mode==='camera'?{cameras:[{camera_id:id.trim(),name:'Test camera',status:'unknown',geometry:{type:'Point',coordinates:draft[0]}}]}:{roads:[{road_id:id.trim(),road_name:'Test road segment',severity:'medium',geometry:{type:'LineString',coordinates:draft}}]}):null;
  function change(mode:DrawMode){onMode(mode);onDraft([]);setCopied('');setId(mode==='camera'?'CAM-001':'ROAD-001');}
  return <details className="coordinate-tool" onToggle={e=>{if(!e.currentTarget.open)change('none');}}><summary><Crosshair size={17}/>Pick coordinates for testing</summary><div className="coordinate-content"><p>Zoom in, then click the map. The draft is not saved to the backend and does not snap to roads.</p><div className="draft-controls"><label>Mode<select value={mode} onChange={e=>change(e.target.value as DrawMode)}><option value="none">Coordinate picking off</option><option value="camera">Place camera</option><option value="road">Draw road segment</option></select></label><label>Identifier<input value={id} onChange={e=>setId(e.target.value)}/></label><button disabled={!draft.length} onClick={()=>onDraft(draft.slice(0,-1))}>Remove last point</button><button disabled={!draft.length} onClick={()=>onDraft([])}>Clear draft</button></div><p>{draft.length} points selected. {mode==='road'?'At least 2 distinct points are needed; add a point at every bend.':''}</p>
    {payload&&<><label className="json-label">Generated JSON<textarea readOnly value={JSON.stringify(payload,null,2)} rows={10}/></label><button className="refresh" onClick={async()=>{try{await navigator.clipboard.writeText(JSON.stringify(payload,null,2));setCopied('JSON copied.');}catch{setCopied('Select the JSON in the box and copy it manually.');}}}>Copy JSON</button><p role="status">{copied}</p><p>Add the element to the array in <code>server/data/{mode==='camera'?'cameras':'road-alerts'}.json</code>, keep the existing elements, then refresh the data. Set <code>road_id</code> on a camera to link it to a road.</p></>}
    <p className="coordinate-note">WGS84: [longitude, latitude]. Clicked coordinates are approximate; real data needs GPS/survey or GIS geometry.</p></div></details>;
}
