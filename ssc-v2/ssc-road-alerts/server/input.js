import { requireValue } from './errors.js';
import { POLICY } from './config.js';
export function object(value) {
  requireValue(value !== null && typeof value === 'object' && !Array.isArray(value), 'Body must be a JSON object');
  return value;
}
export function fields(value, allowed) {
  object(value);
  requireValue(Object.keys(value).every(key => allowed.includes(key)), `Only these fields are supported: ${allowed.join(', ')}`);
  return value;
}
export function id(value, name) {
  requireValue(typeof value === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(value), `${name} must be 1–80 characters: A–Z, a–z, digits, _ or -`);
  return value;
}
export function timestamp(value, now = Date.now()) {
  requireValue(typeof value === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value)), 'Timestamp must be ISO 8601 with a time zone');
  requireValue(Date.parse(value) <= now + POLICY.maxFutureSkewMs, 'The time is too far in the future');
  return new Date(value).toISOString();
}
export function percent(value, name) {
  requireValue(typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100, `${name} must be a number from 0 to 100`);
  return value;
}
export function imageUrl(value) {
  requireValue(typeof value === 'string' && value.length <= 2048 && /^(https?:\/\/|\/(?!\/))[^\s\\]+$/i.test(value), 'image_url must be an HTTP(S) URL or a /... path');
  if (/^https?:/i.test(value)) {
    let parsed; try { parsed = new URL(value); } catch { requireValue(false, 'Invalid image URL'); }
    requireValue(!!parsed.hostname && !parsed.username && !parsed.password, 'The image URL must not contain a username/password');
  }
  return value;
}
export async function body(req, limit) {
  if (Number(req.headers['content-length']) > limit) { req.resume(); requireValue(false, 'The request exceeds the size limit', 413); }
  return new Promise((resolve,reject)=>{
    const chunks=[];let size=0;let done=false;
    req.on('data',chunk=>{
      if(done)return;
      size+=chunk.length;
      if(size>limit){done=true;chunks.length=0;try{requireValue(false,'The request exceeds the size limit',413);}catch(error){reject(error);}return;}
      chunks.push(chunk);
    });
    req.on('end',()=>{if(!done){done=true;resolve(Buffer.concat(chunks));}});
    req.on('error',error=>{if(!done){done=true;reject(error);}});
    req.on('aborted',()=>{if(!done){done=true;reject(new Error('The request was interrupted'));}});
  });
}
export async function jsonBody(req) {
  requireValue(req.headers['content-type']?.split(';')[0].trim() === 'application/json', 'Content-Type: application/json is required', 415);
  const bytes = await body(req, POLICY.maxJsonBytes);
  let value; try { value = JSON.parse(bytes.toString('utf8')); } catch { requireValue(false, 'Invalid JSON'); }
  return object(value);
}
