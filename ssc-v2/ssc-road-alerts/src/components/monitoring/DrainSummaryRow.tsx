import { DRAIN_COLOR, DRAIN_LABEL, DRAIN_ORDER } from '../../config/drain';
import type { DrainStateName, DrainSummary } from '../../models/drain';

const total = (s: DrainSummary) => s.clear + s.watch + s.clean + s.unknown;
const parts = (s: DrainSummary) => DRAIN_ORDER.filter(k => s[k] > 0).map(k => ({ key: k, count: s[k], label: DRAIN_LABEL[k] }));

/** Summary string, e.g. "Drains: 1 needs cleaning · 2 watch". Empty when there are no cameras. */
export function drainSummaryText(summary?: DrainSummary): string {
  if (!summary || total(summary) === 0) return '';
  return `Drains: ${parts(summary).map(p => `${p.count} ${p.label.toLowerCase()}`).join(' · ')}`;
}

function Worst({ state, cameraId }: { state: DrainStateName; cameraId: string | null }) {
  if (state === 'unknown') return null;
  return <p className="muted">Worst: <strong>{DRAIN_LABEL[state]}</strong>{cameraId ? ` (camera ${cameraId})` : ''}</p>;
}

export function DrainSummaryRow({ summary, compact = false }: { summary?: DrainSummary; compact?: boolean }) {
  const text = drainSummaryText(summary);
  if (!summary || !text) return null;
  if (compact) return <small className="drain-summary-compact" aria-label={text}>{text}</small>;
  return <div className="drain-summary" aria-label="Drain status summary by camera">
    <ul className="drain-summary-list">
      {parts(summary).map(p => <li key={p.key} style={{ color: DRAIN_COLOR[p.key].color, background: DRAIN_COLOR[p.key].background, borderColor: DRAIN_COLOR[p.key].color }}>
        <strong>{p.count}</strong> {p.label}
      </li>)}
    </ul>
    <Worst state={summary.worst_state} cameraId={summary.worst_camera_id}/>
  </div>;
}
