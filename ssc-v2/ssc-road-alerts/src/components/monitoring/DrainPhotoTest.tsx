import { useEffect, useId, useRef, useState } from 'react';
import { formatPct } from '../../config/drain';
import { CaptureError, resizeToJpeg, uploadCapture, waitForAnalysis } from '../../services/captureService';
import type { AnalysisImages, AnalysisMonitoring } from '../../services/captureService';
import './drain-photo-test.css';

/** Phần tối thiểu của Camera mà khung này cần (Camera thật tương thích cấu trúc). */
export interface PhotoTestCamera { camera_id: string; drain_roi?: unknown }
export interface DrainPhotoTestProps { camera: PhotoTestCamera; onDone: () => void }

type Phase = 'idle' | 'resizing' | 'uploading' | 'waiting' | 'done';
interface Outcome { monitoring: AnalysisMonitoring; images: AnalysisImages; totalMs: number }

const NO_DRAIN_TEXT = 'Drain inlet coverage could not be measured (the model saw no drain and the camera has no drain zone).';
const seconds = (ms: number) => (ms / 1000).toFixed(1);

function AnalyzedImage({ url }: { url?: string }) {
  const [failed, setFailed] = useState(false);
  return <figure className="observation-image dpt-image"><figcaption>AI analysis result image</figcaption>
    {url && !failed
      ? <a href={url} target="_blank" rel="noreferrer"><img src={url} alt="AI analysis result image" onError={() => setFailed(true)} /></a>
      : <div className="image-placeholder">{failed ? 'Could not load the result image. Check the URL or image access.' : 'No analysis result image.'}</div>}
  </figure>;
}

function ResultCard({ outcome }: { outcome: Outcome }) {
  const { monitoring: m, images, totalMs } = outcome;
  return <div className="dpt-result" role="status">
    <p className="dpt-method">{m.blockage_method === 'roi' ? 'Calculated from the drain zone you drew' : 'Calculated with the old formula (no drain zone yet)'}</p>
    {m.drain_blockage_pct !== undefined
      ? <p className="dpt-big">Drain inlet coverage: {formatPct(m.drain_blockage_pct)}%</p>
      : <p className="dpt-big dpt-big-unknown">{NO_DRAIN_TEXT}</p>}
    {m.waste_coverage_pct !== undefined && <p className="dpt-line">Litter level in the image: {formatPct(m.waste_coverage_pct)}%</p>}
    {m.certainty !== undefined && <p className="dpt-line">Model certainty: {formatPct(m.certainty * 100)}%</p>}
    {m.no_trash_in_roi && <p className="dpt-flag">No litter in the drain zone</p>}
    {m.low_certainty && <p className="dpt-flag dpt-flag-warn">Low certainty: the result may be less accurate.</p>}
    <p className="dpt-line">Time from sending to result: {seconds(totalMs)} s</p>
    <AnalyzedImage key={images.analyzed_url ?? 'none'} url={images.analyzed_url} />
    <p className="muted dpt-honest">Reference indicator only: the AI model still misses some litter; the result is only valid when the camera is fixed and the drain zone is drawn correctly.</p>
  </div>;
}

export function DrainPhotoTest({ camera, onDone }: DrainPhotoTestProps) {
  const uid = useId();
  const cameraId = camera.camera_id;
  const hasRoi = !!camera.drain_roi;

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [phase, setPhase] = useState<Phase>('idle');
  const [elapsedMs, setElapsedMs] = useState(0);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string | null>(null);

  const running = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const onDoneRef = useRef(onDone);
  useEffect(() => { onDoneRef.current = onDone; }, [onDone]);

  // Huỷ mọi việc đang chạy khi gỡ khung hoặc đổi camera.
  useEffect(() => () => { controller.current?.abort(); controller.current = null; running.current = false; }, [cameraId]);

  // Object URL cho ảnh xem trước: tạo trong effect (an toàn với StrictMode), luôn thu hồi khi đổi/gỡ.
  useEffect(() => {
    if (!file) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const busy = phase === 'resizing' || phase === 'uploading' || phase === 'waiting';

  function pickFile(next: File | null) {
    setError(null);
    setOutcome(null);
    setPhase('idle');
    if (next && next.type && !next.type.startsWith('image/')) {
      setFile(null);
      setError('The selected file is not an image.');
      return;
    }
    setFile(next);
  }

  function reset() {
    setFile(null); setOutcome(null); setError(null); setPhase('idle'); setElapsedMs(0);
    setInputKey(k => k + 1); // tạo lại <input type=file> để xoá tên tệp cũ
  }

  async function run() {
    if (running.current || !file) return; // chống bấm đúp
    running.current = true;
    const ac = new AbortController();
    controller.current = ac;
    const { signal } = ac;
    setError(null); setOutcome(null); setElapsedMs(0); setPhase('resizing');
    try {
      const jpeg = await resizeToJpeg(file);
      if (signal.aborted) return;
      setPhase('uploading');
      const sentAt = Date.now();
      const up = await uploadCapture(cameraId, jpeg.blob, { signal });
      if (signal.aborted) return;
      if (!up.ok) { setError(up.error); setPhase('idle'); return; }
      setPhase('waiting');
      const res = await waitForAnalysis(cameraId, up.capturedAt, { signal, onTick: ms => { if (!signal.aborted) setElapsedMs(ms); } });
      if (signal.aborted) return;
      if (!res.ok) { setError(res.error); setPhase('idle'); return; }
      setOutcome({ monitoring: res.monitoring, images: res.images, totalMs: Date.now() - sentAt });
      setPhase('done');
      onDoneRef.current(); // cha tải lại danh sách camera
    } catch (e) {
      if (signal.aborted) return;
      setError(e instanceof CaptureError ? e.message : 'Unexpected error while processing the image. Try again or choose another image.');
      setPhase('idle');
    } finally {
      if (controller.current === ac) { controller.current = null; running.current = false; }
    }
  }

  const progress = phase === 'resizing' ? 'Resizing image…'
    : phase === 'uploading' ? 'Sending…'
    : phase === 'waiting' ? `Waiting for AI analysis… ${Math.floor(elapsedMs / 1000)} s`
    : '';

  return <section className="dpt" aria-labelledby={`${uid}-h`}>
    <h3 id={`${uid}-h`}>Send a test photo and see the result</h3>
    <p className="dpt-help">Choose a photo with the SAME framing as the image used to draw the drain zone. The photo is stored on the v2 server running on this machine.</p>
    {!hasRoi && <p className="notice dpt-note">This camera has no drain zone: the result will use the old formula (less reliable when the drain is fully covered).</p>}

    <div className="dpt-pick">
      <label htmlFor={`${uid}-file`}>Photo to analyse</label>
      <input key={inputKey} id={`${uid}-file`} type="file" accept="image/*" disabled={busy}
        onChange={e => pickFile(e.target.files?.[0] ?? null)} />
      {previewUrl && <img className="dpt-thumb" src={previewUrl} alt="Selected photo (preview)" />}
    </div>

    <div className="dpt-actions">
      {phase === 'done'
        ? <button type="button" className="secondary" onClick={reset}>Send another photo</button>
        : <button type="button" className="refresh" disabled={!file || busy} onClick={() => void run()}>Send and analyse</button>}
    </div>

    {progress && <p className="muted dpt-progress" role="status">{progress}</p>}
    {error && <p className="dpt-error" role="alert">{error}</p>}
    {outcome && <ResultCard outcome={outcome} />}
  </section>;
}
