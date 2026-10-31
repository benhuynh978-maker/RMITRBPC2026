"""
CleanSight live demo API: nhận một ảnh, chạy model, trả ảnh đã khoanh + hai chỉ số.

Dịch vụ RIÊNG, độc lập với hệ thống chính (ssc-road-alerts, inference, test-WebUI-modelAI không bị sửa).
Chỉ dùng lại hàm analyze() của ssc-v2/inference (model baseline_v1_rev2, công thức legacy, không có vùng cống).

Cam kết (đều có kiểm thử trong test_demo_api.py):
  - Ảnh KHÔNG bao giờ được ghi ra đĩa: thân yêu cầu là dữ liệu ảnh thô (image/jpeg | image/png), đọc thẳng vào RAM
    (không dùng multipart vì thư viện web sẽ ghi file > 1 MB ra thư mục tạm).
  - Không log nội dung ảnh, tên tệp hay địa chỉ IP. Chạy uvicorn với --no-access-log.
  - CORS chỉ cho đúng các origin trong CLEANSIGHT_ALLOWED_ORIGINS; thiếu biến này (hoặc có "*") thì KHÔNG khởi động.
  - Kiểm kích thước ảnh bằng PIL TRƯỚC khi giải mã; thu về cạnh dài <= 1600 px; mã hoá lại JPEG (bỏ EXIF).

Hợp đồng:
  GET  /api/health   -> {"status":"ok","ready":true|false}
  POST /api/analyze  (thân = ảnh thô, Content-Type image/jpeg hoặc image/png)
       200 -> {"waste_pct","level_index"(-1..3),"drain_pct"|null,"annotated_jpg"(data URL)}
       lỗi -> {"error","code"}: 400 invalid_image, 413 too_big, 415 unsupported_type, 422 too_large|too_small|too_dark,
              429 rate_limited|busy_global (+ Retry-After), 503 busy|not_ready, 500 server_error

Chạy (từ thư mục này, dùng python của .venv; xem README.md):
  CLEANSIGHT_ALLOWED_ORIGINS=https://ten-site.netlify.app python -B -m uvicorn server:app --host 127.0.0.1 --port 8140 --no-access-log
"""
from __future__ import annotations

import os
import sys

# --- Kiểm cấu hình TRƯỚC khi nạp thư viện nặng: sai thì dừng ngay, không mở cổng. ---
def _allowed_origins() -> list[str]:
    raw = os.environ.get("CLEANSIGHT_ALLOWED_ORIGINS", "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if not origins:
        raise RuntimeError(
            "Thieu CLEANSIGHT_ALLOWED_ORIGINS (vd https://ten-site.netlify.app). "
            "Dich vu tu choi khoi dong de khong mo CORS cho moi trang web."
        )
    for origin in origins:
        if origin == "*" or not origin.startswith(("http://", "https://")):
            raise RuntimeError(f"CLEANSIGHT_ALLOWED_ORIGINS khong hop le: {origin!r} (can dang https://host, khong dung '*').")
    return origins


ALLOWED_ORIGINS = _allowed_origins()

import base64  # noqa: E402
import io  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from collections import defaultdict, deque  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "ssc-v2" / "inference"))
import analysis  # noqa: E402  (nạp ultralytics; cần sys.path ở trên)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MAX_BODY_BYTES = _int_env("CLEANSIGHT_MAX_BODY_BYTES", 8 * 1024 * 1024)
MAX_PIXELS = _int_env("CLEANSIGHT_MAX_PIXELS", 40_000_000)
MAX_SIDE_PX = _int_env("CLEANSIGHT_MAX_SIDE_PX", 1600)
MIN_SIDE_PX = 64
MAX_WAITING = _int_env("CLEANSIGHT_MAX_WAITING", 3)  # số yêu cầu được xếp hàng chờ, ngoài 1 yêu cầu đang chạy
PER_MINUTE = _int_env("CLEANSIGHT_RATE_PER_MINUTE", 5)
PER_HOUR = _int_env("CLEANSIGHT_RATE_PER_HOUR", 50)
GLOBAL_PER_MINUTE = _int_env("CLEANSIGHT_RATE_GLOBAL_PER_MINUTE", 20)

# Ngưỡng nhãn mức rác: khớp POLICY.waste của backend (1/5/10/20 % = Low/Medium/High/Severe).
WASTE_THRESHOLDS = (1.0, 5.0, 10.0, 20.0)
ACCEPTED_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.headers = status, code, message, headers or {}


def level_index(pct: float) -> int:
    """-1 = dưới ngưỡng Low (< 1 %); 0..3 = Low, Medium, High, Severe."""
    index = -1
    for i, threshold in enumerate(WASTE_THRESHOLDS):
        if pct >= threshold:
            index = i
    return index


class RateLimiter:
    """Cửa sổ trượt trong bộ nhớ: theo IP (phút + giờ) và một trần chung toàn dịch vụ (phút)."""

    def __init__(self, per_minute: int, per_hour: int, global_per_minute: int):
        self.per_minute, self.per_hour, self.global_per_minute = per_minute, per_hour, global_per_minute
        self._hits: dict[str, deque] = defaultdict(deque)
        self._global: deque = deque()
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int, str]:
        """(được phép, số giây chờ, mã lỗi)."""
        now = time.monotonic()
        with self._lock:
            while self._global and now - self._global[0] > 60:
                self._global.popleft()
            if len(self._global) >= self.global_per_minute:
                return False, max(1, int(61 - (now - self._global[0]))), "busy_global"
            hits = self._hits[key]
            while hits and now - hits[0] > 3600:
                hits.popleft()
            recent = [t for t in hits if now - t <= 60]
            if len(recent) >= self.per_minute:
                return False, max(1, int(61 - (now - recent[0]))), "rate_limited"
            if len(hits) >= self.per_hour:
                return False, max(1, int(3601 - (now - hits[0]))), "rate_limited"
            hits.append(now)
            self._global.append(now)
            if len(self._hits) > 5000:  # dọn IP không còn lượt nào để bộ nhớ không phình mãi
                for ip in [k for k, v in self._hits.items() if not v]:
                    del self._hits[ip]
            return True, 0, ""


limiter = RateLimiter(PER_MINUTE, PER_HOUR, GLOBAL_PER_MINUTE)
model_lock = threading.Lock()  # một suy luận một lúc
_pending = 0  # yêu cầu đang chạy + đang chờ
_pending_lock = threading.Lock()
_ready = False


def reserve_slot() -> None:
    """Giữ một chỗ trong hàng chờ model (1 đang chạy + MAX_WAITING chờ); đầy thì 503. Dùng chung với phòng thử (lab.py)."""
    global _pending
    with _pending_lock:
        if _pending >= MAX_WAITING + 1:
            raise ApiError(503, "busy", "The demo is busy right now. Please try again in a few seconds.", {"Retry-After": "5"})
        _pending += 1


def release_slot() -> None:
    global _pending
    with _pending_lock:
        _pending -= 1


def client_ip(request: Request) -> str:
    """Dịch vụ chỉ nghe 127.0.0.1 và đứng sau Tailscale Funnel. Lấy phần tử CUỐI của X-Forwarded-For:
    nếu proxy ghi đè thì chỉ có một giá trị; nếu proxy nối thêm thì phần tử cuối là địa chỉ thật,
    còn phần đầu có thể do người gọi tự điền (giả mạo)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


def _warm_up() -> None:
    global _ready
    blank = np.full((64, 64, 3), 128, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", blank)
    try:
        if ok:
            with model_lock:
                analysis.analyze(buf.tobytes())
        _ready = True
        print("[startup] model san sang", file=sys.stderr)
    except Exception as error:  # noqa: BLE001
        _ready = False
        print(f"[startup] khong nap duoc model: {type(error).__name__}", file=sys.stderr)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await run_in_threadpool(_warm_up)
    yield


app = FastAPI(title="CleanSight live demo API", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Lab-Session"],
    expose_headers=["Retry-After"],  # không khai báo thì trình duyệt không cho trang đọc Retry-After của yêu cầu khác nguồn
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _error_response(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message, "code": code}, headers=headers or {})


@app.exception_handler(ApiError)
async def _api_error(_request: Request, exc: ApiError):
    return _error_response(exc.status, exc.code, exc.message, exc.headers)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_request: Request, exc: StarletteHTTPException):
    return _error_response(exc.status_code, f"http_{exc.status_code}", "Request not allowed.")


@app.exception_handler(Exception)
async def _unhandled(_request: Request, exc: Exception):
    print(f"[error] {type(exc).__name__}", file=sys.stderr)  # chỉ tên lỗi, không nội dung
    return _error_response(500, "server_error", "The live demo ran into a problem.")


def decode_upload(raw: bytes) -> bytes:
    """Giải mã + chuẩn hoá ảnh tải lên -> JPEG bytes (cạnh dài <= MAX_SIDE_PX, đã xoay theo EXIF, đã bỏ EXIF)."""
    try:
        image = Image.open(io.BytesIO(raw))  # chỉ đọc phần đầu, chưa giải mã điểm ảnh
        fmt = image.format
        width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ApiError(400, "invalid_image", "This file could not be read as a photo.") from None
    if fmt not in ("JPEG", "PNG"):
        raise ApiError(415, "unsupported_type", "Only JPG and PNG photos are supported.")
    if width * height > MAX_PIXELS:
        raise ApiError(422, "too_large", "This photo has too many pixels.")
    if min(width, height) < MIN_SIDE_PX:
        raise ApiError(422, "too_small", "This photo is too small to analyse.")
    try:
        image = ImageOps.exif_transpose(image)
        if image.mode in ("RGBA", "LA", "P") and (image.mode != "P" or "transparency" in image.info):
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise ApiError(400, "invalid_image", "This file could not be read as a photo.") from None
    bgr = np.asarray(image)[:, :, ::-1]
    h, w = bgr.shape[:2]
    longest = max(h, w)
    if longest > MAX_SIDE_PX:
        scale = MAX_SIDE_PX / longest
        bgr = cv2.resize(bgr, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", np.ascontiguousarray(bgr), [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise ApiError(500, "server_error", "The live demo ran into a problem.")
    return buf.tobytes()


def process(raw: bytes) -> dict:
    """Chạy trong threadpool. Không ghi gì ra đĩa."""
    jpeg = decode_upload(raw)
    try:
        with model_lock:
            result = analysis.analyze(jpeg, quality_gate=True)
    except ValueError:
        raise ApiError(400, "invalid_image", "This file could not be read as a photo.") from None
    if not result.get("usable"):
        raise ApiError(422, "too_dark", "This photo is too dark to analyse. The demo works on daytime photos.")
    waste = float(result["waste_coverage_pct"])
    drain = result.get("drain_blockage_pct")  # vắng khi model không thấy miệng cống
    return {
        "waste_pct": round(waste, 2),
        "level_index": level_index(waste),
        "drain_pct": None if drain is None else round(float(drain), 2),
        "annotated_jpg": "data:image/jpeg;base64," + base64.b64encode(result["analyzed_bytes"]).decode(),
    }


async def read_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise ApiError(413, "too_big", "This file is too large.")
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise ApiError(413, "too_big", "This file is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


@app.get("/api/health")
async def health():
    return {"status": "ok", "ready": _ready}


@app.post("/api/analyze")
async def analyze_endpoint(request: Request):
    allowed, retry_after, code = limiter.check(client_ip(request))
    if not allowed:
        message = "The demo is busy. Please try again shortly." if code == "busy_global" else "Too many photos sent."
        raise ApiError(429, code, message, {"Retry-After": str(retry_after)})
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in ACCEPTED_TYPES:
        raise ApiError(415, "unsupported_type", "Only JPG and PNG photos are supported.")
    if not _ready:
        raise ApiError(503, "not_ready", "The live demo is starting. Please try again in a moment.")
    raw = await read_body(request, MAX_BODY_BYTES)
    if not raw:
        raise ApiError(400, "invalid_image", "No photo received.")

    reserve_slot()
    try:
        result = await run_in_threadpool(process, raw)
    finally:
        release_slot()
    return JSONResponse(result)


# Phòng thử hiệu chỉnh cho giám khảo (Board lab + Drain lab): xem lab.py.
import lab  # noqa: E402

lab.register(app, sys.modules[__name__])
