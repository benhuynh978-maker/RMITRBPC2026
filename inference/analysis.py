"""
Phan tich anh bang model YOLO26s-seg (lop 0: Trash, 1: Drain) da train san.

Chi lam dung 1 viec: nhan bytes JPEG, tra ve {waste_coverage_pct,
drain_blockage_pct, confidence, analyzed_bytes}. Khong biet gi ve HTTP hay
hang doi job — logic goi API nam o ai_worker.py.

Quy uoc (xem ke hoach da duyet):
- waste_coverage_pct = dien tich hop nhat (union) cac mask lop Trash / dien
  tich anh, tinh theo %.
- drain_blockage_pct = dien tich (Trash giao Drain) / dien tich mask Drain.
  Neu khong phat hien Drain nao trong anh -> BO TRONG truong nay (khong gui 0),
  de backend loai camera do khoi phep tinh trung binh cua tuyen.
- confidence = nho nhat trong cac confidence cua object da dung de tinh 2
  so tren (uu tien than trong: 1 detection yeu keo ca anh xuong
  needs_review). Neu khong phat hien object nao (anh sach) -> 0.575.
"""
from __future__ import annotations

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
        str(HERE / ".." / "runs" / "segment" / "runs" / "train" / "baseline_v1_rev2" / "weights" / "best.pt"),
    )
).resolve()
DETECT_CONF = float(os.environ.get("AI_DETECT_CONF", "0.25"))
PREDICT_IMGSZ = 1024

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


def analyze(jpeg_bytes: bytes) -> dict:
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

    results = _model().predict(
        source=image,
        imgsz=PREDICT_IMGSZ,
        conf=DETECT_CONF,
        retina_masks=True,
        verbose=False,
    )
    if not results:
        raise RuntimeError("Model khong tra ve ket qua nao")
    r = results[0]

    height, width = r.orig_shape
    total_pixels = height * width
    trash_union = np.zeros((height, width), dtype=bool)
    drain_union = np.zeros((height, width), dtype=bool)
    confidences: list[float] = []

    if r.masks is not None and r.boxes is not None and len(r.boxes) > 0:
        mask_data = r.masks.data.cpu().numpy()
        classes = r.boxes.cls.cpu().numpy().astype(int)
        confs = r.boxes.conf.cpu().numpy()
        for i in range(mask_data.shape[0]):
            instance_mask = mask_data[i] > 0.5
            cls_id = int(classes[i])
            conf = float(confs[i])
            if cls_id == TRASH_CLASS:
                trash_union |= instance_mask
                confidences.append(conf)
            elif cls_id == DRAIN_CLASS:
                drain_union |= instance_mask
                confidences.append(conf)

    waste_coverage_pct = _clip_percent(trash_union.sum() / total_pixels * 100) if total_pixels else 0.0

    drain_area = int(drain_union.sum())
    if drain_area > 0:
        intersection = int(np.logical_and(trash_union, drain_union).sum())
        drain_blockage_pct = _clip_percent(intersection / drain_area * 100)
    else:
        # Khong thay mieng cong nao -> BO TRONG, khong gui 0. Gui 0 se bi hieu la
        # "da do, cong sach" va keo trung binh cua ca tuyen xuong.
        drain_blockage_pct = None

    # 0.575 = precision(M) do duoc tren tap val (results.csv, epoch 80): khong phat hien
    # gi KHONG dong nghia anh chac chan sach, vi recall cua model moi ~45%.
    confidence = round(min(confidences), 4) if confidences else 0.575

    annotated_bgr = r.plot()  # numpy BGR, da ve san box/mask theo mau lop.
    ok, buffer = cv2.imencode(".jpg", annotated_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("Khong ma hoa duoc anh ket qua thanh JPEG")

    result = {
        "waste_coverage_pct": waste_coverage_pct,
        "confidence": confidence,
        "analyzed_bytes": buffer.tobytes(),
    }
    if drain_blockage_pct is not None:
        result["drain_blockage_pct"] = drain_blockage_pct
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
