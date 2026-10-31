import { House } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import useDocumentTitle from '../hooks/useDocumentTitle.js';
import Button from '../components/Button.jsx';

export default function NotFound() {
  const { t } = useI18n();
  useDocumentTitle(t('meta.notFound'));
  return (
    <section className="notfound" aria-labelledby="nf-title">
      <div className="container notfound__inner">
        <p className="notfound__code" aria-hidden="true">
          {t('notFound.code')}
        </p>
        <h1 id="nf-title" className="h2">
          {t('notFound.title')}
        </h1>
        <p className="lead">{t('notFound.text')}</p>
        <Button to="/" icon={House}>
          {t('notFound.button')}
        </Button>
      </div>
    </section>
  );
}
