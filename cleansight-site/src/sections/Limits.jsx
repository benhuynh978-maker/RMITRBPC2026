import Section from '../components/Section.jsx';
import Badge from '../components/Badge.jsx';

const LIMITS = [
  ['Periodic photos', 'CleanSight works from photos taken on a schedule. It is not real-time and it is not a flood forecast. It gives early warning of clogged drains.'],
  ['Daytime only', 'CleanSight is built for daytime photos only.'],
  ['One camera, one drain', 'Each camera watches a single drain.'],
  ['Marker board at setup', 'The litter map needs a printed marker board in view during setup.'],
  ['Detection is still modest', 'Recall is 0.44 on our validation set: the model still misses litter.'],
  ['Privacy blurring is planned, not built', 'Automatic blurring of faces and licence plates is planned but NOT yet implemented. The cameras point at the ground and the drain.'],
  ['Litter area is not reliable yet', 'The area estimate for small objects is not yet reliable (see the field test).'],
];

const ROADMAP = [
  'Larger retest of litter area',
  'Better detection model',
  'Privacy blurring',
  'Live try-it page',
  'Pilot with partners',
];

export default function Limits() {
  return (
    <Section
      id="limits"
      eyebrow="Limits and roadmap"
      title="What CleanSight cannot do yet"
      lead="We would rather you know the limits now than find them in the field."
    >
      <ul className="limit-list">
        {LIMITS.map(([t, d]) => (
          <li key={t} className="limit-item">
            <svg className="limit-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
              <path d="M12 2 1 21h22L12 2zm1 14h-2v-2h2v2zm0-4h-2V8h2v4z" />
            </svg>
            <div>
              <h3>{t}</h3>
              <p>{d}</p>
            </div>
          </li>
        ))}
      </ul>

      <h3 className="roadmap-title">Roadmap</h3>
      <ul className="chip-list" aria-label="Roadmap items">
        {ROADMAP.map((r) => (
          <li key={r}>
            <Badge variant="prototype">{r}</Badge>
          </li>
        ))}
      </ul>
    </Section>
  );
}
