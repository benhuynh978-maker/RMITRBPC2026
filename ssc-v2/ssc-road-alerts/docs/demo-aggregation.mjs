// Mo phong song: nhieu camera tren CUNG 1 tuyen, xem chinh xac backend tra ve gi.
// KHONG dung server/data/ that - tu tao thu muc tam, xoa sau khi xong.
// Chay: node docs/demo-aggregation.mjs  (tu thu muc ssc-road-alerts)
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createApiServer } from '../server/app.js';

const dir = await mkdtemp(join(tmpdir(), 'ssc-demo-'));
let now = Date.parse('2026-09-21T08:00:00Z');
const server = createApiServer({ dataDir: dir, clock: () => now, apiKey: 'admin', enableTestApi: true });
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

async function call(path, method = 'GET', body) {
  const res = await fetch(base + path, {
    method,
    headers: { 'X-API-Key': 'admin', ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: res.status, data: await res.json() };
}
function show(title) { console.log(`\n=== ${title} ===`); }
function road() { return call('/api/road-alerts/DEMO-R1').then(r => r.data); }
function pp(x) { return JSON.stringify(x, null, 2); }

show('0) Tao 1 tuyen + 3 camera tren CUNG tuyen do');
await call('/api/road-alerts', 'POST', { road_id: 'DEMO-R1', road_name: 'Tuyến demo 3 camera', geometry: { type: 'LineString', coordinates: [[106.70, 10.77], [106.72, 10.79]] } });
await call('/api/cameras', 'POST', { camera_id: 'DEMO-CAM-SACH', road_id: 'DEMO-R1', name: 'Camera đầu tuyến (sạch)', geometry: { type: 'Point', coordinates: [106.70, 10.77] } });
await call('/api/cameras', 'POST', { camera_id: 'DEMO-CAM-BAN', road_id: 'DEMO-R1', name: 'Camera giữa tuyến (rác nhiều)', geometry: { type: 'Point', coordinates: [106.71, 10.78] } });
await call('/api/cameras', 'POST', { camera_id: 'DEMO-CAM-XA', road_id: 'DEMO-R1', name: 'Camera cuối tuyến (chưa gửi ảnh)', geometry: { type: 'Point', coordinates: [106.72, 10.79] } });
console.log('Da tao xong. 3 camera CHUA co anh nao -> xem tuyen luc nay:');
console.log(pp(await road()));

show('1) Camera SACH gui ket qua: rac 8%, che cong 5%');
await call('/api/test/simulate', 'POST', { camera_id: 'DEMO-CAM-SACH', observation_id: 'OBS-SACH-1', captured_at: new Date(now).toISOString(), waste_coverage_pct: 8, drain_blockage_pct: 5, confidence: 0.95 });
console.log(pp(await road()));

show('2) Camera BAN gui ket qua NANG: rac 92%, che cong 88% (cach camera SACH ~50m tren cung tuyen)');
now += 5000;
await call('/api/test/simulate', 'POST', { camera_id: 'DEMO-CAM-BAN', observation_id: 'OBS-BAN-1', captured_at: new Date(now).toISOString(), waste_coverage_pct: 92, drain_blockage_pct: 88, confidence: 0.95 });
console.log(pp(await road()));
console.log('>>> Y NGHIA: tuyen nhay thang len severity cua camera XAU NHAT (BAN), du camera SACH van con tot.');
console.log('>>> waste_coverage_pct cua TUYEN =', (await road()).monitoring.waste_coverage_pct, '(= dung so cua camera BAN, khong phai trung binh (92+8)/2=50)');

show('3) Camera XA van chua tung gui anh nao (con lai trong 3 camera)');
const r3 = await road();
console.log('camera_count =', r3.camera_count, '| analyzed_camera_count =', r3.analyzed_camera_count, '| data_quality =', r3.data_quality);
console.log('>>> Y NGHIA: tuyen van "fresh" du 1/3 camera chua bao gio hoat dong - vi data_quality chi tinh tren cac camera CON DANG lien ket, XA khong bi tru diem vi chua co du lieu ban dau.');

show('4) 15 phut troi qua, khong camera nao gui them anh moi');
now += 15 * 60_000 + 1000;
const r4 = await road();
console.log(pp(r4));
console.log('>>> Y NGHIA: severity tut ve "normal", NHUNG data_quality =', r4.data_quality, '(khong phai "fresh"). UI phai tu phan biet 2 truong hop nay - "that su sach" vs "mat tin hieu".');

show('5) Camera BAN gui lai anh moi (van con nang), camera SACH va XA im lang');
now += 2000;
await call('/api/test/simulate', 'POST', { camera_id: 'DEMO-CAM-BAN', observation_id: 'OBS-BAN-2', captured_at: new Date(now).toISOString(), waste_coverage_pct: 95, drain_blockage_pct: 90, confidence: 0.95 });
const r5 = await road();
console.log(pp(r5));
console.log('>>> Y NGHIA: tuyen tro lai severity cao NGAY LAP TUC chi vi 1/3 camera "song lai", 2 camera con lai (SACH, XA) khong con anh huong gi den con so nay (da qua 15 phut).');
console.log('>>> data_quality =', r5.data_quality, '(2/3 camera da het han -> "partial", khong phai "fresh") - warnings:', r5.description);

show('6) Xem GET /api/cameras - moi camera co con so RIENG cua no (khong bi gop)');
const cams = (await call('/api/cameras')).data.cameras;
for (const c of cams) console.log(`  ${c.camera_id.padEnd(16)} status=${c.status.padEnd(8)} monitoring=${c.monitoring ? JSON.stringify(c.monitoring.waste_coverage_pct) + '%' : 'chưa có'}`);
console.log('>>> Y NGHIA: chi so TUNG camera van doc rieng duoc qua GET /api/cameras/:id - "mat" o day la o cach TUYEN gop lai (MAX), khong phai backend xoa du lieu camera.');

await new Promise(r => server.close(r));
await rm(dir, { recursive: true, force: true });
console.log('\nDa don thu muc tam. Khong dung lieu that.');
