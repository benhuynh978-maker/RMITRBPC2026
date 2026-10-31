"""Ham dung chung cho exp01. Khong import inference/analysis.py (tai hien doc lap)."""
from __future__ import annotations

import csv
import math
import os
import sys
import time
from pathlib import Path

os.environ["YOLO_VERBOSE"] = "False"
# console Windows (cp1252) khong in duoc tieng Viet co dau
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import cv2
import numpy as np

import config as C

BANDS = ("green", "yellow", "red")


# ---------------------------------------------------------------- du lieu / nhan

def load_labels(label_path: Path) -> list[tuple[int, np.ndarray]]:
    polys = []
    with open(label_path, "r", encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            parts = line.split()
            if not parts:
                continue
            cls = int(parts[0])
            vals = np.array([float(v) for v in parts[1:]], dtype=np.float64)
            if vals.size < 6 or vals.size % 2:
                raise ValueError(f"Dong nhan khong hop le {label_path}:{ln} ({vals.size} so)")
            polys.append((cls, vals.reshape(-1, 2)))
    return polys


def _find_image(images_dir: Path, stem: str) -> Path:
    for ext in C.IMAGE_EXTS:
        p = images_dir / f"{stem}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"Khong thay anh cho nhan {stem} trong {images_dir}")


def list_drain_images(split: str) -> list[dict]:
    """Danh sach anh (sap xep theo stem) co >= 1 polygon Drain."""
    if split not in C.SPLITS:
        raise ValueError(f"Split khong duoc phep: {split}")
    labels_dir = C.DATASET_DIR / split / "labels"
    images_dir = C.DATASET_DIR / split / "images"
    for d in (labels_dir, images_dir):
        if not d.is_dir():
            raise FileNotFoundError(f"Thieu thu muc: {d}")
    items = []
    for lp in sorted(labels_dir.glob("*.txt")):
        polys = load_labels(lp)
        if not any(c == C.DRAIN_CLASS for c, _ in polys):
            continue
        items.append({
            "split": split,
            "stem": lp.stem,
            "label_path": lp,
            "image_path": _find_image(images_dir, lp.stem),
            "polys": polys,
        })
    return items


def list_all_drain_images() -> list[dict]:
    items = []
    for s in C.SPLITS:
        items.extend(list_drain_images(s))
    return items


def check_counts(items: list[dict]) -> None:
    n_img = {s: 0 for s in C.SPLITS}
    n_poly = 0
    for it in items:
        n_img[it["split"]] += 1
        n_poly += sum(1 for c, _ in it["polys"] if c == C.DRAIN_CLASS)
    total = sum(n_img.values())
    print(f"[dem] anh co Drain: {n_img} tong={total}; polygon Drain: {n_poly}")
    ok = (total == C.EXPECTED_DRAIN_IMAGES_TOTAL and n_poly == C.EXPECTED_DRAIN_POLYGONS
          and all(n_img[s] == C.EXPECTED_DRAIN_IMAGES[s] for s in C.SPLITS))
    if not ok:
        bar = "!" * 70
        print(f"{bar}\nCANH BAO: so luong khac ky vong "
              f"(ky vong {C.EXPECTED_DRAIN_IMAGES} tong={C.EXPECTED_DRAIN_IMAGES_TOTAL}, "
              f"polygon={C.EXPECTED_DRAIN_POLYGONS})\n{bar}")


def read_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Khong doc duoc anh: {path}")
    return img


# ---------------------------------------------------------------- hinh hoc

def poly_to_px(poly_norm: np.ndarray, h: int, w: int) -> np.ndarray:
    return poly_norm * np.array([w, h], dtype=np.float64)


def rasterize_px(polys_px: list[np.ndarray], h: int, w: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.uint8)
    # fillPoly tung polygon mot de lay hop (union), tranh even-odd khi chong lan
    for p in polys_px:
        pts = np.round(p).astype(np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(mask, [pts], 1)
    return mask.astype(bool)


def rasterize_norm(polys_norm: list[np.ndarray], h: int, w: int) -> np.ndarray:
    return rasterize_px([poly_to_px(p, h, w) for p in polys_norm], h, w)


def polygon_centroid(px: np.ndarray) -> np.ndarray:
    m = cv2.moments(px.astype(np.float32).reshape(-1, 1, 2))
    if abs(m["m00"]) > 1e-9:
        return np.array([m["m10"] / m["m00"], m["m01"] / m["m00"]])
    return px.mean(axis=0)


def polygon_area(px: np.ndarray) -> float:
    """Dien tich shoelace (khac so pixel rasterize vi fillPoly tinh ca pixel bien)."""
    x, y = px[:, 0], px[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def shift_polygon(px: np.ndarray, frac: float, direction: str) -> np.ndarray:
    bw = float(px[:, 0].max() - px[:, 0].min())
    bh = float(px[:, 1].max() - px[:, 1].min())
    d = {"left": (-frac * bw, 0.0), "right": (frac * bw, 0.0),
         "up": (0.0, -frac * bh), "down": (0.0, frac * bh)}[direction]
    return px + np.array(d)


def scale_polygon(px: np.ndarray, factor: float) -> np.ndarray:
    c = polygon_centroid(px)
    return c + (px - c) * factor


def m2_variants(px: np.ndarray) -> dict[str, np.ndarray]:
    """Cac ROI nhieu cho M2; ten cot: m2_s05_left, ..., m2_sc090, m2_sc110."""
    out = {}
    for frac in C.M2_SHIFTS:
        for d in C.M2_DIRECTIONS:
            out[f"m2_s{round(frac * 100):02d}_{d}"] = shift_polygon(px, frac, d)
    for s in C.M2_SCALES:
        out[f"m2_sc{round(s * 100):03d}"] = scale_polygon(px, s)
    return out


def m2_names() -> list[str]:
    names = [f"m2_s{round(f * 100):02d}_{d}" for f in C.M2_SHIFTS for d in C.M2_DIRECTIONS]
    return names + [f"m2_sc{round(s * 100):03d}" for s in C.M2_SCALES]


def gt_for_image(polys: list[tuple[int, np.ndarray]], h: int, w: int):
    """Tra ve (trash_union_gt, [drain_mask], [drain_px]) theo thu tu Drain trong file nhan."""
    trash = rasterize_norm([p for c, p in polys if c == C.TRASH_CLASS], h, w)
    drains_px = [poly_to_px(p, h, w) for c, p in polys if c == C.DRAIN_CLASS]
    drain_masks = [rasterize_px([px], h, w) for px in drains_px]
    return trash, drain_masks, drains_px


# ---------------------------------------------------------------- cong thuc

def clip_percent(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def blockage_m0(trash_union: np.ndarray, drain_union: np.ndarray) -> float | None:
    """Cong thuc production: |trash ∩ drain_union| / |drain_union|; None neu khong co drain."""
    area = int(drain_union.sum())
    if area == 0:
        return None
    inter = int(np.logical_and(trash_union, drain_union).sum())
    return clip_percent(inter / area * 100)


def blockage_roi(trash_union: np.ndarray, roi: np.ndarray) -> float:
    """M1/M2 va GT: |trash ∩ roi| / |roi| * 100; NaN neu ROI rong."""
    area = int(roi.sum())
    if area == 0:
        return math.nan
    return int(np.logical_and(trash_union, roi).sum()) / area * 100.0


def old_confidence(inst_cls: np.ndarray, inst_conf: np.ndarray) -> float:
    keep = [float(cf) for c, cf in zip(inst_cls, inst_conf) if int(c) in (C.TRASH_CLASS, C.DRAIN_CLASS)]
    return round(min(keep), 4) if keep else C.DEFAULT_CONFIDENCE


def new_certainty(inst_masks: np.ndarray, inst_cls: np.ndarray, inst_conf: np.ndarray,
                  roi: np.ndarray) -> float:
    """Trung binh co trong so (so pixel mask trong ROI) cua conf cac instance Trash."""
    num = 0.0
    den = 0
    for m, c, cf in zip(inst_masks, inst_cls, inst_conf):
        if int(c) != C.TRASH_CLASS:
            continue
        wgt = int(np.logical_and(m, roi).sum())
        num += wgt * float(cf)
        den += wgt
    return num / den if den > 0 else math.nan


def is_missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def band(v) -> str:
    if is_missing(v):
        return "missing"
    if v < C.YELLOW_THRESHOLD:
        return "green"
    if v < C.RED_THRESHOLD:
        return "yellow"
    return "red"


def flag(v) -> bool:
    return (not is_missing(v)) and v < C.FLAG_THRESHOLD


# ---------------------------------------------------------------- lam muot

def rolling_median(values: list, k: int = C.MEDIAN_WINDOW) -> list:
    """Median cua k gia tri gan nhat (bo gia tri thieu); None neu cua so khong co gia tri."""
    out = []
    for t in range(len(values)):
        win = [v for v in values[max(0, t - k + 1):t + 1] if not is_missing(v)]
        out.append(float(np.median(win)) if win else None)
    return out


def hysteresis_step(state: str, v: float) -> str:
    if state == "green":
        if v >= C.HYST_RED_ENTER:
            return "red"
        if v >= C.HYST_YELLOW_ENTER:
            return "yellow"
        return "green"
    if state == "yellow":
        if v >= C.HYST_RED_ENTER:
            return "red"
        if v < C.HYST_YELLOW_EXIT:
            return "green"
        return "yellow"
    if state == "red":
        if v < C.HYST_RED_EXIT:
            return "yellow" if v >= C.HYST_YELLOW_EXIT else "green"
        return "red"
    raise ValueError(f"Trang thai khong hop le: {state}")


def hysteresis_run(values: list, init_state: str | None = None) -> list:
    """Khoi tao bang nguong thuong o gia tri hop le dau tien (neu khong cho init_state).
    Gia tri thieu -> giu trang thai cu ('missing' neu chua khoi tao)."""
    state = init_state
    out = []
    for v in values:
        if is_missing(v):
            out.append(state if state is not None else "missing")
            continue
        state = band(v) if state is None else hysteresis_step(state, v)
        out.append(state)
    return out


def count_flips(states: list) -> int:
    return sum(1 for a, b in zip(states[:-1], states[1:]) if a != b)


# ---------------------------------------------------------------- thong ke

def bootstrap_ci(x, n: int = C.BOOTSTRAP_N, seed: int = C.SEED, alpha: float = 0.05):
    x = np.asarray([v for v in x if not is_missing(v)], dtype=np.float64)
    if x.size == 0:
        return (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(n, x.size))
    stats = x[idx].mean(axis=1)
    return (float(np.percentile(stats, 100 * alpha / 2)), float(np.percentile(stats, 100 * (1 - alpha / 2))))


# ---------------------------------------------------------------- anh / model

def jpeg_roundtrip(img: np.ndarray, quality: int) -> np.ndarray:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("cv2.imencode that bai")
    out = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if out is None:
        raise RuntimeError("cv2.imdecode that bai")
    return out


def degrade_esp32(img: np.ndarray, size: int = C.ESP32_SIZE, quality: int = C.ESP32_JPEG_QUALITY) -> np.ndarray:
    small = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
    return jpeg_roundtrip(small, quality)


# Dieu kien anh: C0 goc; C1 ESP32-like q12 (chinh); C2 ESP32-like q25 (bo sung, sat anh ESP32 that hon)
CONDITIONS = ("C0", "C1", "C2")
CONDITION_QUALITY = {"C1": C.ESP32_JPEG_QUALITY, "C2": C.C2_JPEG_QUALITY}


def prepare_condition(img: np.ndarray, cond: str) -> np.ndarray:
    if cond == "C0":
        return img
    if cond not in CONDITION_QUALITY:
        raise ValueError(f"Dieu kien khong hop le: {cond}")
    return degrade_esp32(img, quality=CONDITION_QUALITY[cond])


def get_device():
    import torch
    if torch.cuda.is_available():
        print(f"[device] CUDA: {torch.cuda.get_device_name(0)}")
        return 0
    print("[device] CUDA khong co -> chay CPU (cham)")
    return "cpu"


def load_model():
    if not C.MODEL_PATH.exists():
        raise FileNotFoundError(f"Khong thay trong so model: {C.MODEL_PATH}")
    from ultralytics import YOLO
    print(f"[model] {C.MODEL_PATH}")
    return YOLO(str(C.MODEL_PATH))


def run_model(model, img: np.ndarray, device) -> dict:
    """Predict giong production; tra ve mask hop va tung instance (bool, kich thuoc anh vao)."""
    h, w = img.shape[:2]
    t0 = time.perf_counter()
    results = model.predict(source=img, imgsz=C.PREDICT_IMGSZ, conf=C.DETECT_CONF,
                            retina_masks=True, verbose=False, device=device)
    if not results:
        raise RuntimeError("Model khong tra ve ket qua")
    r = results[0]
    trash = np.zeros((h, w), dtype=bool)
    drain = np.zeros((h, w), dtype=bool)
    masks, classes, confs = [], [], []
    if r.masks is not None and r.boxes is not None and len(r.boxes) > 0:
        data = r.masks.data.cpu().numpy()
        cls_arr = r.boxes.cls.cpu().numpy().astype(int)
        conf_arr = r.boxes.conf.cpu().numpy()
        for i in range(data.shape[0]):
            m = data[i] > C.MASK_THRESHOLD
            if m.shape != (h, w):
                print(f"CANH BAO: mask {m.shape} != anh {(h, w)} -> resize nearest")
                m = cv2.resize(m.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST).astype(bool)
            c = int(cls_arr[i])
            if c == C.TRASH_CLASS:
                trash |= m
            elif c == C.DRAIN_CLASS:
                drain |= m
            masks.append(m)
            classes.append(c)
            confs.append(float(conf_arr[i]))
    elapsed = time.perf_counter() - t0
    inst_masks = np.stack(masks) if masks else np.zeros((0, h, w), dtype=bool)
    return {
        "trash_union": trash,
        "drain_union": drain,
        "inst_masks": inst_masks,
        "inst_cls": np.array(classes, dtype=np.int64),
        "inst_conf": np.array(confs, dtype=np.float64),
        "time_s": elapsed,
    }


# ---------------------------------------------------------------- CSV

def fmt(v, nd: int = 4):
    if v is None:
        return ""
    if isinstance(v, (bool, np.bool_)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return "" if math.isnan(v) else round(float(v), nd)
    return v


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fieldnames)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: fmt(r.get(k)) for k in fieldnames})
    print(f"[ghi] {path} ({len(rows)} dong)")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Thieu file: {path} (chay buoc truoc chua?)")
    with open(path, "r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def to_float(s) -> float:
    return math.nan if s in ("", None) else float(s)
