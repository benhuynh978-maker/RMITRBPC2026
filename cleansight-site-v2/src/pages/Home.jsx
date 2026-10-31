import {
  Activity,
  ArrowRight,
  CalendarClock,
  Cctv,
  Eye,
  Landmark,
  Mail,
  MapPinned,
  Megaphone,
  Recycle,
  Ruler,
  ScanSearch,
  Store,
  Target,
  Trash2,
  Truck,
  Waves,
} from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import useDocumentTitle from '../hooks/useDocumentTitle.js';
import { CONTACT_EMAIL } from '../lib/config.js';
import Section, { SectionHeader } from '../components/Section.jsx';
import Button from '../components/Button.jsx';
import Reveal from '../components/Reveal.jsx';
import StatTile from '../components/StatTile.jsx';
import StepCard from '../components/StepCard.jsx';
import FeatureCard from '../components/FeatureCard.jsx';
import ArchitectureDiagram from '../components/ArchitectureDiagram.jsx';
import RefMarks from '../components/RefMarks.jsx';
import References from '../components/References.jsx';

const PROBLEM_ICONS = [CalendarClock, Megaphone, Waves];
const QUESTION_ICONS = [Trash2, MapPinned, Target];
const DEPLOY_ICONS = [Cctv, Ruler, Truck];
const FEATURE_ICONS = [ScanSearch, Activity, Ruler];
const AUDIENCE_ICONS = [Recycle, Landmark, Store];

function Hero() {
  const { t } = useI18n();
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero__bg" aria-hidden="true" />
      <div className="container hero__inner">
        <Reveal className="hero__copy">
          <p className="eyebrow">{t('home.hero.eyebrow')}</p>
          <h1 id="hero-title" className="display">
            {t('brand.slogan')}
          </h1>
          <p className="lead lead--hero">{t('home.hero.value')}</p>
          <div className="hero__actions">
            <Button to={{ pathname: '/', hash: '#cach-hoat-dong' }} iconAfter={ArrowRight}>
              {t('home.hero.ctaPrimary')}
            </Button>
            <Button to="/thu-ai" variant="secondary" icon={Eye}>
              {t('home.hero.ctaSecondary')}
            </Button>
          </div>
        </Reveal>

        <Reveal className="hero__visual" delay={120}>
          <div className="hero__frame">
            <img
              src="/img/hero.jpg"
              width="1280"
              height="720"
              alt={t('home.hero.imgAlt')}
              fetchPriority="high"
              decoding="async"
            />
            <span className="hero__corner hero__corner--tl" aria-hidden="true" />
            <span className="hero__corner hero__corner--br" aria-hidden="true" />
            <p className="hero__caption">{t('home.hero.caption')}</p>
          </div>
          <div className="hero__deco" aria-hidden="true" />
        </Reveal>
      </div>
    </section>
  );
}

function Problem() {
  const { t } = useI18n();
  const stats = t('home.problem.stats');
  const points = t('home.problem.points');
  return (
    <Section id="van-de" titleId="problem-title">
      <SectionHeader
        id="problem-title"
        eyebrow={t('home.problem.eyebrow')}
        title={t('home.problem.title')}
        lead={t('home.problem.lead')}
      />
      <div className="grid grid--3 stats-row">
        {stats.map((s, i) => (
          <StatTile key={s.value} value={s.value} label={s.label} refs={s.refs} delay={i * 80} />
        ))}
      </div>
      <ul className="grid grid--3 points">
        {points.map((p, i) => {
          const Icon = PROBLEM_ICONS[i];
          return (
            <Reveal as="li" key={p.title} className="point" delay={i * 80}>
              <span className="point__icon" aria-hidden="true">
                <Icon size={20} />
              </span>
              <div>
                <h3 className="h4">{p.title}</h3>
                <p>
                  {p.text}
                  <RefMarks refs={p.refs} />
                </p>
              </div>
            </Reveal>
          );
        })}
      </ul>
    </Section>
  );
}

function Solution() {
  const { t } = useI18n();
  const qs = t('home.solution.questions');
  return (
    <Section id="giai-phap" titleId="solution-title" alt>
      <SectionHeader
        id="solution-title"
        eyebrow={t('home.solution.eyebrow')}
        title={t('home.solution.title')}
        lead={t('home.solution.lead')}
      />
      <ol className="grid grid--3 questions">
        {qs.map((q, i) => (
          <FeatureCard
            as="li"
            key={q.title}
            icon={QUESTION_ICONS[i]}
            kicker={`0${i + 1}`}
            title={q.title}
            text={q.text}
            delay={i * 80}
          />
        ))}
      </ol>
      <Reveal as="p" className="note">
        {t('home.solution.note')}
      </Reveal>
    </Section>
  );
}

function HowItWorks() {
  const { t } = useI18n();
  return (
    <Section id="cach-hoat-dong" titleId="how-title">
      <SectionHeader id="how-title" eyebrow={t('home.how.eyebrow')} title={t('home.how.title')} lead={t('home.how.lead')} />
      <ArchitectureDiagram />
    </Section>
  );
}

function Deploy() {
  const { t } = useI18n();
  const steps = t('home.deploy.steps');
  return (
    <Section id="trien-khai" titleId="deploy-title" alt>
      <SectionHeader
        id="deploy-title"
        eyebrow={t('home.deploy.eyebrow')}
        title={t('home.deploy.title')}
        lead={t('home.deploy.lead')}
      />
      <ol className="steps grid grid--3">
        {steps.map((s, i) => (
          <StepCard key={s.title} n={i + 1} icon={DEPLOY_ICONS[i]} title={s.title} text={s.text} delay={i * 80} />
        ))}
      </ol>
    </Section>
  );
}

function WhatsNew() {
  const { t } = useI18n();
  const features = t('home.newness.features');
  return (
    <Section id="diem-khac-biet" titleId="new-title">
      <SectionHeader
        id="new-title"
        eyebrow={t('home.newness.eyebrow')}
        title={t('home.newness.title')}
        lead={t('home.newness.lead')}
      />
      <div className="grid grid--3">
        {features.map((f, i) => (
          <FeatureCard key={f.title} icon={FEATURE_ICONS[i]} title={f.title} text={f.text} delay={i * 80} />
        ))}
      </div>
    </Section>
  );
}

function Sdg() {
  const { t } = useI18n();
  const targets = t('home.sdg.targets');
  return (
    <section className="sdg" aria-labelledby="sdg-title">
      <div className="container">
        <Reveal className="sdg__inner">
          <div className="sdg__head">
            <h2 id="sdg-title" className="sdg__title">
              {t('home.sdg.title')}
              <RefMarks refs={[16]} />
            </h2>
            <p className="sdg__lead">{t('home.sdg.lead')}</p>
          </div>
          <ul className="sdg__targets">
            {targets.map((tg, i) => (
              <li key={tg.code} className="sdg__target">
                <span className={`sdg__code${i === 0 ? ' sdg__code--primary' : ''}`}>{tg.code}</span>
                <span>
                  {tg.text}
                  {i === 0 && <span className="sdg__primary">{t('home.sdg.primary')}</span>}
                </span>
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}

function Contact() {
  const { t } = useI18n();
  const items = t('home.contact.audiences');
  return (
    <Section id="lien-he" titleId="contact-title" alt>
      <SectionHeader
        id="contact-title"
        eyebrow={t('home.contact.eyebrow')}
        title={t('home.contact.title')}
        lead={t('home.contact.lead')}
      />
      <ul className="grid grid--3">
        {items.map((it, i) => (
          <FeatureCard as="li" key={it.title} icon={AUDIENCE_ICONS[i]} title={it.title} delay={i * 80}>
            <p>
              {it.text}
              <RefMarks refs={it.refs} />
            </p>
          </FeatureCard>
        ))}
      </ul>
      <Reveal className="contact-email">
        <span className="feature__icon" aria-hidden="true">
          <Mail size={24} />
        </span>
        <div className="contact-email__body">
          <h3 className="h4">{t('home.contact.emailTitle')}</h3>
          <p className="contact-email__line">
            <a className="contact-email__addr" href={`mailto:${CONTACT_EMAIL}`}>
              {CONTACT_EMAIL}
            </a>
          </p>
        </div>
      </Reveal>
    </Section>
  );
}

export default function Home() {
  const { t } = useI18n();
  // Title derives from the single slogan key so changing the slogan updates it too.
  useDocumentTitle(`${t('meta.home')} — ${t('brand.slogan').replace(/\.$/, '')}`);
  return (
    <>
      <Hero />
      <Problem />
      <Solution />
      <HowItWorks />
      <Deploy />
      <WhatsNew />
      <Sdg />
      <References ids={[1, 9, 11, 13, 16]} />
      <Contact />
    </>
  );
}
