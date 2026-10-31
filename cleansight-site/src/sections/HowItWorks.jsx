import Section from '../components/Section.jsx';
import Card from '../components/Card.jsx';
import Badge from '../components/Badge.jsx';

const STEPS = [
  {
    n: 1,
    name: 'Capture',
    badge: <Badge variant="prototype">Prototype design</Badge>,
    lead: 'A fixed camera takes periodic photos of one street drain.',
    items: [
      'Camera: ESP32-S3 with an OV5640 sensor',
      'Connection: 4G modem (A7670C)',
      'Power: battery plus solar panel',
      'Periodic photos, not a video stream',
    ],
  },
  {
    n: 2,
    name: 'Understand',
    lead: 'AI reads each photo and turns it into numbers.',
    items: [
      'YOLO26s-seg outlines Trash and Drain in the image',
      'A drain-blockage index is measured inside a fixed drain zone',
      'Temporal smoothing keeps the drain state from flickering between photos',
    ],
  },
  {
    n: 3,
    name: 'Act',
    lead: 'A map tells crews where to go first.',
    items: [
      'Road alert level, drain state and litter zones shown on the map',
      'Rain data from Open-Meteo raises the alert by one level',
      'Crews see the most urgent roads and drains first',
    ],
  },
];

export default function HowItWorks() {
  return (
    <Section
      id="how"
      alt
      eyebrow="How it works"
      title="Capture, understand, act"
      lead="Three steps from a photo of a drain to a task on a crew’s map."
    >
      <ol className="steps grid grid-3">
        {STEPS.map((s) => (
          <li key={s.n} className="steps-item">
            <Card className="step-card">
              <div className="step-top">
                <span className="step-num" aria-hidden="true">{s.n}</span>
                {s.badge}
              </div>
              <h3>
                <span className="sr-only">Step {s.n}: </span>
                {s.name}
              </h3>
              <p className="step-lead">{s.lead}</p>
              <ul className="tick-list">
                {s.items.map((it) => (
                  <li key={it}>{it}</li>
                ))}
              </ul>
            </Card>
          </li>
        ))}
      </ol>

      <figure className="figure">
        <img
          src="/img/architecture.png"
          width="1745"
          height="994"
          loading="lazy"
          alt="System architecture diagram. Column 1, Capture: a fixed camera (ESP32-S3 with OV5640, 4G modem A7670C, battery and solar power) and a smartphone for calibration photos send images over HTTPS and 4G to column 2, the Node.js backend, which queues jobs, stores results, smooths the drain state, aggregates per road, scores the alert level and adds Open-Meteo rain data. The backend sends jobs to column 3, the Python AI worker (YOLO26s-seg for Trash and Drain, brightness quality gate, blockage inside the drain zone, trash zones projected onto the map), and receives results. Calibration data (drain zone, camera pose from an ArUco marker board, board position and heading) is stored and used by the AI worker. Column 4, the React and Leaflet map web app, shows road alert level, drain state and trash zones from the backend's data API."
        />
        <figcaption>
          System overview: photos flow from the camera to the backend, through the AI worker, and back as road alerts
          on the map. The camera hardware shown is a <strong>prototype design</strong>.
        </figcaption>
      </figure>
    </Section>
  );
}
