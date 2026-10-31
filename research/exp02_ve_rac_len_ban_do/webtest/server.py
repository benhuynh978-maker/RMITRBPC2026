"""
Máy chủ FastAPI cho trang thử nghiệm webtest (exp02): hiệu chỉnh camera bằng bảng ArUco từ ảnh tải lên,
xem vùng camera thấy trên bản đồ, rồi chạy model YOLO trên ảnh mới và chiếu vùng rác lên bản đồ.

Chạy (mặc định CHỈ bind 127.0.0.1), từ thư mục exp02_ve_rac_len_ban_do/webtest:
  ..\\..\\..\\.venv\\Scripts\\python.exe -B -m uvicorn server:app --host 127.0.0.1 --port 8120

Dùng với điện thoại qua Tailscale: run_tailscale.ps1 (chỉ nghe địa chỉ Tailscale, không nghe 0.0.0.0).
Mọi /api/* (trừ /api/health) cần header X-Access-Code (mã 6 số, xem store.get_access_code; in ra console lúc khởi động).
Hợp đồng API: xem webtest/README.md (FE sở hữu). Mọi lỗi nghiệp vụ trả JSON {"ok": false, "error": "<English text>"}.
Biến môi trường: WEBTEST_CALIB_DIR, WEBTEST_DATA_DIR, WEBTEST_ACCESS_CODE (xem store.py), WEBTEST_MODEL_PATH (ghi đè
weights), WEBTEST_HOST / WEBTEST_PORT (chỉ dùng khi chạy `python server.py`).
Hình học chiếu dùng lại project_mask.py / calibrate_aruco.py của exp02 (không nhân bản logic).
"""
from __future__ import annotations

import math
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

os.environ.setdefault("YOLO_VERBOSE", "False")

HERE = Path(__file__).resolve().parent
EXP_DIR = HERE.parent
for _p in (str(EXP_DIR), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from fastapi import Body, FastAPI, File, Form, Query, Request, UploadFile  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

import calibrate_aruco  # noqa: E402
import calib_quality  # noqa: E402
import config  # noqa: E402
import project_mask as pm  # noqa: E402
import imaging  # noqa: E402
import board_coords  # noqa: E402
import store  # noqa: E402

WEB_DIR = HERE / "web"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# --- Tham số model (giống model_demo/run_demo_model.py và inference/analysis.py) ---
DEFAULT_MODEL_PATH = (
    config.PROJECT_ROOT / "runs" / "segment" / "runs" / "train" / "baseline_v1_rev2" / "weights" / "best.pt"
)
PREDICT_IMGSZ = 1024
DETECT_CONF = 0.25           # đổi bằng biến môi trường WEBTEST_CONF (thấp hơn = thấy nhiều rác nhỏ hơn nhưng dễ khoanh nhầm hơn)


def _detect_conf() -> float:
    try:
        v = float(os.environ.get("WEBTEST_CONF", ""))
        return v if 0.01 <= v <= 0.95 else DETECT_CONF
    except ValueError:
        return DETECT_CONF
MASK_THRESHOLD = 0.5
TRASH_CLASS_ID = 0
# Chỉ bỏ vùng RẤT nhỏ (nhiễu vài điểm ảnh): diện tích viền ngoài < MIN_AREA_FRAC diện tích ảnh (tối thiểu MIN_AREA_PX_FLOOR px).
# Trước đây 0.0005 (0.05% ảnh, ~1180 px ở ảnh 2048x1153) làm mất rác nhỏ cỡ 3-4 cm ở 2 m. Đổi bằng biến môi trường
# WEBTEST_MIN_AREA_FRAC (ví dụ 0.0005 để về như cũ, 0 để giữ mọi vùng từ MIN_AREA_PX_FLOOR trở lên).
def _min_area_frac() -> float:
    try:
        v = float(os.environ.get("WEBTEST_MIN_AREA_FRAC", ""))
        return v if v >= 0 else 0.00003
    except ValueError:
        return 0.00003


MIN_AREA_PX_FLOOR = 20.0
EPS_FRAC_PERIMETER = 0.002   # approxPolyDP: eps = max(1 px, 0.002 * chu vi)
EPS_MIN_PX = 1.0
ASPECT_TOLERANCE = 0.01

DEFAULT_MARKER_SIZE_MM = config.PRINT_MARKER_SIZE_MM  # 250


# ---------------------------------------------------------------------------------------
# Lỗi + JSON
# ---------------------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


def error_response(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "error": message, **extra})


def _num(x):
    """Số Python thuần, NaN/inf -> None (JSON chuẩn không có NaN)."""
    f = float(x)
    return f if math.isfinite(f) else None


# ---------------------------------------------------------------------------------------
# Model (nạp lười + warm-up nền khi khởi động; một suy luận một lúc)
# ---------------------------------------------------------------------------------------
_MODEL = None
_MODEL_LOCK = threading.Lock()


def model_path() -> Path:
    return Path(os.environ.get("WEBTEST_MODEL_PATH") or DEFAULT_MODEL_PATH)


def _get_model():
    """Gọi khi đang giữ _MODEL_LOCK."""
    global _MODEL
    if _MODEL is None:
        mp = model_path()
        if not mp.is_file():
            raise ApiError(503, f"Model weights file not found: {mp.name}")
        from ultralytics import YOLO
        _MODEL = YOLO(str(mp))
    return _MODEL


def infer_trash_mask(image_bgr: np.ndarray):
    """
    Chạy YOLO-seg trên ảnh BGR, chỉ lấy lớp 0 (Trash), mask > 0.5.
    Trả (mask_bool_union (H,W), n_instances, list độ tin cậy từng instance, ảnh_chú_thích_BGR).
    Test có thể thay hàm này bằng bản giả.
    """
    h, w = image_bgr.shape[:2]
    with _MODEL_LOCK:
        model = _get_model()
        r = model.predict(
            source=image_bgr, imgsz=PREDICT_IMGSZ, conf=_detect_conf(), retina_masks=True, verbose=False
        )[0]
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
        annotated = r.plot()
    return union, len(confs), confs, annotated


def _warm_up() -> None:
    try:
        infer_trash_mask(np.zeros((480, 640, 3), dtype=np.uint8))
        print("[webtest] model ready", flush=True)
    except Exception as exc:  # noqa: BLE001 - không để lỗi nạp model làm sập máy chủ
        print(f"[webtest] could not load the model: {exc}", file=sys.stderr, flush=True)


@asynccontextmanager
async def lifespan(_app):
    print(f"[webtest] Access code: {store.get_access_code()}", flush=True)
    threading.Thread(target=_warm_up, name="webtest-warmup", daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)  # không lộ schema API ra mạng


@app.exception_handler(ApiError)
async def _api_error_handler(_request: Request, exc: ApiError):
    return error_response(exc.status, exc.message, **exc.extra)


@app.exception_handler(RequestValidationError)
async def _validation_handler(_request: Request, exc: RequestValidationError):
    errors = exc.errors()
    types = {str(e.get("type", "")) for e in errors}
    fields = []
    for e in errors:
        loc = [str(x) for x in e.get("loc", ()) if x not in ("body", "query", "form") and not isinstance(x, int)]
        fields.append(".".join(loc) or "data")
    extra = {"side_px_min": None, "overlay_jpg_b64": None} if _request.url.path == "/api/calibrate" else {}
    if "photo" in fields:
        return error_response(422, "Missing photo (field 'photo' in the multipart form).", **extra)
    if "json_invalid" in types:
        return error_response(422, "The JSON body is malformed.", **extra)
    if types & {"model_attributes_type", "dict_type"}:
        return error_response(422, "The request body must be a JSON object.", **extra)
    return error_response(422, "Invalid request data: " + ", ".join(sorted(set(fields))) + ".", **extra)


@app.exception_handler(StarletteHTTPException)
async def _http_handler(_request: Request, exc: StarletteHTTPException):
    # Thông điệp mặc định của framework là tiếng Anh: luôn đổi sang câu tiếng Anh theo mã trạng thái.
    known = {
        400: "Malformed request data (corrupt form or JSON body).",
        401: "Not authorised.",
        403: "Access denied.",
        404: "Not found.",
        405: "Method not allowed.",
        408: "Request timed out.",
        413: "Upload too large (max 25 MB).",
        415: "Unsupported data format.",
        422: "Invalid request data.",
    }
    return error_response(exc.status_code, known.get(exc.status_code, "Invalid request."))


ACCESS_EXEMPT_PATHS = ("/api/health",)
ACCESS_DENIED_MESSAGE = "Missing or wrong access code."


FAIL_LIMIT = 10          # sai mã quá 10 lần trong 60 giây từ cùng một địa chỉ thì bị chặn 60 giây (chống dò 6 số)
FAIL_WINDOW_S = 60.0
_fails: dict = {}
_fails_lock = threading.Lock()


def _recent_fails(ip: str, now: float) -> list:
    """Danh sách thời điểm sai mã còn trong cửa sổ (gọi khi đang giữ _fails_lock)."""
    recent = [t for t in _fails.get(ip, []) if now - t < FAIL_WINDOW_S]
    if recent:
        _fails[ip] = recent
    else:
        _fails.pop(ip, None)
    return recent


def _access_ok(request: Request) -> bool:
    given = request.headers.get("x-access-code") or ""
    return secrets.compare_digest(given.encode("utf-8"), store.get_access_code().encode("utf-8"))


@app.middleware("http")
async def _guard(request: Request, call_next):
    # Kiểm mã TRƯỚC mọi thứ khác (chưa đọc body): chỉ /api/* cần mã; trang tĩnh và /api/health thì không.
    path = request.url.path
    if (path == "/api" or path.startswith("/api/")) and path not in ACCESS_EXEMPT_PATHS:
        ip = request.client.host if request.client else "?"
        now = time.monotonic()
        with _fails_lock:
            blocked = len(_recent_fails(ip, now)) >= FAIL_LIMIT
        if blocked:
            return error_response(429, "Too many wrong codes. Try again in 1 minute.")
        if not _access_ok(request):
            with _fails_lock:
                _fails.setdefault(ip, []).append(now)
            return error_response(401, ACCESS_DENIED_MESSAGE)
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_UPLOAD_BYTES + 1024 * 1024:
        return error_response(413, "Upload too large (max 25 MB).")
    try:
        return await call_next(request)
    except Exception:  # noqa: BLE001 - lỗi không lường trước: log phía máy chủ, trả JSON gọn
        traceback.print_exc()
        return error_response(500, "Unexpected server error. Please try again.")


# ---------------------------------------------------------------------------------------
# Tiện ích dùng chung
# ---------------------------------------------------------------------------------------
def _read_upload(photo: UploadFile) -> bytes:
    raw = photo.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "The photo exceeds 25 MB.")
    if not raw:
        raise ApiError(400, "The photo file is empty.")
    return raw


def _decode(raw: bytes):
    try:
        return imaging.decode_upload(raw)
    except imaging.ImageError as exc:
        raise ApiError(400, str(exc)) from None


def _parse_float(value: Optional[str], name: str, default: Optional[float]) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return default
    try:
        f = float(str(value).strip().replace(",", "."))
    except ValueError:
        raise ApiError(422, f"Value '{name}' is not a number.") from None
    if not math.isfinite(f):
        raise ApiError(422, f"Value '{name}' is invalid.")
    return f


def _en_quality_warning(w) -> str:
    """calib_quality.py (outside webtest) emits Vietnamese warnings; map each rule to its English text for the UI."""
    s = str(w)
    if s.startswith("Bảng quá nhỏ"):
        return f"Board too small in the photo (<{calib_quality.MIN_SIDE_PX:.0f} px): the pose may be wrong."
    if s.startswith("Hai nghiệm pose"):
        return ("The two pose solutions are almost equally good (the pose may be flipped): retake the photo from a "
                "more oblique angle, closer, or with a larger board, and check the computed camera position.")
    if s.startswith("Độ cao camera"):
        return "The estimated camera height differs from the entered value: check the measurement, board size and photo quality."
    if s.startswith("Ảnh bị mờ"):
        return "The board area is blurry (out of focus or camera shake): retake a sharp photo, since blur causes the worst pose errors."
    if s.startswith("Ảnh JPEG chất lượng thấp"):
        m = re.search(r"~(\d+) < (\d+)", s)
        est = f" (estimated ~{m.group(1)} < {m.group(2)})" if m else ""
        return f"Low JPEG quality{est}: take the calibration photo at the highest JPEG quality (or PNG)."
    return "Photo quality warning."


def _check_latlon(lat, lon) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise ApiError(422, "Latitude must be between -90 and 90.")
    if not (-180.0 <= lon <= 180.0):
        raise ApiError(422, "Longitude must be between -180 and 180.")


def _saved_calibration() -> Optional[dict]:
    """Hiệu chỉnh đã lưu nếu file đọc/parse được và đủ khoá cần dùng; ngược lại None (coi như chưa hiệu chỉnh)."""
    try:
        c = store.load_calibration()
    except (OSError, ValueError):
        return None
    need = ("marker_latlon", "R", "t", "camera_matrix", "image_size")
    if not isinstance(c, dict) or any(k not in c for k in need):
        return None
    return c


def _pending_or_404(calibration_id: str) -> dict:
    pend = store.load_pending(calibration_id)
    if pend is None:
        raise ApiError(404, "Calibration result not found (expired or unknown). Please detect the board again.")
    return pend


# ---------------------------------------------------------------------------------------
# 1) POST /api/calibrate
# ---------------------------------------------------------------------------------------
@app.post("/api/calibrate")
def api_calibrate(
    photo: Optional[UploadFile] = File(None),
    inbox_id: Optional[str] = Form(None),
    marker_size_mm: Optional[str] = Form(None),
    fov_deg: Optional[str] = Form(None),
):
    try:
        return _calibrate(photo, inbox_id, marker_size_mm, fov_deg)
    except ApiError as exc:
        # Mọi lỗi của calibrate đều mang side_px_min/overlay_jpg_b64 (null nếu chưa dò được); ảnh hỏng -> 422
        exc.extra.setdefault("side_px_min", None)
        exc.extra.setdefault("overlay_jpg_b64", None)
        if exc.status == 400:
            exc.status = 422
        raise


def _calibrate(photo: Optional[UploadFile], inbox_id: Optional[str], marker_size_mm: Optional[str],
               fov_deg: Optional[str]):
    inbox_id = (inbox_id or "").strip() or None  # ô form để trống coi như không gửi
    if (photo is None) == (inbox_id is None):
        raise ApiError(422, "Provide exactly one photo: upload a file or pick a phone photo.")
    size_mm = _parse_float(marker_size_mm, "marker_size_mm", DEFAULT_MARKER_SIZE_MM)
    if not (10.0 <= size_mm <= 5000.0):
        raise ApiError(422, "Board side length must be between 10 and 5000 mm.")
    fov_in = _parse_float(fov_deg, "fov_deg", None)
    if fov_in is not None and not (1.0 <= fov_in <= 179.0):
        raise ApiError(422, "Lens field of view (fov_deg) must be between 1 and 179 degrees.")

    if photo is not None:
        raw = _read_upload(photo)
    else:
        raw = store.load_inbox_bytes(inbox_id)
        if raw is None:
            raise ApiError(404, "Phone photo not found (expired or deleted). Please send it again.")
    bgr, f35 = _decode(raw)
    h, w = bgr.shape[:2]

    warnings: List[str] = []
    if fov_in is not None:
        fov, fov_source = fov_in, "input"
    elif f35 is not None:
        fov, fov_source = imaging.diagonal_fov_from_35mm(f35), "exif"
    else:
        fov, fov_source = config.DIAGONAL_FOV_DEG, "default"
        warnings.append(
            f"Could not read the focal length from the photo: using the default field of view of "
            f"{config.DIAGONAL_FOV_DEG:.0f}° (ESP32 camera). Phones are usually about 70–85°; if yours differs, "
            f"region positions and sizes will be off. Enter the field of view (degrees, diagonal) if you know it."
        )

    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise ApiError(500, "Could not process the photo.")
    with tempfile.TemporaryDirectory(prefix="webtest_calib_") as td:
        img_path = Path(td) / "calib.png"
        img_path.write_bytes(buf.tobytes())
        try:
            result = calibrate_aruco.detect_and_solve_pnp(
                img_path, config.MARKER_ID, size_mm, diagonal_fov_deg=fov
            )
        except RuntimeError as exc:
            msg = str(exc)
            # The matched fragments are the (Vietnamese) RuntimeError texts raised by calibrate_aruco.py (outside webtest).
            if "Không tìm thấy marker" in msg:
                text = ("No ArUco board found in the photo. Capture the whole board clearly, unobstructed, "
                        "without glare and in good light.")
            elif "không có id" in msg:
                text = "The photo has an ArUco code but it is not the calibration board (ID 0 of DICT_4X4_50 is required)."
            else:
                text = "Could not solve the camera position from the board. Please retake a sharper photo."
            raise ApiError(422, text, side_px_min=None, overlay_jpg_b64=None) from None

    q = result["quality"]
    side_min = float(q["marker_side_px_min"])
    overlay = imaging.draw_overlay(bgr, result["R"], result["t"], result["camera_matrix"], size_mm / 1000.0)
    overlay_b64 = imaging.encode_jpg_b64(overlay)

    if calib_quality.is_too_small(side_min):
        raise ApiError(
            422,
            f"Board too small in the photo (shortest side {math.floor(side_min * 10) / 10:.1f} px, minimum "
            f"{calib_quality.MIN_SIDE_PX:.1f} px). Move closer or use a larger board.",
            side_px_min=_num(side_min),
            overlay_jpg_b64=overlay_b64,
        )

    calibration_id = secrets.token_hex(8)
    store.save_pending(calibration_id, {
        "id": calibration_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "marker_size_mm": size_mm,
        "fov_source": fov_source,
        "result": {
            "R": result["R"].tolist(),
            "t": result["t"].tolist(),
            "camera_matrix": result["camera_matrix"].tolist(),
            "image_size": [int(w), int(h)],
            "reproj_error_rms_px": float(result["reproj_error_rms_px"]),
            "quality": q,
            "diagonal_fov_deg": float(fov),
        },
        "image_jpg_b64": imaging.encode_jpg_b64(bgr, quality=90),
    })
    return {
        "ok": True,
        "calibration_id": calibration_id,
        "side_px_min": _num(side_min),
        "side_px_mean": _num(q["marker_side_px_mean"]),
        "fov_deg": float(fov),
        "fov_source": fov_source,
        "focal_35mm": None if f35 is None else float(f35),
        "warnings": warnings + [_en_quality_warning(x) for x in q["warnings"]],
        "camera_height_m_est": _num(q["camera_height_m_est"]),
        "image_size": [int(w), int(h)],
        "overlay_jpg_b64": overlay_b64,
    }


# ---------------------------------------------------------------------------------------
# 2) GET /api/footprint
# ---------------------------------------------------------------------------------------
@app.get("/api/footprint")
def api_footprint(
    calibration_id: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    azimuth_deg: Optional[float] = Query(None),
    max_range_m: float = Query(12.0),
):
    if calibration_id:  # kết quả hiệu chỉnh chưa lưu: bắt buộc có lat/lon
        pend = _pending_or_404(calibration_id)
        if lat is None or lon is None:
            raise ApiError(422, "Missing latitude/longitude (lat, lon).")
        src = {"R": pend["result"]["R"], "t": pend["result"]["t"],
               "camera_matrix": pend["result"]["camera_matrix"], "image_size": pend["result"]["image_size"]}
        lat0, lon0, az0 = lat, lon, (0.0 if azimuth_deg is None else azimuth_deg)
    else:  # hiệu chỉnh ĐÃ LƯU (để tải lại trang vẫn vẽ lại được); lat/lon/azimuth lấy từ query, thiếu thì từ file
        saved = _saved_calibration()
        if saved is None:
            raise ApiError(404, "No saved calibration.")
        src = saved
        lat0 = saved["marker_latlon"][0] if lat is None else lat
        lon0 = saved["marker_latlon"][1] if lon is None else lon
        az0 = saved.get("azimuth_deg", 0.0) if azimuth_deg is None else azimuth_deg
    lat, lon = lat0, lon0
    _check_latlon(lat, lon)
    if not math.isfinite(az0):
        raise ApiError(422, "Invalid azimuth.")
    rng = 12.0 if not math.isfinite(max_range_m) else min(50.0, max(1.0, max_range_m))
    az = az0 % 360.0
    calib = {"camera_id": store.CAMERA_ID, "marker_latlon": [lat, lon], "azimuth_deg": az,
             "R": src["R"], "t": src["t"], "camera_matrix": src["camera_matrix"], "image_size": src["image_size"]}
    w, h = calib["image_size"]

    poly_marker = pm.ground_footprint_polygon(calib, (w, h), rng)
    if len(poly_marker) < 3:
        raise ApiError(422, "The camera does not see the ground within this range.")
    e, n = pm.marker_xy_to_enu(poly_marker[:, 0], poly_marker[:, 1], az)
    ring = pm._ring_m_to_lonlat(pm._oriented(np.stack([e, n], axis=1), True), lat, lon)

    cam = pm.camera_position_geojson(calib)
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"kind": "footprint"},
             "geometry": {"type": "Polygon", "coordinates": [ring]}},
            {"type": "Feature", "properties": {"kind": "marker"},
             "geometry": {"type": "Point", "coordinates": [lon, lat]}},
            {"type": "Feature",
             "properties": {"kind": "camera", "height_m": float(cam["properties"]["height_m"])},
             "geometry": cam["geometry"]},
        ],
    }


# ---------------------------------------------------------------------------------------
# 3) POST /api/calibration/save   4) GET /api/calibration
# ---------------------------------------------------------------------------------------
def _json_number(body: dict, key: str) -> float:
    v = body.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise ApiError(422, f"Missing or invalid value '{key}' (must be a number).")
    return float(v)


@app.post("/api/calibration/save")
def api_calibration_save(body: dict = Body(...)):
    cid = body.get("calibration_id")
    if not isinstance(cid, str):
        raise ApiError(422, "Missing 'calibration_id'.")
    lat, lon, az = _json_number(body, "lat"), _json_number(body, "lon"), _json_number(body, "azimuth_deg")
    _check_latlon(lat, lon)
    az = az % 360.0
    pend = _pending_or_404(cid)

    res = pend["result"]
    result = {
        "R": np.array(res["R"], dtype=np.float64),
        "t": np.array(res["t"], dtype=np.float64),
        "camera_matrix": np.array(res["camera_matrix"], dtype=np.float64),
        "image_size": res["image_size"],
        "reproj_error_rms_px": res["reproj_error_rms_px"],
        "quality": res["quality"],
        "diagonal_fov_deg": res["diagonal_fov_deg"],
    }
    out = store.calibration_path()
    tmp = out.with_name(f"{out.name}.{secrets.token_hex(4)}.tmp")
    try:
        data = calibrate_aruco.save_calibration(store.CAMERA_ID, (lat, lon), result, "webtest", tmp)
        data["azimuth_deg"] = az
        store.write_json_atomic(tmp, data)
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return {"ok": True, "camera_id": store.CAMERA_ID}


@app.get("/api/calibration")
def api_calibration_get():
    c = _saved_calibration()
    if c is None:
        return {"ok": False, "error": "Not calibrated"}
    q = c.get("quality") or {}
    return {
        "ok": True,
        "calibration": {
            "camera_id": c.get("camera_id", store.CAMERA_ID),
            "marker_latlon": c["marker_latlon"],
            "azimuth_deg": c.get("azimuth_deg", 0.0),
            "fov_deg": c.get("diagonal_fov_deg", config.DIAGONAL_FOV_DEG),
            "image_size": c["image_size"],
            "side_px_min": q.get("marker_side_px_min"),
            "created_at": c.get("created_at"),
        },
    }


# ---------------------------------------------------------------------------------------
# 5) POST /api/observe   6) GET/DELETE /api/observations
# ---------------------------------------------------------------------------------------
def _simplify_ring(ring_px: np.ndarray, eps: float) -> np.ndarray:
    ap = cv2.approxPolyDP(ring_px.astype(np.float32).reshape(-1, 1, 2), float(eps), True)
    ap = ap.reshape(-1, 2).astype(np.float64)
    return ap if len(ap) >= 3 else ring_px


def mask_to_region_features(mask: np.ndarray, calib: dict, confidence: Optional[float], stats: Optional[dict] = None):
    """
    Mask (H,W) -> (list Feature Polygon, tổng m², số đỉnh bị bỏ). Mỗi vùng 4-liên thông là 1 Polygon (có lỗ).
    Diện tích m² tính từ viền biên-pixel CHÍNH XÁC (không rút gọn); hình vẽ dùng viền rút gọn approxPolyDP.
    """
    h, w = mask.shape
    m = np.asarray(mask) > 0
    polys = pm.mask_to_pixel_boundary_polygons(m)
    if not polys:
        return [], 0.0, 0
    lat0, lon0 = calib["marker_latlon"]
    setup = pm._projection_setup(calib, (w, h), False)
    min_area = max(MIN_AREA_PX_FLOOR, _min_area_frac() * h * w)
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
            "properties": {"area_m2": _num(area_m2), "area_px": int(p["area_px"]),
                           "confidence": confidence, "kind": "trash"},
            "geometry": {"type": "Polygon", "coordinates": rings},
        })
        total += area_m2
    return features, float(total), int(dropped)


def _iso_ms(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


@app.post("/api/observe")
def api_observe(photo: UploadFile = File(...)):
    # FastAPI đã nhận xong toàn bộ ảnh trước khi vào hàm này -> đây là lúc máy chủ nhận xong ảnh
    received = datetime.now(timezone.utc)
    calib = _saved_calibration()
    if calib is None:
        raise ApiError(409, "Camera not calibrated")

    bgr, _f35 = _decode(_read_upload(photo))
    h, w = bgr.shape[:2]
    cw, ch = calib["image_size"]
    if abs((w / h) / (cw / ch) - 1.0) > ASPECT_TOLERANCE:
        raise ApiError(
            422,
            f"The photo must have the same aspect ratio / fixed position as the calibration photo "
            f"(this photo {w}x{h}, calibration photo {cw}x{ch}).",
        )

    t0 = time.perf_counter()
    mask, n_instances, confs, annotated = infer_trash_mask(bgr)
    inference_ms = (time.perf_counter() - t0) * 1000.0
    mask = np.asarray(mask)
    if mask.shape != (h, w):
        raise RuntimeError(f"mask {mask.shape} không khớp ảnh {(h, w)}")

    mean_conf = round(float(np.mean(confs)), 4) if confs else None
    reg_stats: dict = {}
    features, total_m2, dropped = mask_to_region_features(mask, calib, mean_conf, reg_stats)
    # Đánh số vùng + ghi Y/X (so với tâm bảng) cho từng vùng. KHÔNG loại vùng nào: tờ bảng (model hay khoanh nhầm
    # thành rác, Y/X gần 0) vẫn có trong danh sách; người thử tự trừ diện tích nền của tờ bảng.
    features = board_coords.annotate_regions(features, calib)

    warnings: List[str] = []
    if n_instances == 0 or not mask.any():
        warnings.append("No trash detected in the image.")
    elif not features:
        warnings.append("The detected trash regions were too small or not on the ground, so they were ignored.")
    if reg_stats.get("small_ignored"):
        warnings.append(f"Ignored {reg_stats['small_ignored']} very small region(s) (under {reg_stats['min_area_px']:.0f} pixels, treated as noise).")
    if dropped:
        warnings.append(f"Dropped {dropped} outline point(s) that do not reach the ground (near or above the horizon).")

    obs_id = secrets.token_hex(8)
    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    regions = {"type": "FeatureCollection", "features": features}
    total_m2 = _num(total_m2) or 0.0
    processed = datetime.now(timezone.utc)
    timing = {
        "received_at": _iso_ms(received),
        "processed_at": _iso_ms(processed),
        "processing_ms": round((processed - received).total_seconds() * 1000.0, 1),
    }
    store.add_observation({
        "id": obs_id,
        "captured_at": captured_at,
        **timing,
        "calibration_created_at": calib.get("created_at"),
        "n_instances": int(n_instances),
        "n_regions": len(features),
        "total_area_m2": total_m2,
        "regions": regions,
    })
    return {
        "ok": True,
        "observation_id": obs_id,
        "captured_at": captured_at,
        **timing,
        "n_instances": int(n_instances),
        "n_regions": len(features),
        "small_regions_ignored": int(reg_stats.get("small_ignored", 0)),
        "regions": regions,
        "total_area_m2": total_m2,
        "annotated_jpg_b64": imaging.encode_jpg_b64(
            annotated if annotated is not None else bgr, max_side=imaging.OVERLAY_MAX_SIDE_PX
        ),
        "inference_ms": round(inference_ms, 1),
        "image_size": [int(w), int(h)],
        "warnings": warnings,
        "dropped_points": int(dropped),
    }


@app.get("/api/observations")
def api_observations_list():
    return {"ok": True, "observations": store.list_observations()}


@app.delete("/api/observations")
def api_observations_clear():
    store.clear_observations()
    return {"ok": True}


# ---------------------------------------------------------------------------------------
# 7) POST/GET /api/inbox   8) GET /api/status
# ---------------------------------------------------------------------------------------
INBOX_THUMB_MAX_SIDE_PX = 240


@app.post("/api/inbox")
def api_inbox_post(photo: UploadFile = File(...)):
    raw = _read_upload(photo)
    bgr, f35 = _decode(raw)  # chỉ để kiểm ảnh hợp lệ + lấy kích thước/EXIF; LƯU bytes gốc nguyên vẹn
    h, w = bgr.shape[:2]
    inbox_id = secrets.token_hex(8)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = store.save_inbox(inbox_id, raw, {
        "created_at": created_at,
        "image_size": [int(w), int(h)],
        "has_focal": f35 is not None,
        "thumb_jpg_b64": imaging.encode_jpg_b64(bgr, max_side=INBOX_THUMB_MAX_SIDE_PX, quality=80),
    })
    return {
        "ok": True,
        "inbox_id": inbox_id,
        "created_at": created_at,
        "size_bytes": meta["size_bytes"],
        "image_size": [int(w), int(h)],
        "has_focal": f35 is not None,
    }


@app.get("/api/inbox")
def api_inbox_list():
    return {"ok": True, "items": [
        {k: m.get(k) for k in ("id", "created_at", "size_bytes", "image_size", "has_focal", "thumb_jpg_b64")}
        for m in store.list_inbox()
    ]}


@app.get("/api/status")
def api_status():
    obs = store.list_observations()
    inbox = store.list_inbox()
    return {
        "ok": True,
        "calibrated": _saved_calibration() is not None,
        "observation_count": len(obs),
        "latest_observation_id": obs[-1].get("id") if obs else None,
        "inbox_count": len(inbox),
        "latest_inbox_id": inbox[0]["id"] if inbox else None,
    }


# ---------------------------------------------------------------------------------------
# 9) GET /api/health
# ---------------------------------------------------------------------------------------
@app.get("/api/health")
def api_health():
    return {"ok": True, "model_loaded": _MODEL is not None, "calibrated": _saved_calibration() is not None}


# ---------------------------------------------------------------------------------------
# Trang tĩnh: GET / và /web/* (webtest/web/ do FE tạo; chưa có thì 404 JSON rõ ràng)
# ---------------------------------------------------------------------------------------
def _static(rel: str):
    base = WEB_DIR.resolve()
    try:
        target = (base / rel).resolve()
        if target.is_dir():
            target = target / "index.html"
        ok = target.is_relative_to(base) and target.is_file()
    except (ValueError, OSError):  # đường dẫn có ký tự không hợp lệ (vd byte NUL)
        ok = False
    if not ok:
        if rel in ("", "index.html"):
            return error_response(404, "Web page not found (webtest/web/index.html).")
        if rel == "phone.html":
            return error_response(404, "Phone page not found (webtest/web/phone.html).")
        return error_response(404, "File not found.")
    return FileResponse(target, headers={"Cache-Control": "no-cache"})


@app.get("/")
def index_page():
    return _static("index.html")


@app.get("/phone")
def phone_page():
    return _static("phone.html")


@app.get("/web/{path:path}")
def web_files(path: str):
    return _static(path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("WEBTEST_HOST") or "127.0.0.1", port=int(os.environ.get("WEBTEST_PORT") or 8120))
