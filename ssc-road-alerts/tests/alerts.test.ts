import { describe,it,expect,vi,afterEach } from 'vitest';
import { normalizeAlerts,toLeafletPositions } from '../src/services/normalizeAlerts';
const road={road_id:'R1',severity:3,geometry:{type:'LineString',coordinates:[[106.7,10.77],[106.71,10.78]]}};
afterEach(()=>vi.unstubAllGlobals());
describe('API contract',()=>{
 it('normalizes arrays, envelopes and FeatureCollections',()=>{
  expect(normalizeAlerts([road])[0].severity).toBe('high');
  expect(normalizeAlerts({roads:[road]})).toEqual(normalizeAlerts({data:[road]}));
  expect(normalizeAlerts({type:'FeatureCollection',features:[{type:'Feature',geometry:road.geometry,properties:{road_id:'R1',severity:3}}]})).toEqual(normalizeAlerts([road]));
 });
 it('swaps GeoJSON lon/lat exactly once',()=>expect(toLeafletPositions([[106.7,10.77]])).toEqual([[10.77,106.7]]));
 it('accepts empty responses without inventing alerts',()=>expect(normalizeAlerts([])).toEqual([]));
 it('rejects unknown severity, bad geometry and duplicate IDs',()=>{
  expect(()=>normalizeAlerts([{...road,severity:'unrecognized'}])).toThrow();
  expect(()=>normalizeAlerts([{...road,severity:'constructor'}])).toThrow();
  expect(()=>normalizeAlerts([{...road,geometry:{type:'LineString',coordinates:[[200,10],[106,10]]}}])).toThrow();
  expect(()=>normalizeAlerts([road,road])).toThrow();
 });
});
