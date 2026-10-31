import Section from '../components/Section.jsx';
import Card from '../components/Card.jsx';

const CARDS = [
  {
    q: 'Where?',
    icon: (
      <path d="M12 2c-4.4 0-8 3.5-8 7.9C4 15.5 12 22 12 22s8-6.5 8-12.1C20 5.5 16.4 2 12 2zm0 10.5a2.6 2.6 0 1 1 0-5.2 2.6 2.6 0 0 1 0 5.2z" />
    ),
    text: 'Crews follow fixed routes. Nobody sees which street corner is quietly filling up with litter, so the worst spots can wait the longest.',
  },
  {
    q: 'When?',
    icon: <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 5v5.4l3.6 2.1-.8 1.3L11 13V7h2z" />,
    text: 'Collection runs on a schedule, not on need. Litter can pile up the day before a storm, right when drains are about to be tested.',
  },
  {
    q: 'Which drain?',
    icon: (
      <path d="M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm2 3v8h2V8H6zm4 0v8h2V8h-2zm4 0v8h2V8h-2z" />
    ),
    text: 'There are far more drains than people to check them. Without a signal, a blocked drain inlet is often found only after the street has flooded.',
  },
];

export default function Problem() {
  return (
    <Section
      id="problem"
      eyebrow="The problem"
      title="Litter blocks drains. Crews can’t see where or when."
      lead="In rainy-season cities such as Ho Chi Minh City, litter that settles on drain inlets can block them and turn a heavy shower into local street flooding. Collection is organised by fixed routes and schedules, so crews do not know where litter is piling up, or when."
    >
      <div className="grid grid-3">
        {CARDS.map((c) => (
          <Card key={c.q} className="problem-card">
            <svg className="icon" viewBox="0 0 24 24" width="32" height="32" aria-hidden="true" focusable="false">
              {c.icon}
            </svg>
            <h3>{c.q}</h3>
            <p className="muted">{c.text}</p>
          </Card>
        ))}
      </div>
    </Section>
  );
}
