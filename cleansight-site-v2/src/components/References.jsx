import { ChevronDown } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import { REFERENCES, ENGLISH_SOURCES } from '../lib/references.js';

/**
 * Numbered reference list (numbers kept from the project report), collapsed by default.
 * Citation links (#ref-n) open it: see RefMarks and ScrollManager.
 */
export default function References({ ids }) {
  const { t, lang } = useI18n();
  return (
    <section className="refs" aria-labelledby="refs-title">
      <div className="container">
        <details className="refs__details">
          <summary className="refs__summary">
            <h2 id="refs-title" className="refs__title">
              {t('common.refsTitle')} <span className="refs__count">({ids.length})</span>
            </h2>
            <ChevronDown size={20} aria-hidden="true" className="refs__chevron" />
          </summary>
          <p className="refs__note">{t('common.refsNote')}</p>
          <ol className="refs__list">
            {ids.map((n) => (
              <li key={n} id={`ref-${n}`} tabIndex={-1}>
                <span className="refs__num">[{n}]</span>
                <span lang={lang === 'en' && !ENGLISH_SOURCES.has(n) ? 'vi' : undefined}>{REFERENCES[n]}</span>
              </li>
            ))}
          </ol>
        </details>
      </div>
    </section>
  );
}
