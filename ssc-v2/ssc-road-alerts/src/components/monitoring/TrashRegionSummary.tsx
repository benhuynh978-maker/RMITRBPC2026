import type { Camera } from '../../models/camera';
import { summarizeTrashRegions } from '../../services/normalizeTrash';

/** Vùng rác AI đã khoanh (đã vẽ trên bản đồ) của camera: số vùng, tổng diện tích và từng vùng. Ẩn khi camera không có trường này. */
export function TrashRegionSummary({ camera }: { camera: Camera }) {
  const regions = camera.trash_regions;
  if (!regions) return null;
  const { count, total_m2 } = summarizeTrashRegions(regions);
  const fmt = (v: number) => v.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return <section className="trash-regions" aria-label="Litter outlined on the map">
    <h3>Litter outlined on the map</h3>
    {count === 0
      ? <p className="muted">No litter outlined in the latest analysis.</p>
      : <><p><strong>{count}</strong> region{count === 1 ? '' : 's'}, <strong>{fmt(total_m2)} m²</strong> in total. Drawn on the map in red; zoom in on the camera to see them.</p>
        <ol className="trash-region-list">
          {regions.slice(0, 8).map((r, i) => <li key={i}>Region {i + 1}: {fmt(r.area_m2)} m²{r.kind === 'drain' ? ' (on the drain zone)' : ''}</li>)}
          {count > 8 && <li className="muted">+{count - 8} more</li>}
        </ol></>}
  </section>;
}
