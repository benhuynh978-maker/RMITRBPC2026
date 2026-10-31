import Section from '../components/Section.jsx';
import Card from '../components/Card.jsx';

const AUDIENCES = [
  {
    name: 'Environmental-cleaning units',
    points: [
      'Prioritised pick-up spots instead of fixed routes alone',
      'Aims to cut empty trips to streets that are already clean',
      'A clear task list: where to go and which drain first',
    ],
  },
  {
    name: 'Local governments (ward and district offices)',
    points: [
      'See which drains look blocked, so they can be cleared first',
      'Evidence of where litter builds up, to support planning',
      'One shared map for the road and drain status in an area',
    ],
  },
  {
    name: 'Businesses and campuses',
    points: [
      'Property managers can keep entrances, car parks and drains clear',
      'Spot trouble spots on your own site before they become complaints',
      'A shared view for facilities staff and cleaning contractors',
    ],
  },
];

export default function Who() {
  return (
    <Section
      id="who"
      eyebrow="Who it’s for"
      title="Built for the people who keep streets clear"
      lead="The same map serves crews, offices and site managers."
    >
      <div className="grid grid-3">
        {AUDIENCES.map((a) => (
          <Card key={a.name} title={a.name}>
            <ul className="tick-list">
              {a.points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </Section>
  );
}
