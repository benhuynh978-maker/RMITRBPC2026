import Section from '../components/Section.jsx';
import Card from '../components/Card.jsx';
import Badge from '../components/Badge.jsx';
import AlertMap from './demo/AlertMap.jsx';
import SmoothingDemo from './demo/SmoothingDemo.jsx';
import PhotoExplorer from './demo/PhotoExplorer.jsx';
import BoardCalculator from './demo/BoardCalculator.jsx';

export default function Demo() {
  return (
    <Section
      id="demo"
      eyebrow="See it in action"
      title="Try the ideas yourself"
      lead="Static demos with pre-computed data. No upload needed."
    >
      <div className="demo-stack">
        <AlertMap />
        <SmoothingDemo />
        <PhotoExplorer />
        <div className="grid grid-2 demo-pair">
          <BoardCalculator />
          <Card
            className="demo-card card-disabled"
            title="Try it live"
            badge={<Badge variant="demo">Demo / coming soon</Badge>}
            aria-disabled="true"
          >
            <p className="muted">
              Coming soon: visitors will be able to upload a photo of a street drain and see the AI result right here.
              The link will be added later.
            </p>
            <button type="button" className="btn btn-dark" disabled>
              Upload a photo (coming soon)
            </button>
          </Card>
        </div>
      </div>
    </Section>
  );
}
