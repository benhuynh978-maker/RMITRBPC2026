import { X, MapPinned } from 'lucide-react';
import { useI18n } from '../../i18n/I18nProvider.jsx';
import { formatArea, formatDateTime, formatDuration, formatPct, minutesBetween, stateKey } from '../../lib/cityDemo.js';

const fill = (tpl, vars) => Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), tpl);

// Colour of a reading by the product's thresholds (watch 20, needs cleaning 50). Shape/position carry the meaning too.
const barClass = (v) => (v >= 50 ? 'is-clean' : v >= 20 ? 'is-watch' : 'is-clear');

/** Last readings the status is computed from: bars with the 20% and 50% thresholds. Oldest on the left. */
function ReadingBars({ recent, label }) {
  const items = [...recent].reverse(); // oldest -> newest
  const W = 240;
  const H = 96;
  const pad = { l: 28, r: 6, t: 6, b: 6 };
  const innerH = H - pad.t - pad.b;
  const y = (v) => pad.t + innerH * (1 - Math.min(100, Math.max(0, v)) / 100);
  const slot = (W - pad.l - pad.r) / Math.max(items.length, 1);
  const bw = Math.min(30, slot * 0.6);
  return (
    <figure className="city-bars">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        {[0, 20, 50, 100].map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} className={v === 20 || v === 50 ? 'city-bars__thr' : 'city-bars__axis'} />
            <text x={pad.l - 4} y={y(v) + 3} textAnchor="end" className="city-bars__tick">
              {v}%
            </text>
          </g>
        ))}
        {items.map((r, i) => {
          const cx = pad.l + slot * (i + 0.5);
          return <rect key={r.at} x={cx - bw / 2} y={y(r.v)} width={bw} height={Math.max(1, y(0) - y(r.v))} rx="2" className={`city-bars__bar ${barClass(r.v)}`} />;
        })}
      </svg>
      <figcaption className="sr-only">{items.map((r) => formatPct(r.v, 1)).join(', ')}</figcaption>
    </figure>
  );
}

export default function CameraCard({ cam, asOf, onClose, onShow }) {
  const { t, lang } = useI18n();
  const key = stateKey(cam);
  const tpl = t('city.duration');
  const zoneNo = Number(cam.zone.replace(/\D/g, '')) || cam.zone;
  const since = cam.since ? formatDuration(minutesBetween(cam.since, asOf), tpl) : '';
  const latest = cam.latest;
  const stateName = t(`city.state.${key}.name`);

  return (
    <article className="city-card" aria-labelledby="city-card-title">
      <header className="city-card__head">
        <div>
          <h3 id="city-card-title" className="h4">
            {fill(t('city.card.title'), { id: cam.id })}
          </h3>
          <p className="city-card__meta">
            {fill(t('city.card.zone'), { n: zoneNo })} · <span className="city-sim-tag">{t('city.card.simulated')}</span>
          </p>
        </div>
        <button type="button" className="city-iconbtn" onClick={onClose} aria-label={t('city.card.close')}>
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      <p className={`city-state city-state--${key}`}>
        <span className="city-state__badge" aria-hidden="true">
          {t(`city.state.${key}.letter`)}
        </span>
        <span>{since && (key === 'clean' || key === 'watch' || key === 'clear') ? fill(t('city.card.statusFor'), { state: stateName, d: since }) : stateName}</span>
      </p>

      {key === 'collecting' && <p className="city-note">{fill(t('city.card.collecting'), { n: cam.window })}</p>}
      {key === 'offline' && (
        <p className="city-note">
          {cam.last_frame
            ? fill(t('city.card.offline'), { d: formatDuration(minutesBetween(cam.last_frame, asOf), tpl), time: formatDateTime(cam.last_frame, lang) })
            : t('city.card.noFrame')}
        </p>
      )}

      <section className="city-card__sec" aria-labelledby="city-drain-title">
        <h4 id="city-drain-title" className="city-card__h">
          {t('city.card.drainTitle')}
        </h4>
        {cam.blockage_pct != null && (
          <p className="city-big">
            {formatPct(cam.blockage_pct, 0)} <span>{t('city.card.coverage')}</span>
          </p>
        )}
        {cam.recent.length > 0 && (
          <>
            <p className="city-card__sub">{t('city.card.readings')}</p>
            <ReadingBars recent={cam.recent} label={`${t('city.card.readings')}: ${cam.recent.map((r) => formatPct(r.v, 1)).join(', ')}`} />
            <p className="city-card__small">{t('city.card.readingsHelp')}</p>
            <p className="city-card__small">{t('city.card.thresholds')}</p>
          </>
        )}
      </section>

      {latest && (
        <section className="city-card__sec" aria-labelledby="city-latest-title">
          <h4 id="city-latest-title" className="city-card__h">
            {t('city.card.latestTitle')}
          </h4>
          <dl className="city-dl">
            <div>
              <dt>{t('city.card.frameTime')}</dt>
              <dd>{formatDateTime(latest.at, lang)}</dd>
            </div>
            <div>
              <dt>{t('city.card.litterPct')}</dt>
              <dd>{formatPct(latest.waste_pct, 1)}</dd>
            </div>
            <div>
              <dt>{t('city.card.litterLevel')}</dt>
              <dd>{t(`city.level.${latest.waste_level}`)}</dd>
            </div>
            <div>
              <dt>{t('city.card.alertLevel')}</dt>
              <dd>{t(`city.level.${latest.severity}`)}</dd>
            </div>
            <div>
              <dt>{t('city.card.regions')}</dt>
              <dd>{cam.regions.length ? fill(t('city.card.regionsValue'), { n: cam.regions.length, a: formatArea(latest.total_area_m2) }) : t('city.card.noRegions')}</dd>
            </div>
          </dl>
          {cam.regions.length > 0 && (
            <ol className="city-regions">
              {cam.regions.slice(0, 6).map((r, i) => (
                <li key={`${r.kind}-${i}`}>
                  {fill(t('city.card.regionRow'), { i: i + 1, a: formatArea(r.area_m2) })}
                  {r.kind === 'drain' ? ` (${t('city.card.onDrain')})` : ''}
                </li>
              ))}
              {cam.regions.length > 6 && <li className="city-regions__more">+{cam.regions.length - 6}</li>}
            </ol>
          )}
        </section>
      )}

      <p className="city-card__small">{fill(t('city.card.setup'), { h: cam.height_m })}</p>

      <button type="button" className="btn btn--secondary btn--sm city-card__show" onClick={onShow}>
        <MapPinned size={16} aria-hidden="true" />
        <span>{t('city.card.show')}</span>
      </button>
    </article>
  );
}
