import { Circle, Pane, Popup } from 'react-leaflet';
import type { CameraForecast } from '../../models/weather';
import { formatTime } from '../monitoring/Metrics';
export function RainLayer({forecasts}:{forecasts:CameraForecast[]}) {
  return <Pane name="rain-forecast" style={{zIndex:350}}>{forecasts.filter(c=>c.will_rain===true&&c.status!=='unavailable').map(c=><Circle key={c.camera_id} center={[c.coordinates[1],c.coordinates[0]]} radius={c.display_radius_m} pathOptions={{color:c.status==='stale'?'#64748b':'#2563eb',fillColor:'#3b82f6',fillOpacity:0.13,weight:2,dashArray:c.status==='fresh'?undefined:'6 5'}}><Popup><strong>{c.camera_name}</strong><p>Dự báo mưa trong 12 giờ tới{c.status==='stale'?' · DỮ LIỆU CŨ':c.status==='partial'?' · Thiếu một phần dữ liệu':''}</p><p>Từ khoảng: {formatTime(c.first_rain_at??undefined)}</p><p>Xác suất giáng thủy cao nhất theo giờ: {c.max_probability??'Chưa có'}%</p><p>Mưa + mưa rào lớn nhất: {c.max_rain_mm_per_hour??'Chưa có'} mm/giờ</p><small>Vòng tròn {c.display_radius_m} m chỉ đánh dấu quanh camera, không phải ranh giới vùng mưa.</small></Popup></Circle>)}</Pane>;
}
