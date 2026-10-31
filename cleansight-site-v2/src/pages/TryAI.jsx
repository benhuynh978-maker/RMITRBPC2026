import { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, ShieldCheck, Clock3, Trash2, Waves, Info, AlertCircle, Loader } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import useDocumentTitle from '../hooks/useDocumentTitle.js';
import PageHero from '../components/PageHero.jsx';
import Section from '../components/Section.jsx';
import Reveal from '../components/Reveal.jsx';
import { Badge } from '../components/Badge.jsx';
import DisabledNote from '../components/DisabledNote.jsx';
import { DEMO_HEALTH_INTERVAL_MS } from '../lib/config.js';
import { DemoError, analyzePhoto, checkHealth, demoEnabled, prepareImage } from '../lib/demoApi.js';
import samplesData from '../data/samples.json';

// Sample results come from samples.json, generated offline by research/cleansight_samples/make_samples.py
// (model run on each sample photo). Results for the visitor's own photo come from the live demo service.
const SAMPLES = samplesData.samples;

function LiveStatus({ service }) {
  const { t } = useI18n();
  return (
    <p className={`live-status live-status--${service}`} role="status">
      <span className="live-status__dot" aria-hidden="true" />
      {t(`tryAi.live.status.${service}`)}
    </p>
  );
}

function UploadPanel({ selectedId, onSelect, service, phase, error, onFile }) {
  const { t } = useI18n();
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const enabled = service === 'online' && phase === 'idle';
  const busy = phase !== 'idle';

  const pick = (file) => {
    if (file) onFile(file);
  };

  const errorText = error
    ? t(`tryAi.live.errors.${error.code}`) +
      (error.retryAfter ? ` ${t('tryAi.live.retryAfter').replace('{n}', String(error.retryAfter))}` : '')
    : '';

  return (
    <Reveal as="section" className="card tryai__panel" aria-labelledby="upload-title">
      <div className="tryai__panel-head">
        <h2 id="upload-title" className="h3">
          {t('tryAi.upload.title')}
        </h2>
      </div>

      <p className="tryai__samples-title">{t('tryAi.upload.samplesTitle')}</p>
      <ul className="samples">
        {SAMPLES.map((s) => {
          const selected = s.id === selectedId;
          return (
            <li key={s.id}>
              <button
                type="button"
                className={`sample${selected ? ' is-selected' : ''}`}
                aria-pressed={selected}
                onClick={() => onSelect(s.id)}
              >
                <img
                  src={`/img/samples/${s.id}-thumb.jpg`}
                  width="400"
                  height="225"
                  alt=""
                  loading="lazy"
                  decoding="async"
                />
                <span className="sample__label">{t(`tryAi.samples.${s.id}.label`)}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <p className="tryai__samples-title tryai__own-title">{t('tryAi.upload.ownTitle')}</p>
      <LiveStatus service={service} />
      <label
        className={`dropzone${enabled ? ' dropzone--live' : ''}${dragging && enabled ? ' is-dragging' : ''}`}
        onDragOver={(e) => {
          if (!enabled) return;
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (enabled) pick(e.dataTransfer?.files?.[0]);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png"
          className="sr-only"
          disabled={!enabled}
          aria-describedby="tryai-hint"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = ''; // lets the same file be chosen again
            pick(file);
          }}
        />
        <span className="dropzone__icon" aria-hidden="true">
          {busy ? <Loader size={28} className="spin" /> : <Upload size={28} />}
        </span>
        <span className="dropzone__title">
          {phase === 'preparing'
            ? t('tryAi.live.preparing')
            : phase === 'analysing'
              ? t('tryAi.live.analysing')
              : t('tryAi.upload.drop')}
        </span>
        <span className="dropzone__sub">{t('tryAi.upload.formats')}</span>
      </label>
      <DisabledNote id="tryai-hint">
        {service === 'online' ? t('tryAi.live.onlineNote') : t('tryAi.live.offlineNote')}
      </DisabledNote>
      {errorText && (
        <p className="live-error" role="alert">
          <AlertCircle size={18} aria-hidden="true" />
          <span>{errorText}</span>
        </p>
      )}
    </Reveal>
  );
}

function ResultPanel({ item }) {
  const { t, lang } = useI18n();
  const levels = t('tryAi.result.levels');
  const fmt = (n) => n.toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US', { maximumFractionDigits: 2 });
  const belowLow = item.levelIndex < 0;
  const drainFound = item.drainPct !== null;

  return (
    <Reveal as="section" className="card tryai__panel" aria-labelledby="result-title" delay={100}>
      <div className="tryai__panel-head">
        <h2 id="result-title" className="h3">
          {t('tryAi.result.title')}
        </h2>
        <Badge variant="teal" icon={Info}>
          {item.kind === 'live' ? t('tryAi.live.badge') : t('tryAi.result.badge')}
        </Badge>
      </div>

      <div aria-live="polite">
        <figure className="result-figure">
          <img
            src={item.annotatedSrc}
            width={item.width}
            height={item.height}
            alt={item.alt}
            decoding="async"
          />
          <figcaption>{t('tryAi.result.caption')}</figcaption>
        </figure>

        <dl className="metric-tiles">
          <div className="metric-tile">
            <dt>
              <Trash2 size={18} aria-hidden="true" />
              {t('tryAi.result.metricTrash')}
            </dt>
            <dd>
              {fmt(item.wastePct)}%<span className="metric-tile__unit"> {t('tryAi.result.ofFrame')}</span>
            </dd>
          </div>
          <div className="metric-tile">
            <dt>
              <Waves size={18} aria-hidden="true" />
              {t('tryAi.result.metricDrain')}
            </dt>
            <dd className={drainFound ? undefined : 'metric-tile__text'}>
              {drainFound ? `${fmt(item.drainPct)}%` : t('tryAi.result.drainNone')}
            </dd>
          </div>
        </dl>

        <div className="scale">
          <p className="scale__title">{t('tryAi.result.scaleTitle')}</p>
          <ul className="scale__levels">
            {levels.map((l, i) => (
              <li
                key={l}
                className={`scale__level scale__level--${i}${i === item.levelIndex ? ' is-active' : ''}`}
                aria-current={i === item.levelIndex ? 'true' : undefined}
              >
                {l}
              </li>
            ))}
          </ul>
          {belowLow && <p className="scale__below">{t('tryAi.result.belowLow')}</p>}
          <p className="scale__note">{t('tryAi.result.thresholds')}</p>
        </div>

        <div className="sample-note">
          <h3 className="h4">{t('tryAi.result.noteTitle')}</h3>
          <p>{item.note}</p>
          <p className="sample-note__disclaimer">
            <Info size={16} aria-hidden="true" />
            <span>{t('tryAi.result.disclaimer')}</span>
          </p>
        </div>
      </div>
    </Reveal>
  );
}

export default function TryAI() {
  const { t } = useI18n();
  useDocumentTitle(t('meta.tryAi'));

  const [selectedId, setSelectedId] = useState(SAMPLES[0].id);
  const [view, setView] = useState('sample'); // 'sample' | 'live'
  const [live, setLive] = useState(null);
  const [service, setService] = useState(demoEnabled() ? 'checking' : 'offline'); // checking | online | offline
  const [phase, setPhase] = useState('idle'); // idle | preparing | analysing
  const [error, setError] = useState(null);
  const resultRef = useRef(null);
  const requestRef = useRef(null); // AbortController of the request in flight
  const busyRef = useRef(false);

  // On narrow screens the result sits below the upload panel, out of sight: bring it into view.
  const bringResultIntoView = useCallback(() => {
    if (typeof window.matchMedia !== 'function' || !window.matchMedia('(max-width: 959px)').matches) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    resultRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  }, []);

  // Is the live demo up? Check on load, then every 30 s while the tab is visible.
  useEffect(() => {
    if (!demoEnabled()) return undefined;
    const controller = new AbortController();
    let timer;
    let running = false;
    const tick = async () => {
      if (running) return;
      running = true;
      if (document.visibilityState === 'visible') {
        const ok = await checkHealth(controller.signal);
        if (controller.signal.aborted) return;
        setService(ok ? 'online' : 'offline');
      }
      running = false;
      timer = setTimeout(tick, DEMO_HEALTH_INTERVAL_MS);
    };
    tick();
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        clearTimeout(timer);
        tick();
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);

  // Leaving the page cancels a request in flight.
  useEffect(() => () => requestRef.current?.abort(), []);

  const handleSample = (id) => {
    setSelectedId(id);
    setView('sample');
    setError(null);
    bringResultIntoView();
  };

  const handleFile = async (file) => {
    if (busyRef.current) return; // double click / double drop
    busyRef.current = true;
    const controller = new AbortController();
    requestRef.current = controller;
    setError(null);
    setPhase('preparing');
    try {
      const blob = await prepareImage(file);
      if (controller.signal.aborted) return;
      setPhase('analysing');
      const result = await analyzePhoto(blob, controller.signal);
      if (controller.signal.aborted) return;
      setLive(result);
      setView('live');
      setPhase('idle');
      bringResultIntoView();
    } catch (e) {
      if (controller.signal.aborted) return;
      const code = e instanceof DemoError ? e.code : 'server';
      setError({ code, retryAfter: e instanceof DemoError ? e.retryAfter : null });
      setPhase('idle');
      if (code === 'network') setService('offline'); // it will come back at the next health check
    } finally {
      busyRef.current = false;
    }
  };

  const sample = SAMPLES.find((s) => s.id === selectedId) ?? SAMPLES[0];
  const item =
    view === 'live' && live
      ? { ...live, kind: 'live', alt: t('tryAi.live.alt'), note: t('tryAi.live.note') }
      : {
          kind: 'sample',
          annotatedSrc: `/img/samples/${sample.id}-annotated.jpg`,
          width: sample.width,
          height: sample.height,
          wastePct: sample.wastePct,
          levelIndex: sample.levelIndex,
          drainPct: sample.drainPct,
          alt: `${t('tryAi.result.annotatedAlt')} ${t(`tryAi.samples.${sample.id}.alt`)}`,
          note: t(`tryAi.samples.${sample.id}.note`),
        };

  return (
    <>
      <PageHero eyebrow={t('tryAi.hero.eyebrow')} title={t('tryAi.hero.title')} lead={t('tryAi.hero.lead')} />
      <Section id="thu-ai" titleId="banner-title" tight>
        <Reveal className="banner">
          <span className="banner__icon" aria-hidden="true">
            <Clock3 size={28} />
          </span>
          <div>
            <h2 id="banner-title" className="h3">
              {t('tryAi.banner.title')}
            </h2>
            <p>{t('tryAi.banner.text')}</p>
          </div>
        </Reveal>

        <div className="tryai">
          <UploadPanel
            selectedId={view === 'sample' ? selectedId : null}
            onSelect={handleSample}
            service={service}
            phase={phase}
            error={error}
            onFile={handleFile}
          />
          <div ref={resultRef} className="tryai__result">
            <ResultPanel item={item} />
          </div>
        </div>

        <Reveal as="p" className="note note--privacy">
          <ShieldCheck size={18} aria-hidden="true" />
          <span>
            <strong>{t('tryAi.privacy.title')}:</strong> {t('tryAi.privacy.text')}
          </span>
        </Reveal>
      </Section>
    </>
  );
}
