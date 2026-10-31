import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { aspectMismatch, formatPolygonString, isValidPolygon, parsePolygonString, ROI_MAX_POINTS, ROI_MIN_POINTS } from '../../lib/roiGeometry';
import type { RoiPoint, Size } from '../../lib/roiGeometry';
import { removeDrainRoi, saveDrainRoi, setAdminKey } from '../../services/roiService';
import type { RoiResult } from '../../services/roiService';
import { KeyForm } from './roi/KeyForm';
import { RoiCanvas } from './roi/RoiCanvas';
import { RoiToolbar } from './roi/RoiToolbar';
import './drain-roi.css';

/** Phần tối thiểu của Camera mà editor cần (Camera thật tương thích cấu trúc). */
export interface RoiCamera {
  camera_id: string;
  name?: string;
  images?: { original_url?: string; analyzed_url?: string; captured_at?: string };
  drain_roi?: { polygon: [number, number][]; source: 'ai' | 'manual'; calibrated_at: string };
}
export interface DrainRoiEditorProps { camera: RoiCamera; onSaved: () => void }

const SAVE_WARNING = 'Saving a new ROI clears this camera\'s smoothed drain status. At least 3 new readings are needed (about 3 minutes if the camera shoots every 60 seconds) before a status shows again.';
const REMOVE_WARNING = 'Removing the ROI reverts to the old formula and clears the smoothed drain status. At least 3 new readings are needed (about 3 minutes if the camera shoots every 60 seconds) before a status shows again.';
const SAVED_OK = 'Drain zone saved. The drain status will reappear after at least 3 new readings (about 3 minutes if the camera shoots every 60 seconds).';
const REMOVED_OK = 'Drain zone removed. The system reverts to the old formula; the drain status will be recalculated after at least 3 new readings.';

type Phase = 'idle' | 'confirmSave' | 'confirmRemove' | 'needKey';
type Action = { kind: 'save'; polygon: RoiPoint[] } | { kind: 'remove' };
type Message = { kind: 'ok' | 'error'; text: string };
type Measured = Size & { src: string };

/** Khung vỏ: <details> thu gọn; chỉ dựng phần thân (ảnh, tải kích thước) sau lần mở đầu tiên. Đặt key theo camera_id để đổi camera là reset. */
export function DrainRoiEditor(props: DrainRoiEditorProps) {
  const [opened, setOpened] = useState(true); // mở sẵn để quay demo không phải tìm
  return <details className="roi-editor" open onToggle={e => { if (e.currentTarget.open) setOpened(true); }}>
    <summary>Draw / calibrate the drain inlet zone (ROI)</summary>
    {opened && <DrainRoiPanel key={props.camera.camera_id} {...props} />}
  </details>;
}

/** Thân editor (export để test render). */
export function DrainRoiPanel({ camera, onSaved }: DrainRoiEditorProps) {
  const uid = useId();
  const originalUrl = camera.images?.original_url;
  const saved = camera.drain_roi?.polygon;

  const [points, setPoints] = useState<RoiPoint[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [photoMode, setPhotoMode] = useState<'camera' | 'upload'>(originalUrl ? 'camera' : 'upload');
  const [file, setFile] = useState<File | null>(null);
  const [uploadUrl, setUploadUrl] = useState<string | null>(null);
  const [uploadSize, setUploadSize] = useState<Measured | null>(null);
  const [cameraSize, setCameraSize] = useState<Measured | null>(null);
  const [ack, setAck] = useState(false);
  const [importText, setImportText] = useState('');
  const [importError, setImportError] = useState('');
  const [copyMsg, setCopyMsg] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<Message | null>(null);

  const mounted = useRef(true);
  const inFlight = useRef(false);
  const pending = useRef<Action | null>(null);
  const onSavedRef = useRef(onSaved);
  useEffect(() => { onSavedRef.current = onSaved; }, [onSaved]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  // Object URL của ảnh tải lên: tạo trong effect (an toàn với StrictMode) và luôn thu hồi khi đổi/gỡ.
  useEffect(() => {
    if (!file) { setUploadUrl(null); return; }
    const url = URL.createObjectURL(file);
    setUploadUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Đọc kích thước ảnh gốc của camera (để so tỉ lệ với ảnh tải lên).
  useEffect(() => {
    if (!originalUrl) return;
    const img = new Image();
    img.onload = () => { if (img.naturalWidth > 0 && img.naturalHeight > 0) setCameraSize({ src: originalUrl, w: img.naturalWidth, h: img.naturalHeight }); };
    img.src = originalUrl;
    return () => { img.onload = null; img.onerror = null; };
  }, [originalUrl]);

  const mode = photoMode === 'camera' && originalUrl ? 'camera' : 'upload';
  const src = mode === 'camera' ? originalUrl ?? null : uploadUrl;
  const camSize = cameraSize && cameraSize.src === originalUrl ? cameraSize : null;
  const upSize = uploadSize && uploadSize.src === uploadUrl ? uploadSize : null;
  const check = useMemo(() => isValidPolygon(points), [points]);
  const mismatch = mode === 'upload' && !!upSize && !!camSize && aspectMismatch(upSize, camSize);
  const unknownRatio = mode === 'upload' && !!upSize && !camSize;
  const locked = phase !== 'idle' || busy;
  const canSave = check.ok && !locked && (!mismatch || ack);
  const sel = selected !== null && selected < points.length ? selected : null;

  function openConfirm(next: Phase) { setPhase(next); setMessage(null); }

  async function execute(action: Action) {
    if (inFlight.current) return; // chống bấm đúp
    inFlight.current = true;
    pending.current = action;
    setBusy(true); setPhase('idle'); setMessage(null);
    const cameraId = camera.camera_id;
    let result: RoiResult;
    try {
      result = action.kind === 'save' ? await saveDrainRoi(cameraId, action.polygon, 'manual') : await removeDrainRoi(cameraId);
    } catch {
      result = { ok: false, status: 0, error: 'Unexpected error while sending the request.' };
    } finally {
      inFlight.current = false;
    }
    if (result.ok) onSavedRef.current(); // luôn làm mới danh sách, kể cả khi khung đã đóng giữa chừng
    if (!mounted.current) return;
    setBusy(false);
    if (result.ok) {
      pending.current = null;
      setMessage({ kind: 'ok', text: action.kind === 'save' ? SAVED_OK : REMOVED_OK });
    } else if (result.needsKey) {
      setPhase('needKey');
      setMessage({ kind: 'error', text: result.error });
    } else {
      pending.current = null;
      setMessage({ kind: 'error', text: result.error });
    }
  }

  function onKeySubmit(key: string) {
    setAdminKey(key);
    const action = pending.current;
    if (action) void execute(action); else setPhase('idle');
  }

  function changeFile(next: File | null) {
    setAck(false); setUploadSize(null); setMessage(null);
    if (next && !next.type.startsWith('image/')) {
      setFile(null);
      setMessage({ kind: 'error', text: 'The selected file is not an image.' });
      return;
    }
    setFile(next);
  }

  function importPoints() {
    const result = parsePolygonString(importText);
    if (!result.ok) { setImportError(result.error); return; }
    setImportError('');
    setPoints(result.points);
    setSelected(null);
  }

  async function copyPoints() {
    const text = formatPolygonString(points);
    try {
      await navigator.clipboard.writeText(text);
      if (mounted.current) setCopyMsg('Point string copied.');
    } catch {
      if (mounted.current) {
        setImportText(text);
        setCopyMsg('Automatic copy failed; the point string was placed in the box below, select and copy it manually.');
      }
    }
  }

  function deleteSelected() {
    if (sel === null) return;
    setPoints(points.filter((_, i) => i !== sel));
    setSelected(null);
  }

  const n = points.length;
  return <div className="roi-body">
    <p className="roi-help">Outline the drain inlet as you see it in the image (pixel accuracy is not needed; a shift of ~10% adds almost no error). Draw on an image where the inlet is clear; if the drain is currently covered by litter, use an older uncovered image.</p>

    <fieldset className="roi-source" disabled={locked}>
      <legend>Image to draw on</legend>
      <label><input type="radio" name={`${uid}-src`} checked={mode === 'camera'} disabled={!originalUrl} onChange={() => setPhotoMode('camera')} /> Latest original camera photo</label>
      <label><input type="radio" name={`${uid}-src`} checked={mode === 'upload'} onChange={() => setPhotoMode('upload')} /> Upload an image from this device</label>
      {mode === 'upload' && <>
        <input type="file" accept="image/*" aria-label="Choose an image from this device" onChange={e => changeFile(e.target.files?.[0] ?? null)} />
        <span className="muted">The image is only used for drawing in the browser and is not uploaded to the server.</span>
      </>}
    </fieldset>

    {mismatch && <div className="notice roi-note" role="alert">
      <span>The uploaded image has a different aspect ratio from the camera image; the drawn zone will be misaligned on the camera image. Use an image with the same framing.</span>
      <label className="roi-ack"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} /> I understand, save anyway</label>
    </div>}
    {unknownRatio && <p className="muted roi-note">The camera image aspect ratio is unknown — make sure the image has the same framing.</p>}

    <ul className="roi-legend" aria-label="Legend">
      <li><span className="roi-swatch roi-swatch-saved" aria-hidden="true" /> Current ROI{saved ? ' (dashed)' : ': none'}</li>
      <li><span className="roi-swatch roi-swatch-draft" aria-hidden="true" /> Zone being drawn (solid, light fill)</li>
    </ul>

    <RoiCanvas
      src={src}
      points={points}
      saved={saved}
      selected={sel}
      locked={locked}
      onChange={setPoints}
      onSelect={setSelected}
      onImageLoad={info => {
        if (info.src === uploadUrl) setUploadSize({ src: info.src, w: info.w, h: info.h });
        else if (info.src === originalUrl) setCameraSize({ src: info.src, w: info.w, h: info.h });
      }}
    />
    <p className="muted roi-hint">Click the image to add a point, drag a point to adjust. Keyboard: Tab to a point, arrow keys to move (Shift to move faster), Delete to remove the point.</p>

    <p className="roi-count" aria-live="polite"><strong>{n} points ({ROI_MIN_POINTS}–{ROI_MAX_POINTS})</strong></p>
    {n > 0 && n < ROI_MIN_POINTS && <p className="muted" role="status">At least {ROI_MIN_POINTS} points are needed to save ({n} so far).</p>}
    {n >= ROI_MIN_POINTS && check.errors.length > 0 && <ul className="roi-errors" role="alert">{check.errors.map(msg => <li key={msg}>{msg}</li>)}</ul>}

    <RoiToolbar
      count={n}
      hasSelection={sel !== null}
      hasSaved={!!saved}
      disabled={locked}
      onUndo={() => { setPoints(points.slice(0, -1)); setSelected(null); }}
      onDeleteSelected={deleteSelected}
      onClear={() => { setPoints([]); setSelected(null); }}
      onLoadSaved={() => { if (saved) { setPoints(saved.map(([x, y]): RoiPoint => [x, y])); setSelected(null); } }}
    />

    <div className="roi-import">
      <label htmlFor={`${uid}-import`}>Point string (format <code>x,y x,y …</code>, from <code>calibrate_roi.py</code>)</label>
      <textarea id={`${uid}-import`} rows={2} spellCheck={false} value={importText} disabled={locked} onChange={e => { setImportText(e.target.value); setImportError(''); }} />
      {importError && <p className="roi-error" role="alert">{importError}</p>}
      <div className="roi-actions">
        <button type="button" className="secondary" disabled={locked || !importText.trim()} onClick={importPoints}>Import point string</button>
        <button type="button" className="secondary" disabled={locked || n === 0} onClick={() => void copyPoints()}>Copy point string</button>
      </div>
      {copyMsg && <p className="muted" role="status">{copyMsg}</p>}
    </div>

    <div className="roi-save">
      <div className="roi-actions">
        <button type="button" className="refresh" disabled={!canSave} onClick={() => openConfirm('confirmSave')}>Save drain zone</button>
        {camera.drain_roi && <button type="button" className="secondary" disabled={locked} onClick={() => openConfirm('confirmRemove')}>Remove drain zone</button>}
        {busy && <span className="muted" role="status">Sending to the server…</span>}
      </div>
      {phase === 'confirmSave' && <div className="notice roi-confirm" role="alertdialog" aria-label="Confirm saving the drain zone">
        <p>{SAVE_WARNING}</p>
        <div className="roi-actions">
          <button type="button" className="refresh" disabled={busy || !canSaveNow(check.ok, mismatch, ack)} onClick={() => void execute({ kind: 'save', polygon: points.map(([x, y]): RoiPoint => [x, y]) })}>Confirm save</button>
          <button type="button" className="secondary" disabled={busy} onClick={() => setPhase('idle')}>Cancel</button>
        </div>
      </div>}
      {phase === 'confirmRemove' && <div className="notice roi-confirm" role="alertdialog" aria-label="Confirm removing the drain zone">
        <p>{REMOVE_WARNING}</p>
        <div className="roi-actions">
          <button type="button" className="refresh" disabled={busy} onClick={() => void execute({ kind: 'remove' })}>Confirm removal</button>
          <button type="button" className="secondary" disabled={busy} onClick={() => setPhase('idle')}>Cancel</button>
        </div>
      </div>}
      {phase === 'needKey' && <KeyForm onSubmit={onKeySubmit} onCancel={() => { pending.current = null; setPhase('idle'); setMessage(null); }} />}
      {message && (message.kind === 'ok'
        ? <p className="roi-ok" role="status">{message.text}</p>
        : <p className="roi-error" role="alert">{message.text}</p>)}
    </div>
  </div>;
}

const canSaveNow = (valid: boolean, mismatch: boolean, ack: boolean) => valid && (!mismatch || ack);
