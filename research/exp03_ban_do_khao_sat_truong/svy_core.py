"""
Lõi xử lý của công cụ khảo sát (exp03). MỘT ảnh = MỘT điểm khảo sát, ảnh có cả bảng ArUco và rác:

  ảnh -> dò bảng (tự hiệu chỉnh từ chính ảnh này) -> AI khoanh rác -> bỏ phần tờ bảng khỏi vùng rác
      -> chiếu vùng rác xuống mặt đất, tính m^2.

Vùng được lưu trong HỆ TOẠ ĐỘ BẢNG (x dọc +X của bảng, y dọc +Y của bảng, mét, gốc là tâm bảng), KHÔNG lưu lat/lon:
nhờ vậy đổi vị trí / hướng của điểm trên bản đồ là phép tịnh tiến + xoay, không phải chạy lại AI.
Đổi sang lat/lon: ring_to_lonlat (dùng đúng project_mask.marker_xy_to_enu + meters_to_latlon của exp02).

Hình học dùng lại NGUYÊN các module exp02 (calibrate_aruco, calib_quality, project_mask, camera_model) và
webtest/imaging.py (chỉ ĐỌC, không sửa). Không import webtest/server.py.
"""
from __future__ import annotations

import hashlib
import io
import math
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

os.environ.setdefault("YOLO_VERBOSE", "False")

HERE = Path(__file__).resolve().parent
EXP_DIR = HERE.parent / "exp02_ve_rac_len_ban_do"
WEBTEST_DIR = EXP_DIR / "webtest"
for _p in (str(EXP_DIR), str(WEBTEST_DIR)):
    if _p not in sys.path:
        sys.path.append(_p)   # append: module của exp03 (svy_*) không bao giờ bị che

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import calib_quality  # noqa: E402
import calibrate_aruco  # noqa: E402
import camera_model  # noqa: E402
import config  # noqa: E402
import imaging  # noqa: E402
import project_mask as pm  # noqa: E402

DEFAULT_MODEL_PATH = (
    config.PROJECT_ROOT / "runs" / "segment" / "runs" / "train" / "baseline_v1_rev2" / "weights" / "best.pt"
)
PREDICT_IMGSZ = 1024          # giống webtest/server.py
DETECT_CONF = 0.25
MASK_THRESHOLD = 0.5
TRASH_CLASS_ID = 0
MIN_AREA_PX_FLOOR = 20.0
MIN_AREA_FRAC = 0.00003
EPS_FRAC_PERIMETER = 0.002
MAX_REGIONS_PER_SPOT = 150
MIN_MANUAL_AREA_M2 = 1e-4


class PhotoError(Exception):
    """Ảnh không đọc được (không phải ảnh, hỏng, quá lớn). str(exc) là câu tiếng Việt cho người dùng."""


# ---------------------------------------------------------------- model
_MODEL = None
_MODEL_LOCK = threading.Lock()


def model_path() -> Path:
    return Path(os.environ.get("SURVEY_MODEL_PATH") or DEFAULT_MODEL_PATH)


def _detect_conf() -> float:
    try:
        v = float(os.environ.get("SURVEY_CONF", ""))
        return v if 0.01 <= v <= 0.95 else DETECT_CONF
    except ValueError:
        return DETECT_CONF


def infer_trash_mask(image_bgr: np.ndarray) -> Tuple[np.ndarray, int, List[float]]:
    """YOLO-seg, chỉ lớp 0 (Trash), mask > 0.5. Trả (mask_bool_hợp (H,W), số vùng AI, độ tin cậy từng vùng)."""
    global _MODEL
    h, w = image_bgr.shape[:2]
    with _MODEL_LOCK:
        if _MODEL is None:
            mp = model_path()
            if not mp.is_file():
                raise RuntimeError(f"Không thấy file model: {mp}")
            from ultralytics import YOLO
            _MODEL = YOLO(str(mp))
        r = _MODEL.predict(source=image_bgr, imgsz=PREDICT_IMGSZ, conf=_detect_conf(), retina_masks=True, verbose=False)[0]
        union = np.zeros((h, w), dtype=bool)
        confs: List[float] = []
        if r.masks is not None and r.boxes is not None and len(r.boxes) > 0:
            mask_data = r.masks.data.cpu().numpy()
            classes = r.boxes.cls.cpu().numpy().astype(int)
            conf_arr = r.boxes.conf.cpu().numpy()
            for i in range(mask_data.shape[0]):
                if int(classes[i]) != TRASH_CLASS_ID:
                    continue
                m = mask_data[i] > MASK_THRESHOLD
                if m.shape != (h, w):
                    m = cv2.resize(m.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
                union |= m
                confs.append(float(conf_arr[i]))
    return union, len(confs), confs


# ---------------------------------------------------------------- ảnh
def _exif_local_time(raw: bytes) -> Optional[str]:
    """Giờ chụp ghi trong EXIF (giờ địa phương của điện thoại, không có múi giờ) -> 'YYYY-MM-DDTHH:MM:SS' hoặc None."""
    try:
        im = Image.open(io.BytesIO(raw))
        ex = im.getexif()
        v = None
        try:
            v = ex.get_ifd(0x8769).get(0x9003)   # DateTimeOriginal
        except Exception:
            v = None
        v = v or ex.get(0x0132)                   # DateTime
        if not v:
            return None
        dt = datetime.strptime(str(v).strip()[:19], "%Y:%m:%d %H:%M:%S")
        if not (2000 <= dt.year <= 2100):
            return None
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def encode_jpg(bgr: np.ndarray, max_side: Optional[int] = None, quality: int = 85) -> bytes:
    if max_side:
        h, w = bgr.shape[:2]
        if max(h, w) > max_side:
            s = max_side / max(h, w)
            bgr = cv2.resize(bgr, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        raise RuntimeError("Không mã hoá được ảnh JPEG")
    return buf.tobytes()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------- hình học
def _r(v, nd=4):
    return round(float(v), nd)


def _simplify_ring(ring_px: np.ndarray, eps: float) -> np.ndarray:
    ap = cv2.approxPolyDP(ring_px.astype(np.float32).reshape(-1, 1, 2), float(eps), True)
    ap = ap.reshape(-1, 2).astype(np.float64)
    return ap if len(ap) >= 3 else ring_px


def paper_polygon_m(marker_size_mm: float) -> np.ndarray:
    """
    Tờ giấy in bảng, trong hệ bảng (mét): bảng ở phía trên, chữ in bên dưới (xem generate_marker.py: lề trên 30 mm,
    lề bên >= 23 mm, phần chữ + thước kẻ cao khoảng 140 mm). Thêm 2 cm dư để bỏ cả bóng/mép giấy.
    """
    s = marker_size_mm / 1000.0
    half_w = s / 2 + 0.025 + 0.02
    y_top = s / 2 + 0.035 + 0.02
    y_bot = -(s / 2 + 0.150 + 0.02)
    return np.array([[-half_w, y_top], [half_w, y_top], [half_w, y_bot], [-half_w, y_bot]], dtype=np.float64)


def project_ground_to_pixels(points_m: np.ndarray, R, t, K) -> np.ndarray:
    pts3 = np.zeros((len(points_m), 3), dtype=np.float64)
    pts3[:, :2] = points_m
    rvec, _ = cv2.Rodrigues(np.asarray(R, dtype=np.float64))
    px, _ = cv2.projectPoints(pts3, rvec, np.asarray(t, dtype=np.float64).reshape(3, 1),
                              np.asarray(K, dtype=np.float64), np.zeros((5, 1)))
    return px.reshape(-1, 2)


def regions_from_mask(mask: np.ndarray, calib: dict, stats: dict) -> List[dict]:
    """Mask (H,W) -> các vùng (mỗi vùng liên thông 1 đa giác, có thể có lỗ), toạ độ hệ bảng (mét) + m^2 chính xác."""
    h, w = mask.shape
    polys = pm.mask_to_pixel_boundary_polygons(np.asarray(mask) > 0)
    stats["small_ignored"] = 0
    stats["dropped_points"] = 0
    if not polys:
        return []
    setup = pm._projection_setup(calib, (w, h), False)
    min_area = max(MIN_AREA_PX_FLOOR, MIN_AREA_FRAC * h * w)
    out = []
    for p in polys:
        outer = p["outer"]
        if abs(pm._ring_area(outer)) < min_area:
            stats["small_ignored"] += 1
            continue
        perim = float(np.abs(np.diff(np.vstack([outer, outer[:1]]), axis=0)).sum())
        eps = max(1.0, EPS_FRAC_PERIMETER * perim)
        outer_m, nd = pm.project_pixel_polygon_to_ground_m(outer, (w, h), calib, _setup=setup)
        stats["dropped_points"] += nd
        if outer_m is None:
            continue
        holes_m = []
        for hole in p["holes"]:
            hm, ndh = pm.project_pixel_polygon_to_ground_m(hole, (w, h), calib, _setup=setup)
            stats["dropped_points"] += ndh
            if hm is not None:
                holes_m.append(hm)
        area = pm.polygon_area_m2(outer_m, holes_m)
        simp_px = _simplify_ring(outer, eps)
        so, _ = pm.project_pixel_polygon_to_ground_m(simp_px, (w, h), calib, _setup=setup)
        draw_outer = so if so is not None else outer_m
        draw_holes = []
        for hole in p["holes"]:
            sh, _ = pm.project_pixel_polygon_to_ground_m(_simplify_ring(hole, eps), (w, h), calib, _setup=setup)
            if sh is not None:
                draw_holes.append(sh)
        if not math.isfinite(area) or area <= 0:
            continue
        out.append({
            "area_m2": _r(area), "area_px": int(p["area_px"]),
            "ring_m": [[_r(x, 4), _r(y, 4)] for x, y in draw_outer],
            "holes_m": [[[_r(x, 4), _r(y, 4)] for x, y in hm] for hm in draw_holes],
            "ring_px": [[int(round(u)), int(round(v))] for u, v in simp_px],
        })
    out.sort(key=lambda r: -r["area_m2"])
    if len(out) > MAX_REGIONS_PER_SPOT:
        stats["small_ignored"] += len(out) - MAX_REGIONS_PER_SPOT
        out = out[:MAX_REGIONS_PER_SPOT]
    for i, r in enumerate(out, 1):
        r["id"] = f"a{i}"
        r["hidden"] = False
    return out


# ---------------------------------------------------------------- xử lý một ảnh
def process_photo(raw: bytes, marker_size_mm: float, max_range_m: float,
                  infer: Optional[Callable] = None) -> Tuple[dict, np.ndarray]:
    """
    Trả (hồ sơ điểm - chưa có id/seq/tên/vị trí, ảnh BGR đã tiền xử lý).
    status == "ok": dò được bảng và đã chạy AI; "failed": không dò được bảng / bảng quá nhỏ (có `error` tiếng Việt),
    ảnh vẫn được giữ làm bằng chứng. Ảnh không đọc được -> PhotoError.
    """
    infer = infer or infer_trash_mask
    try:
        bgr, f35 = imaging.decode_upload(raw)
    except imaging.ImageError as exc:
        raise PhotoError({
            "The uploaded file is not a valid image. Only JPEG or PNG is accepted.": "File không phải ảnh hợp lệ (chỉ nhận JPEG hoặc PNG).",
            "Only JPEG or PNG images are accepted.": "Chỉ nhận ảnh JPEG hoặc PNG.",
            "The image resolution is too large.": "Ảnh có độ phân giải quá lớn.",
        }.get(str(exc), "Ảnh bị hỏng hoặc không đọc được.")) from None
    h, w = bgr.shape[:2]

    received = datetime.now(timezone.utc)
    captured_local = _exif_local_time(raw)
    rec: dict = {
        "status": "failed", "error": None,
        "sha256": sha256(raw),
        "received_at": received.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "captured_local": captured_local or datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "time_source": "exif" if captured_local else "received",
        "image_size": [int(w), int(h)],
        "marker_size_mm": float(marker_size_mm),
        "calib": None, "ai_regions": [], "manual_regions": [],
        "footprint_m": [], "board_m": [], "n_instances": 0, "mean_conf": None, "warnings": [],
        "fov_deg": None, "fov_source": None, "focal_35mm": None, "side_px_min": None, "camera_height_m": None,
    }

    warnings: List[str] = []
    if f35 is not None:
        fov, fov_source = imaging.diagonal_fov_from_35mm(f35), "exif"
    else:
        fov, fov_source = config.DIAGONAL_FOV_DEG, "default"
        warnings.append(
            f"Ảnh không có thông tin tiêu cự (EXIF): dùng góc nhìn mặc định {config.DIAGONAL_FOV_DEG:.0f}°. "
            f"Điện thoại thường 70–85°, nên diện tích m² có thể lệch. Hãy gửi ảnh gốc, không qua Zalo/Messenger."
        )
    rec.update({"fov_deg": _r(fov, 2), "fov_source": fov_source, "focal_35mm": None if f35 is None else float(f35)})

    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise PhotoError("Không xử lý được ảnh.")
    with tempfile.TemporaryDirectory(prefix="survey_calib_") as td:
        img_path = Path(td) / "calib.png"
        img_path.write_bytes(buf.tobytes())
        try:
            res = calibrate_aruco.detect_and_solve_pnp(img_path, config.MARKER_ID, marker_size_mm, diagonal_fov_deg=fov)
        except RuntimeError as exc:
            msg = str(exc)
            if "Không tìm thấy marker" in msg:
                rec["error"] = "Không thấy bảng ArUco trong ảnh. Chụp lại: thấy trọn tờ bảng, không bị che, không chói."
            elif "không có id" in msg:
                rec["error"] = "Trong ảnh có mã ArUco nhưng không phải bảng hiệu chỉnh (cần ID 0 của DICT_4X4_50)."
            else:
                rec["error"] = "Không giải được vị trí camera từ bảng. Chụp lại ảnh nét hơn."
            rec["warnings"] = warnings
            return rec, bgr

    q = res["quality"]
    side_min = float(q["marker_side_px_min"])
    rec["side_px_min"] = _r(side_min, 1)
    rec["camera_height_m"] = None if q.get("camera_height_m_est") is None else _r(q["camera_height_m_est"], 2)
    if calib_quality.is_too_small(side_min):
        rec["error"] = (f"Bảng quá nhỏ trong ảnh (cạnh ngắn nhất {math.floor(side_min * 10) / 10:.1f} px, "
                        f"cần ≥ {calib_quality.MIN_SIDE_PX:.0f} px). Đứng gần bảng hơn hoặc zoom vào.")
        rec["warnings"] = warnings
        return rec, bgr
    warnings += [str(x) for x in (q.get("warnings") or [])]

    calib = {
        "camera_id": "SURVEY", "R": np.asarray(res["R"]).tolist(), "t": np.asarray(res["t"]).reshape(3).tolist(),
        "camera_matrix": np.asarray(res["camera_matrix"]).tolist(), "image_size": [int(w), int(h)],
        "marker_latlon": [0.0, 0.0], "azimuth_deg": 0.0,
    }
    rec["calib"] = {k: calib[k] for k in ("R", "t", "camera_matrix", "image_size")}

    mask, n_inst, confs = infer(bgr)
    mask = np.asarray(mask).astype(bool)
    if mask.shape != (h, w):
        raise RuntimeError(f"mask {mask.shape} không khớp ảnh {(h, w)}")
    # Bỏ phần tờ giấy bảng (model hay khoanh nhầm thành rác)
    paper_px = project_ground_to_pixels(paper_polygon_m(marker_size_mm), res["R"], res["t"], res["camera_matrix"])
    paper_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(paper_mask, [np.round(paper_px).astype(np.int32).reshape(-1, 1, 2)], 1)
    removed = int((mask & (paper_mask > 0)).sum())
    mask &= (paper_mask == 0)

    stats: dict = {}
    regions = regions_from_mask(mask, calib, stats)
    mean_conf = round(float(np.mean(confs)), 4) if confs else None
    for r in regions:
        r["conf"] = mean_conf
    if n_inst == 0 or not mask.any():
        warnings.append("AI không thấy rác nào trong ảnh này (AI còn bỏ sót, có thể vẫn có rác).")
    if stats.get("small_ignored"):
        warnings.append(f"Bỏ qua {stats['small_ignored']} vùng rất nhỏ (coi là nhiễu).")
    if stats.get("dropped_points"):
        warnings.append(f"Bỏ {stats['dropped_points']} điểm viền không chạm mặt đất (gần/ trên đường chân trời).")

    foot = pm.ground_footprint_polygon(calib, (w, h), float(max_range_m))
    half = marker_size_mm / 2000.0
    rec.update({
        "status": "ok", "error": None, "warnings": warnings,
        "ai_regions": regions,
        "footprint_m": [[_r(x, 3), _r(y, 3)] for x, y in foot] if len(foot) >= 3 else [],
        "board_m": [[-half, half], [half, half], [half, -half], [-half, -half]],
        "n_instances": int(n_inst), "mean_conf": mean_conf, "paper_px_removed": removed,
    })
    return rec, bgr


def render_overlay(bgr: np.ndarray, spot: dict) -> np.ndarray:
    """Ảnh + vùng AI đang hiện (đỏ) + viền bảng (xanh lá). Vùng vẽ tay không có toạ độ ảnh nên không vẽ ở đây."""
    out = bgr.copy()
    h, w = out.shape[:2]
    layer = out.copy()
    th = max(2, int(round(max(h, w) / 500)))
    for r in spot.get("ai_regions", []):
        if r.get("hidden") or not r.get("ring_px"):
            continue
        pts = np.array(r["ring_px"], dtype=np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(layer, [pts], (60, 60, 235))
    out = cv2.addWeighted(layer, 0.45, out, 0.55, 0)
    for r in spot.get("ai_regions", []):
        if r.get("hidden") or not r.get("ring_px"):
            continue
        cv2.polylines(out, [np.array(r["ring_px"], dtype=np.int32).reshape(-1, 1, 2)], True, (30, 30, 200), th, cv2.LINE_AA)
    c = spot.get("calib")
    if c:
        half = spot["marker_size_mm"] / 2000.0
        sq = np.array([[-half, half], [half, half], [half, -half], [-half, -half]])
        px = project_ground_to_pixels(sq, c["R"], c["t"], c["camera_matrix"])
        cv2.polylines(out, [np.round(px).astype(np.int32).reshape(-1, 1, 2)], True, (0, 200, 0), th, cv2.LINE_AA)
    return out


# ---------------------------------------------------------------- chỉnh tay
def ring_area_m2(ring) -> float:
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def clean_manual_ring(ring) -> List[List[float]]:
    """Kiểm vùng vẽ tay (mét, hệ bảng): 3–200 đỉnh hữu hạn, trong phạm vi ±300 m, diện tích đủ lớn."""
    if not isinstance(ring, list) or not (3 <= len(ring) <= 200):
        raise ValueError("Vùng vẽ tay cần từ 3 đến 200 đỉnh.")
    out = []
    for p in ring:
        if (not isinstance(p, (list, tuple)) or len(p) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 300 for v in p)):
            raise ValueError("Toạ độ đỉnh không hợp lệ.")
        out.append([_r(p[0], 4), _r(p[1], 4)])
    if ring_area_m2(out) < MIN_MANUAL_AREA_M2:
        raise ValueError("Vùng vẽ tay quá nhỏ hoặc các đỉnh thẳng hàng.")
    return out


def visible_regions(spot: dict) -> List[dict]:
    """Các vùng đang tính vào số liệu: vùng AI chưa ẩn + vùng vẽ tay. Mỗi vùng: kind, id, area_m2, ring_m, holes_m."""
    out = []
    for r in spot.get("ai_regions", []):
        if not r.get("hidden"):
            out.append({"kind": "ai", "id": r["id"], "area_m2": r["area_m2"], "ring_m": r["ring_m"],
                        "holes_m": r.get("holes_m", []), "conf": r.get("conf")})
    for r in spot.get("manual_regions", []):
        out.append({"kind": "manual", "id": r["id"], "area_m2": r["area_m2"], "ring_m": r["ring_m"], "holes_m": [], "conf": None})
    return out


def spot_area_m2(spot: dict) -> float:
    return round(sum(r["area_m2"] for r in visible_regions(spot)), 4)


def effective_az(spot: dict, settings: dict) -> float:
    p = spot.get("placement") or {}
    az = p.get("az")
    return float(settings.get("az_global", 0.0) if az is None else az) % 360.0


def is_placed(spot: dict) -> bool:
    p = spot.get("placement")
    return bool(p) and p.get("lat") is not None and p.get("lon") is not None


def ring_to_lonlat(ring_m, lat0: float, lon0: float, az: float) -> List[List[float]]:
    """Vòng (x,y) mét hệ bảng -> [[lat, lon], ...] (dùng cho bản trình bày)."""
    out = []
    for x, y in ring_m:
        e, n = pm.marker_xy_to_enu(float(x), float(y), az)
        lat, lon = pm.meters_to_latlon(lat0, lon0, e, n)
        out.append([round(lat, 8), round(lon, 8)])
    return out


# ---------------------------------------------------------------- tổng hợp
def _spot_polys_enu(spot: dict, settings: dict, ref_lat: float, ref_lon: float):
    """Vùng đang hiện của điểm đã đặt, trong hệ (Đông, Bắc) mét quanh điểm tham chiếu chung. -> [(outer, holes)]."""
    p = spot["placement"]
    az = effective_az(spot, settings)
    dn = math.radians(p["lat"] - ref_lat) * config.EARTH_RADIUS_M
    de = math.radians(p["lon"] - ref_lon) * config.EARTH_RADIUS_M * math.cos(math.radians(ref_lat))
    out = []
    for r in visible_regions(spot):
        def conv(ring):
            arr = []
            for x, y in ring:
                e, n = pm.marker_xy_to_enu(float(x), float(y), az)
                arr.append((e + de, n + dn))
            return np.array(arr, dtype=np.float64)
        out.append((conv(r["ring_m"]), [conv(hm) for hm in r.get("holes_m", [])]))
    return out


def _raster(polys, x0, y0, nx, ny, cell):
    """Hai mặt nạ: `filled` (gồm cả ô trên biên) và `inner` (bỏ ô trên biên). Diện tích thật nằm giữa hai cái."""
    filled = np.zeros((ny, nx), dtype=np.uint8)
    for outer, holes in polys:
        o = np.round((outer - [x0, y0]) / cell).astype(np.int32)
        cv2.fillPoly(filled, [o.reshape(-1, 1, 2)], 1)
        for hm in holes:
            hh = np.round((hm - [x0, y0]) / cell).astype(np.int32)
            cv2.fillPoly(filled, [hh.reshape(-1, 1, 2)], 0)
    edge = np.zeros((ny, nx), dtype=np.uint8)
    for outer, holes in polys:
        for ring in [outer] + list(holes):
            q = np.round((ring - [x0, y0]) / cell).astype(np.int32)
            cv2.polylines(edge, [q.reshape(-1, 1, 2)], True, 1, 1)
    inner = filled & (1 - edge)
    return filled, inner


def compute_overlaps(spots: List[dict], settings: dict, cell: float = 0.05, min_m2: float = 0.02) -> List[dict]:
    """Các cặp điểm có vùng rác chồng nhau (cùng một mảnh đất bị tính hai lần). -> [{a, b, m2}]."""
    placed = [s for s in spots if s.get("status") == "ok" and s.get("include", True) and is_placed(s) and visible_regions(s)]
    if len(placed) < 2:
        return []
    ref_lat, ref_lon = placed[0]["placement"]["lat"], placed[0]["placement"]["lon"]
    items = []
    for s in placed:
        polys = _spot_polys_enu(s, settings, ref_lat, ref_lon)
        pts = np.vstack([o for o, _ in polys])
        items.append((s, polys, pts.min(axis=0), pts.max(axis=0)))
    res = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            si, pi, lo_i, hi_i = items[i]
            sj, pj, lo_j, hi_j = items[j]
            lo = np.maximum(lo_i, lo_j)
            hi = np.minimum(hi_i, hi_j)
            if np.any(hi <= lo):
                continue
            nx = int(math.ceil((hi[0] - lo[0]) / cell)) + 2
            ny = int(math.ceil((hi[1] - lo[1]) / cell)) + 2
            if nx * ny > 25_000_000:
                continue
            af, ai = _raster(pi, lo[0], lo[1], nx, ny, cell)
            bf, bi = _raster(pj, lo[0], lo[1], nx, ny, cell)
            m2 = 0.5 * (float(np.count_nonzero(af & bf)) + float(np.count_nonzero(ai & bi))) * cell * cell
            if m2 >= min_m2:
                res.append({"a": si["id"], "b": sj["id"], "a_name": si.get("name"), "b_name": sj.get("name"), "m2": round(m2, 2)})
    return res


def summarize(data: dict) -> dict:
    settings = data["settings"]
    spots = data["spots"]
    ok = [s for s in spots if s.get("status") == "ok"]
    counted = [s for s in ok if s.get("include", True) and is_placed(s)]
    n_ai = sum(1 for s in counted for r in s["ai_regions"] if not r.get("hidden"))
    n_manual = sum(len(s["manual_regions"]) for s in counted)
    area_manual = sum(r["area_m2"] for s in counted for r in s["manual_regions"])
    total = sum(spot_area_m2(s) for s in counted)
    return {
        "n_photos": len(spots), "n_failed": sum(1 for s in spots if s.get("status") != "ok"),
        "n_unplaced": sum(1 for s in ok if not is_placed(s)),
        "n_spots": len(counted), "n_ai_regions": n_ai, "n_manual_regions": n_manual,
        "area_m2": round(total, 2), "area_manual_m2": round(area_manual, 2), "area_ai_m2": round(total - area_manual, 2),
        "overlaps": compute_overlaps(spots, settings),
    }
