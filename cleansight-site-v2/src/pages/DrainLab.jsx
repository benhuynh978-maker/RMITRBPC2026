import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Loader, Waves } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider.jsx';
import useDocumentTitle from '../hooks/useDocumentTitle.js';
import PageHero from '../components/PageHero.jsx';
import Section from '../components/Section.jsx';
import Reveal from '../components/Reveal.jsx';
import Button from '../components/Button.jsx';
import { RoiCanvas } from '../components/lab/RoiCanvas.tsx';
import { RoiToolbar } from '../components/lab/RoiToolbar.tsx';
import { ROI_MAX_POINTS, ROI_MIN_POINTS, isValidPolygon } from '../lib/roiGeometry.ts';
import { labErrorText, labPost } from '../lib/labApi.js';
import useDemoStatus from '../lib/useDemoStatus.js';

// Phòng thử vẽ vùng cống: phần vẽ (RoiCanvas, RoiToolbar, roiGeometry) là mã của giao diện cống trong ssc-v2, giữ nguyên;
// nút "Measure" gọi dịch vụ live demo (analysis.analyze(roi=...)) thay vì lưu ROI vào camera. Trang này chỉ có tiếng Anh.
const SAMPLE = { id: 'drain-litter', src: '/img/lab/drain-litter.jpg' };
const pct = (n) => (typeof n === 'number' ? n.toLocaleString('en-US', { maximumFractionDigits: 1 }) : '?');

function Status({ service }) {
  const { t } = useI18n();
  return (
    <p className={`live-status live-status--${service}`} role="status">
      <span className="live-status__dot" aria-hidden="true" />
      {t(`tryAi.live.status.${service}`)}
    </p>
  );
}

function ResultCard({ result }) {
  return (
    <div className="dpt-result" role="status">
      <p className="dpt-method">Calculated from the drain zone you drew</p>
      {typeof result.drain_blockage_pct === 'number' ? (
        <p className="dpt-big">Drain inlet coverage: {pct(result.drain_blockage_pct)}%</p>
      ) : (
        <p className="dpt-big dpt-big-unknown">Drain inlet coverage could not be measured.</p>
      )}
      <p className="dpt-line">Litter level in the whole image: {pct(result.waste_coverage_pct)}%</p>
      {typeof result.certainty === 'number' && <p className="dpt-line">Model certainty inside the zone: {pct(result.certainty * 100)}%</p>}
      {result.no_trash_in_roi && <p className="dpt-flag">No litter in the drain zone</p>}
      <p className="dpt-line">Time for the model to answer: {(result.inference_ms / 1000).toFixed(1)} s</p>
      <figure className="dpt-image">
        <img src={result.annotated_jpg} width={result.image_size?.[0]} height={result.image_size?.[1]} alt="The sample photo with your drain zone (green) and the litter the model outlined (blue)." />
        <figcaption className="muted">Green line: your drain zone. Blue: what the model outlined as litter.</figcaption>
      </figure>
      <details className="lab-method">
        <summary>How it is calculated</summary>
        <ul>
          <li>Drain inlet coverage = pixels the model outlined as litter inside your zone ÷ pixels of your zone. A fully covered inlet still gets a number, because the zone is drawn by a person, not found by the model.</li>
          <li>The figure measures litter inside the outlined zone and does not check whether a real drain is there: a zone drawn on a heap of litter away from any drain gives a high number too. It is only meaningful when the camera is fixed and the zone matches the drain inlet; if the camera shifts the result is wrong and the system cannot tell.</li>
          <li>This lab shows one photo. The real system takes the median of the latest readings and holds a state with hysteresis so the status does not flicker (not shown here), and has not been shown to make the measurement more accurate.</li>
        </ul>
      </details>
      <p className="muted dpt-honest">Reference indicator only: the AI model still misses some litter and can outline things that are not litter.</p>
    </div>
  );
}

export default function DrainLab() {
  const { t } = useI18n();
  useDocumentTitle(t('meta.drainLab'));
  const [service] = useDemoStatus();
  const [points, setPoints] = useState([]);
  const [selected, setSelected] = useState(null);
  const [phase, setPhase] = useState('idle'); // idle | measuring
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const busyRef = useRef(false);
  const requestRef = useRef(null);
  const resultRef = useRef(null);

  useEffect(() => () => requestRef.current?.abort(), []);
  useEffect(() => {
    if (!result) return;
    const reduce = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    resultRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'nearest' });
  }, [result]);

  const check = useMemo(() => isValidPolygon(points), [points]);
  const locked = phase !== 'idle';
  const online = service === 'online';
  const canMeasure = check.ok && !locked && online;
  const sel = selected !== null && selected < points.length ? selected : null;
  const n = points.length;

  async function measure() {
    if (busyRef.current || !canMeasure) return; // chống bấm đúp
    busyRef.current = true;
    const controller = new AbortController();
    requestRef.current = controller;
    setPhase('measuring');
    setError('');
    try {
      const r = await labPost('/api/lab/drain/measure', { sample_id: SAMPLE.id, polygon: points.map(([x, y]) => [x, y]) }, controller.signal);
      if (controller.signal.aborted) return;
      if (r.status === 200 && r.data?.ok) setResult(r.data);
      else setError(labErrorText(r));
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(labErrorText(e));
    } finally {
      busyRef.current = false;
      if (!controller.signal.aborted) setPhase('idle');
    }
  }

  return (
    <>
      <PageHero
        eyebrow="Calibration lab"
        title="Draw the drain zone"
        lead="A person outlines the drain inlet once. The system then measures how much of that zone is covered by litter."
      />
      <Section id="drain-lab" titleId="drain-lab-title" tight>
        <div className="lab-drain">
          <p className="lab-back">
            <Link to="/hieu-chinh">
              <ArrowLeft size={16} aria-hidden="true" /> Calibration lab
            </Link>
          </p>
          <Reveal as="section" className="card lab-card" aria-labelledby="drain-lab-title">
            <h2 id="drain-lab-title" className="h3">
              <Waves size={20} aria-hidden="true" /> Outline the drain inlet
            </h2>
            <p className="roi-help">
              Outline the drain inlet as you see it in the photo (pixel accuracy is not needed; a shift of about 10% adds almost no error). This is the team&rsquo;s own sample photo: litter covers part of the inlet.
            </p>
            <Status service={service} />
            <ul className="roi-legend" aria-label="Legend">
              <li><span className="roi-swatch roi-swatch-draft" aria-hidden="true" /> Zone being drawn (solid, light fill)</li>
            </ul>

            <RoiCanvas
              src={SAMPLE.src}
              points={points}
              selected={sel}
              locked={locked}
              onChange={setPoints}
              onSelect={setSelected}
              onImageLoad={() => {}}
            />
            <p className="muted roi-hint">Click the photo to add a point, drag a point to adjust. Keyboard: Tab to a point, arrow keys to move (Shift to move faster), Delete to remove the point.</p>

            <p className="roi-count" aria-live="polite"><strong>{n} points ({ROI_MIN_POINTS}–{ROI_MAX_POINTS})</strong></p>
            {n > 0 && n < ROI_MIN_POINTS && <p className="muted" role="status">At least {ROI_MIN_POINTS} points are needed to measure ({n} so far).</p>}
            {n >= ROI_MIN_POINTS && check.errors.length > 0 && <ul className="roi-errors" role="alert">{check.errors.map((m) => <li key={m}>{m}</li>)}</ul>}

            <RoiToolbar
              count={n}
              hasSelection={sel !== null}
              hasSaved={false}
              showLoadSaved={false}
              disabled={locked}
              onUndo={() => { setPoints(points.slice(0, -1)); setSelected(null); }}
              onDeleteSelected={() => { if (sel !== null) { setPoints(points.filter((_, i) => i !== sel)); setSelected(null); } }}
              onClear={() => { setPoints([]); setSelected(null); }}
            />

            <div className="roi-actions lab-measure">
              <Button disabled={!canMeasure} onClick={measure} icon={phase === 'measuring' ? Loader : undefined}>
                {phase === 'measuring' ? 'Measuring…' : 'Measure drain coverage'}
              </Button>
            </div>
            {!online && service !== 'checking' && <p className="muted" role="status">{t('tryAi.live.offlineNote')}</p>}
            {error && (
              <p className="roi-error lab-error" role="alert">
                <AlertCircle size={18} aria-hidden="true" />
                <span>{error}</span>
              </p>
            )}
          </Reveal>

          {result && (
            <div ref={resultRef} className="lab-result">
              <Reveal as="section" className="card lab-card" aria-label="Measurement result">
                <h2 className="h3">Result</h2>
                <ResultCard result={result} />
              </Reveal>
            </div>
          )}
        </div>
      </Section>
    </>
  );
}
