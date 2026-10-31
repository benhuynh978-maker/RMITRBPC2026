import type { Coordinate } from '../models/roadAlert';
/** Halfway along the geometry, not the average of vertices (which may leave the road). */
export function roadMidpoint(points:Coordinate[]):[number,number] {
 const lengths=points.slice(1).map((p,i)=>{
  const a=points[i];const rad=Math.PI/180;
  const h=Math.sin((p[1]-a[1])*rad/2)**2+Math.cos(a[1]*rad)*Math.cos(p[1]*rad)*Math.sin((p[0]-a[0])*rad/2)**2;
  return 2*Math.asin(Math.sqrt(Math.min(1,h)));
 });
 let target=lengths.reduce((a,b)=>a+b,0)/2;
 for(let i=0;i<lengths.length;i++) {
  const len=lengths[i];
  if(len>0&&target<=len){const t=target/len;return [points[i][0]+(points[i+1][0]-points[i][0])*t,points[i][1]+(points[i+1][1]-points[i][1])*t];}
  target-=len;
 }
 return [points[0][0],points[0][1]];
}
