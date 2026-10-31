import { requireValue } from './errors.js';
import { POLICY } from './config.js';
export function object(value) {
  requireValue(value !== null && typeof value === 'object' && !Array.isArray(value), 'Body cần là JSON object');
  return value;
}
export function fields(value, allowed) {
  object(value);
  requireValue(Object.keys(value).every(key => allowed.includes(key)), `Chỉ hỗ trợ các trường: ${allowed.join(', ')}`);
  return value;
}
export function id(value, name) {
  requireValue(typeof value === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(value), `${name} cần 1–80 ký tự A–Z, a–z, số, _ hoặc -`);
  return value;
}
export function timestamp(value, now = Date.now()) {
  requireValue(typeof value === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value)), 'Timestamp cần ISO 8601 có múi giờ');
  requireValue(Date.parse(value) <= now + POLICY.maxFutureSkewMs, 'Thời gian nằm quá xa trong tương lai');
  return new Date(value).toISOString();
}
export function percent(value, name) {
  requireValue(typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100, `${name} phải là số 0–100`);
  return value;
}
export function imageUrl(value) {
  requireValue(typeof value === 'string' && value.length <= 2048 && /^(https?:\/\/|\/(?!\/))[^\s\\]+$/i.test(value), 'image_url cần URL HTTP(S) hoặc đường dẫn /...');
  if (/^https?:/i.test(value)) {
    let parsed; try { parsed = new URL(value); } catch { requireValue(false, 'URL ảnh không hợp lệ'); }
    requireValue(!!parsed.hostname && !parsed.username && !parsed.password, 'URL ảnh không được chứa username/password');
  }
  return value;
}
export async function body(req, limit) {
  if (Number(req.headers['content-length']) > limit) { req.resume(); requireValue(false, 'Request vượt giới hạn kích thước', 413); }
  return new Promise((resolve,reject)=>{
    const chunks=[];let size=0;let done=false;
    req.on('data',chunk=>{
      if(done)return;
      size+=chunk.length;
      if(size>limit){done=true;chunks.length=0;try{requireValue(false,'Request vượt giới hạn kích thước',413);}catch(error){reject(error);}return;}
      chunks.push(chunk);
    });
    req.on('end',()=>{if(!done){done=true;resolve(Buffer.concat(chunks));}});
    req.on('error',error=>{if(!done){done=true;reject(error);}});
    req.on('aborted',()=>{if(!done){done=true;reject(new Error('Request bị ngắt'));}});
  });
}
export async function jsonBody(req) {
  requireValue(req.headers['content-type']?.split(';')[0].trim() === 'application/json', 'Cần Content-Type: application/json', 415);
  const bytes = await body(req, POLICY.maxJsonBytes);
  let value; try { value = JSON.parse(bytes.toString('utf8')); } catch { requireValue(false, 'JSON không hợp lệ'); }
  return object(value);
}
