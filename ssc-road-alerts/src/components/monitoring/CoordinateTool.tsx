import { useState } from 'react';
import { Crosshair } from 'lucide-react';
import type { DraftPoint, DrawMode } from '../map/CoordinatePicker';

export function CoordinateTool({ mode, draft, onMode, onDraft }: {
  mode:DrawMode; draft:DraftPoint[]; onMode:(mode:DrawMode)=>void; onDraft:(points:DraftPoint[])=>void;
}) {
  const [id,setId]=useState('CAM-001');
  const [copied,setCopied]=useState('');
  const valid=id.trim()&&(mode==='camera'?draft.length===1:mode==='road'&&draft.length>=2&&draft.some(p=>p[0]!==draft[0][0]||p[1]!==draft[0][1]));
  const payload=valid?(mode==='camera'?{cameras:[{camera_id:id.trim(),name:'Camera thử nghiệm',status:'unknown',geometry:{type:'Point',coordinates:draft[0]}}]}:{roads:[{road_id:id.trim(),road_name:'Đoạn đường thử nghiệm',severity:'medium',geometry:{type:'LineString',coordinates:draft}}]}):null;
  function change(mode:DrawMode){onMode(mode);onDraft([]);setCopied('');setId(mode==='camera'?'CAM-001':'ROAD-001');}
  return <details className="coordinate-tool" onToggle={e=>{if(!e.currentTarget.open)change('none');}}><summary><Crosshair size={17}/>Lấy tọa độ để thử nghiệm</summary><div className="coordinate-content"><p>Phóng to rồi bấm trên bản đồ. Bản nháp không tự lưu vào backend và không tự bám đường.</p><div className="draft-controls"><label>Chế độ<select value={mode} onChange={e=>change(e.target.value as DrawMode)}><option value="none">Tắt lấy tọa độ</option><option value="camera">Đặt vị trí camera</option><option value="road">Vẽ đoạn đường</option></select></label><label>Mã định danh<input value={id} onChange={e=>setId(e.target.value)}/></label><button disabled={!draft.length} onClick={()=>onDraft(draft.slice(0,-1))}>Bỏ điểm cuối</button><button disabled={!draft.length} onClick={()=>onDraft([])}>Xóa bản nháp</button></div><p>Đã chọn {draft.length} điểm. {mode==='road'?'Cần ít nhất 2 điểm khác nhau; thêm điểm tại mỗi khúc cua.':''}</p>
    {payload&&<><label className="json-label">JSON đã tạo<textarea readOnly value={JSON.stringify(payload,null,2)} rows={10}/></label><button className="refresh" onClick={async()=>{try{await navigator.clipboard.writeText(JSON.stringify(payload,null,2));setCopied('Đã sao chép JSON hiện tại.');}catch{setCopied('Hãy chọn JSON trong ô và sao chép thủ công.');}}}>Sao chép JSON</button><p role="status">{copied}</p><p>Thêm phần tử vào mảng trong <code>server/data/{mode==='camera'?'cameras':'road-alerts'}.json</code>, giữ các phần tử đã có, sau đó cập nhật dữ liệu. Gắn <code>road_id</code> cho camera để liên kết tuyến.</p></>}
    <p className="coordinate-note">WGS84: [kinh độ, vĩ độ]. Tọa độ bấm chỉ gần đúng; cần GPS/khảo sát hoặc geometry GIS cho dữ liệu thực.</p></div></details>;
}
