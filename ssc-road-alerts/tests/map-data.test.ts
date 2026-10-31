import {it,expect} from 'vitest';
import {normalizeCameras} from '../src/services/mapService';
import {roadMidpoint} from '../src/services/roadMidpoint';
it('accepts empty cameras and rejects swapped/out-of-range coordinates',()=>{
 expect(normalizeCameras({cameras:[]})).toEqual([]);
 expect(()=>normalizeCameras({cameras:[{camera_id:'C1',geometry:{type:'Point',coordinates:[10,106]}}]})).toThrow();
});
it('rejects duplicate camera IDs',()=>{
 const c={camera_id:'C1',geometry:{type:'Point',coordinates:[106,10]}};
 expect(()=>normalizeCameras({cameras:[c,c]})).toThrow();
});
it('places road point on the line by length rather than averaging vertices',()=>{
 expect(roadMidpoint([[0,0],[1,0],[4,0]])[0]).toBeCloseTo(2);
 expect(roadMidpoint([[0,0],[0,0]])).toEqual([0,0]);
});
