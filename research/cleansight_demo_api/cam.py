"""
CleanSight "Camera lab": camera IMOU nhà gửi ảnh về dịch vụ, ảnh được LƯU, hiển thị, và vẽ rác lên bản đồ.

Khác hẳn lab.py (ảnh mẫu, chỉ trong RAM, không ghi đĩa): module này GHI ẢNH RA ĐĨA, vào một thư mục RIÊNG NẰM NGOÀI repo
(mặc định ~/CleanSightCamData) để không bao giờ lọt vào Git/Netlify. Đây là camera nhà dùng để thử, không phải dữ liệu công cộng.

Luồng:
  camera --(RTSP, cầu nối chạy trên laptop; sau này có thể là camera tự đẩy)--> POST /api/cam/ingest (khoá riêng CLEANSIGHT_CAM_INGEST_KEY)
      -> lưu ảnh gốc -> chạy model (cùng hàng đợi/khoá model với /api/analyze) -> lưu ảnh khoanh + kết quả (JSON)
  Trình duyệt: đăng nhập bằng MÃ TRUY CẬP (CLEANSIGHT_CAM_ACCESS_CODE) -> token ngắn hạn trong RAM -> xem ảnh mới nhất, lịch sử, bản đồ.

Bật/tắt: chỉ đăng ký route khi CẢ HAI biến CLEANSIGHT_CAM_ACCESS_CODE và CLEANSIGHT_CAM_INGEST_KEY được đặt (cấu hình thiếu một nửa -> không khởi động).
Mã truy cập và khoá KHÔNG nằm trong repo (đặt bằng biến môi trường; xem cam.env.example).
Theo yêu cầu của chủ dự án: KHÔNG giới hạn số lần thử mã, KHÔNG giới hạn dung lượng/thời gian lưu (camera nhà).

Hiệu chỉnh: ban đầu dùng hiệu chỉnh TẠM (dò từ ảnh bảng mẫu, KHÔNG phải của camera này, đánh dấu provisional=true) để vẽ thử;
có thể hiệu chỉnh thật từ một khung hình của camera (cần tờ bảng ArUco trong khung).
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import Body, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

import lab
from lab import LabError

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

TOKEN_TTL_S = 8 * 3600
MAX_TOKENS = 50
MAX_INGEST_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000
MIN_SIDE_PX = 64
LIST_DEFAULT = 24
LIST_MAX = 200
MAX_PENDING = 6
CAMERA_ID = "CAM"
FRAME_ID_RE = re.compile(r"^\d{8}T\d{12}Z$")
KEY_MIN_LEN = 16
CODE_MIN_LEN = 4
PROVISIONAL_SAMPLE = "board-near"
ASPECT_TOLERANCE = lab.ASPECT_TOLERANCE


# ---------------------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------------------
class Settings:
    def __init__(self, code: str, key: str, data_dir: Path):
        self.code_hash = hashlib.sha256(code.encode("utf-8")).digest()
        self.key_hash = hashlib.sha256(key.encode("utf-8")).digest()
        self.data_dir = data_dir


def load_settings(env=None) -> Optional[Settings]:
    """None = tính năng tắt (cả hai biến trống). Cấu hình thiếu một nửa, khoá quá ngắn hoặc thư mục dữ liệu nằm trong repo -> RuntimeError."""
    env = os.environ if env is None else env
    code = (env.get("CLEANSIGHT_CAM_ACCESS_CODE") or "").strip()
    key = (env.get("CLEANSIGHT_CAM_INGEST_KEY") or "").strip()
    if not code and not key:
        return None
    if not code or not key:
        raise RuntimeError("Camera lab: phải đặt CẢ CLEANSIGHT_CAM_ACCESS_CODE và CLEANSIGHT_CAM_INGEST_KEY (hoặc không đặt cái nào).")
    if len(code) < CODE_MIN_LEN:
        raise RuntimeError(f"Camera lab: CLEANSIGHT_CAM_ACCESS_CODE quá ngắn (tối thiểu {CODE_MIN_LEN} ký tự).")
    if len(key) < KEY_MIN_LEN:
        raise RuntimeError(f"Camera lab: CLEANSIGHT_CAM_INGEST_KEY quá ngắn (tối thiểu {KEY_MIN_LEN} ký tự, nên là chuỗi ngẫu nhiên).")
    raw_dir = (env.get("CLEANSIGHT_CAM_DATA_DIR") or "").strip()
    data_dir = Path(raw_dir).expanduser() if raw_dir else Path.home() / "CleanSightCamData"
    data_dir = data_dir.resolve()
    try:
        data_dir.relative_to(REPO_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise RuntimeError(f"Camera lab: thư mục dữ liệu ({data_dir}) nằm TRONG repo; đặt nó ngoài repo để ảnh không lọt vào Git.")
    return Settings(code, key, data_dir)


def _same(secret_hash: bytes, given) -> bool:
    if not isinstance(given, str) or len(given) > 512:
        return False
    return hmac.compare_digest(hashlib.sha256(given.encode("utf-8")).digest(), secret_hash)


# ---------------------------------------------------------------------------------------
# Lưu trữ trên đĩa
# ---------------------------------------------------------------------------------------
def _atomic_write(path: Path, data: bytes) -> None:
    """Ghi qua tên tạm rồi đổi tên: người đọc không bao giờ thấy file dở dang."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.frames = root / "frames"
        self.lock = threading.Lock()
        self.frames.mkdir(parents=True, exist_ok=True)

    def new_id(self) -> str:
        with self.lock:
            now = datetime.now(timezone.utc)
            while True:
                fid = f"{now:%Y%m%dT%H%M%S}{now.microsecond:06d}Z"
                if not self.path(fid, ".json").exists() and not self.path(fid, ".jpg").exists():
                    return fid
                now += timedelta(microseconds=1)

    def day_dir(self, fid: str) -> Path:
        return self.frames / fid[:8]

    def path(self, fid: str, suffix: str) -> Path:
        return self.day_dir(fid) / f"{fid}{suffix}"

    def write(self, fid: str, suffix: str, data: bytes) -> None:
        self.day_dir(fid).mkdir(parents=True, exist_ok=True)
        _atomic_write(self.path(fid, suffix), data)

    def write_meta(self, fid: str, meta: dict) -> None:
        # JSON ghi CUỐI CÙNG: khung chỉ xuất hiện trong danh sách khi đã đủ file.
        self.write(fid, ".json", json.dumps(meta, ensure_ascii=False).encode("utf-8"))

    def read_meta(self, fid: str) -> Optional[dict]:
        try:
            return json.loads(self.path(fid, ".json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def list_ids(self, limit: int, before: Optional[str] = None) -> list:
        """Id mới nhất trước. Duyệt thư mục ngày từ mới đến cũ nên không phải quét toàn bộ lịch sử."""
        out: list = []
        try:
            days = sorted((d.name for d in self.frames.iterdir() if d.is_dir() and re.fullmatch(r"\d{8}", d.name)), reverse=True)
        except OSError:
            return out
        for day in days:
            if before is not None and day > before[:8]:
                continue
            try:
                ids = sorted((p.stem for p in (self.frames / day).glob("*.json") if FRAME_ID_RE.match(p.stem)), reverse=True)
            except OSError:
                continue
            for fid in ids:
                if before is not None and fid >= before:
                    continue
                out.append(fid)
                if len(out) >= limit:
                    return out
        return out

    # hiệu chỉnh đã lưu
    @property
    def calib_path(self) -> Path:
        return self.root / "calibration.json"

    def read_calibration(self) -> Optional[dict]:
        try:
            return json.loads(self.calib_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def write_calibration(self, calib: dict) -> None:
        _atomic_write(self.calib_path, json.dumps(calib).encode("utf-8"))


# ---------------------------------------------------------------------------------------
# Đăng ký route
# ---------------------------------------------------------------------------------------
def register(app, srv, settings: Optional[Settings] = None) -> bool:
    """Đăng ký /api/cam/*. Trả False (không làm gì) nếu tính năng tắt. Gọi SAU lab.register (dùng chung lab.SLOT, LabError)."""
    st = settings if settings is not None else load_settings()
    if st is None:
        return False
    store = Store(st.data_dir)
    tokens: "OrderedDict[str, float]" = OrderedDict()
    tokens_lock = threading.Lock()
    pending: "OrderedDict[str, dict]" = OrderedDict()   # calibration_id -> kết quả dò bảng chưa lưu
    pending_lock = threading.Lock()
    calib_lock = threading.Lock()
    app.state.cam_store = store
    app.state.cam_tokens = tokens
    print(f"[cam] Camera lab bật; thư mục dữ liệu: {st.data_dir}", file=sys.stderr)

    # ---------------- xác thực ----------------
    def _auth(request: Request) -> None:
        token = request.headers.get("x-cam-token", "")
        now = time.monotonic()
        with tokens_lock:
            for k in [k for k, exp in tokens.items() if exp <= now]:
                del tokens[k]
            ok = token in tokens
        if not ok:
            raise LabError(401, "Access code required.", "unauthorized")

    @app.post("/api/cam/login")
    def cam_login(body: dict = Body(...)):
        if not _same(st.code_hash, body.get("code")):
            raise LabError(401, "Wrong access code.", "bad_code")
        token = secrets.token_urlsafe(32)
        with tokens_lock:
            tokens[token] = time.monotonic() + TOKEN_TTL_S
            while len(tokens) > MAX_TOKENS:
                tokens.popitem(last=False)
        return {"ok": True, "token": token, "expires_in": TOKEN_TTL_S}

    # ---------------- hiệu chỉnh ----------------
    def _calibration() -> dict:
        """Hiệu chỉnh đang dùng. Chưa có -> tạo hiệu chỉnh TẠM từ ảnh bảng mẫu (KHÔNG phải của camera này)."""
        with calib_lock:
            c = store.read_calibration()
            if c is not None:
                return c
            sample = lab.SAMPLES[PROVISIONAL_SAMPLE]
            path = lab.SAMPLES_DIR / sample["file"]
            res, _payload = lab.detect_board_pose(path, lab._sample_bgr(PROVISIONAL_SAMPLE), lab.DEFAULT_MARKER_SIZE_MM, None)
            c = {
                "camera_id": CAMERA_ID, "marker_latlon": list(lab.DEFAULT_LATLNG), "azimuth_deg": 0.0,
                "R": res["R"], "t": res["t"], "camera_matrix": res["camera_matrix"], "image_size": res["image_size"],
                "diagonal_fov_deg": res["diagonal_fov_deg"], "side_px_min": res["side_px_min"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "provisional": True,
                "source": "TEMPORARY: sample board photo, not this camera. Positions on the map are only for trying the drawing.",
            }
            store.write_calibration(c)
            return c

    def _public_calibration(c: dict) -> dict:
        return {
            "provisional": bool(c.get("provisional")), "source": c.get("source", ""),
            "camera_id": c.get("camera_id", CAMERA_ID), "marker_latlon": c["marker_latlon"], "azimuth_deg": c["azimuth_deg"],
            "fov_deg": c["diagonal_fov_deg"], "image_size": c["image_size"], "side_px_min": c["side_px_min"],
            "created_at": c.get("created_at"),
        }

    @app.get("/api/cam/calibration")
    def cam_calibration(request: Request):
        _auth(request)
        return {"ok": True, "calibration": _public_calibration(_calibration())}

    def _resolve_frame_id(value) -> str:
        if value == "latest":
            ids = store.list_ids(1)
            if not ids:
                raise LabError(404, "No camera frame yet.", "no_frame")
            return ids[0]
        if not isinstance(value, str) or not FRAME_ID_RE.match(value) or not store.path(value, ".jpg").is_file():
            raise LabError(404, "Frame not found.", "not_found")
        return value

    @app.post("/api/cam/calibration/detect")
    def cam_calibration_detect(request: Request, body: dict = Body(...)):
        _auth(request)
        fid = _resolve_frame_id(body.get("frame_id", "latest"))
        size_mm = lab._number_field(body, "marker_size_mm", lab.DEFAULT_MARKER_SIZE_MM, 10.0, 5000.0,
                                    "Board side length must be between 10 and 5000 mm.")
        fov_in = lab._number_field(body, "fov_deg", None, 1.0, 179.0,
                                   "Lens field of view (fov_deg) must be between 1 and 179 degrees.")
        path = store.path(fid, ".jpg")
        bgr = cv2.imread(str(path))
        if bgr is None:
            raise LabError(500, "The stored frame could not be read.", "server_error")
        res, payload = lab.detect_board_pose(path, bgr, size_mm, fov_in)
        cid = secrets.token_hex(8)
        with pending_lock:
            pending[cid] = {"id": cid, "frame_id": fid, "result": res}
            while len(pending) > MAX_PENDING:
                pending.popitem(last=False)
        return {"ok": True, "calibration_id": cid, "frame_id": fid, **payload}

    @app.post("/api/cam/calibration/save")
    def cam_calibration_save(request: Request, body: dict = Body(...)):
        _auth(request)
        cid = body.get("calibration_id")
        if not isinstance(cid, str):
            raise LabError(422, "Missing 'calibration_id'.", "invalid_value")
        lat = lab._number_field(body, "lat", None, -90.0, 90.0, "Missing or invalid value 'lat' (must be a number).")
        lon = lab._number_field(body, "lon", None, -180.0, 180.0, "Missing or invalid value 'lon' (must be a number).")
        az = lab._number_field(body, "azimuth_deg", None, -100000.0, 100000.0, "Missing or invalid value 'azimuth_deg' (must be a number).")
        if lat is None or lon is None or az is None:
            raise LabError(422, "Missing latitude, longitude or azimuth.", "invalid_value")
        with pending_lock:
            pend = pending.get(cid)
        if pend is None:
            raise LabError(404, "Calibration result not found (expired or unknown). Please detect the board again.", "not_found")
        res = pend["result"]
        c = {
            "camera_id": CAMERA_ID, "marker_latlon": [lat, lon], "azimuth_deg": az % 360.0,
            "R": res["R"], "t": res["t"], "camera_matrix": res["camera_matrix"], "image_size": res["image_size"],
            "diagonal_fov_deg": res["diagonal_fov_deg"], "side_px_min": res["side_px_min"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provisional": False, "source": f"board detected in camera frame {pend['frame_id']}",
        }
        try:
            with calib_lock:
                store.write_calibration(c)
        except OSError:
            raise LabError(507, "Could not save the calibration to disk.", "storage_failed") from None
        return {"ok": True, "calibration": _public_calibration(c)}

    @app.get("/api/cam/footprint")
    def cam_footprint(request: Request, calibration_id: Optional[str] = Query(None), lat: Optional[float] = Query(None),
                      lon: Optional[float] = Query(None), azimuth_deg: Optional[float] = Query(None),
                      max_range_m: float = Query(12.0)):
        _auth(request)
        if calibration_id:
            with pending_lock:
                pend = pending.get(calibration_id)
            if pend is None:
                raise LabError(404, "Calibration result not found (expired or unknown). Please detect the board again.", "not_found")
            if lat is None or lon is None:
                raise LabError(422, "Missing latitude/longitude (lat, lon).", "invalid_value")
            return lab.build_footprint(pend["result"], lat, lon, 0.0 if azimuth_deg is None else azimuth_deg, max_range_m)
        c = _calibration()
        return lab.build_footprint(c, c["marker_latlon"][0] if lat is None else lat, c["marker_latlon"][1] if lon is None else lon,
                                   c["azimuth_deg"] if azimuth_deg is None else azimuth_deg, max_range_m)

    # ---------------- nhận ảnh từ camera / cầu nối ----------------
    def _validate_jpeg(raw: bytes) -> np.ndarray:
        """Kiểm tra TRƯỚC khi giải mã điểm ảnh (chống ảnh bom), rồi giải mã. Trả ảnh BGR."""
        if not raw:
            raise LabError(400, "No photo received.", "invalid_image")
        if raw[:3] != b"\xff\xd8\xff":
            raise LabError(415, "Only JPEG frames are accepted.", "unsupported_type")
        try:
            im = Image.open(io.BytesIO(raw))
            fmt, (w, h) = im.format, im.size
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise LabError(400, "This frame could not be read as a JPEG photo.", "invalid_image") from None
        if fmt != "JPEG":
            raise LabError(415, "Only JPEG frames are accepted.", "unsupported_type")
        if w * h > MAX_PIXELS:
            raise LabError(422, "This frame has too many pixels.", "too_large")
        if min(w, h) < MIN_SIDE_PX:
            raise LabError(422, "This frame is too small to analyse.", "too_small")
        bgr = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            raise LabError(400, "This frame could not be decoded.", "invalid_image")
        return bgr

    def _process_frame(raw: bytes) -> dict:
        received = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        bgr = _validate_jpeg(raw)
        h, w = bgr.shape[:2]
        fid = store.new_id()
        try:
            store.write(fid, ".jpg", raw)   # ảnh gốc, nguyên byte, lưu TRƯỚC mọi xử lý
        except OSError:
            raise LabError(507, "Could not save the frame to disk.", "storage_failed") from None

        calib = _calibration()
        meta = {
            "id": fid, "received_at": received.strftime("%Y-%m-%dT%H:%M:%SZ"), "width": int(w), "height": int(h), "bytes": len(raw),
            "status": "analysed", "provisional_calibration": bool(calib.get("provisional")),
            "n_instances": 0, "n_regions": 0, "total_area_m2": 0.0,
            "regions": {"type": "FeatureCollection", "features": []}, "warnings": [],
            "inference_ms": None, "processing_ms": None, "has_annotated": False,
        }
        annotated = None
        try:
            t1 = time.perf_counter()
            with lab.SLOT():
                union, confs, annotated = lab.run_trash_model(bgr)
            meta["inference_ms"] = round((time.perf_counter() - t1) * 1000.0, 1)
            meta["n_instances"] = len(confs)
            cw, ch = calib["image_size"]
            if abs((w / h) / (cw / ch) - 1.0) > ASPECT_TOLERANCE:
                meta["status"] = "aspect_mismatch"
                meta["warnings"].append(
                    f"This frame is {w}x{h} but the calibration photo is {cw}x{ch} (different aspect ratio): trash was outlined "
                    f"on the photo but not placed on the map. Calibrate again with a frame from this camera.")
            else:
                rp = lab.regions_from_mask(union, confs, calib)
                meta.update(regions=rp["regions"], n_regions=rp["n_regions"], total_area_m2=rp["total_area_m2"], warnings=rp["warnings"])
        except LabError as exc:          # hàng chờ đầy / model chưa sẵn sàng: giữ ảnh gốc, bỏ qua phân tích
            meta["status"] = "busy" if exc.code == "busy" else ("not_ready" if exc.code == "not_ready" else "error")
            meta["warnings"].append("The frame was saved but not analysed: " + exc.message)
        except Exception as exc:         # noqa: BLE001  chỉ ghi tên lỗi, không nội dung
            print(f"[cam] loi khi xu ly khung: {type(exc).__name__}", file=sys.stderr)
            meta["status"] = "error"
            meta["warnings"].append("The frame was saved but the analysis failed.")
        try:
            if annotated is not None:
                ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ok:
                    store.write(fid, ".ann.jpg", buf.tobytes())
                    meta["has_annotated"] = True
            meta["processing_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            store.write_meta(fid, meta)
        except OSError:
            raise LabError(507, "Could not save the result to disk.", "storage_failed") from None
        return {"ok": True, "id": fid, "status": meta["status"], "n_instances": meta["n_instances"],
                "n_regions": meta["n_regions"], "total_area_m2": meta["total_area_m2"]}

    @app.post("/api/cam/ingest")
    async def cam_ingest(request: Request):
        if not _same(st.key_hash, request.headers.get("x-cam-key", "")):
            raise LabError(401, "Invalid ingest key.", "bad_key")
        try:
            raw = await srv.read_body(request, MAX_INGEST_BYTES)
        except srv.ApiError as exc:
            raise LabError(exc.status, exc.message, exc.code, exc.headers) from None
        return await run_in_threadpool(_process_frame, raw)

    # ---------------- đọc ----------------
    def _summary(meta: dict) -> dict:
        return {k: v for k, v in meta.items() if k != "regions"}

    @app.get("/api/cam/latest")
    def cam_latest(request: Request):
        _auth(request)
        for fid in store.list_ids(3):       # bỏ qua khung vừa ghi dở (hiếm)
            meta = store.read_meta(fid)
            if meta is not None:
                return {"ok": True, "frame": meta, "calibration": _public_calibration(_calibration())}
        return {"ok": True, "frame": None, "calibration": _public_calibration(_calibration())}

    @app.get("/api/cam/frames")
    def cam_frames(request: Request, limit: int = Query(LIST_DEFAULT), before: Optional[str] = Query(None)):
        _auth(request)
        if before is not None and not FRAME_ID_RE.match(before):
            raise LabError(422, "Invalid 'before'.", "invalid_value")
        limit = max(1, min(LIST_MAX, limit))
        frames = [m for m in (store.read_meta(fid) for fid in store.list_ids(limit, before)) if m is not None]
        return {"ok": True, "frames": [_summary(m) for m in frames],
                "next_before": frames[-1]["id"] if len(frames) == limit else None}

    @app.get("/api/cam/frames/{frame_id}")
    def cam_frame(request: Request, frame_id: str):
        _auth(request)
        meta = store.read_meta(frame_id) if FRAME_ID_RE.match(frame_id) else None
        if meta is None:
            raise LabError(404, "Frame not found.", "not_found")
        return {"ok": True, "frame": meta}

    @app.get("/api/cam/frames/{frame_id}/image")
    def cam_frame_image(request: Request, frame_id: str, kind: str = Query("original")):
        _auth(request)
        if kind not in ("original", "annotated"):
            raise LabError(422, "kind must be 'original' or 'annotated'.", "invalid_value")
        if not FRAME_ID_RE.match(frame_id) or store.read_meta(frame_id) is None:
            raise LabError(404, "Frame not found.", "not_found")
        try:
            data = store.path(frame_id, ".jpg" if kind == "original" else ".ann.jpg").read_bytes()
        except OSError:
            raise LabError(404, "This image is not available.", "not_found") from None
        return Response(content=data, media_type="image/jpeg")

    return True
