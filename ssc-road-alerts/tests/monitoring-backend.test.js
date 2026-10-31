import { it, expect } from 'vitest';
import { validateDataset } from '../server/validation.js';

it('accepts extended example schemas and rejects malformed monitoring at the server boundary', async () => {
  // Test fixtures are independent from editable user examples/data files.
  const roads = {roads:[{road_id:'FIXTURE-R1',severity:'high',geometry:{type:'LineString',coordinates:[[106,10],[107,11]]},monitoring:{waste_coverage_pct:86}}]};
  const cameras = {cameras:[{camera_id:'FIXTURE-C1',road_id:'FIXTURE-R1',geometry:{type:'Point',coordinates:[106,10]},images:{analyzed_url:'https://example.com/ai.jpg'}}]};
  expect(validateDataset(roads, 'roads').roads[0].monitoring.waste_coverage_pct).toBe(86);
  expect(validateDataset(cameras, 'cameras').cameras[0].images.analyzed_url).toContain('https://');
  const r=roads.roads[0]; const c=cameras.cameras[0];
  expect(()=>validateDataset({roads:[{...r,monitoring:{waste_coverage_pct:-1}}]},'roads')).toThrow();
  expect(()=>validateDataset({roads:[{...r,monitoring:{rain_expected:'true'}}]},'roads')).toThrow();
  expect(()=>validateDataset({cameras:[{...c,images:{original_url:'javascript:alert(1)'}}]},'cameras')).toThrow();
  expect(()=>validateDataset({cameras:[{...c,road_id:2}]},'cameras')).toThrow();
});
