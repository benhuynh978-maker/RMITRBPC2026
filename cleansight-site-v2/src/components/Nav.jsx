import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import { NAV_ITEMS, navTarget } from '../lib/routes.js';
import Logo from './Logo.jsx';
import LangToggle from './LangToggle.jsx';
import Button from './Button.jsx';

// Keep in sync with the burger breakpoint in components.css.
const DESKTOP_MQ = '(min-width: 1240px)';
const CONTACT_TARGET = { pathname: '/', hash: '#lien-he' };

export default function Nav() {
  const { t } = useI18n();
  const { key } = useLocation();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  // Border + blur once the page has scrolled.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Close the drawer on every navigation, including same-page #section links.
  useEffect(() => {
    setOpen(false);
  }, [key]);

  // Escape closes the drawer; lock page scroll while it is open.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    document.body.classList.add('no-scroll');
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.classList.remove('no-scroll');
    };
  }, [open]);

  // Leave drawer state behind when resizing up to desktop.
  useEffect(() => {
    const mq = window.matchMedia(DESKTOP_MQ);
    const onChange = (e) => e.matches && setOpen(false);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const close = () => setOpen(false);

  const links = NAV_ITEMS.map((item) => (
    <li key={item.key}>
      {item.hash ? (
        <Link to={navTarget(item)} className="nav__link" onClick={close}>
          {t(`nav.${item.key}`)}
        </Link>
      ) : (
        <NavLink to={item.path} className="nav__link" onClick={close}>
          {t(`nav.${item.key}`)}
        </NavLink>
      )}
    </li>
  ));

  return (
    <header className={`nav${scrolled ? ' nav--scrolled' : ''}${open ? ' nav--open' : ''}`}>
      <div className="container nav__inner">
        <Link to="/" className="nav__brand" aria-label={t('nav.homeLink')}>
          <Logo />
        </Link>

        <nav className="nav__desktop" aria-label={t('nav.label')}>
          <ul className="nav__list">{links}</ul>
        </nav>

        <div className="nav__actions">
          <LangToggle />
          <Button to={CONTACT_TARGET} size="sm" className="nav__cta">
            {t('nav.cta')}
          </Button>
          <button
            type="button"
            className="nav__burger"
            aria-expanded={open}
            aria-controls="mobile-menu"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X size={22} aria-hidden="true" /> : <Menu size={22} aria-hidden="true" />}
            <span className="sr-only">{open ? t('nav.menuClose') : t('nav.menuOpen')}</span>
          </button>
        </div>
      </div>

      <div id="mobile-menu" className="nav__drawer" hidden={!open}>
        <nav className="container" aria-label={t('nav.label')}>
          <ul className="nav__drawer-list">{links}</ul>
          <Button to={CONTACT_TARGET} className="nav__drawer-cta" onClick={close}>
            {t('nav.cta')}
          </Button>
        </nav>
      </div>
    </header>
  );
}
