import { Polygon, Popup } from 'react-leaflet';
import { toLeafletPositions } from '../../services/normalizeAlerts';
import type { Camera } from '../../models/camera';

/**
 * Vùng rác (m²) của mọi camera có trường `trash_regions`, vẽ luôn (không có nút bật/tắt).
 * Ở mức thu nhỏ các đa giác chỉ lớn cỡ vài điểm ảnh; phóng to vào một camera (tối đa mức 21) mới thấy rõ.
 */
export function TrashRegionLayer({ cameras }: { cameras: Camera[] }) {
  return <>{cameras.flatMap(camera => (camera.trash_regions ?? []).map((region, index) =>
    <Polygon key={`${camera.camera_id}:${index}`} positions={toLeafletPositions(region.ring)} pathOptions={{
      color: region.kind === 'drain' ? '#7f1d1d' : '#b91c1c', weight: region.kind === 'drain' ? 2 : 1.5, fillColor: '#ef4444', fillOpacity: 0.5,
    }}>
      <Popup><strong>Litter region · {region.area_m2.toLocaleString('en-US', { maximumFractionDigits: 2 })} m²</strong>
        <p>{camera.name ?? camera.camera_id}{region.kind === 'drain' ? ' · on the drain zone' : ''}</p></Popup>
    </Polygon>))}</>;
}
