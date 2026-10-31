import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { I18nProvider, useI18n } from './i18n/I18nProvider.jsx';
import Nav from './components/Nav.jsx';
import Footer from './components/Footer.jsx';
import ScrollManager from './components/ScrollManager.jsx';
import Home from './pages/Home.jsx';

// Try-AI and 404 are split into their own chunks.
const TryAI = lazy(() => import('./pages/TryAI.jsx'));
const Lab = lazy(() => import('./pages/Lab.jsx'));
const DrainLab = lazy(() => import('./pages/DrainLab.jsx'));
const NotFound = lazy(() => import('./pages/NotFound.jsx'));

// v2.0 had separate pages; their content now lives in home-page sections.
const LEGACY_REDIRECTS = [
  ['/cong-nghe', '/#cach-hoat-dong'],
  ['/thu-nghiem', '/'],
  ['/lien-he', '/#lien-he'],
];

function PageFallback() {
  const { t } = useI18n();
  return (
    <div className="page-fallback" role="status">
      <span className="sr-only">{t('common.loading')}</span>
    </div>
  );
}

function Layout() {
  const { t } = useI18n();
  return (
    <>
      <a className="skip-link" href="#main">
        {t('common.skip')}
      </a>
      <Nav />
      <main id="main" tabIndex={-1}>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/thu-ai" element={<TryAI />} />
            <Route path="/hieu-chinh" element={<Lab />} />
            <Route path="/hieu-chinh/cong" element={<DrainLab />} />
            {LEGACY_REDIRECTS.map(([from, to]) => (
              <Route key={from} path={from} element={<Navigate to={to} replace />} />
            ))}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
    </>
  );
}

export default function App() {
  return (
    <I18nProvider>
      <BrowserRouter>
        <ScrollManager />
        <Layout />
      </BrowserRouter>
    </I18nProvider>
  );
}
