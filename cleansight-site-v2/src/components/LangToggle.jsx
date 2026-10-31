import { useI18n } from '../i18n/I18nProvider.jsx';

/** "VI | EN" segmented toggle. */
export default function LangToggle({ className = '' }) {
  const { lang, setLang, t } = useI18n();
  return (
    <div className={`lang ${className}`.trim()} role="group" aria-label={t('nav.langGroup')}>
      <button
        type="button"
        className="lang__btn"
        aria-pressed={lang === 'vi'}
        lang="vi"
        title={t('nav.langVi')}
        onClick={() => setLang('vi')}
      >
        <span aria-hidden="true">VI</span>
        <span className="sr-only">{t('nav.langVi')}</span>
      </button>
      <span className="lang__sep" aria-hidden="true">
        |
      </span>
      <button
        type="button"
        className="lang__btn"
        aria-pressed={lang === 'en'}
        lang="en"
        title={t('nav.langEn')}
        onClick={() => setLang('en')}
      >
        <span aria-hidden="true">EN</span>
        <span className="sr-only">{t('nav.langEn')}</span>
      </button>
    </div>
  );
}
