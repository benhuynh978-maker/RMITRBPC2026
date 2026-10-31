import { Clock3, MapPinned, Waves } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import useDocumentTitle from '../hooks/useDocumentTitle.js';
import PageHero from '../components/PageHero.jsx';
import Section from '../components/Section.jsx';
import Reveal from '../components/Reveal.jsx';
import Button from '../components/Button.jsx';
import FeatureCard from '../components/FeatureCard.jsx';
import useDemoStatus from '../lib/useDemoStatus.js';

function Status({ service }) {
  const { t } = useI18n();
  return (
    <p className={`live-status live-status--${service}`} role="status">
      <span className="live-status__dot" aria-hidden="true" />
      {t(`tryAi.live.status.${service}`)}
    </p>
  );
}

export default function Lab() {
  const { t } = useI18n();
  useDocumentTitle(t('meta.lab'));
  const [service] = useDemoStatus();

  return (
    <>
      <PageHero eyebrow={t('lab.hero.eyebrow')} title={t('lab.hero.title')} lead={t('lab.hero.lead')} />
      <Section id="lab" titleId="banner-title" tight>
        <Reveal className="banner">
          <span className="banner__icon" aria-hidden="true">
            <Clock3 size={28} />
          </span>
          <div>
            <h2 id="banner-title" className="h3">
              {t('lab.banner.title')}
            </h2>
            <p>{t('lab.banner.text')}</p>
            <Status service={service} />
          </div>
        </Reveal>

        <ul className="grid grid--2 lab-cards">
          <FeatureCard as="li" icon={MapPinned} kicker="01" title={t('lab.board.title')} text={t('lab.board.text')}>
            <Button href="/lab/board/" className="lab-cta">
              {t('lab.board.cta')}
            </Button>
          </FeatureCard>
          <FeatureCard as="li" icon={Waves} kicker="02" title={t('lab.drain.title')} text={t('lab.drain.text')}>
            <Button to="/hieu-chinh/cong" className="lab-cta">
              {t('lab.drain.cta')}
            </Button>
          </FeatureCard>
        </ul>

        <Reveal as="p" className="note">
          {t('lab.note')}
        </Reveal>
      </Section>
    </>
  );
}
