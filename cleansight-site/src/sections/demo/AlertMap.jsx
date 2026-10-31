import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import Card from '../../components/Card.jsx';
import Badge from '../../components/Badge.jsx';
import { TILE_URL, TILE_ATTRIBUTION } from '../../lib/config.js';
import {
  MAP_CENTER,
  MAP_ZOOM,
  LEVELS,
  DRAIN_STATES,
  LEVEL_ACTIONS,
  DRAIN_ACTIONS,
  ROADS,
  DRAINS,
} from '../../data/alerts.js';

const LEVEL_COLORS = ['#0072b2', '#e69f00', '#d55e00'];
// Line style differs per level too, so the map never relies on colour alone.
const LEVEL_STYLE = [
  { weight: 5, dashArray: null },
  { weight: 6, dashArray: '12 8' },
  { weight: 9, dashArray: null },
];
const DRAIN_LETTER = ['L', 'W', 'N'];

// Label anchor: 22% along the first segment, away from the drain markers near the middle.
function labelPoint(path) {
  const [a, b] = path;
  return [a[0] + (b[0] - a[0]) * 0.22, a[1] + (b[1] - a[1]) * 0.22];
}

const effectiveLevel = (road, rain) => Math.min(2, road.baseLevel + (rain ? 1 : 0));
const ageText = (min) => `${min} min ago (example)`;

function drainIcon(state, selected) {
  return L.divIcon({
    className: 'drain-icon-wrap',
    html: `<span class="drain-pin drain-s${state}${selected ? ' is-selected' : ''}"><b>${DRAIN_LETTER[state]}</b></span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

export default function AlertMap() {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const roadLayers = useRef({});
  const drainLayers = useRef({});
  const labelLayers = useRef({});
  const [rain, setRain] = useState(false);
  const [sel, setSel] = useState(null); // { type: 'road' | 'drain', id }

  // Create the map once.
  useEffect(() => {
    const map = L.map(elRef.current, {
      center: MAP_CENTER,
      zoom: MAP_ZOOM,
      scrollWheelZoom: false,
      dragging: !L.Browser.mobile,
      tap: false,
    });
    L.tileLayer(TILE_URL, { maxZoom: 19, attribution: TILE_ATTRIBUTION }).addTo(map);
    mapRef.current = map;

    ROADS.forEach((road) => {
      const line = L.polyline(road.path, { color: LEVEL_COLORS[road.baseLevel], opacity: 0.95, lineCap: 'round' }).addTo(map);
      line.on('click', () => setSel({ type: 'road', id: road.id }));
      roadLayers.current[road.id] = line;
      // Text label near the start of the road (away from drain markers), so level is never colour-only.
      const anchor = L.circleMarker(labelPoint(road.path), { radius: 1, opacity: 0, fillOpacity: 0, interactive: false }).addTo(map);
      anchor.bindTooltip(road.id, { permanent: true, direction: road.labelDir ?? 'center', className: 'road-label', interactive: false });
      labelLayers.current[road.id] = anchor;
    });
    DRAINS.forEach((drain) => {
      const marker = L.marker(drain.pos, {
        icon: drainIcon(drain.state, false),
        title: `Drain ${drain.id}: ${DRAIN_STATES[drain.state]}`,
        alt: `Drain ${drain.id}: ${DRAIN_STATES[drain.state]}`,
        keyboard: true,
      }).addTo(map);
      marker.on('click', () => setSel({ type: 'drain', id: drain.id }));
      drainLayers.current[drain.id] = marker;
    });

    return () => {
      map.remove();
      mapRef.current = null;
      roadLayers.current = {};
      drainLayers.current = {};
      labelLayers.current = {};
    };
  }, []);

  // Restyle when rain or selection changes.
  useEffect(() => {
    ROADS.forEach((road) => {
      const layer = roadLayers.current[road.id];
      if (!layer) return;
      const lvl = effectiveLevel(road, rain);
      const isSel = sel?.type === 'road' && sel.id === road.id;
      const st = LEVEL_STYLE[lvl];
      layer.setStyle({
        color: LEVEL_COLORS[lvl],
        weight: st.weight + (isSel ? 4 : 0),
        dashArray: st.dashArray,
      });
      labelLayers.current[road.id]?.setTooltipContent(`${road.id} · ${LEVELS[lvl]}`);
      if (isSel) layer.bringToFront();
    });
    DRAINS.forEach((drain) => {
      const m = drainLayers.current[drain.id];
      if (m) m.setIcon(drainIcon(drain.state, sel?.type === 'drain' && sel.id === drain.id));
    });
  }, [rain, sel]);

  const details = useMemo(() => {
    if (!sel) return null;
    if (sel.type === 'road') {
      const road = ROADS.find((r) => r.id === sel.id);
      const lvl = effectiveLevel(road, rain);
      let boost;
      if (!rain) boost = 'No (rain simulation is off)';
      else if (road.baseLevel === 2) boost = 'No change: already at the top level (High)';
      else boost = `Yes: raised from ${LEVELS[road.baseLevel]} to ${LEVELS[lvl]}`;
      return {
        kind: 'Road',
        title: road.name,
        level: LEVELS[lvl],
        levelIdx: lvl,
        age: ageText(road.photoMin),
        boost,
        action: LEVEL_ACTIONS[lvl],
        extra: DRAINS.filter((d) => d.roadId === road.id).map((d) => `${d.id} (${DRAIN_STATES[d.state]})`),
      };
    }
    const drain = DRAINS.find((d) => d.id === sel.id);
    return {
      kind: 'Drain',
      title: `Drain ${drain.id} (example)`,
      level: DRAIN_STATES[drain.state],
      levelIdx: drain.state,
      age: ageText(drain.photoMin),
      boost: 'Not applicable: rain adjusts road alert levels, not the drain state',
      action: DRAIN_ACTIONS[drain.state],
      extra: [`On road ${drain.roadId}`],
    };
  }, [sel, rain]);

  return (
    <Card className="demo-card demo-wide" title="Alert map" badge={<Badge variant="demo">Demo data</Badge>}>
      <p className="muted">
        Roads are coloured by alert level and drains show their state. Click a road or a drain, or pick one from the
        list below the map.
      </p>

      <div className="map-toolbar">
        <label className="switch">
          <input type="checkbox" checked={rain} onChange={(e) => setRain(e.target.checked)} />
          <span className="switch-track" aria-hidden="true" />
          <span>Simulate rain</span>
        </label>
        <p className="small muted map-explain">
          {rain
            ? 'Rain is on: every road is one alert level higher (capped at High).'
            : 'Rain raises the alert one level. Turn it on to see every road move up a step.'}
        </p>
      </div>

      <div className="map-layout">
        <div className="map-wrap">
          <div
            ref={elRef}
            className="map"
            role="region"
            aria-label="Map of illustrative road alert levels and drains in Ho Chi Minh City"
          />
          <p className="small muted map-note">Illustrative roads and values. Not real streets and not live data.</p>
        </div>

        <aside className="map-panel" aria-live="polite" aria-label="Selected item details">
          {details ? (
            <>
              <p className="eyebrow">{details.kind}</p>
              <h4>{details.title}</h4>
              <dl className="kv">
                <dt>{details.kind === 'Road' ? 'Alert level' : 'Drain state'}</dt>
                <dd>
                  <span className={`chip chip-l${details.levelIdx}`}>{details.level}</span>
                </dd>
                <dt>Last photo</dt>
                <dd>{details.age}</dd>
                <dt>Rain boosted</dt>
                <dd>{details.boost}</dd>
                <dt>What crews should do</dt>
                <dd>{details.action}</dd>
                {details.extra.length > 0 && (
                  <>
                    <dt>{details.kind === 'Road' ? 'Drains on this road' : 'Location'}</dt>
                    <dd>{details.extra.join(', ')}</dd>
                  </>
                )}
              </dl>
            </>
          ) : (
            <p className="muted">Select a road or a drain to see its level, photo age, rain effect and what crews should do.</p>
          )}
        </aside>
      </div>

      <div className="legend" aria-label="Legend">
        <p className="legend-title">Road alert level</p>
        <ul className="legend-list">
          {LEVELS.map((name, i) => (
            <li key={name}>
              <svg width="44" height="14" viewBox="0 0 44 14" aria-hidden="true" focusable="false">
                <line x1="3" y1="7" x2="41" y2="7" stroke={LEVEL_COLORS[i]} strokeWidth={LEVEL_STYLE[i].weight} strokeDasharray={LEVEL_STYLE[i].dashArray ?? undefined} strokeLinecap="round" />
              </svg>
              {name}
            </li>
          ))}
        </ul>
        <p className="legend-title">Drain state</p>
        <ul className="legend-list">
          {DRAIN_STATES.map((name, i) => (
            <li key={name}>
              <span className={`drain-pin drain-s${i} legend-pin`} aria-hidden="true">
                <b>{DRAIN_LETTER[i]}</b>
              </span>
              {name}
            </li>
          ))}
        </ul>
      </div>

      <div className="pick-list">
        <p className="legend-title">Or choose from the list</p>
        <div className="pick-buttons">
          {ROADS.map((r) => (
            <button key={r.id} type="button" className={`pick${sel?.type === 'road' && sel.id === r.id ? ' is-on' : ''}`} onClick={() => setSel({ type: 'road', id: r.id })}>
              {r.id} &middot; {LEVELS[effectiveLevel(r, rain)]}
            </button>
          ))}
          {DRAINS.map((d) => (
            <button key={d.id} type="button" className={`pick pick-drain${sel?.type === 'drain' && sel.id === d.id ? ' is-on' : ''}`} onClick={() => setSel({ type: 'drain', id: d.id })}>
              {d.id} &middot; {DRAIN_STATES[d.state]}
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}
