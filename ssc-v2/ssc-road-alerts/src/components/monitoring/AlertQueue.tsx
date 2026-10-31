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
    const link = document.createElement('a'); link.href = url; link.download = `CleanSight-pickup-ticket-${alert.road.road_id.replace(/[^a-zA-Z0-9_-]/g, '_')}.txt`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    update(alert.key, { prepared_at:new Date().toISOString(), team:team.trim(), note:note.trim() });
    setFeedback('Ticket downloaded. You still need to send it to the receiving unit.');
  }
  return <div className="handling-form">
    <p className="muted">Status is stored in this browser only. Exporting a ticket does not notify the sanitation unit.</p>
    <button className="secondary" disabled={!!record?.acknowledged_at || stale} onClick={() => update(alert.key, {acknowledged_at:new Date().toISOString()})}>{record?.acknowledged_at ? 'Acknowledged' : 'Acknowledge'}</button>
    <label>Receiving unit<input value={team} onChange={e => setTeam(e.target.value)} maxLength={160} placeholder="Sanitation team / local unit name"/></label>
    <label>Handling notes<textarea value={note} onChange={e => setNote(e.target.value)} maxLength={2000} rows={3} placeholder="Drain location, inspection request, contact details…"/></label>
    <button className="refresh" disabled={!team.trim() || !record?.acknowledged_at || stale} onClick={download}>Export handoff ticket</button>
    <p className="muted">{!record?.acknowledged_at ? 'Acknowledge first to create a ticket. ' : ''}{record?.prepared_at ? `Ticket created at ${new Date(record.prepared_at).toLocaleString('en-GB')}. Receipt not confirmed.` : ''}</p>
    <p role="status">{feedback}</p>
  </div>;
}
export function AlertQueue({ alerts, cameras, records, update, onSelect, demo, stale }: {
  alerts: MonitoringAlert[]; cameras: Camera[]; records: Record<string, HandlingRecord>;
  update: (key: string, patch: HandlingRecord) => void; onSelect: (id: string) => void; demo: boolean; stale: boolean;
}) {
  return <section className="alert-queue"><div className="section-heading"><div><span className="eyebrow">ACT BEFORE RAIN</span><h2>Priority alerts <span className="count">{alerts.length}</span></h2></div></div>
    {stale && <p className="notice">Road data could not be updated. Acknowledge / export is locked until the connection succeeds.</p>}
    {!alerts.length && <p className="empty">No alerts in the data shown. This does not mean every road is safe.</p>}
    <div className="queue-grid">{alerts.map(alert => <article key={alert.key} className="queue-card" style={{borderTopColor:SEVERITY[alert.severity].color}}>
      <div className="section-heading"><span className="badge" style={{color:SEVERITY[alert.severity].color,background:SEVERITY[alert.severity].background}}>{SEVERITY[alert.severity].label}</span><small>{records[alert.key]?.acknowledged_at ? 'Seen on this device' : 'Not acknowledged'}</small></div>
      <button className="text-button" onClick={() => onSelect(alert.road.road_id)}>{alert.road.road_name ?? alert.road.road_id} ↗</button>
      <ul>{alert.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
      <details><summary>Acknowledge & create handling ticket</summary><HandlingForm alert={alert} cameras={cameras} record={records[alert.key]} update={update} demo={demo} stale={stale}/></details>
    </article>)}</div>
  </section>;
}
