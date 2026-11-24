// Chạy LUẬT THẬT của backend (ssc-v2/ssc-road-alerts/server/aggregation.js, chỉ đọc) trên các chuỗi đo do test_demo_data.py đưa vào,
// để so với bản Python trong make_demo_data.py. Dùng:  node check_policy.mjs < cases.json   (hoặc: node check_policy.mjs --policy)
import fs from 'node:fs';
import { computeDrainState } from '../../ssc-v2/ssc-road-alerts/server/aggregation.js';
import { POLICY } from '../../ssc-v2/ssc-road-alerts/server/config.js';

if (process.argv.includes('--policy')) {
  process.stdout.write(JSON.stringify(POLICY));
  process.exit(0);
}

const cases = JSON.parse(fs.readFileSync(0, 'utf8'));   // [[ [phút, giá trị %], ... ], ...]
const T0 = Date.UTC(2026, 10, 1, 0, 0, 0);
const out = cases.map((series) => {
  const camera = { camera_id: 'C', road_id: 'R', observations: [], drain_state: undefined };
  return series.map(([minute, value], i) => {
    const t = T0 + minute * 60000;
    camera.observations.unshift({
      status: 'processed', observation_id: `o${i}`, captured_at: new Date(t).toISOString(), road_id: 'R',
      result: { usable: true, drain_blockage_pct: value, blockage_method: 'roi' },
    });
    if (camera.observations.length > POLICY.maxObservationsPerCamera) camera.observations.length = POLICY.maxObservationsPerCamera;
    camera.drain_state = computeDrainState(camera, t);
    const s = camera.drain_state;
    return [s.state, s.smoothed_blockage_pct ?? null, s.reason, s.window_count, Date.parse(s.since)];
  });
});
process.stdout.write(JSON.stringify(out));
