import type { Monitoring } from '../../models/monitoring';
import { SEVERITY } from '../../config/severity';

export const formatTime = (value?: string) => value ? new Date(value).toLocaleString('vi-VN') : 'Chưa có thời gian quan sát';

/** Chú thích phụ: trung bình dễ đọc nhưng giấu mất điểm nặng cục bộ, nên nói rõ gộp từ mấy camera và mức cao nhất. */
function Average({ count, max, unit }: { count?: number; max?: number; unit: string }) {
  if (!count) return null;
  return <small className="metric-note">Trung bình {count} {unit}{max !== undefined ? ` · cao nhất ${max}%` : ''}</small>;
}

export function Metrics({ data }: { data?: Monitoring }) {
  return <><dl className="metrics">
    <div>
      <dt>Mức độ rác</dt>
      <dd>{data?.waste_level ? SEVERITY[data.waste_level].label : 'Chưa có'}{data?.waste_coverage_pct !== undefined ? ` · ${data.waste_coverage_pct}%` : ''}</dd>
      <Average count={data?.waste_camera_count} max={data?.waste_max_pct} unit="camera"/>
    </div>
    <div>
      <dt>Tỉ lệ ngập</dt>
      <dd>{data?.drain_blockage_pct === undefined ? 'Chưa có' : `${data.drain_blockage_pct}%`}</dd>
      <Average count={data?.flood_camera_count} max={data?.flood_max_pct} unit="camera thấy cống"/>
    </div>
  </dl>
  {data?.rain_expected !== undefined && <p className="muted">Tín hiệu mưa: {data.rain_expected ? 'Dự báo có mưa' : 'Chưa báo mưa'}</p>}
  <p className="muted">{formatTime(data?.observed_at)} · Chỉ số từ lần quan sát, không phải thời điểm tải trang.</p></>;
}
