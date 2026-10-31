"""
Lưu trữ file của webtest (đường dẫn đọc từ biến môi trường MỖI LẦN gọi nên test đổi được thư mục):

  WEBTEST_CALIB_DIR  (mặc định exp02/calibration)  : chứa WEB-DEMO.json
  WEBTEST_DATA_DIR   (mặc định exp02/webtest/data)  : chứa pending/<id>.json, inbox/<id>.bin + <id>.json,
                                                      observations.json và access_code.txt
  WEBTEST_ACCESS_CODE (tuỳ chọn)                    : ghi đè mã truy cập 6 số (dùng cho test)

Mọi lần ghi đều NGUYÊN TỬ (ghi file tạm cùng thư mục rồi os.replace).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import List, Optional

import config

CAMERA_ID = "WEB-DEMO"
PENDING_MAX_AGE_S = 24 * 3600
PENDING_MAX_COUNT = 20
OBSERVATIONS_MAX = 50
INBOX_MAX_AGE_S = 24 * 3600
INBOX_MAX_COUNT = 10
_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_CODE_RE = re.compile(r"^\d{6}$")

_obs_lock = threading.Lock()
_inbox_lock = threading.Lock()
_code_lock = threading.Lock()
_last_ns = 0


def calib_dir() -> Path:
    return Path(os.environ.get("WEBTEST_CALIB_DIR") or config.CALIBRATION_DIR)


def data_dir() -> Path:
    return Path(os.environ.get("WEBTEST_DATA_DIR") or (Path(__file__).resolve().parent / "data"))


def calibration_path() -> Path:
    return calib_dir() / f"{CAMERA_ID}.json"


def write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------- pending (kết quả hiệu chỉnh chưa lưu) ----------------
def valid_id(value: str) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value))


def _pending_dir() -> Path:
    return data_dir() / "pending"


def cleanup_pending() -> None:
    """Xoá pending cũ hơn 24 giờ, rồi giữ tối đa 20 file mới nhất."""
    d = _pending_dir()
    if not d.is_dir():
        return
    now = time.time()
    files = []
    for p in d.glob("*.json"):
        try:
            files.append((p.stat().st_mtime, p))
        except OSError:
            continue
    keep = []
    for mtime, p in files:
        if now - mtime > PENDING_MAX_AGE_S:
            _unlink(p)
        else:
            keep.append((mtime, p))
    keep.sort(key=lambda x: x[0], reverse=True)
    for _, p in keep[PENDING_MAX_COUNT:]:
        _unlink(p)


def _unlink(p: Path) -> None:
    try:
        p.unlink()
    except OSError:
        pass


def save_pending(calibration_id: str, payload: dict) -> None:
    write_json_atomic(_pending_dir() / f"{calibration_id}.json", payload)
    cleanup_pending()


def load_pending(calibration_id: str) -> Optional[dict]:
    if not valid_id(calibration_id):
        return None
    p = _pending_dir() / f"{calibration_id}.json"
    if not p.is_file():
        return None
    try:
        return read_json(p)
    except (OSError, ValueError):
        return None


# ---------------- calibration ----------------
def load_calibration() -> Optional[dict]:
    p = calibration_path()
    if not p.is_file():
        return None
    return read_json(p)


# ---------------- observations ----------------
def _obs_path() -> Path:
    return data_dir() / "observations.json"


def list_observations() -> List[dict]:
    with _obs_lock:
        return _read_obs()


def _read_obs() -> List[dict]:
    p = _obs_path()
    if not p.is_file():
        return []
    try:
        data = read_json(p)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def add_observation(obs: dict) -> None:
    with _obs_lock:
        items = _read_obs()
        items.append(obs)
        write_json_atomic(_obs_path(), items[-OBSERVATIONS_MAX:])


def clear_observations() -> None:
    with _obs_lock:
        write_json_atomic(_obs_path(), [])


# ---------------- mã truy cập ----------------
def access_code_path() -> Path:
    return data_dir() / "access_code.txt"


def get_access_code() -> str:
    """
    Mã truy cập 6 chữ số. Env WEBTEST_ACCESS_CODE (nếu có) ghi đè. Nếu không: đọc data/access_code.txt;
    chưa có (hoặc file hỏng) thì sinh một mã bằng `secrets` và ghi nguyên tử - các lần chạy sau dùng lại đúng mã đó.
    """
    env = (os.environ.get("WEBTEST_ACCESS_CODE") or "").strip()
    if env:
        return env
    p = access_code_path()
    with _code_lock:
        try:
            code = p.read_text(encoding="utf-8").strip()
            if _CODE_RE.match(code):
                return code
        except OSError:
            pass
        code = f"{secrets.randbelow(1_000_000):06d}"
        write_bytes_atomic(p, (code + "\n").encode("ascii"))
        return code


# ---------------- inbox (ảnh điện thoại gửi cho laptop; lưu BYTES GỐC để còn EXIF) ----------------
def _inbox_dir() -> Path:
    return data_dir() / "inbox"


def _next_ns() -> int:
    """Thời điểm tăng NGHIÊM NGẶT (đồng hồ Windows thô có thể trả cùng giá trị) để sắp xếp 'mới nhất' không bị hoà."""
    global _last_ns
    _last_ns = max(time.time_ns(), _last_ns + 1)
    return _last_ns


def _cleanup_inbox() -> None:
    """Gọi khi đang giữ _inbox_lock: xoá mục cũ hơn 24 giờ (và .bin mồ côi), rồi giữ tối đa 10 mục mới nhất."""
    d = _inbox_dir()
    if not d.is_dir():
        return
    now = time.time()
    keep = []
    for jp in d.glob("*.json"):
        bp = jp.with_suffix(".bin")
        try:
            mtime = jp.stat().st_mtime
        except OSError:
            continue
        if now - mtime > INBOX_MAX_AGE_S or not bp.is_file():
            _unlink(jp)
            _unlink(bp)
            continue
        try:
            order = int(read_json(jp).get("created_ns", 0))
        except (OSError, ValueError, AttributeError, TypeError):
            _unlink(jp)
            _unlink(bp)
            continue
        keep.append((order, jp))
    keep.sort(key=lambda x: x[0], reverse=True)
    for _, jp in keep[INBOX_MAX_COUNT:]:
        _unlink(jp)
        _unlink(jp.with_suffix(".bin"))
    for bp in d.glob("*.bin"):  # .bin không có .json (ghi dở) và đã quá cũ
        try:
            if not bp.with_suffix(".json").exists() and now - bp.stat().st_mtime > INBOX_MAX_AGE_S:
                _unlink(bp)
        except OSError:
            continue


def save_inbox(inbox_id: str, raw: bytes, meta: dict) -> dict:
    """Ghi bytes gốc rồi mới ghi json (json có mặt = mục đủ cặp). Trả meta đầy đủ (có created_ns)."""
    with _inbox_lock:
        full = {**meta, "id": inbox_id, "created_ns": _next_ns(), "size_bytes": len(raw)}
        write_bytes_atomic(_inbox_dir() / f"{inbox_id}.bin", raw)
        write_json_atomic(_inbox_dir() / f"{inbox_id}.json", full)
        _cleanup_inbox()
        return full


def list_inbox() -> List[dict]:
    """Meta các mục còn hạn, mới nhất trước (gồm cả thumb_jpg_b64)."""
    with _inbox_lock:
        _cleanup_inbox()
        d = _inbox_dir()
        items = []
        if d.is_dir():
            for jp in d.glob("*.json"):
                try:
                    m = read_json(jp)
                except (OSError, ValueError):
                    continue
                if isinstance(m, dict) and "created_ns" in m:
                    items.append(m)
        items.sort(key=lambda m: m["created_ns"], reverse=True)
        return items


def load_inbox_bytes(inbox_id: str) -> Optional[bytes]:
    """Bytes gốc của ảnh trong inbox; None nếu id sai dạng / không tồn tại / đã hết hạn."""
    if not valid_id(inbox_id):
        return None
    with _inbox_lock:
        _cleanup_inbox()
        d = _inbox_dir()
        if not (d / f"{inbox_id}.json").is_file():
            return None
        try:
            return (d / f"{inbox_id}.bin").read_bytes()
        except OSError:
            return None
