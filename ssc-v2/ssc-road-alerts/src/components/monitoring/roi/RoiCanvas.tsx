import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import { ROI_MAX_POINTS, clampPoint01 } from '../../../lib/roiGeometry';
import type { RoiPoint } from '../../../lib/roiGeometry';

const KEY_STEP = 0.005;
const KEY_STEP_SHIFT = 0.02;

interface Drag { index: number; pointerId: number; dx: number; dy: number }

export interface RoiCanvasProps {
  /** URL ảnh đang hiển thị (ảnh camera hoặc object URL của ảnh tải lên); null = chưa có ảnh. */
  src: string | null;
  points: RoiPoint[];
  saved?: RoiPoint[];
  selected: number | null;
  /** Khoá mọi thao tác (đang xác nhận / đang gửi). */
  locked: boolean;
  onChange: (points: RoiPoint[]) => void;
  onSelect: (index: number | null) => void;
  onImageLoad: (info: { src: string; w: number; h: number }) => void;
}

const toSvgPoints = (points: readonly RoiPoint[]) => points.map(([x, y]) => `${x},${y}`).join(' ');

/**
 * Ảnh + lớp phủ SVG viewBox 0..1 (preserveAspectRatio none) khít đúng ảnh hiển thị, nên toạ độ chuẩn hoá ánh xạ 1:1.
 * Điểm kéo là phần tử HTML đặt theo % (tròn đúng dù SVG bị kéo giãn). Mọi sự kiện con trỏ xử lý ở khung ngoài.
 */
export function RoiCanvas({ src, points, saved, selected, locked, onChange, onSelect, onImageLoad }: RoiCanvasProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<Drag | null>(null);
  const pointsRef = useRef(points);
  pointsRef.current = points; // luôn là bản mới nhất khi render; emit() cập nhật tức thì giữa hai lần render
  const pendingFocus = useRef<number | null>(null);
  const [readySrc, setReadySrc] = useState<string | null>(null);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const ready = src !== null && readySrc === src;

  useEffect(() => { if (locked) dragRef.current = null; }, [locked]);
  useEffect(() => {
    const index = pendingFocus.current;
    if (index === null) return;
    pendingFocus.current = null;
    stageRef.current?.querySelector<HTMLElement>(`[data-roi-handle="${index}"]`)?.focus();
  }, [points]);

  const emit = (next: RoiPoint[]) => { pointsRef.current = next; onChange(next); };
  const raw = (e: { clientX: number; clientY: number }): RoiPoint | null => {
    const r = stageRef.current?.getBoundingClientRect();
    if (!r || r.width <= 0 || r.height <= 0) return null;
    return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height];
  };
  const capture = (id: number) => { try { stageRef.current?.setPointerCapture(id); } catch { /* con trỏ đã biến mất */ } };
  const endDrag = (e: PointerEvent) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    dragRef.current = null;
    try { stageRef.current?.releasePointerCapture(e.pointerId); } catch { /* đã tự nhả */ }
  };

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    if (locked || !ready || dragRef.current || !e.isPrimary) return;
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    const pos = raw(e);
    if (!pos) return;
    const handle = (e.target as Element).closest?.('[data-roi-handle]');
    if (handle) {
      const index = Number(handle.getAttribute('data-roi-handle'));
      const p = pointsRef.current[index];
      if (!p) return;
      // Giữ độ lệch giữa ngón/chuột và tâm điểm để điểm không nhảy khi bắt đầu kéo.
      dragRef.current = { index, pointerId: e.pointerId, dx: p[0] - pos[0], dy: p[1] - pos[1] };
      onSelect(index);
      capture(e.pointerId);
      return;
    }
    const current = pointsRef.current;
    if (current.length >= ROI_MAX_POINTS) return;
    e.preventDefault();
    // Bấm lần hai ngay cạnh điểm vừa đặt rơi vào vùng bắt của điểm đó nên không sinh điểm trùng.
    emit([...current, clampPoint01(pos)]);
    dragRef.current = { index: current.length, pointerId: e.pointerId, dx: 0, dy: 0 };
    onSelect(current.length);
    capture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId || locked) return;
    if (e.pointerType === 'mouse' && e.buttons === 0) { dragRef.current = null; return; } // mất pointerup: dừng kéo
    const pos = raw(e);
    if (!pos) return;
    const moved = clampPoint01([pos[0] + drag.dx, pos[1] + drag.dy]);
    emit(pointsRef.current.map((p, i) => (i === drag.index ? moved : p)));
  }

  function onHandleKeyDown(e: KeyboardEvent<HTMLElement>, index: number) {
    if (locked) return;
    const current = pointsRef.current;
    if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault();
      const next = current.filter((_, i) => i !== index);
      pendingFocus.current = next.length ? Math.min(index, next.length - 1) : null;
      onSelect(pendingFocus.current);
      emit(next);
      return;
    }
    const step = e.shiftKey ? KEY_STEP_SHIFT : KEY_STEP;
    const delta: Record<string, RoiPoint> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    const d = delta[e.key];
    if (!d) return;
    e.preventDefault();
    emit(current.map((p, i) => (i === index ? clampPoint01([p[0] + d[0], p[1] + d[1]]) : p)));
  }

  if (!src) return <div className="roi-empty">No image to draw on yet. Choose an image above.</div>;

  return <>
    {failedSrc === src && <p className="roi-error" role="alert">Could not load this image. Try another one.</p>}
    <div
      ref={stageRef}
      className={`roi-stage${locked ? ' is-locked' : ''}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onLostPointerCapture={endDrag}
    >
      <img
        key={src}
        className="roi-img"
        src={src}
        alt="Image used to draw the drain inlet zone"
        draggable={false}
        onLoad={e => {
          const img = e.currentTarget;
          if (img.naturalWidth > 0 && img.naturalHeight > 0) {
            setReadySrc(src);
            setFailedSrc(null);
            onImageLoad({ src, w: img.naturalWidth, h: img.naturalHeight });
          }
        }}
        onError={() => setFailedSrc(src)}
      />
      {ready && <>
        <svg className="roi-svg" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true" focusable="false">
          {saved && saved.length >= 3 && <polygon className="roi-shape-saved" points={toSvgPoints(saved)} vectorEffect="non-scaling-stroke" />}
          {points.length >= 3 && <polygon className="roi-shape-draft" points={toSvgPoints(points)} vectorEffect="non-scaling-stroke" />}
          {points.length === 2 && <polyline className="roi-shape-draft roi-shape-open" points={toSvgPoints(points)} vectorEffect="non-scaling-stroke" />}
        </svg>
        <div className="roi-handles">
          {points.map((p, i) => (
            <button
              key={i}
              type="button"
              tabIndex={0}
              data-roi-handle={i}
              className={`roi-handle${selected === i ? ' is-selected' : ''}`}
              style={{ left: `${p[0] * 100}%`, top: `${p[1] * 100}%` }}
              aria-label={`Point ${i + 1}`}
              aria-disabled={locked || undefined}
              onFocus={() => { if (!locked) onSelect(i); }}
              onKeyDown={e => onHandleKeyDown(e, i)}
            ><span aria-hidden="true">{i + 1}</span></button>
          ))}
        </div>
      </>}
    </div>
  </>;
}
