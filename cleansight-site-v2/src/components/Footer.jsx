import { Link } from 'react-router-dom';
import { Mail, Globe } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import { NAV_ITEMS, navTarget } from '../lib/routes.js';
import { CONTACT_EMAIL } from '../lib/config.js';
import Logo from './Logo.jsx';

export default function Footer() {
  const { t } = useI18n();
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer__grid">
          <div className="footer__brand">
            <Logo inverted />
            <p className="footer__slogan">{t('brand.slogan')}</p>
            <p>{t('footer.blurb')}</p>
          </div>

          <nav aria-labelledby="footer-pages">
            <h2 id="footer-pages" className="footer__title">
              {t('footer.pagesTitle')}
            </h2>
            <ul className="footer__links">
              {NAV_ITEMS.map((item) => (
                <li key={item.key}>
                  <Link to={navTarget(item)}>{t(`nav.${item.key}`)}</Link>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <h2 className="footer__title">{t('footer.contactTitle')}</h2>
            <p className="footer__email">
              <Mail size={18} aria-hidden="true" />
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
            </p>
          </div>

          <div>
            <h2 className="footer__title">{t('footer.sdgTitle')}</h2>
            <p className="footer__sdg">
              <Globe size={18} aria-hidden="true" />
              <span>{t('footer.sdgText')}</span>
            </p>
          </div>
        </div>

        <div className="footer__bottom">
          <p>{t('footer.copyright')}</p>
          <p>{t('footer.prototypeNote')}</p>
        </div>
      </div>
    </footer>
  );
}
