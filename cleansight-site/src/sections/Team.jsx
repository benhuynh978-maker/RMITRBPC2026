import Section from '../components/Section.jsx';
import Card from '../components/Card.jsx';
import Badge from '../components/Badge.jsx';
import { TEAM_NAME, SCHOOL, CONTACT_EMAIL, MEMBERS } from '../data/team.js';

function Avatar() {
  return (
    <svg className="avatar" viewBox="0 0 64 64" role="img" aria-label="Generic avatar placeholder" width="64" height="64">
      <circle cx="32" cy="32" r="32" fill="#d8eef0" />
      <circle cx="32" cy="25" r="11" fill="#5b7f88" />
      <path d="M10 56c3-12 12-18 22-18s19 6 22 18a32 32 0 0 1-44 0z" fill="#5b7f88" />
    </svg>
  );
}

export default function Team() {
  return (
    <Section
      id="team"
      alt
      eyebrow="Team"
      title="Who is behind CleanSight"
      lead="Team details below are placeholders until the final line-up is confirmed."
    >
      <div className="grid grid-2 team-top">
        <Card title={`Team ${TEAM_NAME}`} badge={<Badge variant="placeholder">Placeholder</Badge>}>
          <p>{SCHOOL}</p>
        </Card>
        <Card title="Contact" badge={<Badge variant="placeholder">Placeholder</Badge>}>
          <p>{CONTACT_EMAIL}</p>
        </Card>
      </div>

      <ul className="team-grid">
        {MEMBERS.map((m, i) => (
          <li key={i}>
            <Card className="member">
              <Avatar />
              <h3>{m.name}</h3>
              <p className="muted small">{m.role}</p>
              <Badge variant="placeholder">Placeholder</Badge>
            </Card>
          </li>
        ))}
      </ul>
    </Section>
  );
}
