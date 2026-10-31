import { Circle, Pane, Popup } from 'react-leaflet';
import type { CameraForecast } from '../../models/weather';
import { formatTime } from '../monitoring/Metrics';
export function RainLayer({forecasts}:{forecasts:CameraForecast[]}) {
  return <Pane name="rain-forecast" style={{zIndex:350}}>{forecasts.filter(c=>c.will_rain===true&&c.status!=='unavailable').map(c=><Circle key={c.camera_id} center={[c.coordinates[1],c.coordinates[0]]} radius={c.display_radius_m} pathOptions={{color:c.status==='stale'?'#64748b':'#2563eb',fillColor:'#3b82f6',fillOpacity:0.13,weight:2,dashArray:c.status==='fresh'?undefined:'6 5'}}><Popup><strong>{c.camera_name}</strong><p>Rain forecast (next 12 hours){c.status==='stale'?' · STALE DATA':c.status==='partial'?' · Partial data missing':''}</p><p>From about: {formatTime(c.first_rain_at??undefined)}</p><p>Highest hourly precipitation probability: {c.max_probability??'n/a'}%</p><p>Max rain + showers: {c.max_rain_mm_per_hour??'n/a'} mm/h</p><small>The {c.display_radius_m} m circle only marks the area around the camera; it is not the boundary of the rain area.</small></Popup></Circle>)}</Pane>;
}
