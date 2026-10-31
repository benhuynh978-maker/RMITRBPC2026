"""
Phan tich anh bang model YOLO26s-seg (lop 0: Trash, 1: Drain) da train san.

Chi lam dung 1 viec: nhan bytes JPEG (+ ROI mieng cong cua camera neu co), tra
ve dict ket qua. Khong biet gi ve HTTP hay hang doi job — logic goi API nam o
ai_worker.py.

Quy uoc cu (legacy, giu NGUYEN khi roi=None):
- waste_coverage_pct = dien tich hop nhat (union) cac mask lop Trash / dien
  tich anh, tinh theo %.
- drain_blockage_pct = dien tich (Trash giao Drain) / dien tich mask Drain.
  Neu khong phat hien Drain nao trong anh -> BO TRONG truong nay (khong gui 0),
  de backend loai camera do khoi phep tinh trung binh cua tuyen.
- confidence = nho nhat trong cac confidence cua object da dung de tinh 2
  so tren. Neu khong phat hien object nao (anh sach) -> 0.575.

Bo sung v2 (exp01_chi_so_che_cong, cong thuc M1 + "certainty moi"):
- roi = polygon mieng cong CO DINH cua camera (toa do chuan hoa 0..1, x sang
  phai, y xuong duoi). Co roi -> drain_blockage_pct = |Trash ∩ ROI| / |ROI|
  (blockage_method "roi"), khong can model nhin thay mieng cong.
- certainty = trung binh co trong so cua confidence cac instance Trash, trong
  so = so pixel mask cua instance nam TRONG vung do (ROI, hoac hop mask Drain
  du doan khi khong co ROI). None khi khong co pixel rac nao trong vung do.
  Chi la nhan thong tin, khong chan ket qua.
- Cong chat luong anh (quality_gate=True, worker bat): do sang trung binh anh
  xam < MIN_BRIGHTNESS -> usable False, quality_reason "thieu_sang", KHONG chay
  model. Mac dinh TAT de analyze(jpeg_bytes) cu (site demo) giu nguyen hanh vi.
"""
from __future__ import annotations

import math
import os
import uuid
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

HERE = Path(__file__).resolve().parent

TRASH_CLASS = 0
DRAIN_CLASS = 1

MODEL_PATH = Path(
    os.environ.get(
        "AI_MODEL_PATH",
        str(HERE / ".." / ".." / "runs" / "segment" / "runs" / "train" / "baseline_v1_rev2" / "weights" / "best.pt"),
    )
).resolve()
DETECT_CONF = float(os.environ.get("AI_DETECT_CONF", "0.25"))
PREDICT_IMGSZ = 1024
MASK_THRESHOLD = 0.5

# 0.575 = precision(M) do duoc tren tap val (results.csv, epoch 80): khong phat hien
# gi KHONG dong nghia anh chac chan sach, vi recall cua model moi ~45%.
DEFAULT_CONFIDENCE = 0.575

# Do sang trung binh anh xam (0..255) toi thieu. Pham vi he thong: ban ngay / thoi
# tiet tot; anh toi hon nguong nay coi la khong dung duoc (thieu sang).
MIN_BRIGHTNESS = float(os.environ.get("AI_MIN_BRIGHTNESS", "40"))
QUALITY_REASON_DARK = "thieu_sang"

# Mau/do day vien ROI ve len anh phan tich (BGR).
ROI_COLOR_BGR = (0, 255, 0)

# UUID co dinh dung lam namespace cho uuid5 - chi can khong doi giua cac lan
# chay, khong can bi mat. Ten file anh phan tich phai TAT DINH theo
# (camera_id, observation_id) de gui lai (retry) khong bao gio sinh ra
# analyzed_url khac lan truoc (backend tu choi ket qua gui lai khac noi dung).
_FILENAME_NAMESPACE = uuid.UUID("c9c5a3f0-6b1b-4c1e-9d1a-8f2e6a7b0c3d")

_MODEL: YOLO | None = None


def _model() -> YOLO:
    global _MODEL
    if _MODEL is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Khong thay trong so model: {MODEL_PATH}")
        _MODEL = YOLO(str(MODEL_PATH))
    return _MODEL


def _clip_percent(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


# Gioi han SO DIEM ANH (khong phai dung luong file) - mot JPEG nen tot nhung do phan
# giai cuc lon van lot qua gioi han dung luong, roi lam RAM no khi tao mask retina_masks
# o do phan giai goc (vd anh 50MP tu dien thoai doi moi). Da ghi nhan thuc te: 1 anh lam
# sap ca tien trinh uvicorn (process bien mat, khong phai loi duoc try/except bat duoc).
MAX_PIXELS = 24_000_000  # ~ tuong duong anh 6000x4000 (24MP), du rong cho anh dien thoai binh thuong


# ---------------------------------------------------------------- ham thuan (khong can GPU)

def validate_roi_polygon(polygon) -> list[list[float]]:
    """Kiem tra polygon ROI: list >= 3 cap [x, y] so thuc huu han trong [0, 1].

    Tra ve ban sao dang list[list[float]]; sai dinh dang -> ValueError (thong
    diep ro rang de worker bao fail len backend).
    """
    if not isinstance(polygon, (list, tuple)):
        raise ValueError(f"ROI khong hop le: polygon phai la danh sach diem, nhan {type(polygon).__name__}")
    if len(polygon) < 3:
        raise ValueError(f"ROI khong hop le: can >= 3 diem, nhan {len(polygon)}")
    points: list[list[float]] = []
    for index, point in enumerate(polygon):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(f"ROI khong hop le: diem #{index} phai la cap [x, y], nhan {point!r}")
        coords = []
        for value in point:
            # bool la lop con cua int trong Python -> chan rieng.
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"ROI khong hop le: diem #{index} co toa do khong phai so: {point!r}")
            value = float(value)
            if not math.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(f"ROI khong hop le: diem #{index} nam ngoai [0, 1]: {point!r}")
            coords.append(value)
        points.append(coords)
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    if 0.5 * abs(float(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1)))) < 1e-9:
        raise ValueError("ROI suy bien: polygon co dien tich 0 (cac diem trung nhau hoac thang hang)")
    return points


def roi_mask(polygon, height: int, width: int) -> np.ndarray:
    """Rasterize polygon chuan hoa (0..1) o kich thuoc anh (height, width).

    Cung quy uoc voi exp01 common.py: toa do * [w, h], lam tron, fillPoly gia tri 1.
    """
    points = np.asarray(validate_roi_polygon(polygon), dtype=np.float64)
    pixels = points * np.array([width, height], dtype=np.float64)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, [np.round(pixels).astype(np.int32).reshape(-1, 1, 2)], 1)
    return mask.astype(bool)


def blockage_in_roi(trash_union: np.ndarray, roi: np.ndarray) -> tuple[float, int]:
    """(drain_blockage_pct, so pixel rac trong ROI). ROI rong -> ValueError."""
    roi_area = int(roi.sum())
    if roi_area == 0:
        raise ValueError("ROI suy bien: dien tich 0 pixel o kich thuoc anh nay")
    intersection = int(np.logical_and(trash_union, roi).sum())
    return _clip_percent(intersection / roi_area * 100), intersection


def weighted_certainty(instances, region: np.ndarray) -> float | None:
    """Trung binh co trong so cua conf cac instance Trash.

    instances: iterable (mask_bool, class_id, conf). Trong so = so pixel mask cua
    instance nam trong region. None khi khong co pixel rac nao trong region.
    """
    numerator = 0.0
    denominator = 0
    for mask, cls_id, conf in instances:
        if int(cls_id) != TRASH_CLASS:
            continue
        weight = int(np.logical_and(mask, region).sum())
        numerator += weight * float(conf)
        denominator += weight
    if denominator == 0:
        return None
    return numerator / denominator


def mean_brightness(image_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    return float(gray.mean())


def brightness_ok(image_bgr: np.ndarray, threshold: float | None = None) -> tuple[bool, float]:
    """(du sang?, do sang trung binh anh xam 0..255)."""
    limit = MIN_BRIGHTNESS if threshold is None else float(threshold)
    brightness = mean_brightness(image_bgr)
    return brightness >= limit, brightness


def draw_roi(image_bgr: np.ndarray, polygon) -> np.ndarray:
    """Ve vien ROI (xanh la) len ban sao anh; do day ty le voi kich thuoc anh."""
    height, width = image_bgr.shape[:2]
    points = np.asarray(validate_roi_polygon(polygon), dtype=np.float64) * np.array([width, height])
    thickness = max(2, int(round(min(height, width) / 200)))
    canvas = np.ascontiguousarray(image_bgr).copy()
    cv2.polylines(
        canvas,
        [np.round(points).astype(np.int32).reshape(-1, 1, 2)],
        isClosed=True,
        color=ROI_COLOR_BGR,
        thickness=thickness,
        lineType=cv2.LINE_AA,
    )
    return canvas


def _encode_jpeg(image_bgr: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("Khong ma hoa duoc anh ket qua thanh JPEG")
    return buffer.tobytes()


def decode_image(jpeg_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Khong giai ma duoc anh JPEG (du lieu hong hoac khong dung dinh dang)")
    height0, width0 = image.shape[:2]
    if height0 * width0 > MAX_PIXELS:
        raise ValueError(
            f"Anh do phan giai qua lon ({width0}x{height0} = {width0*height0/1e6:.1f}MP, "
            f"gioi han {MAX_PIXELS/1e6:.0f}MP). Vui long giam kich thuoc anh truoc khi gui."
        )
    return image


def predict(image: np.ndarray):
    """Chay model giong het production; tra ve results[0] cua ultralytics."""
    results = _model().predict(
        source=image,
        imgsz=PREDICT_IMGSZ,
        conf=DETECT_CONF,
        retina_masks=True,
        verbose=False,
    )
    if not results:
        raise RuntimeError("Model khong tra ve ket qua nao")
    return results[0]


# ---------------------------------------------------------------- ham chinh

def analyze(jpeg_bytes: bytes, roi=None, *, quality_gate: bool = False) -> dict:
    """Phan tich 1 anh.

    roi: None (cong thuc legacy) hoac list diem [x, y] chuan hoa 0..1.
    quality_gate: True -> kiem do sang truoc khi chay model (worker bat).

    Tra ve dict luon co: usable, confidence, analyzed_bytes.
    usable True  -> them waste_coverage_pct, blockage_method, certainty,
                    drain_blockage_pct / no_trash_in_roi (vang mat khi khong ap dung).
    usable False -> them quality_reason; KHONG co cac so phan tram.
    """
    image = decode_image(jpeg_bytes)
    height0, width0 = image.shape[:2]

    # Rasterize/kiem ROI TRUOC khi chay model: ROI suy bien -> ValueError som.
    roi_bool = None
    if roi is not None:
        roi_bool = roi_mask(roi, height0, width0)
        if not roi_bool.any():
            raise ValueError("ROI suy bien: dien tich 0 pixel o kich thuoc anh nay")

    if quality_gate:
        ok, brightness = brightness_ok(image)
        if not ok:
            # Khong chay model. Anh "phan tich" = anh goc ma hoa lai (+ vien ROI neu co)
            # de giao dien van hien thi duoc khung hinh bi loai.
            shown = draw_roi(image, roi) if roi is not None else image
            return {
                "usable": False,
                "quality_reason": QUALITY_REASON_DARK,
                "brightness": round(brightness, 2),
                "confidence": DEFAULT_CONFIDENCE,
                "analyzed_bytes": _encode_jpeg(shown),
            }

    r = predict(image)

    height, width = r.orig_shape
    total_pixels = height * width
    trash_union = np.zeros((height, width), dtype=bool)
    drain_union = np.zeros((height, width), dtype=bool)
    confidences: list[float] = []
    instances: list[tuple[np.ndarray, int, float]] = []

    if r.masks is not None and r.boxes is not None and len(r.boxes) > 0:
        mask_data = r.masks.data.cpu().numpy()
        classes = r.boxes.cls.cpu().numpy().astype(int)
        confs = r.boxes.conf.cpu().numpy()
        for i in range(mask_data.shape[0]):
            instance_mask = mask_data[i] > MASK_THRESHOLD
            cls_id = int(classes[i])
            conf = float(confs[i])
            if cls_id == TRASH_CLASS:
                trash_union |= instance_mask
                confidences.append(conf)
                instances.append((instance_mask, cls_id, conf))
            elif cls_id == DRAIN_CLASS:
                drain_union |= instance_mask
                confidences.append(conf)

    waste_coverage_pct = _clip_percent(trash_union.sum() / total_pixels * 100) if total_pixels else 0.0

    if roi_bool is not None:
        if roi_bool.shape != (height, width):  # phong ho: model luon tra orig_shape = anh vao
            raise RuntimeError(f"Kich thuoc mask {(height, width)} khac anh {roi_bool.shape}")
        drain_blockage_pct, intersection = blockage_in_roi(trash_union, roi_bool)
        no_trash_in_roi = intersection == 0
        certainty = weighted_certainty(instances, roi_bool)
        blockage_method = "roi"
    else:
        drain_area = int(drain_union.sum())
        if drain_area > 0:
            intersection = int(np.logical_and(trash_union, drain_union).sum())
            drain_blockage_pct = _clip_percent(intersection / drain_area * 100)
            no_trash_in_roi = intersection == 0
            certainty = weighted_certainty(instances, drain_union)
        else:
            # Khong thay mieng cong nao -> BO TRONG, khong gui 0. Gui 0 se bi hieu la
            # "da do, cong sach" va keo trung binh cua ca tuyen xuong.
            drain_blockage_pct = None
            no_trash_in_roi = None
            certainty = None
        blockage_method = "legacy"

    # Legacy: giu nguyen (min conf), du exp01 cho thay chi so nay phan thong tin.
    confidence = round(min(confidences), 4) if confidences else DEFAULT_CONFIDENCE

    annotated_bgr = r.plot()  # numpy BGR, da ve san box/mask theo mau lop.
    if roi is not None:
        annotated_bgr = draw_roi(annotated_bgr, roi)

    result = {
        "usable": True,
        "waste_coverage_pct": waste_coverage_pct,
        "confidence": confidence,
        "certainty": round(certainty, 4) if certainty is not None else None,
        "blockage_method": blockage_method,
        "analyzed_bytes": _encode_jpeg(annotated_bgr),
    }
    if drain_blockage_pct is not None:
        result["drain_blockage_pct"] = drain_blockage_pct
    if no_trash_in_roi is not None:
        result["no_trash_in_roi"] = bool(no_trash_in_roi)
    return result


def analyzed_filename(camera_id: str, observation_id: str) -> str:
    """UUID tat dinh (uuid5) theo camera_id+observation_id - khong phai
    uuid4 ngau nhien - de retry cung mot job luon ra dung 1 ten file."""
    key = f"{camera_id}:{observation_id}"
    return f"{uuid.uuid5(_FILENAME_NAMESPACE, key)}.jpg"


def save_analyzed_image(analyzed_bytes: bytes, camera_id: str, observation_id: str, images_dir: Path) -> str:
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = analyzed_filename(camera_id, observation_id)
    path = images_dir / filename
    if not path.exists():
        # 'xb': tao moi, loi neu da ton tai - khong bao gio ghi de anh cu,
        # giong dung cach backend Node tu ghi anh (co 'wx').
        with open(path, "xb") as handle:
            handle.write(analyzed_bytes)
    return filename
