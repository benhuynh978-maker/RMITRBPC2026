"""
CleanSight "Calibration lab": hai phòng thử cho giám khảo, chạy trên cùng dịch vụ live demo (server.py).

  1) Board lab  - hiệu chỉnh camera bằng bảng ArUco rồi vẽ vùng rác lên bản đồ   (/api/lab/board/...)
  2) Drain lab  - vẽ vùng miệng cống và đo tỉ lệ rác che cống                    (/api/lab/drain/...)

Thiết kế (khác web test gốc ở research/exp02_ve_rac_len_ban_do/webtest, vốn một-người-dùng và lưu đĩa):
  - Giám khảo KHÔNG tải ảnh lên. Máy chủ giữ sẵn vài ảnh mẫu của đội (lab_samples/, chỉ đọc) và nhận `sample_id`.
    Nhờ vậy không có bề mặt giải mã ảnh người lạ, không có vấn đề riêng tư về ảnh.
  - Trạng thái (hiệu chỉnh đang chờ, hiệu chỉnh đã lưu, lịch sử vùng rác) nằm TRONG RAM, theo từng phiên
    (header X-Lab-Session do trình duyệt tự sinh). Hai giám khảo cùng vào KHÔNG đè dữ liệu của nhau.
    Phiên hết hạn sau 30 phút không dùng; tối đa 40 phiên (đầy thì bỏ phiên cũ nhất). Không ghi gì ra đĩa.
  - Phép tính dùng lại NGUYÊN các module của exp02 (calibrate_aruco, project_mask, imaging, board_coords) và
    analysis.analyze(roi=...) của ssc-v2: không nhân bản logic hình học.
  - Giới hạn tần suất riêng: nhẹ (mọi lời gọi) và nặng (chạy model: observe, drain/measure).
"""
from __future__ import annotations

import base64
import importlib.util
import math
import re
import secrets
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import Body, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

HERE = Path(__file__).resolve().parent
EXP_DIR = HERE.parent / "exp02_ve_rac_len_ban_do"
SAMPLES_DIR = HERE / "lab_samples"

if str(EXP_DIR) not in sys.path:
    sys.path.append(str(EXP_DIR))  # append (không insert): module của dịch vụ này được ưu tiên

import calib_quality  # noqa: E402
import calibrate_aruco  # noqa: E402
import config as exp_config  # noqa: E402
import project_mask as pm  # noqa: E402


def _load_file(name: str, path: Path):
    """Nạp một file .py theo đường dẫn với tên module riêng (tránh trùng tên `server`, `store` của webtest)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


imaging = _load_file("lab_webtest_imaging", EXP_DIR / "webtest" / "imaging.py")
board_coords = _load_file("lab_webtest_board_coords", EXP_DIR / "webtest" / "board_coords.py")

# ---------------------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------------------
DEFAULT_LATLNG = (10.7769, 106.7009)   # điểm mặc định của web test (config.DEMO_MARKER_LATLON)
DEFAULT_MARKER_SIZE_MM = 250.0         # cạnh vùng mã của tờ bảng mẫu, đo bằng thước
CAMERA_ID = "LAB"
ASPECT_TOLERANCE = 0.01
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
SESSION_TTL_S = 30 * 60
MAX_SESSIONS = 40
MAX_PENDING = 6
MAX_OBSERVATIONS = 10
ROI_MAX_POINTS = 64   # khớp giới hạn drain_roi của backend (3-64 điểm); analysis.validate_roi_polygon không kiểm tối đa

# Chạy model: giống webtest/server.py
PREDICT_IMGSZ = 1024
DETECT_CONF = 0.25
MASK_THRESHOLD = 0.5
TRASH_CLASS_ID = 0
MIN_AREA_FRAC = 0.00003
MIN_AREA_PX_FLOOR = 20.0
EPS_FRAC_PERIMETER = 0.002
EPS_MIN_PX = 1.0

SAMPLES = {
    "board-near": {
        "kind": "calibration", "file": "board-near.jpg", "marker_size_mm": DEFAULT_MARKER_SIZE_MM,
        "label": "Board photo",
        "note": "The camera is fixed. The black square of the printed board measures 250 mm (ruler).",
    },
    "board-far": {
        "kind": "calibration", "file": "board-far.jpg", "marker_size_mm": DEFAULT_MARKER_SIZE_MM,
        "label": "Board photo, camera far away (simulated)",
        "note": "The same photo shrunk to 30%, to show what happens when the board looks too small.",
    },
    "board-trash": {
        "kind": "trash", "file": "board-trash.jpg",
        "label": "Photo with trash",
        "note": "Taken from almost the same spot as the board photo (the phone moved about 7 cm), "
                "so positions are accurate to a few centimetres. The printed board is not trash, but the model may outline it.",
    },
    "drain-litter": {
        "kind": "drain", "file": "drain-litter.jpg",
        "label": "Drain inlet covered with litter",
        "note": "Draw the zone around the drain inlet.",
    },
}

_BGR: dict = {}
_BYTES: dict = {}
_IO_LOCK = threading.Lock()


class LabError(Exception):
    def __init__(self, status: int, message: str, code: str = "error", headers: Optional[dict] = None, **extra):
        super().__init__(message)
        self.status, self.message, self.code, self.headers, self.extra = status, message, code, headers or {}, extra


def _num(x) -> Optional[float]:
    f = float(x)
    return f if math.isfinite(f) else None


# ---------------------------------------------------------------------------------------
# Giới hạn tần suất (đối tượng được tạo trong register(), vì cần lớp RateLimiter của server.py)
# ---------------------------------------------------------------------------------------
LIGHT = None   # mọi lời gọi lab
HEAVY = None   # lời gọi chạy model


def _guard(request: Request, srv, heavy: bool) -> None:
    ok, retry_after, code = (HEAVY if heavy else LIGHT).check(srv.client_ip(request))
    if not ok:
        message = "The demo is busy. Please try again shortly." if code == "busy_global" else "Too many requests."
        raise LabError(429, message, code, {"Retry-After": str(retry_after)})


# ---------------------------------------------------------------------------------------
# Phiên trong RAM
# ---------------------------------------------------------------------------------------
class _Session:
    def __init__(self):
        self.pending: "OrderedDict[str, dict]" = OrderedDict()   # calibration_id -> kết quả dò bảng chưa lưu
        self.saved: Optional[dict] = None                         # hiệu chỉnh đã lưu
        self.observations: list = []
        self.lock = threading.Lock()
        self.last = time.monotonic()


_SESSIONS: "OrderedDict[str, _Session]" = OrderedDict()
_SESSIONS_LOCK = threading.Lock()


def _session(request: Request) -> _Session:
    sid = request.headers.get("x-lab-session", "")
    if not SESSION_RE.match(sid):
        raise LabError(400, "Missing or invalid lab session id.", "invalid_session")
    now = time.monotonic()
    with _SESSIONS_LOCK:
        for key in [k for k, s in _SESSIONS.items() if now - s.last > SESSION_TTL_S]:
            del _SESSIONS[key]
        sess = _SESSIONS.get(sid)
        if sess is None:
            while len(_SESSIONS) >= MAX_SESSIONS:
                _SESSIONS.popitem(last=False)   # bỏ phiên cũ nhất
            sess = _SESSIONS[sid] = _Session()
        sess.last = now
        _SESSIONS.move_to_end(sid)
        return sess


# ---------------------------------------------------------------------------------------
# Ảnh mẫu (chỉ đọc)
# ---------------------------------------------------------------------------------------
def _sample(sample_id, kind: str) -> dict:
    s = SAMPLES.get(sample_id) if isinstance(sample_id, str) else None
    if s is None or s["kind"] != kind:
        raise LabError(404, "Unknown sample photo.", "unknown_sample")
    return s


def _sample_bgr(sample_id: str) -> np.ndarray:
    with _IO_LOCK:
        if sample_id not in _BGR:
            img = cv2.imread(str(SAMPLES_DIR / SAMPLES[sample_id]["file"]))
            if img is None:
                raise LabError(500, "Sample photo is missing on the server.", "server_error")
            _BGR[sample_id] = img
        return _BGR[sample_id]


def _sample_bytes(sample_id: str) -> bytes:
    with _IO_LOCK:
        if sample_id not in _BYTES:
            _BYTES[sample_id] = (SAMPLES_DIR / SAMPLES[sample_id]["file"]).read_bytes()
        return _BYTES[sample_id]


def _number_field(body: dict, key: str, default: Optional[float], lo: float, hi: float, text: str) -> Optional[float]:
    v = body.get(key)
    if v is None or v == "":
        return default
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or not (lo <= float(v) <= hi):
        raise LabError(422, text, "invalid_value")
    return float(v)


def _check_latlon(lat, lon) -> None:
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise LabError(422, "Latitude must be within ±90 and longitude within ±180.", "invalid_value")


# ---------------------------------------------------------------------------------------
# Vùng rác -> GeoJSON (sao chép từ webtest/server.py: mask_to_region_features, giữ nguyên thuật toán)
# ---------------------------------------------------------------------------------------
def _simplify_ring(ring_px: np.ndarray, eps: float) -> np.ndarray:
    ap = cv2.approxPolyDP(ring_px.astype(np.float32).reshape(-1, 1, 2), float(eps), True)
    ap = ap.reshape(-1, 2).astype(np.float64)
    return ap if len(ap) >= 3 else ring_px


def mask_to_region_features(mask: np.ndarray, calib: dict, confidence: Optional[float], stats: Optional[dict] = None):
    h, w = mask.shape
    polys = pm.mask_to_pixel_boundary_polygons(np.asarray(mask) > 0)
    if not polys:
        return [], 0.0, 0
    lat0, lon0 = calib["marker_latlon"]
    setup = pm._projection_setup(calib, (w, h), False)
    min_area = max(MIN_AREA_PX_FLOOR, MIN_AREA_FRAC * h * w)
    if stats is not None:
        stats["min_area_px"] = float(min_area)
        stats["small_ignored"] = 0
    features, total, dropped = [], 0.0, 0
    for p in polys:
        outer = p["outer"]
        if abs(pm._ring_area(outer)) < min_area:
            if stats is not None:
                stats["small_ignored"] += 1
            continue
        perim = float(np.abs(np.diff(np.vstack([outer, outer[:1]]), axis=0)).sum())
        eps = max(EPS_MIN_PX, EPS_FRAC_PERIMETER * perim)
        outer_m, nd = pm.project_pixel_polygon_to_ground_m(outer, (w, h), calib, _setup=setup)
        dropped += nd
        if outer_m is None:
            continue
        holes_m = []
        for hole in p["holes"]:
            hm, ndh = pm.project_pixel_polygon_to_ground_m(hole, (w, h), calib, _setup=setup)
            dropped += ndh
            if hm is not None:
                holes_m.append(hm)
        area_m2 = pm.polygon_area_m2(outer_m, holes_m)
        so, _ = pm.project_pixel_polygon_to_ground_m(_simplify_ring(outer, eps), (w, h), calib, _setup=setup)
        draw_outer = so if so is not None else outer_m
        draw_holes = []
        for hole in p["holes"]:
            sh, _ = pm.project_pixel_polygon_to_ground_m(_simplify_ring(hole, eps), (w, h), calib, _setup=setup)
            if sh is not None:
                draw_holes.append(sh)
        rings = [pm._ring_m_to_lonlat(pm._oriented(draw_outer, True), lat0, lon0)]
        rings += [pm._ring_m_to_lonlat(pm._oriented(hm, False), lat0, lon0) for hm in draw_holes]
        features.append({
            "type": "Feature",
            "properties": {"area_m2": _num(area_m2), "area_px": int(p["area_px"]), "confidence": confidence, "kind": "trash"},
            "geometry": {"type": "Polygon", "coordinates": rings},
        })
        total += area_m2
    return features, float(total), int(dropped)


def _en_quality_warning(text: str) -> str:
    """Cảnh báo chất lượng của calib_quality là tiếng Việt: đổi sang tiếng Anh cho trang (khớp web test)."""
    t = str(text)
    if "quá nhỏ" in t:
        return "The board is very small in the photo (under 50 px): the camera pose may be wrong."
    if "lật" in t:
        return ("The two possible camera poses are almost equally good, so the pose may be flipped. Retake the photo from a "
                "more oblique angle or closer, and compare the computed camera position with reality.")
    if "mờ" in t:
        return "The board is blurry in the photo (out of focus or hand shake). Retake it sharper: blur causes the worst pose errors."
    if "JPEG" in t or "jpeg" in t:
        return "The photo is heavily JPEG-compressed. Capture the calibration photo at the highest JPEG quality."
    if "độ cao" in t:
        return "The estimated camera height differs from the height you entered by more than 20%."
    return "Calibration quality warning."


# ---------------------------------------------------------------------------------------
# Đăng ký route
# ---------------------------------------------------------------------------------------
def register(app, srv) -> None:
    """srv = module server.py (cung cấp ApiError, RateLimiter, client_ip, model_lock, reserve_slot/release_slot, _ready)."""
    global LIGHT, HEAVY
    import analysis  # đã nạp bởi server.py

    LIGHT = srv.RateLimiter(srv._int_env("CLEANSIGHT_LAB_LIGHT_PER_MINUTE", 90), 1500, 300)
    HEAVY = srv.RateLimiter(srv._int_env("CLEANSIGHT_LAB_HEAVY_PER_MINUTE", 12), 150, 40)

    @app.exception_handler(LabError)
    async def _lab_error(_request: Request, exc: LabError):
        return JSONResponse(status_code=exc.status, headers=exc.headers,
                            content={"ok": False, "error": exc.message, "code": exc.code, **exc.extra})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "Invalid request.", "code": "invalid_request"})

    class _Slot:
        """Một chỗ trong hàng chờ model + khoá model, dùng chung với /api/analyze."""
        def __enter__(self):
            if not srv._ready:
                raise LabError(503, "The live demo is starting. Please try again in a moment.", "not_ready")
            try:
                srv.reserve_slot()
            except srv.ApiError as exc:
                raise LabError(exc.status, exc.message, exc.code, exc.headers) from None
            srv.model_lock.acquire()
            return self

        def __exit__(self, *exc):
            srv.model_lock.release()
            srv.release_slot()

    def _saved(sess: _Session) -> Optional[dict]:
        return sess.saved

    # ---------------- danh sách ảnh mẫu ----------------
    @app.get("/api/lab/board/samples")
    def board_samples(request: Request):
        _guard(request, srv, False)
        _session(request)
        out = {"calibration": [], "trash": []}
        for sid, s in SAMPLES.items():
            if s["kind"] in out:
                h, w = _sample_bgr(sid).shape[:2]
                item = {"id": sid, "label": s["label"], "note": s["note"], "image_size": [int(w), int(h)]}
                if s["kind"] == "calibration":
                    item["marker_size_mm"] = s["marker_size_mm"]
                out[s["kind"]].append(item)
        return {"ok": True, **out, "defaults": {"lat": DEFAULT_LATLNG[0], "lon": DEFAULT_LATLNG[1], "azimuth_deg": 0.0}}

    # ---------------- 1) dò bảng ----------------
    @app.post("/api/lab/board/detect")
    def board_detect(request: Request, body: dict = Body(...)):
        _guard(request, srv, False)
        sess = _session(request)
        sample_id = body.get("sample_id")
        sample = _sample(sample_id, "calibration")
        size_mm = _number_field(body, "marker_size_mm", DEFAULT_MARKER_SIZE_MM, 10.0, 5000.0,
                                "Board side length must be between 10 and 5000 mm.")
        fov_in = _number_field(body, "fov_deg", None, 1.0, 179.0,
                               "Lens field of view (fov_deg) must be between 1 and 179 degrees.")
        bgr = _sample_bgr(sample_id)
        h, w = bgr.shape[:2]
        warnings = []
        if fov_in is not None:
            fov, fov_source = fov_in, "input"
        else:
            fov, fov_source = exp_config.DIAGONAL_FOV_DEG, "default"
            warnings.append(
                f"Could not read the focal length from the photo: using the default field of view of "
                f"{exp_config.DIAGONAL_FOV_DEG:.0f}° (ESP32 camera). Phones are usually about 70–85°; if yours differs, "
                f"region positions and sizes will be off. Enter the field of view (degrees, diagonal) if you know it."
            )
        try:
            result = calibrate_aruco.detect_and_solve_pnp(
                SAMPLES_DIR / sample["file"], exp_config.MARKER_ID, size_mm, diagonal_fov_deg=fov)
        except RuntimeError as exc:
            msg = str(exc)
            if "Không tìm thấy marker" in msg:
                text = ("No ArUco board found in the photo. Capture the whole board clearly, unobstructed, "
                        "without glare and in good light.")
            elif "không có id" in msg:
                text = "The photo has an ArUco code but it is not the calibration board (ID 0 of DICT_4X4_50 is required)."
            else:
                text = "Could not solve the camera position from the board. Please retake a sharper photo."
            raise LabError(422, text, "board_not_found", side_px_min=None, overlay_jpg_b64=None) from None

        q = result["quality"]
        side_min = float(q["marker_side_px_min"])
        overlay_b64 = imaging.encode_jpg_b64(
            imaging.draw_overlay(bgr, result["R"], result["t"], result["camera_matrix"], size_mm / 1000.0))
        if calib_quality.is_too_small(side_min):
            raise LabError(
                422,
                f"Board too small in the photo (shortest side {math.floor(side_min * 10) / 10:.1f} px, minimum "
                f"{calib_quality.MIN_SIDE_PX:.1f} px). Move closer or use a larger board.",
                "board_too_small", side_px_min=_num(side_min), overlay_jpg_b64=overlay_b64)

        calibration_id = secrets.token_hex(8)
        with sess.lock:
            sess.pending[calibration_id] = {
                "id": calibration_id, "sample_id": sample_id, "marker_size_mm": size_mm, "fov_source": fov_source,
                "result": {
                    "R": result["R"].tolist(), "t": result["t"].tolist(), "camera_matrix": result["camera_matrix"].tolist(),
                    "image_size": [int(w), int(h)], "reproj_error_rms_px": float(result["reproj_error_rms_px"]),
                    "side_px_min": side_min, "diagonal_fov_deg": float(fov),
                },
            }
            while len(sess.pending) > MAX_PENDING:
                sess.pending.popitem(last=False)
        return {
            "ok": True, "calibration_id": calibration_id, "sample_id": sample_id,
            "side_px_min": _num(side_min), "side_px_mean": _num(q["marker_side_px_mean"]),
            "fov_deg": float(fov), "fov_source": fov_source, "focal_35mm": None,
            "warnings": warnings + [_en_quality_warning(x) for x in q["warnings"]],
            "camera_height_m_est": _num(q["camera_height_m_est"]),
            "image_size": [int(w), int(h)], "overlay_jpg_b64": overlay_b64,
        }

    # ---------------- 2) vùng mặt đất camera thấy ----------------
    @app.get("/api/lab/board/footprint")
    def board_footprint(request: Request, calibration_id: Optional[str] = Query(None), lat: Optional[float] = Query(None),
                        lon: Optional[float] = Query(None), azimuth_deg: Optional[float] = Query(None),
                        max_range_m: float = Query(12.0)):
        _guard(request, srv, False)
        sess = _session(request)
        if calibration_id:
            with sess.lock:
                pend = sess.pending.get(calibration_id)
            if pend is None:
                raise LabError(404, "Calibration result not found (expired or unknown). Please detect the board again.", "not_found")
            if lat is None or lon is None:
                raise LabError(422, "Missing latitude/longitude (lat, lon).", "invalid_value")
            src = pend["result"]
            lat0, lon0, az0 = lat, lon, (0.0 if azimuth_deg is None else azimuth_deg)
        else:
            saved = _saved(sess)
            if saved is None:
                raise LabError(404, "No saved calibration.", "not_found")
            src = saved
            lat0 = saved["marker_latlon"][0] if lat is None else lat
            lon0 = saved["marker_latlon"][1] if lon is None else lon
            az0 = saved.get("azimuth_deg", 0.0) if azimuth_deg is None else azimuth_deg
        _check_latlon(lat0, lon0)
        if not math.isfinite(az0):
            raise LabError(422, "Invalid azimuth.", "invalid_value")
        rng = 12.0 if not math.isfinite(max_range_m) else min(50.0, max(1.0, max_range_m))
        az = az0 % 360.0
        calib = {"camera_id": CAMERA_ID, "marker_latlon": [lat0, lon0], "azimuth_deg": az,
                 "R": src["R"], "t": src["t"], "camera_matrix": src["camera_matrix"], "image_size": src["image_size"]}
        w, h = calib["image_size"]
        poly_marker = pm.ground_footprint_polygon(calib, (w, h), rng)
        if len(poly_marker) < 3:
            raise LabError(422, "The camera does not see the ground within this range.", "no_ground")
        e, n = pm.marker_xy_to_enu(poly_marker[:, 0], poly_marker[:, 1], az)
        ring = pm._ring_m_to_lonlat(pm._oriented(np.stack([e, n], axis=1), True), lat0, lon0)
        cam = pm.camera_position_geojson(calib)
        return {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"kind": "footprint"}, "geometry": {"type": "Polygon", "coordinates": [ring]}},
                {"type": "Feature", "properties": {"kind": "marker"}, "geometry": {"type": "Point", "coordinates": [lon0, lat0]}},
                {"type": "Feature", "properties": {"kind": "camera", "height_m": float(cam["properties"]["height_m"])},
                 "geometry": cam["geometry"]},
            ],
        }

    # ---------------- 3) lưu / đọc hiệu chỉnh ----------------
    @app.post("/api/lab/board/calibration/save")
    def board_save(request: Request, body: dict = Body(...)):
        _guard(request, srv, False)
        sess = _session(request)
        cid = body.get("calibration_id")
        if not isinstance(cid, str):
            raise LabError(422, "Missing 'calibration_id'.", "invalid_value")
        lat = _number_field(body, "lat", None, -90.0, 90.0, "Missing or invalid value 'lat' (must be a number).")
        lon = _number_field(body, "lon", None, -180.0, 180.0, "Missing or invalid value 'lon' (must be a number).")
        az = _number_field(body, "azimuth_deg", None, -100000.0, 100000.0, "Missing or invalid value 'azimuth_deg' (must be a number).")
        if lat is None or lon is None or az is None:
            raise LabError(422, "Missing latitude, longitude or azimuth.", "invalid_value")
        with sess.lock:
            pend = sess.pending.get(cid)
            if pend is None:
                raise LabError(404, "Calibration result not found (expired or unknown). Please detect the board again.", "not_found")
            res = pend["result"]
            sess.saved = {
                "camera_id": CAMERA_ID, "marker_latlon": [lat, lon], "azimuth_deg": az % 360.0,
                "R": res["R"], "t": res["t"], "camera_matrix": res["camera_matrix"], "image_size": res["image_size"],
                "diagonal_fov_deg": res["diagonal_fov_deg"], "side_px_min": res["side_px_min"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        return {"ok": True, "camera_id": CAMERA_ID}

    @app.get("/api/lab/board/calibration")
    def board_calibration(request: Request):
        _guard(request, srv, False)
        c = _saved(_session(request))
        if c is None:
            return {"ok": False, "error": "Not calibrated"}
        return {"ok": True, "calibration": {
            "camera_id": c["camera_id"], "marker_latlon": c["marker_latlon"], "azimuth_deg": c["azimuth_deg"],
            "fov_deg": c["diagonal_fov_deg"], "image_size": c["image_size"], "side_px_min": c["side_px_min"],
            "created_at": c["created_at"]}}

    # ---------------- 4) gửi ảnh có rác ----------------
    @app.post("/api/lab/board/observe")
    def board_observe(request: Request, body: dict = Body(...)):
        _guard(request, srv, True)
        sess = _session(request)
        received = datetime.now(timezone.utc)
        calib = _saved(sess)
        if calib is None:
            raise LabError(409, "Camera not calibrated", "not_calibrated")
        sample_id = body.get("sample_id")
        _sample(sample_id, "trash")
        bgr = _sample_bgr(sample_id)
        h, w = bgr.shape[:2]
        cw, ch = calib["image_size"]
        if abs((w / h) / (cw / ch) - 1.0) > ASPECT_TOLERANCE:
            raise LabError(422, f"The photo must have the same aspect ratio / fixed position as the calibration photo "
                                f"(this photo {w}x{h}, calibration photo {cw}x{ch}).", "aspect_mismatch")
        t0 = time.perf_counter()
        with _Slot():
            r = analysis.predict(bgr)
            union = np.zeros((h, w), dtype=bool)
            confs = []
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
            annotated = r.plot()
        inference_ms = (time.perf_counter() - t0) * 1000.0

        mean_conf = round(float(np.mean(confs)), 4) if confs else None
        stats: dict = {}
        features, total_m2, dropped = mask_to_region_features(union, calib, mean_conf, stats)
        features = board_coords.annotate_regions(features, calib)
        warnings = []
        if not confs or not union.any():
            warnings.append("No trash detected in the image.")
        elif not features:
            warnings.append("The detected trash regions were too small or not on the ground, so they were ignored.")
        if stats.get("small_ignored"):
            warnings.append(f"Ignored {stats['small_ignored']} very small region(s) (under {stats['min_area_px']:.0f} pixels, treated as noise).")
        if dropped:
            warnings.append(f"Dropped {dropped} outline point(s) that do not reach the ground (near or above the horizon).")
        obs_id = secrets.token_hex(8)
        regions = {"type": "FeatureCollection", "features": features}
        total_m2 = _num(total_m2) or 0.0
        processed = datetime.now(timezone.utc)
        processing_ms = round((processed - received).total_seconds() * 1000.0, 1)
        obs = {
            "id": obs_id, "captured_at": processed.strftime("%Y-%m-%dT%H:%M:%SZ"), "processing_ms": processing_ms,
            "n_instances": len(confs), "n_regions": len(features), "total_area_m2": total_m2, "regions": regions,
        }
        with sess.lock:
            sess.observations.append(obs)
            del sess.observations[:-MAX_OBSERVATIONS]
        return {
            "ok": True, "observation_id": obs_id, "captured_at": obs["captured_at"], "processing_ms": processing_ms,
            "n_instances": len(confs), "n_regions": len(features), "small_regions_ignored": int(stats.get("small_ignored", 0)),
            "regions": regions, "total_area_m2": total_m2,
            "annotated_jpg_b64": imaging.encode_jpg_b64(annotated, max_side=imaging.OVERLAY_MAX_SIDE_PX),
            "inference_ms": round(inference_ms, 1), "image_size": [int(w), int(h)], "warnings": warnings,
            "dropped_points": int(dropped),
        }

    @app.get("/api/lab/board/observations")
    def board_observations(request: Request):
        _guard(request, srv, False)
        sess = _session(request)
        with sess.lock:
            return {"ok": True, "observations": list(sess.observations)}

    @app.delete("/api/lab/board/observations")
    def board_observations_clear(request: Request):
        _guard(request, srv, False)
        sess = _session(request)
        with sess.lock:
            sess.observations.clear()
        return {"ok": True}

    # ---------------- Drain lab ----------------
    @app.get("/api/lab/drain/samples")
    def drain_samples(request: Request):
        _guard(request, srv, False)
        _session(request)
        items = []
        for sid, s in SAMPLES.items():
            if s["kind"] == "drain":
                h, w = _sample_bgr(sid).shape[:2]
                items.append({"id": sid, "label": s["label"], "note": s["note"], "image_size": [int(w), int(h)]})
        return {"ok": True, "samples": items}

    @app.post("/api/lab/drain/measure")
    def drain_measure(request: Request, body: dict = Body(...)):
        _guard(request, srv, True)
        _session(request)
        sample_id = body.get("sample_id")
        _sample(sample_id, "drain")
        polygon = body.get("polygon")
        try:
            if not isinstance(polygon, list) or len(polygon) > ROI_MAX_POINTS:
                raise ValueError("polygon")
            polygon = analysis.validate_roi_polygon(polygon)
        except (ValueError, TypeError):
            raise LabError(422, "The drain zone must have 3 to 64 points with coordinates between 0 and 1.", "invalid_polygon") from None
        t0 = time.perf_counter()
        try:
            with _Slot():
                result = analysis.analyze(_sample_bytes(sample_id), roi=polygon)
        except ValueError:
            raise LabError(422, "The drawn zone is too small or degenerate. Draw a larger zone around the drain inlet.", "invalid_polygon") from None
        inference_ms = (time.perf_counter() - t0) * 1000.0
        h, w = _sample_bgr(sample_id).shape[:2]
        return {
            "ok": True,
            "drain_blockage_pct": result.get("drain_blockage_pct"),
            "waste_coverage_pct": result.get("waste_coverage_pct"),
            "certainty": result.get("certainty"),
            "no_trash_in_roi": bool(result.get("no_trash_in_roi", False)),
            "blockage_method": result.get("blockage_method"),
            "annotated_jpg": "data:image/jpeg;base64," + base64.b64encode(result["analyzed_bytes"]).decode(),
            "inference_ms": round(inference_ms, 1), "image_size": [int(w), int(h)],
        }
