import { useRef, useState } from 'react';
import { Upload, ShieldCheck, Clock3, Trash2, Waves, Info } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import useDocumentTitle from '../hooks/useDocumentTitle.js';
import PageHero from '../components/PageHero.jsx';
import Section from '../components/Section.jsx';
import Reveal from '../components/Reveal.jsx';
import { Badge, ComingSoon } from '../components/Badge.jsx';
import DisabledNote from '../components/DisabledNote.jsx';
import samplesData from '../data/samples.json';

// Every number on this page comes from samples.json, which is generated offline by
// research/cleansight_samples/make_samples.py (model run on each sample photo). Nothing here is live.
const SAMPLES = samplesData.samples;

function UploadPanel({ selectedId, onSelect }) {
  const { t } = useI18n();
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

      {/* Visual only: uploading your own photo is not built yet (no file input, no handlers). */}
      <div className="dropzone" aria-describedby="tryai-hint">
        <ComingSoon />
        <span className="dropzone__icon" aria-hidden="true">
          <Upload size={28} />
        </span>
        <p className="dropzone__title">{t('tryAi.upload.drop')}</p>
        <p className="dropzone__sub">{t('tryAi.upload.formats')}</p>
      </div>
      <DisabledNote id="tryai-hint">{t('tryAi.upload.soonNote')}</DisabledNote>
    </Reveal>
  );
}

function ResultPanel({ sample }) {
  const { t, lang } = useI18n();
  const levels = t('tryAi.result.levels');
  const fmt = (n) => n.toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US', { maximumFractionDigits: 2 });
  const belowLow = sample.levelIndex < 0;
  const drainFound = sample.drainPct !== null;

  return (
    <Reveal as="section" className="card tryai__panel" aria-labelledby="result-title" delay={100}>
      <div className="tryai__panel-head">
        <h2 id="result-title" className="h3">
          {t('tryAi.result.title')}
        </h2>
        <Badge variant="teal" icon={Info}>
          {t('tryAi.result.badge')}
        </Badge>
      </div>

      <div aria-live="polite">
        <figure className="result-figure">
          <img
            src={`/img/samples/${sample.id}-annotated.jpg`}
            width={sample.width}
            height={sample.height}
            alt={`${t('tryAi.result.annotatedAlt')} ${t(`tryAi.samples.${sample.id}.alt`)}`}
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
              {fmt(sample.wastePct)}%<span className="metric-tile__unit"> {t('tryAi.result.ofFrame')}</span>
            </dd>
          </div>
          <div className="metric-tile">
            <dt>
              <Waves size={18} aria-hidden="true" />
              {t('tryAi.result.metricDrain')}
            </dt>
            <dd className={drainFound ? undefined : 'metric-tile__text'}>
              {drainFound ? `${fmt(sample.drainPct)}%` : t('tryAi.result.drainNone')}
            </dd>
          </div>
        </dl>

        <div className="scale">
          <p className="scale__title">{t('tryAi.result.scaleTitle')}</p>
          <ul className="scale__levels">
            {levels.map((l, i) => (
              <li
                key={l}
                className={`scale__level scale__level--${i}${i === sample.levelIndex ? ' is-active' : ''}`}
                aria-current={i === sample.levelIndex ? 'true' : undefined}
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
          <p>{t(`tryAi.samples.${sample.id}.note`)}</p>
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
  const sample = SAMPLES.find((s) => s.id === selectedId) ?? SAMPLES[0];
  const resultRef = useRef(null);

  // On narrow screens the result sits below the upload panel, out of sight: bring it into view.
  const handleSelect = (id) => {
    setSelectedId(id);
    if (typeof window.matchMedia !== 'function' || !window.matchMedia('(max-width: 959px)').matches) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    resultRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
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
          <UploadPanel selectedId={selectedId} onSelect={handleSelect} />
          <div ref={resultRef} className="tryai__result">
            <ResultPanel sample={sample} />
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
