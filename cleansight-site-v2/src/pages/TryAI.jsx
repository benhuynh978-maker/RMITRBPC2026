import { Upload, Sparkles, ImageOff, ShieldCheck, Clock3, Trash2, Waves, Gauge } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import useDocumentTitle from '../hooks/useDocumentTitle.js';
import PageHero from '../components/PageHero.jsx';
import Section from '../components/Section.jsx';
import Reveal from '../components/Reveal.jsx';
import Button from '../components/Button.jsx';
import { ComingSoon } from '../components/Badge.jsx';
import DisabledNote from '../components/DisabledNote.jsx';

// The same test photo, cropped three ways, stands in for future sample images.
const SAMPLE_CROPS = ['20% 50%', '70% 30%', '90% 60%'];

function UploadPanel() {
  const { t } = useI18n();
  return (
    <Reveal as="section" className="card tryai__panel" aria-labelledby="upload-title">
      <div className="tryai__panel-head">
        <h2 id="upload-title" className="h3">
          {t('tryAi.upload.title')}
        </h2>
        <ComingSoon />
      </div>

      {/* Visual only: no file input, no handlers. */}
      <div className="dropzone">
        <span className="dropzone__icon" aria-hidden="true">
          <Upload size={28} />
        </span>
        <p className="dropzone__title">{t('tryAi.upload.drop')}</p>
        <p className="dropzone__sub">{t('tryAi.upload.formats')}</p>
      </div>

      <p className="tryai__samples-title">{t('tryAi.upload.samplesTitle')}</p>
      <ul className="samples">
        {SAMPLE_CROPS.map((pos, i) => (
          <li key={pos}>
            <button type="button" className="sample" disabled aria-disabled="true" aria-describedby="tryai-hint">
              <img src="/img/hero.jpg" alt="" loading="lazy" decoding="async" style={{ objectPosition: pos }} />
              <span className="sample__label">
                {t('tryAi.upload.sampleLabel')} {i + 1}
              </span>
              <span className="sr-only">: {t('tryAi.upload.sampleAlt')}</span>
            </button>
          </li>
        ))}
      </ul>

      <Button icon={Sparkles} disabled className="tryai__analyze" aria-describedby="tryai-hint">
        {t('tryAi.upload.analyze')}
      </Button>
      <DisabledNote id="tryai-hint" />
    </Reveal>
  );
}

function ResultPanel() {
  const { t } = useI18n();
  const levels = t('tryAi.result.levels');
  const drainStates = t('tryAi.result.drainStates');
  return (
    <Reveal as="section" className="card tryai__panel" aria-labelledby="result-title" delay={100}>
      <div className="tryai__panel-head">
        <h2 id="result-title" className="h3">
          {t('tryAi.result.title')}
        </h2>
        <ComingSoon />
      </div>

      <figure className="empty-frame empty-frame--result">
        <div className="empty-frame__body skeleton">
          <ImageOff size={28} aria-hidden="true" />
          <p>{t('tryAi.result.imagePlaceholder')}</p>
        </div>
        <figcaption className="legend-chips">
          <span className="legend-chip legend-chip--trash">
            <span className="legend-chip__dot" aria-hidden="true" />
            {t('tryAi.result.legendTrash')}
          </span>
          <span className="legend-chip legend-chip--drain">
            <span className="legend-chip__dot" aria-hidden="true" />
            {t('tryAi.result.legendDrain')}
          </span>
        </figcaption>
      </figure>

      <dl className="metric-tiles">
        <div className="metric-tile">
          <dt>
            <Trash2 size={18} aria-hidden="true" />
            {t('tryAi.result.metricTrash')}
          </dt>
          <dd>{t('tryAi.result.empty')}</dd>
        </div>
        <div className="metric-tile">
          <dt>
            <Waves size={18} aria-hidden="true" />
            {t('tryAi.result.metricDrain')}
          </dt>
          <dd>{t('tryAi.result.empty')}</dd>
        </div>
      </dl>

      <div className="scale">
        <p className="scale__title">{t('tryAi.result.scaleTitle')}</p>
        <ul className="scale__levels">
          {levels.map((l, i) => (
            <li key={l} className={`scale__level scale__level--${i}`}>
              {l}
            </li>
          ))}
        </ul>
        <p className="scale__note">{t('tryAi.result.thresholds')}</p>
      </div>

      <div className="scale">
        <p className="scale__title">{t('tryAi.result.drainTitle')}</p>
        <ul className="scale__levels scale__levels--3">
          {drainStates.map((s, i) => (
            <li key={s} className={`scale__level scale__level--d${i}`}>
              {s}
            </li>
          ))}
        </ul>
      </div>

      <div className="confidence">
        <span className="confidence__label">
          <Gauge size={18} aria-hidden="true" />
          {t('tryAi.result.confidence')}
        </span>
        <span className="confidence__value">{t('tryAi.result.empty')}</span>
        <span className="confidence__note">{t('tryAi.result.confidenceNote')}</span>
      </div>
    </Reveal>
  );
}

export default function TryAI() {
  const { t } = useI18n();
  useDocumentTitle(t('meta.tryAi'));
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
          <UploadPanel />
          <ResultPanel />
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
