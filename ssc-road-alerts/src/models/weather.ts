export interface ForecastHour {
  interval_start:string; interval_end:string; probability:number|null;
  rain_mm_per_hour:number|null; likely_rain:boolean;
}
export interface CameraForecast {
  camera_id:string;camera_name:string;road_id?:string;coordinates:[number,number];
  status:'fresh'|'partial'|'stale'|'unavailable'; fetched_at:string|null;error:string|null;
  display_radius_m:number;window_start:string;window_end:string;hourly:ForecastHour[];complete:boolean;
  will_rain:boolean|null;first_rain_at:string|null;max_probability:number|null;max_rain_mm_per_hour:number|null;
}
export interface WeatherResponse {provider:string;horizon_hours:number;generated_at:string;cameras:CameraForecast[]}
