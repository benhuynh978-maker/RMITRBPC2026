"""
Demo exp02 dùng KẾT QUẢ MODEL AI THẬT (YOLO26s-seg) thay cho nhãn tay.

Luồng cho mỗi ảnh:
  0) Chọn ảnh tất định (select_image_stems): ảnh cảnh đường tphcm/ssc có nhãn Trash, độ phủ nhãn
     Trash lớn nhất trước; loại ảnh nhãn trống.
  1) Suy luận model (tham số giống production inference/analysis.py — chỉ tham khảo,
     KHÔNG import): imgsz=1024, conf=0.25, retina_masks=True, ngưỡng mask > 0.5.
  2) Gộp (union) mask mọi instance lớp Trash (class 0).
  3) Tách vùng theo BIÊN PIXEL (project_mask.mask_to_pixel_boundary_polygons: diện tích đa giác khớp
     số pixel mask, có lỗ) -> bỏ vùng nhỏ (< MIN_AREA_FRAC diện tích ảnh) -> giảm đỉnh bằng approxPolyDP.
  4) Chiếu từng vùng bằng project_mask.project_mask_to_geojson(mask=..., boundary="pixel") với calibration
     DEMO-CAM (chỉ đọc, pose từ ảnh GIẢ LẬP — không khớp vật lý với ảnh Try1). Bật
     allow_aspect_mismatch=True: CHỈ DEMO (ảnh Try1 1:1 khác tỉ lệ ảnh hiệu chỉnh 4:3).
  5) Song song chiếu các polygon NHÃN TAY lớp Trash của cùng ảnh (source "label").
  6) Xuất model_demo/outputs/<stem_ngắn>_model.geojson, <stem_ngắn>_label.geojson,
     marker.geojson (vị trí bảng đánh dấu), camera_position.geojson (camera tính từ R,t),
     index.json (danh sách ảnh cho viewer), summary.json (bảng so sánh).

Chỉ ghi vào model_demo/outputs/. Không ghi gì vào outputs/ hay calibration/ dùng chung,
không gọi model.val, không save=True (không sinh thư mục runs/).

Chạy (từ thư mục exp02_ve_rac_len_ban_do/):
  C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B model_demo/run_demo_model.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

os.environ["YOLO_VERBOSE"] = "False"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
EXP_DIR = HERE.parent
sys.path.insert(0, str(EXP_DIR))

import config  # noqa: E402  (chỉ đọc hằng số)
import project_mask  # noqa: E402  (chỉ dùng hàm chiếu, không ghi file)

# --- Tham số model (giống production inference/analysis.py) ---
MODEL_PATH = config.PROJECT_ROOT / "runs" / "segment" / "runs" / "train" / "baseline_v1_rev2" / "weights" / "best.pt"
PREDICT_IMGSZ = 1024
DETECT_CONF = 0.25
MASK_THRESHOLD = 0.5
TRASH_CLASS_ID = 0

# --- Tham số tách contour ---
# Bỏ contour có diện tích (cv2.contourArea của viền ngoài gốc) < 0.05% diện tích ảnh.
MIN_AREA_FRAC = 0.0005
# approxPolyDP: epsilon = max(EPS_MIN_PX, EPS_FRAC_PERIMETER * chu vi contour), đơn vị pixel.
EPS_FRAC_PERIMETER = 0.002
EPS_MIN_PX = 1.0

OUTPUT_DIR = HERE / "outputs"

# --- Quy tắc chọn ảnh demo (tất định, chỉ đọc nhãn; xem select_image_stems) ---
# Ưu tiên ảnh CẢNH ĐƯỜNG/CỐNG: tên file bắt đầu bằng tiền tố tphcm/ssc, CÓ nhãn Trash (loại ảnh nhãn
# trống), xếp theo % diện tích HỢP nhãn Trash giảm dần, hoà thì theo tên. Lấy N_IMAGES ảnh đầu.
# Nếu không đủ N_IMAGES ảnh thì bổ sung bằng ảnh nguồn khác (g1lop...) theo cùng cách xếp hạng,
# cuối cùng mới tới ảnh demo cũ config.DEMO_LABELED_IMAGE_STEM.
STREET_PREFIXES = ("tphcm", "ssc")
N_IMAGES = 3
RANK_GRID = 512  # lưới tô nhãn để đo độ phủ

# Ảnh dataset (1024x1024) khác tỉ lệ ảnh hiệu chỉnh DEMO-CAM (640x480): CHỈ DEMO mới bật cờ này.
ALLOW_ASPECT_MISMATCH_DEMO = True
# Biên mask: "pixel" (diện tích khớp số pixel) thay cho contour qua tâm pixel (co ~0.5 px).
BOUNDARY = "pixel"


# ---------------------------------------------------------------------------
# Hàm thuần (không cần model/GPU) — được test trong test_model_demo.py
# ---------------------------------------------------------------------------
def short_stem(stem: str) -> str:
    """'g1lop_000003_JPG.rf.54f58bb6...' -> 'g1lop_000003_54f58bb6' (gọn, vẫn duy nhất)."""
    if ".rf." in stem:
        base, h = stem.split(".rf.", 1)
        for suffix in ("_JPG", "_jpg", "_PNG", "_png", "_jpeg", "_JPEG"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        return f"{base}_{h[:8]}"
    return stem


def mask_to_contours(
    mask: np.ndarray,
    min_area_frac: float = MIN_AREA_FRAC,
    eps_frac: float = EPS_FRAC_PERIMETER,
    eps_min_px: float = EPS_MIN_PX,
) -> list[dict]:
    """
    mask: mảng 2D bool/uint8 (H, W). Trả list dict theo thứ tự tất định
    (sắp theo diện tích giảm dần, hoà thì theo (y, x) điểm đầu):
      {
        "polygon_px":      ndarray (N,2) int — đỉnh đã giảm bằng approxPolyDP (N >= 3),
        "component":       ndarray (H,W) bool — điểm mask thuộc vùng viền ngoài này,
        "area_px":         int — số pixel mask thật trong vùng (đã trừ lỗ),
        "contour_area_px": float — diện tích viền ngoài gốc (cv2.contourArea, gồm cả lỗ),
      }
    Chỉ lấy viền NGOÀI (RETR_EXTERNAL): lỗ bên trong bị bỏ qua khi tạo polygon.
    """
    m = (np.asarray(mask) > 0).astype(np.uint8)
    if m.ndim != 2:
        raise ValueError(f"mask phải là 2D, nhận shape {m.shape}")
    h, w = m.shape
    min_area = min_area_frac * h * w

    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in contours:
        c_area = float(cv2.contourArea(c))
        if c_area < min_area:
            continue
        eps = max(eps_min_px, eps_frac * cv2.arcLength(c, True))
        approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(approx) < 3:
            approx = c.reshape(-1, 2)
            if len(approx) < 3:
                continue
        filled = np.zeros_like(m)
        cv2.drawContours(filled, [c], -1, 1, thickness=cv2.FILLED)
        component = (filled > 0) & (m > 0)
        out.append(
            {
                "polygon_px": approx.astype(np.int32),
                "component": component,
                "area_px": int(component.sum()),
                "contour_area_px": c_area,
            }
        )
    out.sort(key=lambda d: (-d["area_px"], int(d["polygon_px"][0][1]), int(d["polygon_px"][0][0])))
    return out


def polygon_px_to_norm(polygon_px: np.ndarray, width: int, height: int) -> list[tuple[float, float]]:
    """Pixel (x,y) -> chuẩn hoá 0..1 theo cùng quy ước nhãn YOLO (x/W, y/H)."""
    return [(float(x) / width, float(y) / height) for x, y in polygon_px]


def mean_confidence(component: np.ndarray, instance_masks: list[np.ndarray], confs: list[float]) -> Optional[float]:
    """Trung bình confidence của các instance có mask giao với vùng contour; None nếu không có."""
    hits = [c for im, c in zip(instance_masks, confs) if np.logical_and(component, im).any()]
    if not hits:
        return None
    return round(float(np.mean(hits)), 4)


def parse_label_polygons(label_path: Path, target_class: int = TRASH_CLASS_ID) -> list[list[tuple[float, float]]]:
    """Đọc TẤT CẢ polygon lớp target_class trong file nhãn YOLO-seg (toạ độ chuẩn hoá)."""
    polys = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if not parts or int(float(parts[0])) != target_class:
            continue
        coords = [float(v) for v in parts[1:]]
        if len(coords) % 2 != 0 or len(coords) < 6:
            continue
        polys.append(list(zip(coords[0::2], coords[1::2])))
    return polys


def rasterize_polygons(polys_norm: list[list[tuple[float, float]]], width: int, height: int) -> np.ndarray:
    """Tô các polygon chuẩn hoá thành mask bool (H, W) ở độ phân giải ảnh gốc."""
    m = np.zeros((height, width), dtype=np.uint8)
    for p in polys_norm:
        pts = np.round(np.array(p, dtype=np.float64) * [width, height]).astype(np.int32)
        cv2.fillPoly(m, [pts], 1)
    return m > 0


def mask_iou(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    """IoU 2 mask bool; None nếu cả hai rỗng."""
    union = int(np.logical_or(a, b).sum())
    if union == 0:
        return None
    return float(np.logical_and(a, b).sum()) / union


def mask_to_polygons(
    mask: np.ndarray,
    min_area_frac: float = MIN_AREA_FRAC,
    eps_frac: float = EPS_FRAC_PERIMETER,
    eps_min_px: float = EPS_MIN_PX,
) -> list[dict]:
    """
    Tách mask thành các vùng theo BIÊN PIXEL (project_mask.mask_to_pixel_boundary_polygons: diện tích
    đa giác == số pixel thật, KHÔNG co 0.5 px, có hỗ trợ lỗ) - thay cho mask_to_contours (đường cũ).
    Trả list dict theo thứ tự tất định (diện tích giảm dần):
      {
        "component":  ndarray (H,W) bool - pixel mask của vùng 4-liên thông này,
        "area_px":    int - số pixel thật (đã trừ lỗ),
        "n_holes":    int - số lỗ,
        "eps_px":     float - sai số rút gọn đỉnh dùng khi chiếu, = max(eps_min_px, eps_frac * chu vi viền ngoài),
      }
    Bỏ vùng có diện tích viền ngoài (kể cả lỗ) < min_area_frac diện tích ảnh.
    """
    m = np.asarray(mask) > 0
    if m.ndim != 2:
        raise ValueError(f"mask phải là 2D, nhận shape {m.shape}")
    h, w = m.shape
    min_area = min_area_frac * h * w
    polys = project_mask.mask_to_pixel_boundary_polygons(m)
    if not polys:
        return []
    _, labels = cv2.connectedComponents(m.astype(np.uint8), connectivity=4)
    out = []
    for p in polys:
        outer = p["outer"]
        outer_area = abs(float(project_mask._ring_area(outer)))
        if outer_area < min_area:
            continue
        sx, sy = p["seed_px"]
        perim = float(np.abs(np.diff(np.vstack([outer, outer[:1]]), axis=0)).sum())  # chu vi (cạnh trục)
        out.append(
            {
                "component": labels == labels[sy, sx],
                "area_px": int(p["area_px"]),
                "n_holes": len(p["holes"]),
                "eps_px": max(eps_min_px, eps_frac * perim),
            }
        )
    return out


def trash_coverage_pct(polys_norm: list[list[tuple[float, float]]], grid: int = RANK_GRID) -> float:
    """% diện tích ảnh bị phủ bởi HỢP các polygon nhãn (tô lưới grid x grid)."""
    if not polys_norm:
        return 0.0
    return float(rasterize_polygons(polys_norm, grid, grid).mean()) * 100.0


def rank_images_by_trash(labels_dir: Path, prefixes: Optional[tuple] = None) -> list[tuple[str, float, int]]:
    """
    Xếp hạng ảnh theo độ phủ nhãn Trash GIẢM DẦN (hoà: tên TĂNG DẦN). Chỉ đọc nhãn.
    prefixes: chỉ xét file có tên bắt đầu bằng một trong các tiền tố (None = mọi file).
    Ảnh KHÔNG có polygon Trash hợp lệ (nhãn trống / chỉ lớp khác) bị loại.
    Trả list (stem, coverage_pct, n_polygons).
    """
    rows = []
    for p in sorted(Path(labels_dir).glob("*.txt")):
        if prefixes is not None and not p.name.lower().startswith(tuple(prefixes)):
            continue
        polys = parse_label_polygons(p)
        if not polys:
            continue
        rows.append((p.stem, trash_coverage_pct(polys), len(polys)))
    rows.sort(key=lambda r: (-round(r[1], 6), r[0]))
    return rows


def select_image_stems(
    labels_dir: Path = config.DATASET_TEST_LABELS_DIR,
    images_dir: Path = config.DATASET_TEST_IMAGES_DIR,
    n: int = N_IMAGES,
) -> list[tuple[str, str]]:
    """
    Chọn tất định n ảnh demo. QUY TẮC: ảnh tphcm/ssc có nhãn Trash, có file ảnh .jpg, độ phủ nhãn Trash
    lớn nhất trước (hoà theo tên). Thiếu thì bổ sung ảnh nguồn khác cùng cách xếp hạng, rồi cuối cùng
    config.DEMO_LABELED_IMAGE_STEM. Trả list (stem, nhóm) với nhóm "street" | "other" | "legacy".
    """
    def has_image(stem: str) -> bool:
        return (Path(images_dir) / f"{stem}.jpg").exists()

    chosen: list[tuple[str, str]] = []
    for stem, _, _ in rank_images_by_trash(labels_dir, STREET_PREFIXES):
        if has_image(stem):
            chosen.append((stem, "street"))
        if len(chosen) >= n:
            return chosen
    taken = {s for s, _ in chosen}
    for stem, _, _ in rank_images_by_trash(labels_dir, None):
        if stem in taken or stem.lower().startswith(STREET_PREFIXES) or not has_image(stem):
            continue
        chosen.append((stem, "other"))
        if len(chosen) >= n:
            return chosen
    if len(chosen) < n and config.DEMO_LABELED_IMAGE_STEM not in {s for s, _ in chosen}:
        chosen.append((config.DEMO_LABELED_IMAGE_STEM, "legacy"))
    return chosen


def project_quiet(polygon_norm, image_size, calib, warn_log: dict, **kwargs) -> Optional[dict]:
    """
    Gọi project_mask.project_mask_to_geojson (kwargs chuyển tiếp: mask=, boundary=, allow_aspect_mismatch=,
    simplify_eps_px=) nhưng gom các dòng thông báo lặp lại để in tóm tắt 1 lần — không che lỗi,
    mọi dòng vẫn được đếm và in ra cuối chương trình.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        feat = project_mask.project_mask_to_geojson(polygon_norm, image_size, calib, **kwargs)
    for line in buf.getvalue().splitlines():
        if line.startswith("[CẢNH BÁO] Bỏ điểm"):
            key = "[CẢNH BÁO] Bỏ điểm - tia không cắt mặt đất phía trước camera"
        else:
            key = line
        warn_log[key] = warn_log.get(key, 0) + 1
    return feat

# ---------------------------------------------------------------------------
# Phần chạy model
# ---------------------------------------------------------------------------
def run_model(model, image_bgr: np.ndarray):
    """Suy luận 1 ảnh BGR, trả (instance_masks Trash, confs Trash, thời gian ms, r.speed, orig_shape)."""
    import torch

    t0 = time.perf_counter()
    results = model.predict(
        source=image_bgr,
        imgsz=PREDICT_IMGSZ,
        conf=DETECT_CONF,
        retina_masks=True,
        verbose=False,
    )
    r = results[0]
    masks, confs = [], []
    if r.masks is not None and r.boxes is not None and len(r.boxes) > 0:
        mask_data = r.masks.data.cpu().numpy()
        classes = r.boxes.cls.cpu().numpy().astype(int)
        conf_arr = r.boxes.conf.cpu().numpy()
        for i in range(mask_data.shape[0]):
            if int(classes[i]) == TRASH_CLASS_ID:
                masks.append(mask_data[i] > MASK_THRESHOLD)
                confs.append(float(conf_arr[i]))
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return masks, confs, elapsed_ms, dict(r.speed), tuple(r.orig_shape)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    import torch
    from ultralytics import YOLO

    if not MODEL_PATH.exists():
        print(f"[LỖI] Không thấy weights: {MODEL_PATH}")
        return 1
    calib = project_mask.load_calibration(config.DEMO_CAMERA_ID)  # chỉ đọc
    print(f"Calibration: {config.DEMO_CAMERA_ID} (source={calib.get('source')}, image_size={calib['image_size']})")
    print(f"Model: {MODEL_PATH}")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"Thiết bị: {device} ({torch.cuda.get_device_name(0) if device != 'cpu' else 'CPU'})")
    print(
        f"Tham số: imgsz={PREDICT_IMGSZ}, conf={DETECT_CONF}, retina_masks=True, mask>{MASK_THRESHOLD}; "
        f"vùng: biên pixel (có lỗ), bỏ < {MIN_AREA_FRAC*100:.2f}% ảnh, "
        f"approxPolyDP eps=max({EPS_MIN_PX}px, {EPS_FRAC_PERIMETER}*chu vi)"
    )
    selected = select_image_stems()
    image_stems = [s for s, _ in selected]
    print(
        f"Quy tắc chọn ảnh: tiền tố {STREET_PREFIXES}, có nhãn Trash, độ phủ nhãn Trash lớn nhất trước "
        f"(thiếu thì bổ sung nguồn khác). Ảnh chọn: {[(short_stem(s), g) for s, g in selected]}"
    )
    if not image_stems:
        print("[LỖI] Không chọn được ảnh nào")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    t_load = time.perf_counter()
    model = YOLO(str(MODEL_PATH))
    load_ms = (time.perf_counter() - t_load) * 1000.0

    # Warm-up (khởi tạo CUDA/kernel) trên ảnh đầu tiên — không tính vào thời gian đo
    first = cv2.imread(str(config.DATASET_TEST_IMAGES_DIR / f"{image_stems[0]}.jpg"))
    if first is None:
        print("[LỖI] Không đọc được ảnh warm-up")
        return 1
    _, _, warmup_ms, _, _ = run_model(model, first)
    print(f"Nạp model: {load_ms:.0f} ms; warm-up lần đầu: {warmup_ms:.0f} ms (không tính)")

    warn_log: dict = {}
    index, rows = [], []
    for stem in image_stems:
        img_path = config.DATASET_TEST_IMAGES_DIR / f"{stem}.jpg"
        lbl_path = config.DATASET_TEST_LABELS_DIR / f"{stem}.txt"
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"[LỖI] Không đọc được ảnh: {img_path}")
            return 1
        h, w = img.shape[:2]
        sid = short_stem(stem)
        print(f"\n=== {sid} ({w}x{h}) ===")

        inst_masks, inst_confs, infer_ms, speed, orig_shape = run_model(model, img)
        if orig_shape != (h, w):
            print(f"[LỖI] orig_shape {orig_shape} khác ảnh {h}x{w}")
            return 1
        model_union = np.zeros((h, w), dtype=bool)
        for im in inst_masks:
            if im.shape != (h, w):
                print(f"[LỖI] mask instance {im.shape} khác ảnh {h}x{w} (retina_masks?)")
                return 1
            model_union |= im
        model_contours = mask_to_polygons(model_union)

        model_feats = []
        for idx, c in enumerate(model_contours):
            # allow_aspect_mismatch=True: CHỈ DEMO (ảnh 1:1 vs ảnh hiệu chỉnh 4:3). Mask -> biên pixel.
            feat = project_quiet(
                None, (w, h), calib, warn_log,
                mask=c["component"], boundary=BOUNDARY,
                allow_aspect_mismatch=ALLOW_ASPECT_MISMATCH_DEMO, simplify_eps_px=c["eps_px"],
            )
            if feat is None:
                print(f"[CẢNH BÁO] vùng model #{idx} không chiếu được (không đủ điểm cắt mặt đất)")
                continue
            ring0 = feat["geometry"]["coordinates"]
            ring0 = ring0[0] if feat["geometry"]["type"] == "Polygon" else ring0[0][0]
            feat["properties"].update(
                {
                    "image": stem,
                    "contour_idx": idx,
                    "area_px": c["area_px"],
                    "n_vertices_px": int(len(ring0) - 1),
                    "n_holes": c["n_holes"],
                    "source": "model",
                    "confidence": mean_confidence(c["component"], inst_masks, inst_confs),
                }
            )
            model_feats.append(feat)

        label_polys = parse_label_polygons(lbl_path)
        label_union = rasterize_polygons(label_polys, w, h)
        label_contours = mask_to_polygons(label_union)  # chỉ để đếm (cùng quy tắc với model)
        label_feats = []
        for idx, p in enumerate(label_polys):
            # Polygon nhãn tay là biên liên tục thật (không phải contour qua tâm pixel) -> chiếu nguyên trạng.
            feat = project_quiet(p, (w, h), calib, warn_log, allow_aspect_mismatch=ALLOW_ASPECT_MISMATCH_DEMO)
            if feat is None:
                print(f"[CẢNH BÁO] polygon nhãn #{idx} không chiếu được")
                continue
            feat["properties"].update(
                {
                    "image": stem,
                    "contour_idx": idx,
                    "area_px": int(rasterize_polygons([p], w, h).sum()),
                    "n_vertices_px": len(p),
                    "source": "label",
                    "confidence": None,
                }
            )
            label_feats.append(feat)

        model_name = f"{sid}_model.geojson"
        label_name = f"{sid}_label.geojson"
        write_json(OUTPUT_DIR / model_name, {"type": "FeatureCollection", "features": model_feats})
        write_json(OUTPUT_DIR / label_name, {"type": "FeatureCollection", "features": label_feats})

        iou = mask_iou(model_union, label_union)
        row = {
            "image": stem,
            "id": sid,
            "n_instances_trash": len(inst_masks),
            "instance_confs": [round(c, 4) for c in inst_confs],
            "n_model_contours": len(model_contours),
            "n_model_polygons": len(model_feats),
            "n_label_polygons": len(label_feats),
            "n_label_contours_after_union": len(label_contours),
            "model_area_px": int(model_union.sum()),
            "label_area_px": int(label_union.sum()),
            "model_area_pct": round(float(model_union.mean()) * 100, 3),
            "label_area_pct": round(float(label_union.mean()) * 100, 3),
            "iou": None if iou is None else round(iou, 4),
            "infer_ms": round(infer_ms, 1),
            "ultralytics_speed_ms": {k: round(v, 1) for k, v in speed.items()},
        }
        rows.append(row)
        index.append({"id": sid, "image": stem, "model": model_name, "label": label_name})
        print(
            f"instance Trash={len(inst_masks)}, polygon model={len(model_feats)}, "
            f"polygon nhãn={len(label_feats)}, suy luận={infer_ms:.1f} ms, speed={row['ultralytics_speed_ms']}"
        )

    write_json(OUTPUT_DIR / "marker.geojson", project_mask.marker_point_geojson(calib))
    write_json(OUTPUT_DIR / "camera_position.geojson", project_mask.camera_position_geojson(calib))
    write_json(
        OUTPUT_DIR / "index.json",
        {"marker": "marker.geojson", "camera_position": "camera_position.geojson", "images": index},
    )
    write_json(
        OUTPUT_DIR / "summary.json",
        {
            "params": {
                "model": str(MODEL_PATH),
                "imgsz": PREDICT_IMGSZ,
                "conf": DETECT_CONF,
                "retina_masks": True,
                "mask_threshold": MASK_THRESHOLD,
                "min_area_frac": MIN_AREA_FRAC,
                "eps_frac_perimeter": EPS_FRAC_PERIMETER,
                "eps_min_px": EPS_MIN_PX,
                "boundary": BOUNDARY,
                "allow_aspect_mismatch": ALLOW_ASPECT_MISMATCH_DEMO,
                "image_selection": {
                    "rule": "tiền tố tphcm/ssc, có nhãn Trash, độ phủ nhãn Trash giảm dần (hoà theo tên); thiếu thì bổ sung nguồn khác",
                    "prefixes": list(STREET_PREFIXES),
                    "n_images": N_IMAGES,
                    "chosen": [{"stem": s, "group": g} for s, g in selected],
                },
                "device": device,
            },
            "load_ms": round(load_ms, 1),
            "warmup_ms": round(warmup_ms, 1),
            "rows": rows,
            "projection_warnings": warn_log,
        },
    )

    print("\n=== Bảng so sánh model vs nhãn tay (trên ẢNH, pixel) ===")
    hdr = (
        f"{'ảnh':<24} | {'#poly M':>7} | {'#poly L':>7} | {'#L union':>8} | {'area M px':>10} | "
        f"{'area L px':>10} | {'M %':>6} | {'L %':>6} | {'IoU':>6} | {'ms':>6}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        iou_s = "n/a" if r["iou"] is None else f"{r['iou']:.4f}"
        print(
            f"{r['id']:<24} | {r['n_model_polygons']:>7} | {r['n_label_polygons']:>7} | "
            f"{r['n_label_contours_after_union']:>8} | {r['model_area_px']:>10} | {r['label_area_px']:>10} | "
            f"{r['model_area_pct']:>6.2f} | {r['label_area_pct']:>6.2f} | {iou_s:>6} | {r['infer_ms']:>6.1f}"
        )
    if warn_log:
        print("\n=== Thông báo từ project_mask (gom lại, số lần) ===")
        for k, v in warn_log.items():
            print(f"  x{v}: {k}")
    print(f"\nĐã ghi vào: {OUTPUT_DIR}")
    print(
        "LƯU Ý: DEMO — pose DEMO-CAM lấy từ ảnh giả lập, KHÔNG khớp vật lý với ảnh Try1; "
        "toạ độ bản đồ chỉ để thử luồng. Ảnh dataset khác tỉ lệ ảnh hiệu chỉnh (cờ allow_aspect_mismatch chỉ cho demo)."
    )
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return 0


if __name__ == "__main__":
    sys.exit(main())
