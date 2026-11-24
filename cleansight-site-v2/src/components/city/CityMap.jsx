import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { stateKey } from '../../lib/cityDemo.js';

// Customer map demo: the map is drawn imperatively with Leaflet (as the lab pages do).
// Zoomed out, the six zones are shown as bubbles; zoomed in, every camera is a pin (colour + shape + letter, never colour alone);
// from zoom 17 each camera's view area, drain zone and outlined litter appear, and the selected camera always shows them.
const TILE_URL = 'https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png';
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.fr" target="_blank" rel="noopener">OpenStreetMap France</a> | &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';
const ZONE_ZOOM = 14; // below this zoom: zone bubbles; from it: camera pins
const DETAIL_ZOOM = 17; // from this zoom: view areas and litter outlines for the cameras in view
const SELECT_MAX_ZOOM = 21;

const fmt = (v) => (typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('en-US', { maximumFractionDigits: v < 10 ? 2 : 1 }) : '–');
const fill = (tpl, vars) => Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), tpl);

function pinIcon(key, letter, selected) {
  return L.divIcon({
    className: 'city-pin-wrap',
    html: `<span class="city-pin city-pin--${key}${selected ? ' is-selected' : ''}" aria-hidden="true"><i>${letter}</i></span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

function zoneIcon(code, count, needs) {
  const badge = needs > 0 ? `<em class="city-zone__n">${needs}</em>` : '';
  return L.divIcon({
    className: 'city-zone-wrap',
    html: `<span class="city-zone"><b>${count}</b><small>${code}</small>${badge}</span>`,
    iconSize: [50, 50],
    iconAnchor: [25, 25],
  });
}

function bounds(cam) {
  return L.latLngBounds([...cam.footprint, cam.pos, cam.drain]);
}

export default function CityMap({ data, visible, selectedId, onSelect, resetToken, focusToken, t, lang }) {
  const hostRef = useRef(null);
  const api = useRef({}); // map, layers, markers, detail groups
  const latest = useRef({});
  latest.current = { data, visible, selectedId, onSelect, t, lang };

  // ---- create the map once ----
  useEffect(() => {
    const host = hostRef.current;
    const map = L.map(host, {
      zoomControl: true,
      scrollWheelZoom: false, // a wheel scroll over the map must not trap page scrolling
      dragging: !L.Browser.mobile, // on touch screens one finger scrolls the page; two fingers pinch-zoom
      maxZoom: 21,
      minZoom: 9,
      attributionControl: true,
    });
    L.tileLayer(TILE_URL, { subdomains: 'abc', maxZoom: 21, maxNativeZoom: 20, attribution: TILE_ATTRIBUTION }).addTo(map);
    L.control.scale({ metric: true, imperial: false, position: 'bottomleft' }).addTo(map);
    const pins = L.layerGroup();
    const zones = L.layerGroup();
    const detail = L.layerGroup().addTo(map);
    const a = { map, pins, zones, detail, markers: new Map(), groups: new Map(), mode: null };
    api.current = a;

    const { data: d, t: tr } = latest.current;
    const all = L.latLngBounds(d.cameras.map((c) => c.pos));

    // pins
    for (const cam of d.cameras) {
      const key = stateKey(cam);
      const m = L.marker(cam.pos, {
        icon: pinIcon(key, tr(`city.state.${key}.letter`), false),
        title: fill(tr('city.map.pinTip'), { id: cam.id, state: tr(`city.state.${key}.name`) }),
        alt: cam.id,
        riseOnHover: true,
      });
      m.on('click', () => latest.current.onSelect(cam.id));
      a.markers.set(cam.id, m);
    }
    // zone bubbles
    for (const z of d.zones) {
      const cams = d.cameras.filter((c) => c.zone === z.id);
      const n = Number(z.id.replace(/\D/g, '')) || z.id;
      const needs = cams.filter((c) => stateKey(c) === 'clean').length;
      const m = L.marker(z.center, {
        icon: zoneIcon(z.id, cams.length, needs),
        title: fill(tr('city.map.zoneTip'), { n, c: cams.length, w: needs }),
        alt: fill(tr('city.map.zone'), { n }),
      });
      m.on('click', () => map.fitBounds(L.latLngBounds(cams.map((c) => c.pos)), { padding: [60, 60], maxZoom: 15 }));
      zones.addLayer(m);
    }

    a.syncPins = () => {
      const { data: dd, visible: vis, selectedId: sel } = latest.current;
      const zoomedIn = map.getZoom() >= DETAIL_ZOOM + 1; // the selected camera is drawn in detail: hide its pin so it does not cover the outlines
      for (const cam of dd.cameras) {
        const m = a.markers.get(cam.id);
        const on = (vis.has(stateKey(cam)) || cam.id === sel) && !(cam.id === sel && zoomedIn);
        if (on && !pins.hasLayer(m)) pins.addLayer(m);
        if (!on && pins.hasLayer(m)) pins.removeLayer(m);
      }
    };
    const updateMode = () => {
      const zoom = map.getZoom();
      const mode = zoom < ZONE_ZOOM ? 'zones' : 'pins';
      if (mode !== a.mode) {
        a.mode = mode;
        if (mode === 'zones') {
          map.removeLayer(pins);
          map.addLayer(zones);
        } else {
          map.removeLayer(zones);
          map.addLayer(pins);
        }
      }
      const size = zoom >= 16 ? 'near' : zoom >= 14 ? 'mid' : 'far';
      host.classList.remove('city-map--near', 'city-map--mid', 'city-map--far');
      host.classList.add(`city-map--${size}`);
    };
    a.refreshDetail = () => {
      const { data: dd, selectedId: sel } = latest.current;
      const view = map.getBounds().pad(0.2);
      const showAll = map.getZoom() >= DETAIL_ZOOM;
      for (const cam of dd.cameras) {
        const want = cam.id === sel || (showAll && view.intersects(bounds(cam)));
        const have = a.groups.get(cam.id);
        if (want && !have) {
          const g = buildDetail(cam, cam.id === sel, latest.current);
          a.groups.set(cam.id, g);
          detail.addLayer(g);
        } else if (!want && have) {
          detail.removeLayer(have);
          a.groups.delete(cam.id);
        }
      }
    };
    map.on('zoomend', () => {
      updateMode();
      a.syncPins();
      a.refreshDetail();
    });
    map.on('moveend', a.refreshDetail);

    map.fitBounds(all, { padding: [30, 30] });
    updateMode();
    a.refreshDetail();

    return () => {
      map.remove();
      api.current = {};
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- filter: which pins are on the map ----
  useEffect(() => {
    const a = api.current;
    if (!a.map) return;
    a.syncPins();
  }, [data, visible, selectedId]);

  // ---- selection: highlight, draw, zoom ----
  const prevSel = useRef(null);
  useEffect(() => {
    const a = api.current;
    if (!a.map) return;
    const { t: tr } = latest.current;
    for (const id of [prevSel.current, selectedId]) {
      if (!id) continue;
      const cam = data.cameras.find((c) => c.id === id);
      const m = a.markers.get(id);
      const key = stateKey(cam);
      m.setIcon(pinIcon(key, tr(`city.state.${key}.letter`), id === selectedId));
      m.setZIndexOffset(id === selectedId ? 1000 : 0);
      const old = a.groups.get(id);
      if (old) {
        a.detail.removeLayer(old);
        a.groups.delete(id);
      }
    }
    prevSel.current = selectedId;
    if (selectedId) {
      const cam = data.cameras.find((c) => c.id === selectedId);
      a.map.fitBounds(bounds(cam), { padding: [50, 50], maxZoom: SELECT_MAX_ZOOM });
    }
    a.refreshDetail();
  }, [data, selectedId]);

  // ---- back to the whole city ----
  const firstReset = useRef(true);
  useEffect(() => {
    if (firstReset.current) {
      firstReset.current = false;
      return;
    }
    const a = api.current;
    if (!a.map) return;
    a.map.fitBounds(L.latLngBounds(data.cameras.map((c) => c.pos)), { padding: [30, 30] });
  }, [resetToken, data]);

  // ---- "show on the map" for the camera already selected ----
  const firstFocus = useRef(true);
  useEffect(() => {
    if (firstFocus.current) {
      firstFocus.current = false;
      return;
    }
    const a = api.current;
    const cam = latest.current.data.cameras.find((c) => c.id === latest.current.selectedId);
    if (a.map && cam) a.map.fitBounds(bounds(cam), { padding: [50, 50], maxZoom: SELECT_MAX_ZOOM });
  }, [focusToken]);

  // ---- language change: refresh texts of pins and bubbles ----
  useEffect(() => {
    const a = api.current;
    if (!a.map) return;
    const { t: tr } = latest.current;
    for (const cam of data.cameras) {
      const key = stateKey(cam);
      const m = a.markers.get(cam.id);
      m.setIcon(pinIcon(key, tr(`city.state.${key}.letter`), cam.id === selectedId));
      m.options.title = fill(tr('city.map.pinTip'), { id: cam.id, state: tr(`city.state.${key}.name`) });
      if (m.getElement()) m.getElement().title = m.options.title;
    }
    a.zones.eachLayer((m) => {
      const z = data.zones.find((zz) => zz.center[0] === m.getLatLng().lat && zz.center[1] === m.getLatLng().lng);
      if (!z) return;
      const cams = data.cameras.filter((c) => c.zone === z.id);
      const n = Number(z.id.replace(/\D/g, '')) || z.id;
      const needs = cams.filter((c) => stateKey(c) === 'clean').length;
      m.setIcon(zoneIcon(z.id, cams.length, needs));
      if (m.getElement()) m.getElement().title = fill(tr('city.map.zoneTip'), { n, c: cams.length, w: needs });
    });
    for (const [id, g] of a.groups) {
      a.detail.removeLayer(g);
      a.groups.delete(id);
    }
    a.refreshDetail();
  }, [lang]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={hostRef} className="city-map city-map--far" role="application" aria-label={t('city.map.label')} />;
}

// One camera: view area (teal), drain zone (blue, dashed), outlined litter (red); the selected one is drawn stronger with labels.
function buildDetail(cam, selected, ctx) {
  const { t } = ctx;
  const g = L.featureGroup();
  L.polygon(cam.footprint, { color: '#0e7480', weight: selected ? 2 : 1, fillColor: '#0e7480', fillOpacity: selected ? 0.1 : 0.06, interactive: false }).addTo(g);
  L.polygon(cam.roi, { color: '#0b5cad', weight: 2, dashArray: '4 3', fillColor: '#0b5cad', fillOpacity: 0.15, interactive: false }).addTo(g);
  cam.regions.forEach((r, i) => {
    const poly = L.polygon(r.ring, { color: '#9b1c1c', weight: selected ? 2.5 : 1.5, fillColor: '#ef4444', fillOpacity: selected ? 0.55 : 0.5 });
    const tail = r.kind === 'drain' ? ` (${t('city.map.popupDrain')})` : '';
    poly.bindPopup(`<b>${fill(t('city.map.popupRegion'), { i: i + 1, a: fmt(r.area_m2) })}</b>${tail}`);
    if (selected && cam.regions.length <= 12) poly.bindTooltip(String(i + 1), { permanent: true, direction: 'center', className: 'city-region-no' });
    poly.addTo(g);
  });
  if (selected) {
    L.circleMarker(cam.drain, { radius: 5, color: '#fff', weight: 2, fillColor: '#0b5cad', fillOpacity: 1 })
      .bindTooltip(t('city.map.tipDrain'), { permanent: true, direction: 'bottom', offset: [0, 6], className: 'city-lbl' })
      .addTo(g);
    L.circleMarker(cam.pos, { radius: 6, color: '#fff', weight: 2, fillColor: '#0e7480', fillOpacity: 1 })
      .bindTooltip(fill(t('city.map.tipCamera'), { id: cam.id }), { permanent: true, direction: 'top', offset: [0, -6], className: 'city-lbl' })
      .addTo(g);
  }
  return g;
}
