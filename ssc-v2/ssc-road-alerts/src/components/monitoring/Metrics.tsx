import type { Monitoring } from '../../models/monitoring';
import { SEVERITY } from '../../config/severity';

export const formatTime = (value?: string) => value ? new Date(value).toLocaleString('en-GB') : 'No observation time';

/** Note: an average is easy to read but hides local hot spots, so state how many cameras it covers and the maximum. */
function Average({ count, max, suffix = '' }: { count?: number; max?: number; suffix?: string }) {
  if (!count) return null;
  return <small className="metric-note">Average of {count} {count === 1 ? 'camera' : 'cameras'}{suffix}{max !== undefined ? ` · max ${max}%` : ''}</small>;
}

export function Metrics({ data }: { data?: Monitoring }) {
  return <><dl className="metrics">
    <div>
      <dt>Litter level</dt>
      <dd>{data?.waste_level ? SEVERITY[data.waste_level].label : 'n/a'}{data?.waste_coverage_pct !== undefined ? ` · ${data.waste_coverage_pct}%` : ''}</dd>
      <Average count={data?.waste_camera_count} max={data?.waste_max_pct} />
    </div>
    <div>
      <dt>Drain inlet coverage</dt>
      <dd>{data?.drain_blockage_pct === undefined ? 'n/a' : `${data.drain_blockage_pct}%`}</dd>
      <Average count={data?.flood_camera_count} max={data?.flood_max_pct} suffix=" seeing the drain"/>
    </div>
  </dl>
  {data?.rain_expected !== undefined && <p className="muted">Rain signal: {data.rain_expected ? 'Rain forecast' : 'No rain forecast'}</p>}
  <p className="muted">{formatTime(data?.observed_at)} · Figures come from the observation, not from the time the page was loaded.</p></>;
}
