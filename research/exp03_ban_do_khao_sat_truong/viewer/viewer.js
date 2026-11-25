/* Bản trình bày khảo sát: chỉ ĐỌC window.SURVEY (data.js). Mở được từ file://, không gọi máy chủ nào. */
(function () {
  'use strict';
  var D = window.SURVEY || { title: '', totals: {}, notes: [], spots: [], tiles: {} };
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fmt(v, d) { return Number(v).toLocaleString('vi-VN', { maximumFractionDigits: d == null ? 2 : d }); }

  document.title = D.title;
  $('title').textContent = D.title;
  var t = D.totals || {};
  $('totals').innerHTML =
    '<div class="kpi"><b>' + fmt(t.area_m2 || 0) + ' m²</b><span>diện tích rác ở các điểm đã chụp</span></div>' +
    '<div class="kpi"><b>' + (t.spots || 0) + '</b><span>điểm khảo sát</span></div>' +
    '<div class="kpi"><b>' + (t.n_ai || 0) + '</b><span>vùng do AI khoanh</span></div>' +
    '<div class="kpi"><b>' + (t.n_manual || 0) + '</b><span>vùng vẽ tay</span></div>';
  if (!t.n_manual) $('lg-manual').style.display = 'none';
  $('notes').innerHTML = (D.notes || []).map(function (n) { return '<p>' + esc(n) + '</p>'; }).join('') +
    '<p>Xuất ngày ' + esc(D.generated || '') + '.</p>';

  var map = L.map('map', { zoomControl: true, maxZoom: 22, attributionControl: true });
  var tl = D.tiles || {};
  if (navigator.onLine !== false) {       // lớp trực tuyến nằm dưới: chỉ lấp chỗ ô offline còn thiếu khi có mạng
    L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', { subdomains: 'abc', maxZoom: 22, maxNativeZoom: 20, errorTileUrl: '' })
      .addTo(map);
  }
  if (tl.have) {
    L.tileLayer('tiles/{z}/{x}/{y}.png', { minZoom: 1, maxZoom: 22, minNativeZoom: tl.min, maxNativeZoom: tl.max, errorTileUrl: '',
      attribution: '&copy; OpenStreetMap France | &copy; OpenStreetMap contributors' }).addTo(map);
  } else {
    map.attributionControl.addAttribution('Không có bản đồ nền offline');
  }

  var layer = L.layerGroup().addTo(map), footLayer = L.layerGroup(), haloLayer = L.layerGroup();
  // Vùng rác nhỏ (vài chục cm) chỉ là vài điểm ảnh khi thu nhỏ: vòng tròn cỡ cố định để thấy vị trí, ẩn từ mức 21.
  function syncHalo() { map.getContainer().classList.toggle('map-hi', map.getZoom() >= 20); var on = map.getZoom() <= 20; if (on && !map.hasLayer(haloLayer)) haloLayer.addTo(map); if (!on && map.hasLayer(haloLayer)) map.removeLayer(haloLayer); }
  map.on('zoomend', syncHalo);
  var sel = null, pins = {}, cards = {};
  var bounds = [];

  D.spots.forEach(function (s) {
    bounds.push([s.lat, s.lon]);
    s.regions.forEach(function (r) {
      var rings = [r.ring].concat(r.holes || []);
      r.ring.forEach(function (p) { bounds.push(p); });
      var manual = r.kind === 'manual';
      var st = manual
        ? { color: '#b45309', weight: 2, dashArray: '6 4', fillColor: '#f59e0b', fillOpacity: 0.5 }
        : { color: '#b91c1c', weight: 1.5, fillColor: '#ef4444', fillOpacity: 0.5 };
      var html = '<div class="popup"><b>' + (manual ? 'Vùng vẽ tay' : 'Vùng rác (AI)') + ' · ' + fmt(r.area_m2) + ' m²</b><div>' + esc(s.name) + '</div></div>';
      L.polygon(rings, st).addTo(layer).bindPopup(html);
      var lat = 0, lon = 0; r.ring.forEach(function (q) { lat += q[0]; lon += q[1]; });
      var col = manual ? '#b45309' : '#dc2626';
      L.circleMarker([lat / r.ring.length, lon / r.ring.length], { radius: 8, color: col, weight: 2, fillColor: col, fillOpacity: 0.12 }).addTo(haloLayer).bindPopup(html);
    });
    if (s.footprint && s.footprint.length) L.polygon(s.footprint, { color: '#0284c7', weight: 1, fillColor: '#38bdf8', fillOpacity: 0.12, interactive: false }).addTo(footLayer);
    var mk = L.marker([s.lat, s.lon], { icon: L.divIcon({ className: '', html: '<div class="pin">' + s.seq + '</div>', iconSize: [30, 30], iconAnchor: [15, 15] }) }).addTo(layer);
    mk.bindTooltip(esc(s.name) + ' · ' + fmt(s.area_m2) + ' m²', { permanent: true, direction: 'top', offset: [0, -15], className: 'pin-label' });
    mk.bindPopup(function () {
      var box = document.createElement('div'); box.className = 'popup';
      box.innerHTML = '<b>' + esc(s.name) + '</b><div>' + esc(s.captured) + (s.time_source === 'exif' ? ' (giờ ghi trong ảnh)' : '') + '</div>' +
        '<img alt="Ảnh chụp tại ' + esc(s.name) + '" src="' + esc(s.thumb) + '">' +
        '<div><b style="color:#0f172a">' + fmt(s.area_m2) + ' m²</b> · ' + s.n_ai + ' vùng AI' + (s.n_manual ? ' + ' + s.n_manual + ' vẽ tay' : '') + '</div>';
      box.querySelector('img').onclick = function () { openLb(s); };
      return box;
    }, { minWidth: 250 });
    mk.on('click', function () { select(s.id, false); });
    pins[s.id] = mk;
  });

  $('spots').innerHTML = D.spots.map(function (s) {
    return '<div class="spot" data-id="' + s.id + '"><img alt="" src="' + esc(s.thumb) + '"><div><div class="n">' + esc(s.name) + '</div>' +
      '<div class="m">' + fmt(s.area_m2) + ' m² · ' + s.n_ai + ' AI' + (s.n_manual ? ' + ' + s.n_manual + ' vẽ tay' : '') + '</div><div class="m">' + esc(s.captured) + '</div></div></div>';
  }).join('');
  Array.prototype.forEach.call(document.querySelectorAll('.spot'), function (el) {
    cards[el.getAttribute('data-id')] = el;
    el.onclick = function () { select(el.getAttribute('data-id'), true); };
  });

  function select(id, fly) {
    sel = id;
    Object.keys(cards).forEach(function (k) { cards[k].classList.toggle('sel', k === id); });
    var s = D.spots.filter(function (x) { return x.id === id; })[0];
    if (s && fly) { map.setView([s.lat, s.lon], Math.max(map.getZoom(), 20)); pins[id].openPopup(); }
  }

  $('foot').onchange = function () { if (this.checked) footLayer.addTo(map); else map.removeLayer(footLayer); };

  function openLb(s) {
    var ov = $('lb-ov'), img = $('lb-img');
    var set = function () { img.src = ov.checked ? s.photo_overlay : s.photo; };
    ov.onchange = set; set();
    $('lb-cap').textContent = s.name + ' · ' + s.captured + (s.time_source === 'exif' ? ' (giờ ghi trong ảnh)' : '');
    $('lb').hidden = false;
  }
  $('lb-x').onclick = function () { $('lb').hidden = true; };
  $('lb').onclick = function (e) { if (e.target === $('lb')) $('lb').hidden = true; };
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') $('lb').hidden = true; });

  syncHalo();
  if (bounds.length) map.fitBounds(L.latLngBounds(bounds).pad(0.25), { maxZoom: 20 }); else map.setView([10.7769, 106.7009], 15);
})();
