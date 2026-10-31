import { CircleCheck, CircleHelp, Eye, TriangleAlert, type LucideIcon } from 'lucide-react';
import { DRAIN_COLOR, DRAIN_DESCRIPTION, DRAIN_LABEL, DRAIN_POLICY, drainAriaLabel, drainReasonText, drainThresholdsText, formatPct } from '../../config/drain';
import type { Camera } from '../../models/camera';
import type { DrainRoi, DrainState, DrainStateName } from '../../models/drain';
import { formatTime } from './Metrics';

/** Each state has a different shape so it is not distinguished by colour alone. */
const ICON: Record<DrainStateName, LucideIcon> = { clear: CircleCheck, watch: Eye, clean: TriangleAlert, unknown: CircleHelp };
const FALLBACK: DrainState = { state: 'unknown', window_count: 0, reason: 'no_data' };

export function DrainChip({ state }: { state: DrainStateName }) {
  const Icon = ICON[state];
  const { color, background } = DRAIN_COLOR[state];
  return <span className="drain-chip" role="img" aria-label={drainAriaLabel(state)} title={DRAIN_DESCRIPTION[state]} style={{ color, background, borderColor: color }}>
    <Icon size={16} aria-hidden="true" focusable="false"/><span>{DRAIN_LABEL[state]}</span>
  </span>;
}

function RoiLine({ roi, calibrated }: { roi?: DrainRoi; calibrated: boolean }) {
  if (roi) {
    const source = roi.source === 'manual' ? 'drawn by hand' : 'suggested by AI';
    return <p className="drain-roi">Drain zone calibrated ({source}), version {formatTime(roi.calibrated_at)}</p>;
  }
  if (calibrated) return <p className="drain-roi">Drain zone calibrated</p>;
  return <p className="drain-roi drain-roi-missing">Drain zone not calibrated — using the old formula, less reliable when the drain is fully covered</p>;
}

function Flags({ flags }: { flags?: DrainState['flags'] }) {
  if (!flags?.no_trash_in_roi && !flags?.low_certainty) return null;
  return <ul className="drain-flags">
    {flags.no_trash_in_roi && <li>No litter in the drain zone in the latest reading</li>}
    {flags.low_certainty && <li>Low model certainty</li>}
  </ul>;
}

function Times({ drain }: { drain: DrainState }) {
  return <ul className="drain-times">
    {drain.since && <li>In this state since: {formatTime(drain.since)}</li>}
    {drain.evidence_captured_at && <li>Latest reading: {formatTime(drain.evidence_captured_at)}</li>}
    {drain.updated_at && <li>Status updated: {formatTime(drain.updated_at)}</li>}
  </ul>;
}

function Method() {
  const p = DRAIN_POLICY;
  return <details className="drain-method">
    <summary>How it is calculated</summary>
    <ul>
      <li>Takes the median of up to {p.windowSize} latest readings with the same drain-zone version; at least {p.minReadings} valid readings are needed for a conclusion.</li>
      <li>{drainThresholdsText()} This hold (hysteresis) avoids flickering around a threshold.</li>
      <li>The figure measures litter inside the outlined zone and does not check whether a real drain is there. It is only meaningful when the camera is fixed and the zone matches the drain inlet; if the camera shifts, the result is wrong and the system cannot tell.</li>
      <li>Readings older than {p.maxAgeMinutes} minutes compared with the latest one, or from a disconnected camera, are ignored; the status falls back to Unknown.</li>
    </ul>
    <p className="muted">Reference indicator only: smoothing reduces flicker but has not been shown to make the measurement more accurate; the AI model still misses some litter.</p>
  </details>;
}

export function DrainStatusCard({ camera }: { camera: Camera }) {
  const drain = camera.drain_state ?? FALLBACK;
  const known = drain.state !== 'unknown';
  const reason = known ? '' : drainReasonText(drain.reason ? drain : FALLBACK);
  return <section className="drain-card" aria-label="Drain status (smoothed)">
    <h3>Drain status (smoothed)</h3>
    <div className="drain-head"><DrainChip state={drain.state}/><span className="drain-desc">{DRAIN_DESCRIPTION[drain.state]}</span></div>
    {known && drain.smoothed_blockage_pct !== undefined && <p className="drain-value">Smoothed drain inlet coverage: <strong>{formatPct(drain.smoothed_blockage_pct)}%</strong></p>}
    {reason && <p className="drain-reason" role="status">{reason}</p>}
    {drain.reason !== 'stale' && <p className="muted">Based on {drain.window_count}/{DRAIN_POLICY.windowSize} latest readings (needs ≥ {DRAIN_POLICY.minReadings})</p>}
    <Times drain={drain}/>
    <RoiLine roi={camera.drain_roi} calibrated={drain.roi_calibrated === true}/>
    <Flags flags={drain.flags}/>
    <Method/>
  </section>;
}
