import { Camera, Server, BrainCircuit, Map as MapIcon, CloudRain } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import Reveal from './Reveal.jsx';

const BLOCK_ICONS = [Camera, Server, BrainCircuit, MapIcon];

/** Dashed arrow pointing right; CSS rotates it to point down (stacked layout) or up (rain branch). */
function Arrow({ className }) {
  return (
    <span className={className} aria-hidden="true">
      <svg viewBox="0 0 48 16" width="48" height="16" focusable="false">
        <path d="M2 8h36" stroke="currentColor" strokeWidth="2" strokeDasharray="5 4" strokeLinecap="round" fill="none" />
        <path d="M35 2.5 43 8l-8 5.5" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </svg>
    </span>
  );
}

/**
 * Plain-language system diagram: Camera → Server → AI → Alert map, plus a rain-forecast branch into the map.
 * HTML/CSS only: horizontal from 1024px, a vertical stack with down-arrows below that.
 * Content is real text in an ordered list, so screen readers read it as four steps.
 */
export default function ArchitectureDiagram() {
  const { t } = useI18n();
  const blocks = t('home.how.blocks');

  return (
    <Reveal as="figure" className="flow" aria-label={t('home.how.figLabel')}>
      <ol className="flow__row">
        {blocks.map((b, i) => {
          const Icon = BLOCK_ICONS[i];
          const last = i === blocks.length - 1;
          return (
            <li key={b.title} className={`flow__block${last ? ' flow__block--out' : ''}`}>
              <span className="flow__icon" aria-hidden="true">
                <Icon size={26} />
              </span>
              <div>
                <h3 className="flow__title">{b.title}</h3>
                <p className="flow__text">{b.text}</p>
              </div>
              {!last && <Arrow className="flow__arrow" />}
            </li>
          );
        })}
      </ol>

      <div className="flow__branch-row">
        <div className="flow__branch">
          <Arrow className="flow__arrow flow__arrow--up" />
          <span className="flow__icon flow__icon--soft" aria-hidden="true">
            <CloudRain size={22} />
          </span>
          <p>
            <strong>{t('home.how.rain.title')}</strong>
            <span className="flow__branch-sep" aria-hidden="true">
              {' '}
              →{' '}
            </span>
            <span className="sr-only">: </span>
            {t('home.how.rain.text')}
          </p>
        </div>
      </div>
    </Reveal>
  );
}
