import type { Camera } from '../models/camera';
import type { RoadAlert } from '../models/roadAlert';

/** Dữ liệu minh họa cố định cho chế độ "Mô phỏng minh họa". Không phải hiện trường thật. */
export const demoRoads: RoadAlert[] = [
  { road_id:'DEMO-R1', road_name:'Khu vực Nguyễn Hữu Cảnh (mẫu)', alert_id:'DEMO-A1', severity:'critical', description:'Ưu tiên kiểm tra và thu gom rác quanh cửa cống trước mưa.', geometry:{type:'LineString',coordinates:[[106.7112,10.7874],[106.7132,10.7886],[106.7162,10.7901]]}, monitoring:{waste_coverage_pct:86,waste_level:'critical',drain_blockage_pct:82,waste_camera_count:2,waste_max_pct:91,flood_camera_count:2,flood_max_pct:88,rain_expected:true,observed_at:'2026-09-09T10:00:00Z'} },
  { road_id:'DEMO-R2', road_name:'Khu vực Điện Biên Phủ (mẫu)', alert_id:'DEMO-A2', severity:'medium', description:'Rác bắt đầu tích tụ, cần kiểm tra hiện trường.', geometry:{type:'LineString',coordinates:[[106.7021,10.7971],[106.7043,10.7984],[106.7069,10.7999]]}, monitoring:{waste_coverage_pct:6.5,waste_level:'medium',drain_blockage_pct:48,waste_camera_count:1,waste_max_pct:6.5,flood_camera_count:1,flood_max_pct:48,rain_expected:false,observed_at:'2026-09-09T09:58:00Z'} },
  { road_id:'DEMO-R3', road_name:'Khu vực Nguyễn Huệ (mẫu)', severity:'normal', description:'Chưa ghi nhận điều kiện vượt ngưỡng trong dữ liệu mẫu.', geometry:{type:'LineString',coordinates:[[106.7006,10.7766],[106.7017,10.7751],[106.7031,10.7732]]}, monitoring:{waste_coverage_pct:0.6,waste_level:'normal',drain_blockage_pct:3,rain_expected:false,observed_at:'2026-09-09T09:55:00Z'} },
];

export const demoCameras: Camera[] = [
  { camera_id:'DEMO-C1',name:'Cửa cống 01',road_id:'DEMO-R1',status:'online',geometry:{type:'Point',coordinates:[106.7132,10.7886]},monitoring:{waste_coverage_pct:91,waste_level:'critical',drain_blockage_pct:88,observed_at:'2026-09-09T10:00:00Z'} },
  { camera_id:'DEMO-C2',name:'Cửa cống 02',road_id:'DEMO-R1',status:'offline',geometry:{type:'Point',coordinates:[106.7162,10.7901]},monitoring:{waste_coverage_pct:81,waste_level:'critical',drain_blockage_pct:76,observed_at:'2026-09-09T09:00:00Z'} },
  { camera_id:'DEMO-C3',name:'Cửa cống 03',road_id:'DEMO-R2',status:'online',geometry:{type:'Point',coordinates:[106.7043,10.7984]},monitoring:{waste_coverage_pct:6.5,waste_level:'medium',drain_blockage_pct:48,observed_at:'2026-09-09T09:58:00Z'} },
];
