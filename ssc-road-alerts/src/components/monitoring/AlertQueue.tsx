import { useEffect, useState } from 'react';
import { SEVERITY } from '../../config/severity';
import type { Camera } from '../../models/camera';
import { handoffText, type HandlingRecord, type MonitoringAlert } from '../../services/monitoringService';

function HandlingForm({ alert, cameras, record, update, demo, stale }: {
  alert: MonitoringAlert; cameras: Camera[]; record?: HandlingRecord;
  update: (key: string, patch: HandlingRecord) => void; demo: boolean; stale: boolean;
}) {
  const [team, setTeam] = useState(record?.team ?? '');
  const [note, setNote] = useState(record?.note ?? '');
  const [feedback, setFeedback] = useState('');
  useEffect(() => { setTeam(record?.team ?? ''); setNote(record?.note ?? ''); }, [record?.team, record?.note]);
  function download() {
    if (!team.trim()) return;
    const text = handoffText(alert, cameras, team, note, demo);
    const url = URL.createObjectURL(new Blob(['\uFEFF', text], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = `SSC-phieu-thu-gom-${alert.road.road_id.replace(/[^a-zA-Z0-9_-]/g, '_')}.txt`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    update(alert.key, { prepared_at:new Date().toISOString(), team:team.trim(), note:note.trim() });
    setFeedback('Đã tạo phiếu tải xuống. Bạn cần gửi phiếu cho đơn vị tiếp nhận.');
  }
  return <div className="handling-form">
    <p className="muted">Trạng thái lưu tại trình duyệt này. Xuất phiếu không tự gửi thông báo đến đơn vị vệ sinh.</p>
    <button className="secondary" disabled={!!record?.acknowledged_at || stale} onClick={() => update(alert.key, {acknowledged_at:new Date().toISOString()})}>{record?.acknowledged_at ? 'Đã xác nhận tại máy' : 'Xác nhận đã xem'}</button>
    <label>Đơn vị tiếp nhận<input value={team} onChange={e => setTeam(e.target.value)} maxLength={160} placeholder="Nhập tên đội vệ sinh / đơn vị địa phương"/></label>
    <label>Ghi chú xử lý<textarea value={note} onChange={e => setNote(e.target.value)} maxLength={2000} rows={3} placeholder="Vị trí cửa cống, yêu cầu kiểm tra, thông tin liên hệ…"/></label>
    <button className="refresh" disabled={!team.trim() || !record?.acknowledged_at || stale} onClick={download}>Xuất phiếu chuyển giao</button>
    <p className="muted">{!record?.acknowledged_at ? 'Xác nhận đã xem để lập phiếu. ' : ''}{record?.prepared_at ? `Đã lập phiếu lúc ${new Date(record.prepared_at).toLocaleString('vi-VN')}. Chưa có xác nhận tiếp nhận.` : ''}</p>
    <p role="status">{feedback}</p>
  </div>;
}
export function AlertQueue({ alerts, cameras, records, update, onSelect, demo, stale }: {
  alerts: MonitoringAlert[]; cameras: Camera[]; records: Record<string, HandlingRecord>;
  update: (key: string, patch: HandlingRecord) => void; onSelect: (id: string) => void; demo: boolean; stale: boolean;
}) {
  return <section className="alert-queue"><div className="section-heading"><div><span className="eyebrow">XỬ LÝ TRƯỚC KHI MƯA</span><h2>Cảnh báo ưu tiên <span className="count">{alerts.length}</span></h2></div></div>
    {stale && <p className="notice">Dữ liệu tuyến chưa cập nhật được. Các thao tác xác nhận / xuất phiếu tạm khóa đến khi kết nối thành công.</p>}
    {!alerts.length && <p className="empty">Chưa có cảnh báo từ dữ liệu đang hiển thị. Không đồng nghĩa mọi tuyến đều an toàn.</p>}
    <div className="queue-grid">{alerts.map(alert => <article key={alert.key} className="queue-card" style={{borderTopColor:SEVERITY[alert.severity].color}}>
      <div className="section-heading"><span className="badge" style={{color:SEVERITY[alert.severity].color,background:SEVERITY[alert.severity].background}}>{SEVERITY[alert.severity].label}</span><small>{records[alert.key]?.acknowledged_at ? 'Đã xem tại máy' : 'Chưa xác nhận'}</small></div>
      <button className="text-button" onClick={() => onSelect(alert.road.road_id)}>{alert.road.road_name ?? alert.road.road_id} ↗</button>
      <ul>{alert.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
      <details><summary>Xác nhận & lập phiếu xử lý</summary><HandlingForm alert={alert} cameras={cameras} record={records[alert.key]} update={update} demo={demo} stale={stale}/></details>
    </article>)}</div>
  </section>;
}
