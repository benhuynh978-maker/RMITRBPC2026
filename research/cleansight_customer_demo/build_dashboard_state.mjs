// Biến kết quả mô phỏng thành DỮ LIỆU ĐÚNG DẠNG API của hệ thống (/api/cameras, /api/road-alerts) bằng chính mã của backend ssc-v2
// (chỉ đọc): computeDrainState (trạng thái cống làm mượt), publicCamera, aggregateRoad (gộp theo tuyến, mức cảnh báo, drain_summary)
// và validateDataset (kiểm tra như khi backend ghi file). Không sửa gì trong ssc-v2/ssc-road-alerts/server.
// Dùng:  node build_dashboard_state.mjs < input.json > output.json   (input do make_dashboard_data.py tạo)
import fs from 'node:fs';
import { aggregateRoad, computeDrainState, evaluateSeverity, publicCamera } from '../../ssc-v2/ssc-road-alerts/server/aggregation.js';
import { POLICY } from '../../ssc-v2/ssc-road-alerts/server/config.js';
import { validateDataset } from '../../ssc-v2/ssc-road-alerts/server/validation.js';

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const now = Date.parse(input.as_of);

const cameras = input.cameras.map((c) => {
  const camera = {
    camera_id: c.camera_id, name: c.name, road_id: c.road_id,
    geometry: { type: 'Point', coordinates: c.coordinates },
    drain_roi: { polygon: c.roi_polygon, source: 'manual', calibrated_at: c.calibrated_at },
    observations: [], drain_state: undefined, latest_analysis: undefined,
  };
  let incident = 0;
  c.readings.forEach(([at, blockage, waste], i, all) => {
    const t = Date.parse(at);
    const isLast = i === all.length - 1;
    const wastePct = isLast ? c.latest_waste_pct : waste;
    // như service.enqueue + applyResult: một lần đo đã xử lý, kết quả dùng được, mô phỏng (simulated) và không có ảnh
    const observation = {
      observation_id: `${c.camera_id}-${String(i).padStart(4, '0')}`, camera_id: c.camera_id, road_id: c.road_id,
      captured_at: at, received_at: at, processed_at: at, status: 'processed', usable: true, simulated: true, applied: true,
      result: { usable: true, drain_blockage_pct: blockage, waste_coverage_pct: wastePct, blockage_method: 'roi', roi_version: c.calibrated_at },
    };
    camera.observations.unshift(observation);
    if (camera.observations.length > POLICY.maxObservationsPerCamera) camera.observations.length = POLICY.maxObservationsPerCamera;
    const previous = camera.latest_analysis;
    const severity = evaluateSeverity(wastePct, blockage);
    const sameEpisode = previous && previous.severity !== 'normal' && t - Date.parse(previous.captured_at) <= POLICY.readingMaxAgeMs;
    if (severity !== 'normal' && !sameEpisode) incident += 1;
    camera.latest_analysis = {
      observation_id: observation.observation_id, captured_at: at, simulated: true, severity,
      incident_id: severity === 'normal' ? undefined : sameEpisode ? previous.incident_id : `sim-${c.camera_id}-${incident}`,
      monitoring: { waste_coverage_pct: wastePct, drain_blockage_pct: blockage, observed_at: at, blockage_method: 'roi', low_certainty: false },
      images: { captured_at: at },
    };
    camera.drain_state = computeDrainState(camera, t);
  });
  camera.last_seen_at = c.readings.length ? c.readings[c.readings.length - 1][0] : undefined;
  return camera;
});

const roads = input.roads.map((r) => ({
  road_id: r.road_id, road_name: r.road_name, severity: 'normal', updated_at: input.as_of,
  geometry: { type: 'LineString', coordinates: r.coordinates },
}));

// Kiểm tra như backend khi ghi file (ném lỗi nếu sai dạng)
validateDataset({ cameras }, 'cameras');
validateDataset({ roads }, 'roads');

const outCameras = cameras.map((camera) => {
  const src = input.cameras.find((c) => c.camera_id === camera.camera_id);
  const pub = publicCamera(camera, now);
  return { ...pub, trash_regions: src.trash_regions };
});
const outRoads = roads.map((road) => aggregateRoad(road, cameras, now));
process.stdout.write(JSON.stringify({ roads: outRoads, cameras: outCameras }));
