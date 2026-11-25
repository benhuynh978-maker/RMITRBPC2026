"""
Máy chủ FastAPI của công cụ khảo sát rác (exp03). Chạy riêng, cổng 8130, dữ liệu riêng (data/), KHÔNG dùng
chung gì với webtest (cổng 8120) ngoài việc ĐỌC mã hình học của exp02.

Chạy: run_tailscale.ps1 (chỉ nghe địa chỉ Tailscale, giống webtest) hoặc
  python -B -m uvicorn svy_server:app --host 127.0.0.1 --port 8130

Mọi /api/* (trừ /api/health) cần mã truy cập 6 số: header X-Access-Code, hoặc ?code= cho ảnh (thẻ <img> không gửi
được header). Trang tĩnh (/, /phone, /web/*) không cần mã. Mọi lỗi nghiệp vụ trả {"ok": false, "error": "<tiếng Việt>"}.
"""
from __future__ import annotations

import hashlib
import math
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

import svy_core as core
import svy_export as export
import svy_store as store

HERE = Path(__file__).resolve().parent
WEB_DIR = HERE / "web"
MAX_UPLOAD_BYTES = 40 * 1024 * 1024
MAX_SPOTS = 300
FAIL_LIMIT = 10
FAIL_WINDOW_S = 60.0

# Cho test thay AI bằng bản giả (nhanh, xác định).
_INFER = None


def set_infer(fn) -> None:
    global _INFER
    _INFER = fn


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


def error_response(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "error": message, **extra})


@asynccontextmanager
async def lifespan(_app):
    print(f"[khao-sat] Ma truy cap: {store.get_access_code()}", flush=True)
    if os.environ.get("SURVEY_NO_WARMUP") != "1":
        def warm():
            try:
                import numpy as np
                core.infer_trash_mask(np.zeros((480, 640, 3), dtype=np.uint8))
                print("[khao-sat] model san sang", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[khao-sat] khong nap duoc model: {exc}", flush=True)
        threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(ApiError)
async def _api_error(_r: Request, exc: ApiError):
    return error_response(exc.status, exc.message, **exc.extra)


@app.exception_handler(RequestValidationError)
async def _validation(_r: Request, exc: RequestValidationError):
    return error_response(422, "Dữ liệu gửi lên không hợp lệ.")


@app.exception_handler(StarletteHTTPException)
async def _http(_r: Request, exc: StarletteHTTPException):
    known = {401: "Sai hoặc thiếu mã truy cập.", 404: "Không tìm thấy.", 405: "Không hỗ trợ thao tác này.",
             413: "File quá lớn.", 422: "Dữ liệu không hợp lệ."}
    return error_response(exc.status_code, known.get(exc.status_code, "Yêu cầu không hợp lệ."))


# ---------------------------------------------------------------- mã truy cập
_fails: dict = {}
_fails_lock = threading.Lock()


@app.middleware("http")
async def _guard(request: Request, call_next):
    path = request.url.path
    if (path == "/api" or path.startswith("/api/")) and path != "/api/health":
        ip = request.client.host if request.client else "?"
        now = time.monotonic()
        with _fails_lock:
            recent = [t for t in _fails.get(ip, []) if now - t < FAIL_WINDOW_S]
            _fails[ip] = recent
            blocked = len(recent) >= FAIL_LIMIT
        if blocked:
            return error_response(429, "Nhập sai mã quá nhiều lần. Thử lại sau 1 phút.")
        given = request.headers.get("x-access-code") or request.query_params.get("code") or ""
        if not secrets.compare_digest(given.encode("utf-8"), store.get_access_code().encode("utf-8")):
            with _fails_lock:
                _fails.setdefault(ip, []).append(now)
            return error_response(401, "Sai hoặc thiếu mã truy cập.")
    response = await call_next(request)
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------- tiện ích
def _public_spot(s: dict) -> dict:
    """Bỏ phần nặng/không cần cho trình duyệt (R, t, K, ring_px, bytes)."""
    keys = ("id", "seq", "name", "status", "error", "received_at", "captured_local", "time_source", "image_size",
            "fov_deg", "fov_source", "side_px_min", "camera_height_m", "warnings", "marker_size_mm", "footprint_m",
            "board_m", "n_instances", "mean_conf", "placement", "include", "paper_px_removed")
    out = {k: s.get(k) for k in keys}
    out["ai_regions"] = [{k: r.get(k) for k in ("id", "area_m2", "ring_m", "holes_m", "conf", "hidden")} for r in s.get("ai_regions", [])]
    out["manual_regions"] = list(s.get("manual_regions", []))
    out["area_m2"] = core.spot_area_m2(s) if s.get("status") == "ok" else 0.0
    return out


def _state_payload() -> dict:
    snap = store.snapshot()
    return {"ok": True, "settings": snap["settings"], "spots": [_public_spot(s) for s in snap["spots"]],
            "summary": core.summarize(snap)}


def _num(body: dict, key: str, lo: float, hi: float) -> float:
    v = body.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not (lo <= v <= hi):
        raise ApiError(422, f"Giá trị '{key}' không hợp lệ (cần số trong khoảng {lo} đến {hi}).")
    return float(v)


def _spot_or_404(data: dict, spot_id: str) -> dict:
    s = store.get_spot(data, spot_id) if store.is_valid_id(spot_id) else None
    if s is None:
        raise ApiError(404, "Không tìm thấy điểm này.")
    return s


def _ingest(raw: bytes, source_name: str = "") -> dict:
    """Xử lý một ảnh thành một điểm khảo sát và lưu. Trả hồ sơ công khai. Ảnh trùng (cùng nội dung) -> 409."""
    digest = core.sha256(raw)
    snap = store.snapshot()
    for s in snap["spots"]:
        if s.get("sha256") == digest:
            raise ApiError(409, f"Ảnh này đã được nạp rồi ({s.get('name')}).", duplicate_of=s["id"])
    if len(snap["spots"]) >= MAX_SPOTS:
        raise ApiError(409, f"Đã đủ {MAX_SPOTS} điểm. Xoá bớt điểm cũ trước.")
    settings = snap["settings"]
    try:
        rec, bgr = core.process_photo(raw, settings["marker_size_mm"], settings["max_range_m"], _INFER)
    except core.PhotoError as exc:
        raise ApiError(422, str(exc)) from None
    spot_id = store.new_id()
    store.save_photo_files(spot_id, raw, core.encode_jpg(bgr, 2048, 88), core.encode_jpg(bgr, 480, 80))
    with store.Tx() as data:
        seq = int(data["settings"].get("next_seq", 1))
        data["settings"]["next_seq"] = seq + 1
        rec.update({"id": spot_id, "seq": seq, "name": f"Điểm {seq}", "placement": None, "include": True})
        data["spots"].append(rec)
    return _public_spot(rec)


# ---------------------------------------------------------------- API
@app.get("/api/health")
def api_health():
    return {"ok": True, "tool": "khao-sat-rac"}


@app.get("/api/spots")
def api_spots():
    return _state_payload()


@app.post("/api/photos")
def api_photos(photo: UploadFile = File(...)):
    raw = photo.file.read(MAX_UPLOAD_BYTES + 1)
    if not raw:
        raise ApiError(422, "File ảnh rỗng.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "Ảnh quá lớn (tối đa 40 MB).")
    return {"ok": True, "spot": _ingest(raw), "summary": core.summarize(store.snapshot())}


@app.post("/api/import-folder")
def api_import_folder():
    """Cách 1 (chép file): nạp mọi ảnh JPG/PNG trong thư mục thu_muc_anh/ chưa nạp lần nào (so theo nội dung ảnh)."""
    d = store.folder_in_dir()
    d.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    added, skipped, failed = [], 0, []
    for p in files:
        try:
            if p.stat().st_size > MAX_UPLOAD_BYTES:
                failed.append({"file": p.name, "error": "Ảnh quá lớn."})
                continue
            added.append({"file": p.name, "spot": _ingest(p.read_bytes(), p.name)})
        except ApiError as exc:
            if exc.status == 409 and exc.extra.get("duplicate_of"):
                skipped += 1
            else:
                failed.append({"file": p.name, "error": exc.message})
    return {"ok": True, "folder": str(d), "found": len(files), "added": len(added), "skipped_already_loaded": skipped,
            "failed": failed, "spots": [a["spot"] for a in added], "summary": core.summarize(store.snapshot())}


@app.post("/api/spots/{spot_id}")
def api_spot_update(spot_id: str, body: dict = Body(...)):
    with store.Tx() as data:
        s = _spot_or_404(data, spot_id)
        if "name" in body:
            name = body["name"]
            if not isinstance(name, str) or not (1 <= len(name.strip()) <= 60):
                raise ApiError(422, "Tên điểm cần từ 1 đến 60 ký tự.")
            s["name"] = name.strip()
        if "include" in body:
            if not isinstance(body["include"], bool):
                raise ApiError(422, "Giá trị 'include' phải là đúng/sai.")
            s["include"] = body["include"]
        if "placement" in body:
            p = body["placement"]
            if p is None:
                s["placement"] = None
            elif isinstance(p, dict):
                lat, lon = _num(p, "lat", -85.0, 85.0), _num(p, "lon", -180.0, 180.0)
                az = p.get("az")
                az = None if az is None else _num(p, "az", -720.0, 720.0) % 360.0
                s["placement"] = {"lat": lat, "lon": lon, "az": az}
            else:
                raise ApiError(422, "'placement' không hợp lệ.")
        out = _public_spot(s)
    return {"ok": True, "spot": out, "summary": core.summarize(store.snapshot())}


@app.post("/api/spots/{spot_id}/region/{region_id}")
def api_region_hide(spot_id: str, region_id: str, body: dict = Body(...)):
    hidden = body.get("hidden")
    if not isinstance(hidden, bool):
        raise ApiError(422, "'hidden' phải là đúng/sai.")
    with store.Tx() as data:
        s = _spot_or_404(data, spot_id)
        for r in s.get("ai_regions", []):
            if r["id"] == region_id:
                r["hidden"] = hidden
                break
        else:
            raise ApiError(404, "Không tìm thấy vùng này.")
        out = _public_spot(s)
    return {"ok": True, "spot": out, "summary": core.summarize(store.snapshot())}


@app.post("/api/spots/{spot_id}/manual")
def api_manual_add(spot_id: str, body: dict = Body(...)):
    try:
        ring = core.clean_manual_ring(body.get("ring_m"))
    except ValueError as exc:
        raise ApiError(422, str(exc)) from None
    with store.Tx() as data:
        s = _spot_or_404(data, spot_id)
        if s.get("status") != "ok":
            raise ApiError(409, "Điểm này chưa hiệu chỉnh được nên không vẽ thêm vùng.")
        if len(s["manual_regions"]) >= 100:
            raise ApiError(409, "Mỗi điểm tối đa 100 vùng vẽ tay.")
        n = 1 + max([int(r["id"][1:]) for r in s["manual_regions"]] or [0])
        s["manual_regions"].append({"id": f"m{n}", "area_m2": round(core.ring_area_m2(ring), 4), "ring_m": ring})
        out = _public_spot(s)
    return {"ok": True, "spot": out, "summary": core.summarize(store.snapshot())}


@app.delete("/api/spots/{spot_id}/manual/{region_id}")
def api_manual_delete(spot_id: str, region_id: str):
    with store.Tx() as data:
        s = _spot_or_404(data, spot_id)
        before = len(s["manual_regions"])
        s["manual_regions"] = [r for r in s["manual_regions"] if r["id"] != region_id]
        if len(s["manual_regions"]) == before:
            raise ApiError(404, "Không tìm thấy vùng vẽ tay này.")
        out = _public_spot(s)
    return {"ok": True, "spot": out, "summary": core.summarize(store.snapshot())}


@app.delete("/api/spots/{spot_id}")
def api_spot_delete(spot_id: str):
    with store.Tx() as data:
        _spot_or_404(data, spot_id)
        data["spots"] = [s for s in data["spots"] if s["id"] != spot_id]
    store.delete_photo_files(spot_id)
    return {"ok": True, "summary": core.summarize(store.snapshot())}


@app.post("/api/spots/{spot_id}/reprocess")
def api_spot_reprocess(spot_id: str):
    """Chạy lại từ ảnh gốc đã lưu (ví dụ sau khi đổi cỡ bảng). Giữ tên, vị trí, hướng; BỎ vùng AI đã ẩn và vùng vẽ tay."""
    raw = store.read_photo(spot_id, "orig")
    if raw is None:
        raise ApiError(404, "Không còn ảnh gốc của điểm này.")
    snap = store.snapshot()
    _spot_or_404(snap, spot_id)
    settings = snap["settings"]
    try:
        rec, bgr = core.process_photo(raw, settings["marker_size_mm"], settings["max_range_m"], _INFER)
    except core.PhotoError as exc:
        raise ApiError(422, str(exc)) from None
    store.save_photo_files(spot_id, None, core.encode_jpg(bgr, 2048, 88), core.encode_jpg(bgr, 480, 80))
    with store.Tx() as data:
        s = _spot_or_404(data, spot_id)
        keep = {k: s.get(k) for k in ("id", "seq", "name", "placement", "include")}
        s.clear()
        s.update(rec)
        s.update(keep)
        out = _public_spot(s)
    return {"ok": True, "spot": out, "summary": core.summarize(store.snapshot())}


@app.post("/api/settings")
def api_settings(body: dict = Body(...)):
    with store.Tx() as data:
        st = data["settings"]
        if "title" in body:
            t = body["title"]
            if not isinstance(t, str) or not (1 <= len(t.strip()) <= 100):
                raise ApiError(422, "Tiêu đề cần từ 1 đến 100 ký tự.")
            st["title"] = t.strip()
        if "az_global" in body:
            st["az_global"] = _num(body, "az_global", -720.0, 720.0) % 360.0
        if "marker_size_mm" in body:
            st["marker_size_mm"] = _num(body, "marker_size_mm", 10.0, 5000.0)
        if "max_range_m" in body:
            st["max_range_m"] = _num(body, "max_range_m", 1.0, 50.0)
    return _state_payload()


@app.get("/api/spots/{spot_id}/image")
def api_image(spot_id: str, kind: str = Query("full")):
    if kind == "overlay":
        full = store.read_photo(spot_id, "full")
        snap = store.snapshot()
        s = store.get_spot(snap, spot_id) if store.is_valid_id(spot_id) else None
        if full is None or s is None:
            raise ApiError(404, "Không có ảnh.")
        import cv2
        import numpy as np
        bgr = cv2.imdecode(np.frombuffer(full, np.uint8), cv2.IMREAD_COLOR)
        data = core.encode_jpg(core.render_overlay(bgr, s), None, 85)
    elif kind in ("full", "thumb"):
        data = store.read_photo(spot_id, kind)
    else:
        raise ApiError(422, "Loại ảnh không hợp lệ.")
    if data is None:
        raise ApiError(404, "Không có ảnh.")
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=60"})


# ---------------------------------------------------------------- xuất bản trình bày
@app.post("/api/export/start")
def api_export_start(body: dict = Body(default={})):
    with_tiles = body.get("with_tiles", True)
    if not isinstance(with_tiles, bool):
        raise ApiError(422, "'with_tiles' phải là đúng/sai.")
    ok, msg = export.start(with_tiles)
    if not ok:
        raise ApiError(409, msg)
    return {"ok": True, "status": export.status()}


@app.get("/api/export/status")
def api_export_status():
    return {"ok": True, "status": export.status()}


# ---------------------------------------------------------------- trang tĩnh
def _static(rel: str):
    p = (WEB_DIR / rel).resolve()
    if not str(p).startswith(str(WEB_DIR.resolve())) or not p.is_file():
        raise ApiError(404, "Không tìm thấy.")
    return FileResponse(p, headers={"Cache-Control": "no-cache"})


@app.get("/")
def index_page():
    return _static("index.html")


@app.get("/phone")
def phone_page():
    return _static("phone.html")


@app.get("/web/{path:path}")
def web_files(path: str):
    return _static(path)
