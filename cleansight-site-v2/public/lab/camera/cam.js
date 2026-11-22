// Camera lab: camera nhà gửi ảnh về dịch vụ (research/cleansight_demo_api/cam.py); trang này đăng nhập bằng mã truy cập,
// hiện khung hình mới nhất, lịch sử, và vẽ vùng rác lên bản đồ. Giao diện/bản đồ/mũi tên vị trí lấy từ Board lab (/lab/board/lab.js).
// Mã truy cập được kiểm Ở MÁY CHỦ; trang chỉ giữ token ngắn hạn (sessionStorage của tab). Địa chỉ dịch vụ: /lab/board/lab-config.js.
"use strict";
const $ = (id) => document.getElementById(id);
const API_BASE = String(window.LAB_API_URL || '').replace(/\/+$/, '');
const MSG_MANG = 'Cannot reach the live demo. It runs on the team laptop and is only available while that laptop is on; please try again later.';
const DEFAULT_LATLNG = [10.7769, 106.7009];
const ARROW_LEN_M = 2;        // mũi tên dài 2 m ngoài đời thật
const NUDGE_M = 0.05;         // nút nhích 5 cm
const M_PER_DEG = 111320;
const POLL_MS = 10000;        // hỏi khung mới nhất mỗi 10 giây (camera gửi ~1 phút/lần)
const FRESH_S = 180;          // quá 3 phút không có khung mới -> báo vàng
const TOKEN_KEY = 'cleansight_cam_token';
const TOKEN_RE = /^[A-Za-z0-9_-]{20,128}$/;
const STATUS_TEXT = {
  analysed: 'analysed',
  busy: 'saved, not analysed (the AI was busy)',
  not_ready: 'saved, not analysed (the AI was starting)',
  aspect_mismatch: 'outlined, but not placed on the map (different shape from the calibration photo)',
  error: 'saved, analysis failed'
};

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function showMsg(id, kind, text) {
  const el = $(id);
  el.innerHTML = text ? '<div class="msg ' + kind + '">' + esc(text) + '</div>' : '';
}
function normAz(a) { return ((a % 360) + 360) % 360; }
function fmtNum(v, nd) { return (typeof v === 'number' && isFinite(v)) ? v.toLocaleString('en-GB', { maximumFractionDigits: nd }) : '?'; }
function fmtGio(s) { const d = new Date(s); return isNaN(d.getTime()) ? String(s || '?') : d.toLocaleString('en-GB'); }
function fmtTuoi(sec) {
  if (sec < 60) return Math.max(0, Math.round(sec)) + ' s ago';
  if (sec < 3600) return Math.round(sec / 60) + ' min ago';
  return Math.floor(sec / 3600) + ' h ' + Math.round((sec % 3600) / 60) + ' min ago';
}
function pxText(v) { return (typeof v === 'number' ? v.toFixed(1) : '?') + ' px'; }
async function withBusy(btn, fn) {
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span>Processing…';
  try { return await fn(); }
  finally { btn.disabled = false; btn.innerHTML = old; }
}
let toastTimer = null;
function hienToast(text) {
  const t = $('toast');
  t.textContent = text;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3500);
}
function phongTo(src) { $('lb-img').src = src; $('lb').classList.add('show'); }
$('lb').addEventListener('click', () => $('lb').classList.remove('show'));
$('frame-img').addEventListener('click', (e) => e.target.src && phongTo(e.target.src));
$('r1-img').addEventListener('click', (e) => e.target.src && phongTo(e.target.src));

// ====== Trạng thái ======
const S = {
  token: '',
  frames: [], nextBefore: null,
  latestId: null, shownId: null, lastReceived: null,
  following: true, kind: 'annotated',
  calib: null, calibStamp: null,
  calibId: null, latlng: null, az: 0, fpSeq: 0, fpTimer: null,
  imgSeq: 0, imgUrl: null,
  regionLayer: null,
  fitted: false,
  timers: [],
  running: false
};
try { const t = sessionStorage.getItem(TOKEN_KEY) || ''; if (TOKEN_RE.test(t)) S.token = t; } catch (e) { S.token = ''; }

// ====== Gọi API ======
// Trả {status, data, retryAfter}; lỗi mạng ném Error(MSG_MANG). 401 (không phải lúc đăng nhập) -> quay về màn nhập mã.
async function api(path, opts, noAuth) {
  const o = Object.assign({}, opts || {});
  o.headers = Object.assign({}, o.headers || {});
  if (!noAuth && S.token) o.headers['X-Cam-Token'] = S.token;
  o.credentials = 'omit'; o.cache = 'no-store'; o.referrerPolicy = 'no-referrer';
  let resp;
  try { resp = await fetch(API_BASE + path, o); } catch (e) { throw new Error(MSG_MANG); }
  let data = null;
  try { data = await resp.json(); } catch (e) { data = null; }
  if (resp.status === 401 && !noAuth) khoa('Please enter the access code again.');
  return { status: resp.status, data: data, retryAfter: resp.headers.get('Retry-After') };
}
function postJson(path, obj, noAuth) {
  return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) }, noAuth);
}
function errText(r) {
  if (r.status === 429) return ((r.data && r.data.error) || 'Too many requests.') + (r.retryAfter ? ' Please wait about ' + r.retryAfter + ' seconds.' : '');
  if (r.data && typeof r.data.error === 'string' && r.data.error) return r.data.error;
  if (r.status === 404) return 'Data not found on the server (HTTP 404).';
  if (r.status === 422) return 'The data sent is invalid (HTTP 422).';
  return 'Server error (HTTP ' + r.status + ').';
}
// Ảnh cần header token nên tải bằng fetch rồi dùng blob: URL (thẻ <img> không gửi được header)
async function taiAnh(id, kind) {
  let resp;
  try {
    resp = await fetch(API_BASE + '/api/cam/frames/' + encodeURIComponent(id) + '/image?kind=' + kind,
      { headers: { 'X-Cam-Token': S.token }, credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer' });
  } catch (e) { return null; }
  if (resp.status === 401) { khoa('Please enter the access code again.'); return null; }
  if (!resp.ok) return null;
  return URL.createObjectURL(await resp.blob());
}

// ====== Accordion ======
document.querySelectorAll('.step-head').forEach((h) => {
  h.addEventListener('click', () => $(h.dataset.step).classList.toggle('open'));
});

// ====== Thanh trạng thái ======
function setChip(id, cls, text) { const el = $(id); el.className = 'chip ' + cls; el.textContent = text; }
async function kiemTraSucKhoe() {
  try {
    const r = await api('/api/health', {}, true);
    if (r.status === 200 && r.data && r.data.status === 'ok') {
      setChip('st-server', 'ok', 'online');
      setChip('st-model', r.data.ready ? 'ok' : 'wait', r.data.ready ? 'ready' : 'starting…');
      return true;
    }
    setChip('st-server', 'bad', 'error (HTTP ' + r.status + ')');
  } catch (e) {
    setChip('st-server', 'bad', 'offline');
    setChip('st-model', 'wait', '?');
  }
  return false;
}
function capNhatChipKhung() {
  if (!S.lastReceived) { setChip('st-frame', 'wait', 'none yet'); return; }
  const age = (Date.now() - Date.parse(S.lastReceived)) / 1000;
  if (!isFinite(age)) { setChip('st-frame', 'wait', '?'); return; }
  setChip('st-frame', age <= FRESH_S ? 'ok' : 'wait', fmtTuoi(age) + (age <= FRESH_S ? '' : ' (no new frame)'));
}

// ====== Bản đồ ======
const map = L.map('map', { zoomControl: true }).setView(DEFAULT_LATLNG, 20);
L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
  subdomains: 'abc', maxZoom: 24, maxNativeZoom: 20,
  attribution: '&copy; <a href="https://www.openstreetmap.fr" target="_blank" rel="noopener">OpenStreetMap France</a> | &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
}).addTo(map);
L.control.scale({ metric: true, imperial: false, position: 'bottomleft' }).addTo(map);

// ====== Vùng rác của một khung ======
const STYLE_MOI = { color: '#b91c1c', weight: 3, fillColor: '#ef4444', fillOpacity: 0.45 };
function danhSachVungHtml(regions) {
  const fs = ((regions || {}).features || []).filter((f) => f && f.geometry);
  if (!fs.length) return '';
  let h = '<div style="margin-top:6px;font-size:14px;line-height:1.6"><b>Position relative to board centre</b> (Y = along +Y, X = along +X; up = +Y, right = +X):<br>';
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
    style: () => STYLE_MOI,
    onEachFeature: (f, layer) => {
      const p = f.properties || {};
      const conf = (typeof p.confidence === 'number') ? fmtNum(p.confidence * 100, 0) + ' %' : 'n/a';
      const co = (typeof p.y_m === 'number' && typeof p.x_m === 'number');
      layer.bindPopup('<b>Trash region' + (p.idx ? ' no. ' + esc(p.idx) : '') + '</b>' +
        (co ? '<br>Position relative to board centre: <b>Y = ' + fmtNum(p.y_m, 3) + ' m; X = ' + fmtNum(p.x_m, 3) + ' m</b>' : '') +
        '<br>Area: ' + fmtNum(p.area_m2, 3) + ' m²<br>Mean confidence for the frame: ' + conf);
      if (p.idx) layer.bindTooltip(String(p.idx), { permanent: true, direction: 'center', className: 'vung-so' });
    }
  });
}
function xoaVungRac() { if (S.regionLayer) { map.removeLayer(S.regionLayer); S.regionLayer = null; } }

// ====== Hiện một khung hình ======
function capNhatNutKhung() {
  $('btn-live').style.display = (S.latestId && S.shownId && S.shownId !== S.latestId) ? 'inline-block' : 'none';
  document.querySelectorAll('#kind-row .kind').forEach((b) => b.classList.toggle('on', b.dataset.kind === S.kind));
  document.querySelectorAll('.hist-item').forEach((el) => el.classList.toggle('sel', el.dataset.id === S.shownId));
}
async function datAnh(frame) {
  const seq = ++S.imgSeq;
  const kind = (S.kind === 'annotated' && frame.has_annotated) ? 'annotated' : 'original';
  const url = await taiAnh(frame.id, kind);
  if (seq !== S.imgSeq) { if (url) URL.revokeObjectURL(url); return; }   // đã có yêu cầu mới hơn
  const img = $('frame-img');
  if (!url) { img.style.display = 'none'; img.removeAttribute('src'); return; }
  const old = S.imgUrl;
  S.imgUrl = url;
  img.src = url;
  img.alt = (kind === 'annotated' ? 'Camera frame with the trash outlined by the AI' : 'Original camera frame') + ' (click to enlarge)';
  img.style.display = 'block';
  if (old) URL.revokeObjectURL(old);
}
function hienKhung(frame, fit) {
  S.shownId = frame.id;
  const st = String(frame.status || '');
  $('frame-status').textContent = 'Frame received ' + fmtGio(frame.received_at) + ' · ' + frame.width + '×' + frame.height + ' · ' + (STATUS_TEXT[st] || st);
  // vùng rác trên bản đồ
  xoaVungRac();
  const regions = frame.regions || { type: 'FeatureCollection', features: [] };
  const coVung = (regions.features || []).some((x) => x && x.geometry);
  if (coVung) {
    S.regionLayer = veLopRac(regions).addTo(map);
    if (fit && S.calibId === null) { const b = S.regionLayer.getBounds(); if (b.isValid()) map.fitBounds(b, { padding: [60, 60], maxZoom: 21 }); }
  }
  // tóm tắt
  let html = '';
  if (st === 'analysed') {
    if (!coVung) html += '<div class="msg info"><b>The model detected no trash in this frame.</b> (Model ran in ' + esc(fmtNum(frame.inference_ms, 0)) + ' ms.)</div>';
    else html += '<div class="msg ok">Found <b>' + esc(frame.n_regions) + '</b> trash region(s), total area <b>' + esc(fmtNum(frame.total_area_m2, 3)) +
      ' m²</b> (the model ran ' + esc(fmtNum(frame.inference_ms, 0)) + ' ms). Click a red region on the map for details.</div>' + danhSachVungHtml(regions);
  } else {
    html += '<div class="msg warn">' + esc(STATUS_TEXT[st] || st) + '</div>';
  }
  if (frame.provisional_calibration) html += '<div class="msg warn">This frame was placed on the map with the TEMPORARY calibration: positions are only for trying the drawing.</div>';
  (frame.warnings || []).filter((w) => coVung || !/no trash detected/i.test(String(w))).forEach((w) => { html += '<div class="msg warn">' + esc(w) + '</div>'; });
  $('frame-sum').innerHTML = html;
  capNhatNutKhung();
  datAnh(frame);
}

// ====== Khung mới nhất (hỏi định kỳ) ======
async function taiMoiNhat(first) {
  let r;
  try { r = await api('/api/cam/latest'); }
  catch (e) { $('frame-status').textContent = e.message; return; }
  if (r.status !== 200 || !r.data || !r.data.ok) { if (r.status !== 401) $('frame-status').textContent = errText(r); return; }
  capNhatHieuChinh(r.data.calibration);
  const frame = r.data.frame;
  if (!frame) {
    S.lastReceived = null; S.latestId = null;
    if (!S.shownId) $('frame-status').textContent = 'No frame received yet. The camera sends one about once a minute; this page updates by itself.';
    capNhatChipKhung();
    return;
  }
  const moi = frame.id !== S.latestId;
  S.latestId = frame.id; S.lastReceived = frame.received_at;
  capNhatChipKhung();
  if (moi && !first) taiLichSu(true);
  if (S.following && frame.id !== S.shownId) hienKhung(frame, first || moi);
  else capNhatNutKhung();
}

// ====== Lịch sử ======
function veLichSu() {
  const box = $('hist-list');
  box.innerHTML = '';
  if (!S.frames.length) { box.innerHTML = '<span class="hint">No frames yet.</span>'; }
  S.frames.forEach((f) => {
    const row = document.createElement('div');
    row.className = 'hist-item';
    row.dataset.id = f.id;
    row.tabIndex = 0;
    row.setAttribute('role', 'button');
    const when = document.createElement('span'); when.className = 'when'; when.textContent = fmtGio(f.received_at);
    const st = document.createElement('span');
    st.className = 'st' + (f.status === 'analysed' ? '' : ' bad');
    st.textContent = f.status === 'analysed' ? (f.n_regions + ' regions, ' + fmtNum(f.total_area_m2, 2) + ' m²') : (STATUS_TEXT[f.status] || f.status);
    row.appendChild(when); row.appendChild(st);
    if (f.provisional_calibration) { const t = document.createElement('span'); t.className = 'tmp'; t.textContent = 'temporary calibration'; row.appendChild(t); }
    const chon = () => chonKhung(f.id);
    row.addEventListener('click', chon);
    row.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chon(); } });
    box.appendChild(row);
  });
  $('btn-older').style.display = S.nextBefore ? 'inline-block' : 'none';
  $('b2').textContent = S.frames.length ? S.frames.length + (S.nextBefore ? '+' : '') + (S.frames.length === 1 && !S.nextBefore ? ' frame' : ' frames') : '';
  capNhatNutKhung();
}
async function taiLichSu(reset) {
  const q = new URLSearchParams({ limit: '24' });
  if (!reset && S.nextBefore) q.set('before', S.nextBefore);
  let r;
  try { r = await api('/api/cam/frames?' + q.toString()); } catch (e) { return; }
  if (r.status !== 200 || !r.data || !r.data.ok) return;
  S.frames = reset ? r.data.frames : S.frames.concat(r.data.frames);
  S.nextBefore = r.data.next_before;
  veLichSu();
}
async function chonKhung(id) {
  let r;
  try { r = await api('/api/cam/frames/' + encodeURIComponent(id)); }
  catch (e) { hienToast(e.message); return; }
  if (r.status !== 200 || !r.data || !r.data.ok) { hienToast(errText(r)); return; }
  S.following = false; $('follow').checked = false;
  hienKhung(r.data.frame, true);
}
$('btn-older').addEventListener('click', () => withBusy($('btn-older'), () => taiLichSu(false)));
$('follow').addEventListener('change', () => {
  S.following = $('follow').checked;
  if (S.following) { S.shownId = null; taiMoiNhat(true); }
});
$('btn-live').addEventListener('click', () => { S.following = true; $('follow').checked = true; S.shownId = null; taiMoiNhat(true); });
$('btn-refresh').addEventListener('click', () => withBusy($('btn-refresh'), async () => { await kiemTraSucKhoe(); await taiMoiNhat(false); await taiLichSu(true); }));
document.querySelectorAll('#kind-row .kind').forEach((b) => b.addEventListener('click', async () => {
  S.kind = b.dataset.kind;
  capNhatNutKhung();
  const f = S.frames.find((x) => x.id === S.shownId);
  if (f) datAnh(f);
  else if (S.shownId) { const r = await api('/api/cam/frames/' + encodeURIComponent(S.shownId)); if (r.data && r.data.frame) datAnh(r.data.frame); }
}));

// ====== Hiệu chỉnh: hiển thị, vùng camera thấy ======
const fpLayer = L.layerGroup().addTo(map);
let fpGeo = null;
function veFootprint(data, fit) {
  fpLayer.clearLayers();
  const gj = L.geoJSON(data, {
    interactive: false,
    filter: (f) => f && f.geometry,
    style: () => ({ color: '#15803d', weight: 2, fillColor: '#86efac', fillOpacity: 0.3 }),
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
  if (fit) { const b = gj.getBounds(); if (b.isValid()) map.fitBounds(b, { padding: [40, 40], maxZoom: 21 }); }
}
async function taiFootprintDaLuu(fit) {
  try {
    const r = await api('/api/cam/footprint?max_range_m=12');
    if (r.status === 200 && r.data && r.data.type === 'FeatureCollection') veFootprint(r.data, fit);
  } catch (e) { /* bỏ qua: chỉ là phần xem trước */ }
}
function capNhatHieuChinh(c) {
  if (!c) return;
  const stamp = c.created_at || '';
  const doi = stamp !== S.calibStamp;
  S.calib = c; S.calibStamp = stamp;
  setChip('st-calib', c.provisional ? 'wait' : 'ok', c.provisional ? 'TEMPORARY' : 'calibrated');
  $('b3').textContent = c.provisional ? 'temporary' : '✔ calibrated';
  const ll = c.marker_latlon || [];
  $('calib-summary').className = 'msg ' + (c.provisional ? 'warn' : 'ok');
  $('calib-summary').textContent = (c.provisional ? 'TEMPORARY calibration (not this camera). ' : 'Calibrated. ') + (c.source || '') +
    ' Board at ' + (ll.length === 2 ? Number(ll[0]).toFixed(6) + ', ' + Number(ll[1]).toFixed(6) : '?') +
    ', +Y heading ' + Math.round(c.azimuth_deg) + '°, field of view ' + (typeof c.fov_deg === 'number' ? c.fov_deg.toFixed(1) : '?') + '°.';
  const pw = $('prov-warn');
  pw.style.display = c.provisional ? 'block' : 'none';
  pw.textContent = 'The calibration is TEMPORARY (made from a sample board photo, not from this camera), so positions on the map are only for trying the drawing. Calibrate this camera in section 3.';
  if (doi && S.calibId === null) { taiFootprintDaLuu(!S.fitted); S.fitted = true; }
}

// ====== Hiệu chỉnh: dò bảng trong khung đang xem ======
function hienKetQuaDo(d, bi422) {
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
  const nguon = { input: 'entered by you', 'default': 'default 66° (no lens information)' };
  if (!bi422) {
    $('r1-fov').textContent = (typeof d.fov_deg === 'number' ? d.fov_deg.toFixed(1) + '°' : '?');
    $('r1-src').textContent = '— ' + (nguon[d.fov_source] || d.fov_source || '');
  } else { $('r1-fov').textContent = '—'; $('r1-src').textContent = ''; }
  $('r1-h').textContent = (!bi422 && typeof d.camera_height_m_est === 'number') ? fmtNum(d.camera_height_m_est, 2) + ' m' : '—';
  const ul = $('r1-warn');
  ul.innerHTML = '';
  const ws = (d.warnings || []);
  ul.style.display = ws.length ? 'block' : 'none';
  ws.forEach((w) => { const li = document.createElement('li'); li.textContent = w; ul.appendChild(li); });
}

// ====== Marker + mũi tên vị trí bảng (như Board lab) ======
const pose = { mk: null, line: null, head: null, handle: null, draggingHandle: false };
function offsetLL(ll, dN, dE) { return [ll[0] + dN / M_PER_DEG, ll[1] + dE / (M_PER_DEG * Math.cos(ll[0] * Math.PI / 180))]; }
function tipLL(ll, az, len) { const a = az * Math.PI / 180; return offsetLL(ll, len * Math.cos(a), len * Math.sin(a)); }
function azFromTo(a, b) {
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
  $('pos-val').textContent = S.latlng ? 'Position: ' + S.latlng[0].toFixed(6) + ', ' + S.latlng[1].toFixed(6) : 'Position: —';
}
function dungLopTuThe() {
  if (!pose.mk) {
    pose.mk = L.marker(S.latlng, { draggable: true, keyboard: false, icon: L.divIcon({ className: '', html: '<div class="pin-board"></div>', iconSize: [16, 16], iconAnchor: [8, 8] }) }).addTo(map);
    pose.line = L.polyline([S.latlng, S.latlng], { color: '#1d4ed8', weight: 4, interactive: false }).addTo(map);
    pose.head = L.polyline([S.latlng, S.latlng, S.latlng], { color: '#1d4ed8', weight: 4, interactive: false }).addTo(map);
    pose.handle = L.marker(S.latlng, { draggable: true, keyboard: false, icon: L.divIcon({ className: '', html: '<div class="pin-handle"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }) }).addTo(map);
    pose.handle.bindTooltip('+Y', { permanent: true, direction: 'right', offset: [12, 0], className: 'lbl' });
    pose.mk.on('drag', () => { const p = pose.mk.getLatLng(); datTuThe([p.lat, p.lng], null, true); });
    pose.handle.on('dragstart', () => { pose.draggingHandle = true; });
    pose.handle.on('drag', () => { const p = pose.handle.getLatLng(); const a = azFromTo(S.latlng, [p.lat, p.lng]); if (a !== null) datTuThe(null, a); });
    pose.handle.on('dragend', () => { pose.draggingHandle = false; veMuiTen(); });
  }
  pose.mk.setLatLng(S.latlng);
  veMuiTen();
  capNhatSoDoc();
}
function xoaLopTuThe() {
  ['mk', 'line', 'head', 'handle'].forEach((k) => { if (pose[k]) { map.removeLayer(pose[k]); pose[k] = null; } });
  pose.draggingHandle = false;
}
function datTuThe(ll, az, daKeoMarker) {
  if (ll) S.latlng = ll;
  if (az !== null && az !== undefined) S.az = normAz(az);
  if (pose.mk && ll && !daKeoMarker) pose.mk.setLatLng(S.latlng);
  veMuiTen();
  capNhatSoDoc();
  if (S.calibId) lenLichFootprint();
}
map.on('click', (e) => { if (S.calibId) datTuThe([e.latlng.lat, e.latlng.lng], null); });
document.querySelectorAll('[data-dn]').forEach((b) => b.addEventListener('click', () => {
  if (!S.calibId || !S.latlng) return;
  datTuThe(offsetLL(S.latlng, Number(b.dataset.dn) * NUDGE_M, Number(b.dataset.de) * NUDGE_M), null);
}));
document.querySelectorAll('[data-rot]').forEach((b) => b.addEventListener('click', () => {
  if (!S.calibId || !S.latlng) return;
  datTuThe(null, S.az + Number(b.dataset.rot));
}));

function lenLichFootprint() { clearTimeout(S.fpTimer); S.fpTimer = setTimeout(layFootprintXemTruoc, 400); }
async function layFootprintXemTruoc() {
  if (!S.calibId || !S.latlng) return;
  const seq = ++S.fpSeq;
  const q = new URLSearchParams({ calibration_id: S.calibId, lat: S.latlng[0].toFixed(8), lon: S.latlng[1].toFixed(8), azimuth_deg: S.az.toFixed(3), max_range_m: '12' });
  let r;
  try { r = await api('/api/cam/footprint?' + q.toString()); }
  catch (e) { if (seq === S.fpSeq) showMsg('fp-msg', 'err', e.message); return; }
  if (seq !== S.fpSeq || !S.calibId) return;
  if (r.status === 404) { showMsg('fp-msg', 'err', 'This detection is no longer on the server. Detect the board again.'); return; }
  if (r.status !== 200 || !r.data || r.data.type !== 'FeatureCollection') { showMsg('fp-msg', 'err', errText(r)); return; }
  showMsg('fp-msg', '', '');
  veFootprint(r.data, false);
}

$('btn-detect').addEventListener('click', () => withBusy($('btn-detect'), async () => {
  showMsg('msg-cal', '', ''); showMsg('save-msg', '', '');
  const size = parseFloat($('f-size').value);
  if (!(size > 0)) { showMsg('msg-cal', 'err', 'Enter the real board side length (mm) as a number above 0.'); return; }
  const body = { frame_id: S.shownId || 'latest', marker_size_mm: size };
  const fovTxt = $('f-fov').value.trim();
  if (fovTxt !== '') {
    const fv = parseFloat(fovTxt);
    if (!(fv > 0 && fv < 180)) { showMsg('msg-cal', 'err', 'Field of view must be between 0 and 180 degrees (or leave blank).'); return; }
    body.fov_deg = fv;
  }
  let r;
  try { r = await postJson('/api/cam/calibration/detect', body); }
  catch (e) { showMsg('msg-cal', 'err', e.message); return; }
  const d = r.data || {};
  if (r.status !== 200 || !d.ok) {
    if (r.status !== 401) { if (d.overlay_jpg_b64 || typeof d.side_px_min === 'number') hienKetQuaDo(d, true); showMsg('msg-cal', 'err', errText(r)); }
    return;
  }
  hienKetQuaDo(d, false);
  showMsg('msg-cal', 'ok', 'Board detected in the frame shown. Now set its position on the map below.');
  S.calibId = d.calibration_id;
  const c = S.calib || {};
  S.latlng = (c.marker_latlon && c.marker_latlon.length === 2) ? [Number(c.marker_latlon[0]), Number(c.marker_latlon[1])] : DEFAULT_LATLNG.slice();
  S.az = normAz(Number(c.azimuth_deg) || 0);
  xoaVungRac();
  $('edit-block').style.display = 'block';
  dungLopTuThe();
  map.setView(S.latlng, 20);
  lenLichFootprint();
  $('edit-block').scrollIntoView({ block: 'nearest' });
}));

function thoatChinhSua() {
  S.calibId = null;
  xoaLopTuThe();
  $('edit-block').style.display = 'none';
  showMsg('fp-msg', '', '');
  clearTimeout(S.fpTimer);
}
$('btn-cancel').addEventListener('click', () => {
  thoatChinhSua();
  showMsg('save-msg', '', '');
  taiFootprintDaLuu(false);
  if (S.shownId) chonKhungLaiVung(S.shownId);
});
async function chonKhungLaiVung(id) {   // vẽ lại vùng rác của khung đang xem sau khi thoát chỉnh sửa
  const r = await api('/api/cam/frames/' + encodeURIComponent(id));
  if (r.data && r.data.frame) hienKhung(r.data.frame, false);
}
$('btn-save').addEventListener('click', () => withBusy($('btn-save'), async () => {
  showMsg('save-msg', '', '');
  if (!S.calibId || !S.latlng) { showMsg('save-msg', 'err', 'No board detection yet. Detect the board first.'); return; }
  let r;
  try { r = await postJson('/api/cam/calibration/save', { calibration_id: S.calibId, lat: S.latlng[0], lon: S.latlng[1], azimuth_deg: S.az }); }
  catch (e) { showMsg('save-msg', 'err', e.message); return; }
  if (r.status !== 200 || !r.data || !r.data.ok) { if (r.status !== 401) showMsg('save-msg', 'err', errText(r)); return; }
  const shown = S.shownId;
  thoatChinhSua();
  S.calibStamp = null;
  capNhatHieuChinh(r.data.calibration);
  hienToast('Calibration saved. New frames use it; frames already stored keep the calibration they were analysed with.');
  showMsg('msg-cal', 'ok', 'Calibration saved. New frames will use it; frames already stored keep the calibration they were analysed with.');
  if (shown) chonKhungLaiVung(shown);
}));

// ====== Đăng nhập / khoá ======
function dungTimer() { S.timers.forEach((t) => clearInterval(t)); S.timers = []; S.running = false; }
function xoaDuLieuTrang() {
  xoaVungRac(); xoaLopTuThe(); fpLayer.clearLayers();
  if (S.imgUrl) { URL.revokeObjectURL(S.imgUrl); S.imgUrl = null; }
  const img = $('frame-img'); img.removeAttribute('src'); img.style.display = 'none';
  $('r1-img').removeAttribute('src'); $('r1').style.display = 'none'; $('edit-block').style.display = 'none';
  $('frame-sum').innerHTML = ''; $('hist-list').innerHTML = ''; $('frame-status').textContent = 'Waiting for the first frame…';
  $('prov-warn').style.display = 'none'; $('calib-summary').textContent = 'Loading…'; showMsg('msg-cal', '', ''); showMsg('save-msg', '', '');
  S.frames = []; S.nextBefore = null; S.latestId = S.shownId = S.lastReceived = null; S.calib = S.calibStamp = null; S.calibId = null; S.fitted = false;
  S.following = true; $('follow').checked = true;
  setChip('st-calib', 'wait', '…'); setChip('st-frame', 'wait', '…');
}
function khoa(thongBao) {
  S.token = '';
  try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) { /* bỏ qua */ }
  dungTimer();
  xoaDuLieuTrang();
  $('login').classList.remove('hide');
  $('code').value = '';
  showMsg('login-msg', thongBao ? 'info' : '', thongBao || '');
  $('code').focus();
}
$('btn-lock').addEventListener('click', () => khoa(''));
$('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const code = $('code').value;
  if (!code) { showMsg('login-msg', 'err', 'Enter the access code.'); return; }
  await withBusy($('btn-login'), async () => {
    let r;
    try { r = await postJson('/api/cam/login', { code: code }, true); }
    catch (err) { showMsg('login-msg', 'err', err.message); return; }
    if (r.status === 200 && r.data && r.data.ok && TOKEN_RE.test(r.data.token || '')) {
      S.token = r.data.token;
      try { sessionStorage.setItem(TOKEN_KEY, S.token); } catch (err) { /* token chỉ nằm trong bộ nhớ trang */ }
      $('code').value = '';
      showMsg('login-msg', '', '');
      $('login').classList.add('hide');
      batDau();
    } else if (r.status === 401) {
      showMsg('login-msg', 'err', 'Wrong access code.');
      $('code').select();
    } else {
      showMsg('login-msg', 'err', errText(r));
    }
  });
});

// ====== Khởi động ======
async function nhipDinhKy() {
  if (document.visibilityState !== 'visible' || !S.token) return;
  const ok = await kiemTraSucKhoe();
  if (ok && S.token) taiMoiNhat(false);
}
async function batDau() {
  if (S.running) return;
  S.running = true;
  await kiemTraSucKhoe();
  await taiMoiNhat(true);
  taiLichSu(true);
  S.timers.push(setInterval(nhipDinhKy, POLL_MS));
  S.timers.push(setInterval(capNhatChipKhung, 5000));
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && S.token && S.running) nhipDinhKy(); });

if (S.token) { $('login').classList.add('hide'); batDau(); }
else { $('login').classList.remove('hide'); $('code').focus(); kiemTraSucKhoe(); }
