import Section from '../components/Section.jsx';
import Badge from '../components/Badge.jsx';
import Card from '../components/Card.jsx';
import { TEST_META, RESULT_ROWS } from '../data/evidence.js';
import { TimingChart, HeightChart, PositionChart } from './evidence/Charts.jsx';

export default function Evidence() {
  return (
    <Section
      id="evidence"
      alt
      eyebrow="Evidence"
      title={`Field test ${TEST_META.id}: what worked and what did not`}
      lead={`${TEST_META.date}, ${TEST_META.place}, ${TEST_META.setup}. We report passes, a bias and two fails side by side.`}
    >
      <div className="table-wrap">
        <table className="results">
          <caption className="sr-only">Field test B01 results with verdicts</caption>
          <thead>
            <tr>
              <th scope="col">Test</th>
              <th scope="col">Result</th>
              <th scope="col">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {RESULT_ROWS.map((r) => (
              <tr key={r.test}>
                <th scope="row" data-label="Test">{r.test}</th>
                <td data-label="Result">{r.result}</td>
                <td data-label="Verdict">
                  <Badge variant={r.verdict}>{r.label}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="callout">
        <strong>Honest note:</strong> single session, one operator, one location, daytime.
      </p>

      <h3 className="charts-title">The charts behind the table</h3>
      <div className="charts-grid">
        <Card title="Upload and analysis speed" className="chart-card">
          <TimingChart />
        </Card>
        <Card title="Camera height from the marker" className="chart-card">
          <HeightChart />
        </Card>
        <Card title="Where the litter lands on the map" className="chart-card chart-card-wide">
          <div className="pos-layout">
            <PositionChart />
            <div className="pos-notes">
              <p>
                A point object was placed at 9 known positions around the marker board and photographed 28 times. Each
                line links a true position (+) to what the system measured (dot).
              </p>
              <p>
                Most shots land within 20 cm. The measured points sit slightly further away from the camera than the
                true ones, a bias of about +7 cm along the board&rsquo;s +Y axis. We believe this is object height, but
                it is not yet confirmed.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </Section>
  );
}
