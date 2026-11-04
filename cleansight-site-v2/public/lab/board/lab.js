// Board lab: JS của webtest (exp02) đem vào website CleanSight.
// Khác bản gốc: (1) không có mã truy cập, thay bằng mã phiên ngẫu nhiên (X-Lab-Session); (2) gọi dịch vụ ở window.LAB_API_URL;
// (3) chọn ảnh mẫu của đội thay vì tải ảnh / ảnh từ điện thoại; (4) bỏ vòng hỏi /api/status của trang điện thoại.
// Mọi phần còn lại (bản đồ, chế độ vị trí, nhích/xoay, footprint, lịch sử) giữ nguyên.
"use strict";
// ====== Tiện ích chung ======
const $ = (id) => document.getElementById(id);
const MSG_MANG = 'Cannot reach the live demo. It runs on the team laptop and is only available while that laptop is on; please try again later.';
const DEFAULT_LATLNG = [10.7769, 106.7009];
const ARROW_LEN_M = 2;        // mũi tên dài 2 m ngoài đời thật
const NUDGE_M = 0.05;         // nút nhích 5 cm
const M_PER_DEG = 111320;     // số mét trên 1 độ vĩ độ

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function showMsg(id, kind, text) {
  const el = $(id);
  el.innerHTML = text ? '<div class="msg ' + kind + '">' + esc(text) + '</div>' : '';
}
function normAz(a) { return ((a % 360) + 360) % 360; }

// ====== Địa chỉ dịch vụ + phiên (thay cho mã truy cập 6 số của web test gốc) ======
// window.LAB_API_URL do lab-config.js đặt; trình duyệt tự sinh mã phiên ngẫu nhiên và gửi kèm header X-Lab-Session.
// Máy chủ giữ hiệu chỉnh / lịch sử CỦA PHIÊN NÀY trong RAM (hết hạn sau 30 phút không dùng), nên nhiều người dùng cùng lúc không đè nhau.
const API_BASE = String(window.LAB_API_URL || '').replace(/\/+$/, '');
const SESSION_KEY = 'cleansight_lab_session';
let sessionId = '';
(function () {
  try { sessionId = sessionStorage.getItem(SESSION_KEY) || ''; } catch (e) { sessionId = ''; }
  if (!/^[A-Za-z0-9_-]{16,64}$/.test(sessionId)) {
    const b = new Uint8Array(18);
    crypto.getRandomValues(b);
    sessionId = btoa(String.fromCharCode.apply(null, b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    try { sessionStorage.setItem(SESSION_KEY, sessionId); } catch (e) { /* bỏ qua: phiên chỉ nằm trong bộ nhớ trang */ }
  }
})();

// Gọi API của dịch vụ. Trả {status, data, retryAfter}; lỗi mạng ném Error(MSG_MANG).
async function api(path, opts) {
  const o = Object.assign({}, opts || {});
  o.headers = Object.assign({ 'X-Lab-Session': sessionId }, o.headers || {});
  o.credentials = 'omit'; o.cache = 'no-store'; o.referrerPolicy = 'no-referrer';
  let resp;
  try {
    resp = await fetch(API_BASE + path, o);
  } catch (e) {
    throw new Error(MSG_MANG);
  }
  let data = null;
  try { data = await resp.json(); } catch (e) { data = null; }
  return { status: resp.status, data: data, retryAfter: resp.headers.get('Retry-After') };
}
function postJson(path, obj) {
  return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) });
}
// Lấy thông báo lỗi (tiếng Anh) từ phản hồi không thành công
function errText(r) {
  if (r.status === 429) return ((r.data && r.data.error) || 'Too many requests.') + (r.retryAfter ? ' Please wait about ' + r.retryAfter + ' seconds.' : '');
  if (r.data && typeof r.data.error === 'string' && r.data.error) return r.data.error;
  if (r.status === 404) return 'Data not found on the server (HTTP 404).';
  if (r.status === 400) return 'The photo or data sent is invalid (HTTP 400).';
  if (r.status === 422) return 'The data sent is invalid (HTTP 422).';
  if (r.status === 409) return 'Not calibrated. Do steps 1–3 first (HTTP 409).';
  return 'Server error (HTTP ' + r.status + ').';
}
// Khoá nút + chữ "Processing…" trong lúc chạy
async function withBusy(btn, fn) {
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span>Processing…';
  try { return await fn(); }
  finally { btn.disabled = false; btn.innerHTML = old; }
}
function pxText(v) { return (typeof v === 'number' ? v.toFixed(1) : '?') + ' px'; }

// Phóng to ảnh
function phongTo(src) { $('lb-img').src = src; $('lb').classList.add('show'); }
$('lb').addEventListener('click', () => $('lb').classList.remove('show'));
$('r1-img').addEventListener('click', (e) => phongTo(e.target.src));
$('r4-img').addEventListener('click', (e) => phongTo(e.target.src));

// ====== Trạng thái (nguồn thật nằm ở server) ======
const S = {
  calibId: null,        // calibration_id của phiên dò bảng hiện tại (mất khi tải lại trang)
  latlng: null,         // [lat, lon] bảng
  az: 0,                // azimuth la bàn của +Y
  saved: false,         // server đã có hiệu chỉnh
  dirty: false,         // đã đổi vị trí/hướng sau khi lưu
  fpSeq: 0,             // chống kết quả footprint cũ ghi đè mới
  fpTimer: null,
  fitted: false,        // đã zoom vừa footprint lần đầu chưa
  mode: 1,              // 1 = điểm cố định (mặc định mỗi lần mở trang), 2 = tự chọn vị trí (chỉ giữ trong bộ nhớ trang)
  sessionMode: 1,       // chế độ của phiên dò bảng hiện tại
  msgRecalib: false,    // msg1 đang hiện nhắc của nút "Hiệu chỉnh lại"
  picked: true          // đã có vị trí bảng do người dùng chọn/chấp nhận (chế độ 2 bắt đầu = false)
};

// ====== Accordion / khoá bước ======
const STEP_IDS = ['s1', 's2', 's3', 's4'];
function lockStep(id, locked) { $(id).classList.toggle('locked', locked); if (locked) $(id).classList.remove('open'); }
function openStep(id) {
  STEP_IDS.forEach((s) => $(s).classList.toggle('open', s === id));
  $(id).scrollIntoView({ block: 'nearest' });
}
function markDone(id, done, badge) {
  $(id).classList.toggle('done', done);
  $('b' + id.slice(1)).textContent = done ? (badge || '✔ done') : '';
}
document.querySelectorAll('.step-head').forEach((h) => {
  h.addEventListener('click', () => {
    const st = $(h.dataset.step);
    if (st.classList.contains('locked')) return;
    st.classList.toggle('open');
  });
});

// ====== Thanh trạng thái trên cùng ======
function setChip(id, cls, text) { const el = $(id); el.className = 'chip ' + cls; el.textContent = text; }
async function kiemTraSucKhoe() {
  try {
    const r = await api('/api/health');
    if (r.status === 200 && r.data && r.data.status === 'ok') {
      setChip('st-server', 'ok', 'online');
      setChip('st-model', r.data.ready ? 'ok' : 'wait', r.data.ready ? 'ready' : 'starting…');
      setChip('st-calib', S.saved ? 'ok' : 'wait', S.saved ? 'saved' : 'not calibrated yet');
    } else {
      setChip('st-server', 'bad', 'error (HTTP ' + r.status + ')');
    }
  } catch (e) {
    setChip('st-server', 'bad', 'offline');
    setChip('st-calib', 'wait', '?');
    setChip('st-model', 'wait', '?');
  }
}

// ====== Bản đồ ======
const map = L.map('map', { zoomControl: true }).setView(DEFAULT_LATLNG, 20);
// OSM France (cùng dữ liệu OpenStreetMap): tile.openstreetmap.org bị chặn DNS trên máy thử.
L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
  subdomains: 'abc', maxZoom: 24, maxNativeZoom: 20,
  attribution: '&copy; <a href="https://www.openstreetmap.fr" target="_blank" rel="noopener">OpenStreetMap France</a> | &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
}).addTo(map);
L.control.scale({ metric: true, imperial: false, position: 'bottomleft' }).addTo(map);

// ====== BƯỚC 1: dò bảng ======
function hienKetQuaBuoc1(d, bi422) {
  $('r1').style.display = 'block';
  if (d.overlay_jpg_b64) { $('r1-img').src = 'data:image/jpeg;base64,' + d.overlay_jpg_b64; $('r1-img').style.display = 'block'; }
  else { $('r1-img').removeAttribute('src'); $('r1-img').style.display = 'none'; }
  const px = d.side_px_min;
  $('r1-px').textContent = (typeof px === 'number') ? pxText(px) + ' (shortest side)' : '(not measured)';
  const tag = $('r1-tag');
  if (typeof px === 'number') {
    const du = !bi422 && px >= 50;
    tag.className = 'tag ' + (du ? 'ok' : 'bad');
    tag.textContent = du ? 'large enough (≥ 50 px)' : 'too small (< 50 px), blocked';
  } else { tag.className = ''; tag.textContent = ''; }
  const nguon = { exif: 'read from the photo (EXIF)', input: 'entered by you', 'default': 'default 66° (photo has no lens info)' };
  if (!bi422) {
    $('r1-fov').textContent = (typeof d.fov_deg === 'number' ? d.fov_deg.toFixed(1) + '°' : '?');
    $('r1-src').textContent = '— ' + (nguon[d.fov_source] || d.fov_source || '') +
      ((typeof d.focal_35mm === 'number') ? ' — 35mm-equivalent focal length: ' + fmtNum(d.focal_35mm, 1) + ' mm' : '');
  } else { $('r1-fov').textContent = '—'; $('r1-src').textContent = ''; }
  $('r1-h').textContent = (!bi422 && typeof d.camera_height_m_est === 'number') ? fmtNum(d.camera_height_m_est, 2) + ' m' : '—';
  const ul = $('r1-warn');
  ul.innerHTML = '';
  const ws = (d.warnings || []);
  ul.style.display = ws.length ? 'block' : 'none';
  ws.forEach((w) => { const li = document.createElement('li'); li.textContent = w; ul.appendChild(li); });
}

// ====== Ảnh mẫu của đội (thay cho ảnh từ điện thoại / tệp của web test gốc) ======
// Giám khảo không tải ảnh lên: máy chủ giữ sẵn các ảnh mẫu và nhận sample_id.
let calibSamples = [], trashSamples = [];
let calibSel = null, trashSel = null;
function veMau(boxId, items, selId, onSelect) {
  const box = $(boxId);
  box.innerHTML = '';
  if (!items.length) { box.innerHTML = '<span class="hint">No sample photos available.</span>'; return; }
  items.forEach((it) => {
    const row = document.createElement('div');
    row.className = 'ib-item' + (it.id === selId ? ' sel' : '');
    row.tabIndex = 0;
    row.setAttribute('role', 'button');
    row.setAttribute('aria-pressed', it.id === selId ? 'true' : 'false');
    const img = document.createElement('img');
    img.alt = it.label;
    img.src = '/img/lab/' + it.id + '-thumb.jpg';
    const tx = document.createElement('div');
    tx.className = 'tx';
    const b = document.createElement('b');
    b.textContent = it.label;
    const n = document.createElement('div');
    n.className = 'hint';
    n.textContent = it.note || '';
    tx.appendChild(b); tx.appendChild(n);
    row.appendChild(img); row.appendChild(tx);
    const chon = () => onSelect(it.id);
    row.addEventListener('click', chon);
    row.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chon(); } });
    box.appendChild(row);
  });
}
function chonMauCalib(id) {
  calibSel = id;
  const it = calibSamples.find((x) => x.id === id);
  if (it && it.marker_size_mm) $('f-size').value = it.marker_size_mm;
  veMau('sample-calib', calibSamples, calibSel, chonMauCalib);
}
function chonMauRac(id) {
  trashSel = id;
  veMau('sample-trash', trashSamples, trashSel, chonMauRac);
}
async function taiMau() {
  let r;
  try { r = await api('/api/lab/board/samples'); } catch (e) { return false; }
  if (r.status !== 200 || !r.data || !r.data.ok) return false;
  calibSamples = r.data.calibration || [];
  trashSamples = r.data.trash || [];
  if (!calibSel && calibSamples.length) chonMauCalib(calibSamples[0].id); else veMau('sample-calib', calibSamples, calibSel, chonMauCalib);
  if (!trashSel && trashSamples.length) chonMauRac(trashSamples[0].id); else veMau('sample-trash', trashSamples, trashSel, chonMauRac);
  return true;
}

$('btn-detect').addEventListener('click', () => withBusy($('btn-detect'), async () => {
  showMsg('msg1', '', ''); S.msgRecalib = false;
  if (!calibSel) { showMsg('msg1', 'err', $('st-server').classList.contains('bad') ? MSG_MANG : 'Choose a board photo first.'); return; }
  const size = parseFloat($('f-size').value);
  if (!(size > 0)) { showMsg('msg1', 'err', 'Enter the real board side length (mm) as a number above 0.'); return; }
  const body = { sample_id: calibSel, marker_size_mm: size };
  const fovTxt = $('f-fov').value.trim();
  if (fovTxt !== '') {
    const fv = parseFloat(fovTxt);
    if (!(fv > 0 && fv < 180)) { showMsg('msg1', 'err', 'Field of view must be between 0 and 180 degrees (or leave blank).'); return; }
    body.fov_deg = fv;
  }
  let r;
  try { r = await postJson('/api/lab/board/detect', body); }
  catch (e) { showMsg('msg1', 'err', e.message); return; }
  const d = r.data || {};
  if (r.status !== 200 || !d.ok) {
    hienKetQuaBuoc1(d, true);
    showMsg('msg1', 'err', errText(r));
    return;
  }
  hienKetQuaBuoc1(d, false);
  showMsg('msg1', 'ok', 'Board detected. Continue to step 2.');
  batDauPhienHieuChinh(d.calibration_id);
}));

// ====== BƯỚC 2: marker + mũi tên trên bản đồ ======
const pose = { mk: null, line: null, head: null, handle: null, draggingHandle: false };

function offsetLL(ll, dN, dE) {
  return [ll[0] + dN / M_PER_DEG, ll[1] + dE / (M_PER_DEG * Math.cos(ll[0] * Math.PI / 180))];
}
function tipLL(ll, az, len) {
  const a = az * Math.PI / 180;
  return offsetLL(ll, len * Math.cos(a), len * Math.sin(a));
}
function azFromTo(a, b) {   // góc la bàn từ điểm a tới điểm b
  const dN = (b[0] - a[0]) * M_PER_DEG;
  const dE = (b[1] - a[1]) * M_PER_DEG * Math.cos(a[0] * Math.PI / 180);
  if (Math.abs(dN) < 1e-9 && Math.abs(dE) < 1e-9) return null;
  return normAz(Math.atan2(dE, dN) * 180 / Math.PI);
}

function veMuiTen() {
  if (!pose.mk) return;
  const tip = tipLL(S.latlng, S.az, ARROW_LEN_M);
  pose.line.setLatLngs([S.latlng, tip]);
  pose.head.setLatLngs([tipLL(tip, S.az + 150, 0.3), tip, tipLL(tip, S.az - 150, 0.3)]);
  if (pose.handle && !pose.draggingHandle) pose.handle.setLatLng(tip);
}
function capNhatSoDoc() {
  $('az-val').textContent = S.latlng ? Math.round(S.az) + '°' : '—';
  $('pos-val').textContent = S.latlng ? 'Position: ' + S.latlng[0].toFixed(6) + ', ' + S.latlng[1].toFixed(6)
    : (S.calibId ? 'Position: NOT SET. Click the map where the board is placed.' : 'Position: —');
}

// Tạo (nếu chưa có) các lớp marker/mũi tên; editable = cho kéo thả
function dungLopTuThe(editable) {
  if (!pose.mk) {
    pose.mk = L.marker(S.latlng, {
      draggable: true, keyboard: false,
      icon: L.divIcon({ className: '', html: '<div class="pin-board"></div>', iconSize: [16, 16], iconAnchor: [8, 8] })
    }).addTo(map);
    pose.line = L.polyline([S.latlng, S.latlng], { color: '#1d4ed8', weight: 4, interactive: false }).addTo(map);
    pose.head = L.polyline([S.latlng, S.latlng, S.latlng], { color: '#1d4ed8', weight: 4, interactive: false }).addTo(map);
    pose.handle = L.marker(S.latlng, {
      draggable: true, keyboard: false,
      icon: L.divIcon({ className: '', html: '<div class="pin-handle"></div>', iconSize: [18, 18], iconAnchor: [9, 9] })
    });
    pose.handle.bindTooltip('+Y', { permanent: true, direction: 'right', offset: [12, 0], className: 'lbl' });

    pose.mk.on('drag', () => { const p = pose.mk.getLatLng(); datTuThe([p.lat, p.lng], null, true); });
    pose.handle.on('dragstart', () => { pose.draggingHandle = true; });
    pose.handle.on('drag', () => {
      const p = pose.handle.getLatLng();
      const a = azFromTo(S.latlng, [p.lat, p.lng]);
      if (a !== null) datTuThe(null, a);
    });
    pose.handle.on('dragend', () => { pose.draggingHandle = false; veMuiTen(); });
  }
  if (editable) { pose.mk.dragging.enable(); pose.handle.addTo(map); }
  else { pose.mk.dragging.disable(); map.removeLayer(pose.handle); }
  pose.mk.setLatLng(S.latlng);
  veMuiTen();
  capNhatSoDoc();
}
function xoaLopTuThe() {
  ['mk', 'line', 'head', 'handle'].forEach((k) => { if (pose[k]) { map.removeLayer(pose[k]); pose[k] = null; } });
  pose.draggingHandle = false;
}

// Đổi vị trí và/hoặc hướng; mọi thay đổi gọi footprint (debounce 400 ms)
function datTuThe(ll, az, daKeoMarker) {
  if (ll) S.latlng = ll;
  if (az !== null && az !== undefined) S.az = normAz(az);
  if (ll && !pose.mk) dungLopTuThe(true);   // chế độ 2: lần bấm đầu tiên mới tạo ghim + mũi tên
  if (pose.mk && ll && !daKeoMarker) pose.mk.setLatLng(S.latlng);
  if (ll && !S.picked && S.calibId) {       // chế độ 2: vừa chọn xong vị trí -> mở bước 3
    S.picked = true;
    markDone('s2', true, '✔ placed'); lockStep('s3', false);
    hienToast('Board position set. Go to step 3 to preview and save.');
  }
  veMuiTen();
  capNhatSoDoc();
  if (S.saved && S.calibId) {
    S.dirty = true;
    showMsg('dirty-msg', 'warn', 'You changed the position/heading after saving. Go back to step 3 and click "Save calibration" again before sending photos.');
  }
  if (S.calibId) lenLichFootprint();
}

map.on('click', (e) => {
  // chỉ đặt lại vị trí khi bước 2 đang mở (tránh bấm nhầm sau khi đã lưu)
  if (S.calibId && $('s2').classList.contains('open')) datTuThe([e.latlng.lat, e.latlng.lng], null);
});
document.querySelectorAll('[data-dn]').forEach((b) => b.addEventListener('click', () => {
  if (!S.calibId || !S.latlng) return;
  datTuThe(offsetLL(S.latlng, Number(b.dataset.dn) * NUDGE_M, Number(b.dataset.de) * NUDGE_M), null);
}));
document.querySelectorAll('[data-rot]').forEach((b) => b.addEventListener('click', () => {
  if (!S.calibId || !S.latlng) return;
  datTuThe(null, S.az + Number(b.dataset.rot));
}));

// Bắt đầu phiên hiệu chỉnh mới sau khi dò bảng thành công
function batDauPhienHieuChinh(calibId) {
  S.calibId = calibId;
  S.saved = false; S.dirty = false; S.fitted = false;
  fpLayer.clearLayers();
  clearTimeout(S.fpTimer); S.fpSeq++;   // bỏ kết quả footprint của phiên trước còn đang bay
  S.sessionMode = S.mode;
  if (S.mode === 2) {
    // Chế độ 2: KHÔNG dùng lại vị trí/hướng cũ; bắt buộc bấm vị trí mới (giữ nguyên khung nhìn bản đồ hiện tại)
    S.latlng = null; S.az = 0; S.picked = false;
    xoaLopTuThe();
    $('s2-hint').textContent = 'Mode 2: no board position yet. Zoom the map to where you placed the board and click that exact spot. Then drag the blue arrow (now pointing North) to set the direction of the board\'s \'+Y\' edge (the blue +Y arrow in the step 1 image).';
    capNhatSoDoc();
  } else {
    S.picked = true;
    if (!S.latlng) { S.latlng = DEFAULT_LATLNG.slice(); S.az = 0; map.setView(S.latlng, 20); }
    $('s2-hint').textContent = S2_HINT_MAC_DINH;
    dungLopTuThe(true);
  }
  showMsg('fp-msg', '', ''); showMsg('save-msg', '', ''); showMsg('dirty-msg', '', '');
  $('calib-summary').style.display = 'none';
  $('btn-recalib').style.display = 'none';
  markDone('s1', true, '✔ board OK');
  lockStep('s2', false); lockStep('s3', !S.picked);
  markDone('s2', S.picked, '✔ placed'); markDone('s3', false);
  capNhatCheDo();
  lockStep('s4', true); markDone('s4', false);
  $('s2').classList.add('open');   // giữ bước 1 mở để còn thấy ảnh dò, số px, cảnh báo
  $('s2').scrollIntoView({ block: 'nearest' });
  lenLichFootprint();
}

// ====== Chế độ vị trí bảng (1 = điểm cố định, 2 = tự chọn vị trí) ======
const S2_HINT_MAC_DINH = $('s2-hint').textContent;
const MODE_HINT = {
  1: '',
  2: 'Place the board anywhere: after detecting the board, click its exact spot on the map (the old point is not reused). ' +
     'The position is clicked by hand, so the absolute error is a few metres (measurements relative to the board are unchanged).'
};
// Đổi chế độ chỉ được khi không có phiên hiệu chỉnh đang dở (đã dò bảng nhưng chưa lưu)
function capNhatCheDo() {
  const dangDo = !!S.calibId && !S.saved;
  document.querySelectorAll('input[name="che-do"]').forEach((r) => { r.disabled = dangDo; r.checked = (Number(r.value) === S.mode); });
  $('mode-hint').textContent = MODE_HINT[S.mode] + (dangDo ? ' (Calibration in progress: save it before changing the mode.)' : '');
}
document.querySelectorAll('input[name="che-do"]').forEach((r) => r.addEventListener('change', () => {
  if (S.calibId && !S.saved) { capNhatCheDo(); return; }
  S.mode = Number(r.value) === 2 ? 2 : 1;
  if (S.msgRecalib) hienNhacHieuChinhLai();   // đang hiện nhắc "Hiệu chỉnh lại": đổi theo chế độ mới
  capNhatCheDo();
}));
capNhatCheDo();

// ====== BƯỚC 3: xem trước footprint + lưu ======
const fpLayer = L.layerGroup().addTo(map);
let fpGeo = null;   // lớp GeoJSON footprint hiện tại (để lấy getBounds)

function lenLichFootprint() {
  clearTimeout(S.fpTimer);
  S.fpTimer = setTimeout(layFootprint, 400);
}
// Vẽ FeatureCollection footprint (vùng nhìn thấy + điểm bảng + điểm camera)
function veFootprint(data) {
  fpLayer.clearLayers();
  const gj = L.geoJSON(data, {
    interactive: false,   // bấm lên vùng xanh không được làm đổi vị trí bảng
    filter: (f) => f && f.geometry,
    style: (f) => ({ color: '#15803d', weight: 2, fillColor: '#86efac', fillOpacity: 0.3 }),
    pointToLayer: (f, ll) => {
      const kind = (f.properties || {}).kind;
      const isCam = kind === 'camera';
      const c = L.circleMarker(ll, { radius: 8, color: '#fff', weight: 2, fillColor: isCam ? '#16a34a' : '#2563eb', fillOpacity: 1 });
      const h = (f.properties || {}).height_m;
      const text = isCam ? 'Camera' + (typeof h === 'number' ? ' (height ~' + h.toFixed(1) + ' m)' : '') : 'Board';
      c.bindTooltip(text, { permanent: true, direction: isCam ? 'left' : 'bottom', offset: [isCam ? -10 : 0, isCam ? 0 : 12], className: 'lbl' });
      return c;
    }
  }).addTo(fpLayer);
  fpGeo = gj;
  if (!S.fitted) {
    const b = gj.getBounds();
    if (b.isValid()) { map.fitBounds(b, { padding: [40, 40], maxZoom: 21 }); S.fitted = true; }
  }
}

async function layFootprint() {
  if (!S.calibId || !S.latlng) return;
  const seq = ++S.fpSeq;
  const q = new URLSearchParams({
    calibration_id: S.calibId,
    lat: S.latlng[0].toFixed(8),
    lon: S.latlng[1].toFixed(8),
    azimuth_deg: S.az.toFixed(3),
    max_range_m: '12'
  });
  let r;
  try { r = await api('/api/lab/board/footprint?' + q.toString()); }
  catch (e) { if (seq === S.fpSeq) showMsg('fp-msg', 'err', e.message); return; }
  if (seq !== S.fpSeq) return;   // đã có yêu cầu mới hơn
  if (r.status === 404) { showMsg('fp-msg', 'err', 'This calibration session is no longer on the server. Detect the board again in step 1.'); return; }
  if (r.status !== 200 || !r.data || r.data.type !== 'FeatureCollection') { showMsg('fp-msg', 'err', errText(r)); return; }
  showMsg('fp-msg', '', '');
  veFootprint(r.data);
  markDone('s3', S.saved, '✔ saved');
}

$('btn-save').addEventListener('click', () => withBusy($('btn-save'), async () => {
  showMsg('save-msg', '', '');
  if (!S.calibId) { showMsg('save-msg', 'err', 'No board detection yet. Do step 1 first.'); return; }
  if (!S.latlng || !S.picked) { showMsg('save-msg', 'err', 'Board position not set. Click the map in step 2 first.'); return; }
  let r;
  try {
    r = await postJson('/api/lab/board/calibration/save', { calibration_id: S.calibId, lat: S.latlng[0], lon: S.latlng[1], azimuth_deg: S.az });
  } catch (e) { showMsg('save-msg', 'err', e.message); return; }
  if (r.status !== 200 || !r.data || !r.data.ok) { showMsg('save-msg', 'err', errText(r)); return; }
  S.saved = true; S.dirty = false;
  showMsg('save-msg', 'ok', 'Calibration saved. Continue to step 4.' + (S.sessionMode === 2
    ? ' (Position was clicked by hand: absolute error is a few metres; measurements relative to the board are unchanged.)' : ''));
  capNhatCheDo();
  showMsg('dirty-msg', '', '');
  markDone('s3', true, '✔ saved');
  await taiHieuChinhDaLuu(false);
  kiemTraSucKhoe();
  lockStep('s4', false);
  openStep('s4');
}));

// Đọc hiệu chỉnh đã lưu từ server để hiện tóm tắt (và vẽ lại marker khi tải lại trang)
async function taiHieuChinhDaLuu(veLaiTuThe) {
  let r;
  try { r = await api('/api/lab/board/calibration'); }
  catch (e) { showMsg('msg4', 'err', e.message); return false; }
  const c = r.data && r.data.ok && r.data.calibration;
  if (!c) return false;
  S.saved = true;
  const ll = c.marker_latlon || [];
  const sum = $('calib-summary');
  sum.style.display = 'block';
  sum.textContent = 'Calibrated (' + (c.camera_id || '?') + '): board at ' +
    (ll.length === 2 ? Number(ll[0]).toFixed(6) + ', ' + Number(ll[1]).toFixed(6) : '?') +
    ', +Y heading ' + Math.round(c.azimuth_deg) + '°, field of view ' + (typeof c.fov_deg === 'number' ? c.fov_deg.toFixed(1) : '?') + '°' +
    (typeof c.side_px_min === 'number' ? ', board ' + c.side_px_min.toFixed(0) + ' px' : '') + '.';
  $('btn-recalib').style.display = 'inline-block';
  if (veLaiTuThe && ll.length === 2) {
    S.latlng = [Number(ll[0]), Number(ll[1])];
    S.az = normAz(Number(c.azimuth_deg) || 0);
    S.calibId = null;                // không có calibration_id sau khi tải lại -> chỉ xem, không sửa
    dungLopTuThe(false);
    map.setView(S.latlng, 21);
    lockStep('s1', false); $('s1').classList.remove('open');
    layFootprintDaLuu();
    lockStep('s2', true); lockStep('s3', true);   // chỉ xem; muốn sửa thì bấm "Hiệu chỉnh lại"
    markDone('s1', true, '✔ saved'); markDone('s2', true, '✔ saved'); markDone('s3', true, '✔ saved');
  }
  return true;
}

// Sau khi tải lại trang: server tự lấy vị trí/hướng từ hiệu chỉnh đã lưu (không cần calibration_id)
async function layFootprintDaLuu() {
  try {
    const r = await api('/api/lab/board/footprint?max_range_m=12');
    if (r.status === 200 && r.data && r.data.type === 'FeatureCollection') {
      veFootprint(r.data);
      const b = fpGeo ? fpGeo.getBounds() : null;
      if (b && b.isValid()) map.fitBounds(b, { padding: [40, 40], maxZoom: 21 });
    }
  } catch (e) { console.warn('Could not redraw the saved footprint:', e); }
}

// "Hiệu chỉnh lại": mở lại bước 1 (vị trí cũ vẫn là điểm xuất phát)
function hienNhacHieuChinhLai() {
  showMsg('msg1', 'info', S.mode === 2
    ? 'Mode 2: choose a new board photo and click "Detect board", then click the new position on the map (the old position will not be reused).'
    : 'Choose a new board photo and click "Detect board". The old map position is kept as the starting point.');
}
$('btn-recalib').addEventListener('click', () => {
  S.calibId = null;
  lockStep('s2', true); lockStep('s3', true);
  markDone('s1', false); markDone('s2', false); markDone('s3', false);
  lockStep('s1', false);
  S.msgRecalib = true;
  hienNhacHieuChinhLai();
  capNhatCheDo();
  openStep('s1');
});

// ====== BƯỚC 4: gửi ảnh có rác, vẽ vùng đỏ ======
const STYLE_MOI = { color: '#b91c1c', weight: 3, fillColor: '#ef4444', fillOpacity: 0.45 };
const STYLE_CU = { color: '#f59e0b', weight: 2, fillColor: '#fcd34d', fillOpacity: 0.3 };
let obsList = [];   // cũ -> mới: {id, at, n, total, layer, visible}

function fmtNum(v, nd) {
  return (typeof v === 'number' && isFinite(v)) ? v.toLocaleString('en-GB', { maximumFractionDigits: nd }) : '?';
}
function fmtGio(s) {
  const d = new Date(s);
  return isNaN(d.getTime()) ? String(s || '?') : d.toLocaleString('en-GB');
}
// Danh sách vùng rác của một lần gửi, mỗi vùng một dòng: số thứ tự, Y, X (so với tâm bảng), diện tích
function danhSachVungHtml(regions) {
  const fs = ((regions || {}).features || []).filter((f) => f && f.geometry);
  if (!fs.length) return '';
  let h = '<div id="r4-vung"><b>Position relative to board centre</b> (Y = along +Y, X = along +X; up = +Y, right = +X):<br>';
  fs.forEach((f, i) => {
    const p = f.properties || {};
    const co = (typeof p.y_m === 'number' && typeof p.x_m === 'number');
    h += '<b>Region ' + esc(p.idx || (i + 1)) + ':</b> ' + (co ? 'Y = <b>' + fmtNum(p.y_m, 3) + '</b> m; X = <b>' + fmtNum(p.x_m, 3) + '</b> m' : 'no coordinates') +
      ' · ' + fmtNum(p.area_m2, 3) + ' m²<br>';
  });
  return h + '</div>';
}
function veLopRac(regions) {
  return L.geoJSON(regions || { type: 'FeatureCollection', features: [] }, {
    filter: (f) => f && f.geometry,
    style: () => STYLE_CU,
    onEachFeature: (f, layer) => {
      const p = f.properties || {};
      const conf = (typeof p.confidence === 'number') ? fmtNum(p.confidence * 100, 0) + ' %' : 'n/a';
      const co = (typeof p.y_m === 'number' && typeof p.x_m === 'number');
      layer.bindPopup('<b>Trash region' + (p.idx ? ' no. ' + esc(p.idx) : '') + '</b>' +
        (co ? '<br>Position relative to board centre: <b>Y = ' + fmtNum(p.y_m, 3) + ' m; X = ' + fmtNum(p.x_m, 3) + ' m</b>' : '') +
        '<br>Area: ' + fmtNum(p.area_m2, 3) + ' m²<br>Mean confidence for the photo: ' + conf);
      if (p.idx) layer.bindTooltip(String(p.idx), { permanent: true, direction: 'center', className: 'vung-so' });
    }
  });
}
function themLanGui(o) {
  const layer = veLopRac(o.regions);
  const item = { id: o.id, at: o.captured_at, n: (typeof o.n_regions === 'number') ? o.n_regions : o.n_instances, total: o.total_area_m2, layer: layer, visible: true,
    xuLyXong: o.processed_at, xuLyMs: o.processing_ms, hienSau: null };
  obsList.push(item);
  layer.addTo(map);
  veLaiLichSu();
  return item;
}
function veLaiLichSu() {
  const box = $('obs-list');
  box.innerHTML = '';
  if (!obsList.length) { box.innerHTML = '<span class="hint">No submissions yet.</span>'; return; }
  obsList.forEach((it, i) => {
    const moi = (i === obsList.length - 1);
    it.layer.setStyle(moi ? STYLE_MOI : STYLE_CU);
    if (moi) it.layer.bringToFront();
  });
  for (let i = obsList.length - 1; i >= 0; i--) {   // hiện lần mới nhất ở trên
    const it = obsList[i], moi = (i === obsList.length - 1);
    const row = document.createElement('div');
    row.className = 'obs-item';
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.checked = it.visible; cb.id = 'obs-cb-' + i;
    cb.addEventListener('change', () => {
      it.visible = cb.checked;
      if (it.visible) it.layer.addTo(map); else map.removeLayer(it.layer);
    });
    const sw = document.createElement('span');
    sw.className = 'sw'; sw.style.background = moi ? '#ef4444' : '#fcd34d';
    const lb = document.createElement('label');
    lb.htmlFor = cb.id;
    let txt = fmtGio(it.at) + ' — ' + (it.n || 0) + ' regions, ' + fmtNum(it.total, 2) + ' m²' + (moi ? ' (latest)' : '');
    const gio = [];
    if (typeof it.xuLyMs === 'number') gio.push('server processing ' + fmtNum(it.xuLyMs / 1000, 1) + ' s');
    if (typeof it.hienSau === 'number') gio.push('shown on map after ' + fmtNum(it.hienSau, 1) + ' s');
    if (gio.length) txt += ' · ⏱ ' + gio.join(', ');
    lb.textContent = txt;
    row.appendChild(cb); row.appendChild(sw); row.appendChild(lb);
    box.appendChild(row);
  }
}

$('btn-observe').addEventListener('click', () => withBusy($('btn-observe'), async () => {
  showMsg('msg4', '', '');
  if (S.dirty) { showMsg('msg4', 'err', 'You changed the position/heading after saving. Save again in step 3 first.'); return; }
  if (!trashSel) { showMsg('msg4', 'err', 'Choose a trash photo first.'); return; }
  let r;
  try { r = await postJson('/api/lab/board/observe', { sample_id: trashSel }); }
  catch (e) { showMsg('msg4', 'err', e.message); return; }
  const d = r.data || {};
  if (r.status !== 200 || !d.ok) { showMsg('msg4', 'err', errText(r)); return; }
  const regions = d.regions || { type: 'FeatureCollection', features: [] };
  const item = themLanGui({ id: d.observation_id, captured_at: d.captured_at, n_instances: d.n_instances, n_regions: d.n_regions,
    total_area_m2: d.total_area_m2, regions: regions, processed_at: d.processed_at, processing_ms: d.processing_ms });
  $('r4').style.display = 'block';
  const sum = $('r4-sum');
  const coVung = (regions.features || []).some((x) => x && x.geometry);
  let html;
  const soVung = (typeof d.n_regions === 'number') ? d.n_regions : d.n_instances;
  if (!coVung) html = '<div class="msg info"><b>The model detected no trash in the photo.</b> (Processed normally in ' + fmtNum(d.inference_ms, 0) + ' ms.)</div>';
  else html = '<div class="msg ok">Found <b>' + esc(soVung) + '</b> trash region(s), total area <b>' + esc(fmtNum(d.total_area_m2, 3)) +
    ' m²</b> (server processing ' + esc(fmtNum((d.processing_ms || 0) / 1000, 1)) + ' s, of which the model ran ' + esc(fmtNum(d.inference_ms, 0)) + ' ms). Click a red region for details.</div>' + danhSachVungHtml(regions);
  if (d.dropped_points > 0) html += '<div class="msg warn">' + esc(d.dropped_points) + ' point(s) of the trash regions lie outside the computable area (near the horizon) and were ignored.</div>';
  (d.warnings || []).filter((w) => coVung || !/no trash detected/i.test(String(w))).forEach((w) => { html += '<div class="msg warn">' + esc(w) + '</div>'; });
  sum.innerHTML = html;
  if (d.annotated_jpg_b64) { $('r4-img').src = 'data:image/jpeg;base64,' + d.annotated_jpg_b64; $('r4-img').style.display = 'block'; }
  else { $('r4-img').removeAttribute('src'); $('r4-img').style.display = 'none'; }
  if (coVung) {
    const b = item.layer.getBounds();
    if (b.isValid()) map.fitBounds(b, { padding: [60, 60], maxZoom: 21 });
  }
}));

$('btn-clear').addEventListener('click', () => withBusy($('btn-clear'), async () => {
  if (!window.confirm('Delete all submissions? This cannot be undone.')) return;
  let r;
  try { r = await api('/api/lab/board/observations', { method: 'DELETE' }); }
  catch (e) { showMsg('msg4', 'err', e.message); return; }
  if (r.status !== 200 || !r.data || !r.data.ok) { showMsg('msg4', 'err', errText(r)); return; }
  obsList.forEach((it) => map.removeLayer(it.layer));
  obsList = [];
  veLaiLichSu();
  $('r4').style.display = 'none';
  showMsg('msg4', 'ok', 'All submissions deleted.');
}));

// ====== Khởi động: tải ảnh mẫu và trạng thái của phiên này từ server ======
let daKhoiDong = false;

async function khoiDong() {
  await kiemTraSucKhoe();
  if ($('st-server').classList.contains('bad')) {
    showMsg('msg1', 'err', MSG_MANG);
    return;
  }
  daKhoiDong = true;
  showMsg('msg1', '', '');
  await taiMau();
  const coHC = await taiHieuChinhDaLuu(true);
  if (coHC) { lockStep('s4', false); openStep('s4'); kiemTraSucKhoe(); }
  let r;
  try { r = await api('/api/lab/board/observations'); }
  catch (e) { showMsg('msg4', 'err', e.message); return; }
  if (r.status === 200 && r.data && r.data.ok) {
    (r.data.observations || []).forEach((o) => themLanGui({
      id: o.id, captured_at: o.captured_at, n_instances: o.n_instances, n_regions: o.n_regions,
      total_area_m2: o.total_area_m2, regions: o.regions, processed_at: o.processed_at, processing_ms: o.processing_ms
    }));
  }
}
khoiDong();
// Kiểm tra dịch vụ định kỳ; nếu lúc mở trang dịch vụ chưa chạy thì tự nạp lại khi nó lên
setInterval(async () => {
  await kiemTraSucKhoe();
  if (!daKhoiDong && !$('st-server').classList.contains('bad')) khoiDong();
}, 10000);

// ====== Thông báo nhỏ ======
let toastTimer = null;
function hienToast(text) {
  const t = $('toast');
  t.textContent = text;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 4500);
}
