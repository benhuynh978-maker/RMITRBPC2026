import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FlaskConical, Info, RotateCcw } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import useDocumentTitle from '../hooks/useDocumentTitle.js';
import PageHero from '../components/PageHero.jsx';
import Section from '../components/Section.jsx';
import Reveal from '../components/Reveal.jsx';
import CityMap from '../components/city/CityMap.jsx';
import CameraCard from '../components/city/CameraCard.jsx';
import {
  STATE_KEYS,
  countByState,
  formatArea,
  formatDateTime,
  formatDuration,
  formatPct,
  loadCityData,
  minutesBetween,
  sortByPriority,
  stateKey,
  totalLitterArea,
} from '../lib/cityDemo.js';

const fill = (tpl, vars) => Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), tpl);
const ALL = new Set(STATE_KEYS);

function Pin({ k, t }) {
  return (
    <span className={`city-pin city-pin--${k}`} aria-hidden="true">
      <i>{t(`city.state.${k}.letter`)}</i>
    </span>
  );
}

export default function CityDemo() {
  const { t, lang } = useI18n();
  useDocumentTitle(t('meta.city'));
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState('all');
  const [selectedId, setSelectedId] = useState(null);
  const [resetToken, setResetToken] = useState(0);
  const [focusToken, setFocusToken] = useState(0);
  const cardRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    loadCityData(controller.signal)
      .then(setData)
      .catch((e) => {
        if (e && e.name === 'AbortError') return;
        setError(true);
      });
    return () => controller.abort();
  }, []);

  const cameras = data ? data.cameras : [];
  const counts = useMemo(() => countByState(cameras), [cameras]);
  const sorted = useMemo(() => sortByPriority(cameras), [cameras]);
  const litter = useMemo(() => totalLitterArea(cameras), [cameras]);
  const list = useMemo(() => (filter === 'all' ? sorted : sorted.filter((c) => stateKey(c) === filter)), [sorted, filter]);
  const visible = useMemo(() => (filter === 'all' ? ALL : new Set([filter])), [filter]);
  const selected = useMemo(() => cameras.find((c) => c.id === selectedId) || null, [cameras, selectedId]);

  const select = useCallback((id) => setSelectedId(id), []);
  const closeCard = useCallback(() => setSelectedId(null), []);
  const backToCity = useCallback(() => {
    setSelectedId(null);
    setResetToken((n) => n + 1);
  }, []);

  // On narrow screens the card sits below the map: bring it into view when a camera is chosen.
  useEffect(() => {
    if (!selected || !cardRef.current) return;
    if (window.matchMedia && window.matchMedia('(min-width: 1024px)').matches) return;
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    cardRef.current.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  }, [selected]);

  const asOf = data ? data.as_of : null;
  const tpl = t('city.duration');

  return (
    <>
      <PageHero eyebrow={t('city.hero.eyebrow')} title={t('city.hero.title')} lead={t('city.hero.lead')} />
      <Section id="city" titleId="city-banner-title" tight>
        <Reveal className="city-banner" role="note">
          <span className="city-banner__icon" aria-hidden="true">
            <FlaskConical size={26} />
          </span>
          <div>
            <h2 id="city-banner-title" className="h3">
              {t('city.banner.title')}
            </h2>
            <p>{t('city.banner.text')}</p>
            {asOf && (
              <p className="city-banner__when">
                {fill(t('city.banner.snapshot'), { time: formatDateTime(asOf, lang, { dateStyle: 'full', timeStyle: 'short' }) })}
              </p>
            )}
          </div>
        </Reveal>

        {!data && !error && (
          <p className="city-status" role="status">
            {t('city.load.loading')}
          </p>
        )}
        {error && (
          <p className="city-status city-status--error" role="alert">
            {t('city.load.error')}
          </p>
        )}

        {data && (
          <>
            <div className="city-tiles" role="group" aria-label={t('city.summary.label')}>
              <button type="button" className={`city-tile${filter === 'all' ? ' is-active' : ''}`} aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
                <strong>{cameras.length}</strong>
                <span>{t('city.summary.all')}</span>
              </button>
              {STATE_KEYS.map((k) => (
                <button
                  key={k}
                  type="button"
                  className={`city-tile${filter === k ? ' is-active' : ''}`}
                  aria-pressed={filter === k}
                  onClick={() => setFilter(filter === k ? 'all' : k)}
                  title={t(`city.state.${k}.hint`)}
                >
                  <Pin k={k} t={t} />
                  <strong>{counts[k]}</strong>
                  <span>{t(`city.state.${k}.name`)}</span>
                </button>
              ))}
              <p className="city-tile city-tile--static">
                <strong>{formatArea(litter)} m²</strong>
                <span>{t('city.summary.litter')}</span>
              </p>
            </div>

            <div className="city-layout">
              <div className="city-mapcol">
                <CityMap data={data} visible={visible} selectedId={selectedId} onSelect={select} resetToken={resetToken} focusToken={focusToken} t={t} lang={lang} />
                <div className="city-mapbar">
                  <p className="city-hint">
                    <Info size={16} aria-hidden="true" /> {t('city.map.hint')}
                  </p>
                  <button type="button" className="btn btn--secondary btn--sm" onClick={backToCity}>
                    <RotateCcw size={16} aria-hidden="true" />
                    <span>{t('city.map.reset')}</span>
                  </button>
                </div>
                <ul className="city-key" aria-label={t('city.map.key.title')}>
                  {['clean', 'watch', 'clear', 'collecting', 'offline'].map((k) => (
                    <li key={k}>
                      <Pin k={k} t={t} /> {t(`city.state.${k}.name`)}
                    </li>
                  ))}
                  <li>
                    <span className="city-swatch city-swatch--view" aria-hidden="true" /> {t('city.map.key.view')}
                  </li>
                  <li>
                    <span className="city-swatch city-swatch--drain" aria-hidden="true" /> {t('city.map.key.drain')}
                  </li>
                  <li>
                    <span className="city-swatch city-swatch--litter" aria-hidden="true" /> {t('city.map.key.litter')}
                  </li>
                </ul>
              </div>

              <aside className="city-side" aria-label={t('city.list.title')}>
                {selected && (
                  <div ref={cardRef} className="city-cardwrap">
                    <CameraCard cam={selected} asOf={asOf} onClose={closeCard} onShow={() => setFocusToken((n) => n + 1)} />
                  </div>
                )}
                <section className="city-list" aria-labelledby="city-list-title">
                  <h3 id="city-list-title" className="h4">
                    {t('city.list.title')}
                  </h3>
                  <p className="city-card__small">{t('city.list.lead')}</p>
                  <p className="city-card__small" role="status">
                    {fill(t('city.list.showing'), { n: list.length, total: cameras.length })}
                  </p>
                  {list.length === 0 ? (
                    <p className="city-note">{t('city.list.empty')}</p>
                  ) : (
                    <ul className="city-rows">
                      {list.map((c) => {
                        const k = stateKey(c);
                        const since = c.since && k !== 'collecting' && k !== 'offline' ? formatDuration(minutesBetween(c.since, asOf), tpl) : '';
                        return (
                          <li key={c.id}>
                            <button type="button" className={`city-row${c.id === selectedId ? ' is-selected' : ''}`} aria-current={c.id === selectedId ? 'true' : undefined} onClick={() => select(c.id)}>
                              <Pin k={k} t={t} />
                              <span className="city-row__main">
                                <strong>{c.id}</strong>
                                <span>
                                  {t(`city.state.${k}.name`)}
                                  {since ? ` · ${fill(t('city.list.forDuration'), { d: since })}` : ''}
                                </span>
                              </span>
                              {c.blockage_pct != null && <span className="city-row__pct">{fill(t('city.list.drain'), { p: formatPct(c.blockage_pct, 0) })}</span>}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </section>
              </aside>
            </div>

            <div className="city-notes">
              <Reveal as="section" className="card" aria-labelledby="city-how-title">
                <h2 id="city-how-title" className="h3">
                  {t('city.how.title')}
                </h2>
                <ul className="city-bullets">
                  {t('city.how.items').map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </Reveal>
              <Reveal as="section" className="card" aria-labelledby="city-limits-title">
                <h2 id="city-limits-title" className="h3">
                  {t('city.how.limitsTitle')}
                </h2>
                <ul className="city-bullets">
                  {t('city.how.limits').map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </Reveal>
            </div>
          </>
        )}
      </Section>
    </>
  );
}
