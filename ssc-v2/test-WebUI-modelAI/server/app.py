"""
Service demo cho gia'm kha?o thu? model: nha^.n a?nh -> tra? a?nh ma(.t na.  + 2 chi? so^'.

Chay DONG BO (kha'c backend ssc-road-alerts vo^'n cha.y ba^'t do^`ng bo^. qua hang doi):
nguoi dung upload anh -> chay model ngay -> tra ket qua ve trong cung mot request.

KHONG dung chung du lieu voi ssc-road-alerts: khong ghi cameras.json, khong can
camera_id. Chi dung lai dung ham analyze() da co trong inference/analysis.py de
khong nhan ban logic model.

Chay:
    ..\\..\\..\\.venv\\Scripts\\python.exe -B -m uvicorn app:app --host 0.0.0.0 --port 8110
(chay tu trong thu muc server/)
"""
from __future__ import annotations

import base64
import os
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]          # ban v2: C:\Users\ASUS\Desktop\SSC\ssc-v2
sys.path.insert(0, str(PROJECT_ROOT / "inference"))
from analysis import analyze  # noqa: E402  - can them sys.path truoc khi import

UPLOAD_DIR = Path(os.environ.get("DEMO_UPLOAD_DIR", HERE.parent / "uploads"))
MAX_UPLOAD_BYTES = int(os.environ.get("DEMO_MAX_UPLOAD_BYTES", 8 * 1024 * 1024))
PER_MINUTE = int(os.environ.get("DEMO_RATE_PER_MINUTE", 5))
PER_HOUR = int(os.environ.get("DEMO_RATE_PER_HOUR", 50))
# Netlify domain + localhost khi chay thu. Dat DEMO_ALLOWED_ORIGINS="https://abc.netlify.app"
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("DEMO_ALLOWED_ORIGINS", "*").split(",") if o.strip()]

# Phai khop nguong trong ssc-road-alerts/server/config.js (POLICY.waste).
WASTE_THRESHOLDS = ((20, "Nghiêm trọng"), (10, "Cao"), (5, "Trung bình"), (1, "Thấp"))


def waste_label(pct: float) -> str:
    for threshold, label in WASTE_THRESHOLDS:
        if pct >= threshold:
            return label
    return "Bình thường"


class RateLimiter:
    """Cua so truot trong bo nho, chan theo IP. Mot tien trinh duy nhat nen khong can Redis."""

    def __init__(self, per_minute: int, per_hour: int):
        self.per_minute = per_minute
        self.per_hour = per_hour
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Tra ve (duoc phep, so giay cho toi luot sau)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 3600:
                hits.popleft()
            recent = [t for t in hits if now - t <= 60]
            if len(recent) >= self.per_minute:
                return False, int(61 - (now - recent[0]))
            if len(hits) >= self.per_hour:
                return False, int(3601 - (now - hits[0]))
            hits.append(now)
            # Don cac IP khong con luot nao de bo nho khong phinh vo han.
            if len(self._hits) > 5000:
                for ip in [k for k, v in self._hits.items() if not v]:
                    del self._hits[ip]
            return True, 0


limiter = RateLimiter(PER_MINUTE, PER_HOUR)
# GPU chi chay duoc mot suy luan tai mot thoi diem cho an toan; khoa lai de nhieu
# nguoi upload cung luc thi xep hang thay vi tranh nhau bo nho GPU.
model_lock = threading.Lock()

app = FastAPI(title="SSC — Thử model phát hiện rác", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


def client_ip(request: Request) -> str:
    """Sau Tailscale Funnel, IP that nam o X-Forwarded-For. Chi tin header nay vi
    service duoc dat sau tunnel, khong mo truc tiep ra Internet."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.get("/api/health")
def health():
    return {"status": "ok", "rate_limit": {"per_minute": PER_MINUTE, "per_hour": PER_HOUR}}


@app.post("/api/predict")
def predict(request: Request, image: UploadFile = File(...)):
    allowed, retry_after = limiter.check(client_ip(request))
    if not allowed:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(max(retry_after, 1))},
            content={
                "error": f"Bạn đã gửi quá nhiều ảnh. Giới hạn {PER_MINUTE} ảnh/phút và {PER_HOUR} ảnh/giờ.",
                "retry_after_seconds": max(retry_after, 1),
            },
        )

    raw = image.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        return JSONResponse(status_code=413, content={"error": f"Ảnh vượt quá {MAX_UPLOAD_BYTES // (1024 * 1024)}MB."})
    if not raw:
        return JSONResponse(status_code=400, content={"error": "Không nhận được dữ liệu ảnh."})

    # Luu BAN GOC (chua ve mask) de sau nay danh gia/huan luyen lai tren anh that.
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    saved_as = f"{stamp}-{uuid.uuid4().hex[:8]}.jpg"
    (UPLOAD_DIR / saved_as).write_bytes(raw)

    try:
        with model_lock:
            result = analyze(raw)
    except ValueError as error:  # anh hong / khong giai ma duoc
        return JSONResponse(status_code=400, content={"error": str(error)})
    except Exception as error:  # noqa: BLE001 - khong de mot anh loi lam sap service
        print(f"[predict] loi model: {error}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Model gặp lỗi khi xử lý ảnh này."})

    waste = result["waste_coverage_pct"]
    return {
        "waste_coverage_pct": waste,
        "waste_level": waste_label(waste),
        "drain_blockage_pct": result.get("drain_blockage_pct"),
        "confidence": result["confidence"],
        "annotated_image": "data:image/jpeg;base64," + base64.b64encode(result["analyzed_bytes"]).decode(),
    }


@app.on_event("startup")
def warm_up():
    """Nap model san luc khoi dong de nguoi dau tien khong phai cho ~5 giay."""
    import numpy as np
    import cv2

    blank = np.zeros((64, 64, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", blank)
    if ok:
        try:
            with model_lock:
                analyze(buffer.tobytes())
            print("[startup] model da san sang")
        except Exception as error:  # noqa: BLE001
            print(f"[startup] khong nap duoc model: {error}", file=sys.stderr)
