import { useState } from 'react';
import type { Camera } from '../../models/camera';
import type { RoadAlert } from '../../models/roadAlert';
import { Metrics, formatTime } from './Metrics';

function ObservationImage({ url, label }: { url?: string; label: string }) {
  const [failed, setFailed] = useState(false);
  return <figure className="observation-image"><figcaption>{label}</figcaption>
    {url && !failed ? <a href={url} target="_blank" rel="noreferrer"><img src={url} alt={label} loading="lazy" onError={() => setFailed(true)}/></a> : <div className="image-placeholder">{failed ? 'Không tải được ảnh. Kiểm tra URL hoặc quyền truy cập ảnh.' : 'Chưa có ảnh từ camera / máy chủ.'}</div>}
  </figure>;
}
export function ObservationDetail({ road, camera, cameras, onCamera, onClose }: {
  road?: RoadAlert; camera?: Camera; cameras: Camera[]; onCamera: (camera: Camera) => void; onClose: () => void;
}) {
  if (!road && !camera) return null;
  const linked = road ? cameras.filter(c => c.road_id === road.road_id) : [];
  return <section className="observation-detail" aria-label="Chi tiết quan sát">
    <div className="section-heading"><div><span className="eyebrow">{camera ? 'NÚT CAMERA' : 'TỔNG HỢP TUYẾN ĐƯỜNG'}</span><h2>{camera?.name ?? camera?.camera_id ?? road?.road_name ?? road?.road_id}</h2></div><button className="secondary" onClick={onClose}>Đóng chi tiết</button></div>
    <p>{camera ? `${camera.camera_id} · ${camera.status === 'online' ? 'Trực tuyến' : camera.status === 'offline' ? 'Ngoại tuyến — số liệu có thể đã cũ' : 'Chưa rõ trạng thái'} · Tuyến ${camera.road_id ?? 'chưa liên kết'}` : road?.description ?? 'Chưa có mô tả từ máy chủ.'}</p>
    {camera?.analysis_source==='simulation'&&<p className="notice">Chỉ số từ API mô phỏng, không phải kết quả chạy mô hình AI.</p>}
    {camera?.analysis_status==='stale'&&<p className="notice">Phân tích đã quá thời hạn. Không dùng số liệu này để kết luận hiện trạng.</p>}
    {!camera&&road?.data_quality==='unknown'&&<p className="notice">Chưa có phân tích camera còn hiệu lực. Tuyến chưa đủ dữ liệu để kết luận an toàn.</p>}
    <Metrics data={camera?.monitoring ?? (!camera ? road?.monitoring : undefined)}/>
    {camera ? <><div className="image-pair"><ObservationImage key={`original:${camera.camera_id}:${camera.images?.original_url}`} url={camera.images?.original_url} label="Ảnh chụp gốc"/><ObservationImage key={`ai:${camera.camera_id}:${camera.images?.analyzed_url}`} url={camera.images?.analyzed_url} label="Ảnh kết quả phân tích AI"/></div><p className="muted">Ảnh: {formatTime(camera.images?.captured_at)}. Nhấn ảnh để mở kích thước đầy đủ.</p></> : <div className="linked-cameras"><h3>Camera trên tuyến ({linked.length})</h3>{linked.map(c => <button className="secondary" key={c.camera_id} onClick={() => onCamera(c)}>{c.name ?? c.camera_id} · {c.status === 'online' ? 'Trực tuyến' : c.status === 'offline' ? 'Ngoại tuyến' : 'Chưa rõ'}</button>)}{!linked.length && <p>Chưa có camera liên kết qua road_id. Chỉ số tuyến do backend tổng hợp.</p>}</div>}
  </section>;
}
