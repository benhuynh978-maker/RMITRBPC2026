"""
Lưu trữ của công cụ khảo sát (exp03). Mọi thứ nằm trong MỘT thư mục dữ liệu riêng (mặc định exp03/data, đổi bằng
biến môi trường SURVEY_DATA_DIR; đường dẫn đọc MỖI LẦN gọi để test đổi được). KHÔNG đụng dữ liệu của webtest.

  data/spots.json        : {"settings": {...}, "spots": [...]}  (ghi nguyên tử)
  data/photos/<id>.orig  : bytes ảnh GỐC điện thoại gửi (giữ nguyên, có EXIF) - chỉ để lưu, không đưa ra mạng
  data/photos/<id>.jpg   : ảnh đã xoay đúng chiều, cạnh dài <= 2048 px, KHÔNG có EXIF (ảnh dùng để hiển thị / xuất)
  data/photos/<id>_t.jpg : ảnh thu nhỏ 480 px
  data/tiles/z/x/y.png   : ô bản đồ nền đã tải (cho bản trình bày không cần mạng)
  data/exports/          : bản trình bày đã xuất
  data/access_code.txt   : mã truy cập 6 số
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import uuid
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_CODE_RE = re.compile(r"^\d{6}$")

DEFAULT_SETTINGS = {
    "title": "Bản đồ rác khu vực trường",
    "az_global": 0.0,          # hướng chung của cạnh +Y của bảng (0 = Bắc, 90 = Đông)
    "marker_size_mm": 250.0,   # cạnh vùng mã của tờ bảng
    "max_range_m": 12.0,       # tầm xa vẽ "vùng camera thấy"
    "next_seq": 1,
}

_lock = threading.RLock()
_state = None            # cache trong RAM: {"path": str, "data": {...}}


def data_dir() -> Path:
    return Path(os.environ.get("SURVEY_DATA_DIR") or (HERE / "data"))


def photos_dir() -> Path:
    return data_dir() / "photos"


def tiles_dir() -> Path:
    return data_dir() / "tiles"


def exports_dir() -> Path:
    return data_dir() / "exports"


def folder_in_dir() -> Path:
    """Thư mục thả ảnh (cách 1: chép file) - cố định, KHÔNG nhận đường dẫn tuỳ ý từ mạng."""
    return Path(os.environ.get("SURVEY_FOLDER_IN") or (HERE / "thu_muc_anh"))


def is_valid_id(x) -> bool:
    return isinstance(x, str) and bool(_ID_RE.match(x))


def new_id() -> str:
    return secrets.token_hex(8)


def write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
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


# ---------------------------------------------------------------- trạng thái (spots.json)
def _path() -> Path:
    return data_dir() / "spots.json"


def _load_locked() -> dict:
    global _state
    p = str(_path())
    if _state is not None and _state["path"] == p:
        return _state["data"]
    data = {"settings": dict(DEFAULT_SETTINGS), "spots": []}
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data["settings"].update({k: v for k, v in (raw.get("settings") or {}).items() if k in DEFAULT_SETTINGS})
            data["spots"] = [s for s in (raw.get("spots") or []) if isinstance(s, dict) and is_valid_id(s.get("id"))]
    except (OSError, ValueError):
        pass
    _state = {"path": p, "data": data}
    return data


def reset_cache() -> None:
    global _state
    with _lock:
        _state = None


class Tx:
    """Giữ khoá, trả dict trạng thái; thoát khối `with` thì ghi file (trừ khi có lỗi)."""

    def __enter__(self):
        _lock.acquire()
        self.data = _load_locked()
        return self.data

    def __exit__(self, et, ev, tb):
        try:
            if et is None:
                write_json_atomic(_path(), self.data)
            else:
                reset_cache()   # bỏ phần thay đổi dở dang, lần sau đọc lại từ đĩa
        finally:
            _lock.release()
        return False


def snapshot() -> dict:
    """Bản sao sâu chỉ để đọc."""
    with _lock:
        return json.loads(json.dumps(_load_locked()))


def get_spot(data: dict, spot_id: str) -> Optional[dict]:
    for s in data["spots"]:
        if s["id"] == spot_id:
            return s
    return None


# ---------------------------------------------------------------- ảnh
def save_photo_files(spot_id: str, orig: Optional[bytes], full_jpg: Optional[bytes], thumb_jpg: Optional[bytes]) -> None:
    d = photos_dir()
    if orig is not None:
        write_bytes_atomic(d / f"{spot_id}.orig", orig)
    if full_jpg is not None:
        write_bytes_atomic(d / f"{spot_id}.jpg", full_jpg)
    if thumb_jpg is not None:
        write_bytes_atomic(d / f"{spot_id}_t.jpg", thumb_jpg)


def read_photo(spot_id: str, kind: str) -> Optional[bytes]:
    if not is_valid_id(spot_id):
        return None
    name = {"orig": f"{spot_id}.orig", "full": f"{spot_id}.jpg", "thumb": f"{spot_id}_t.jpg"}.get(kind)
    if not name:
        return None
    try:
        return (photos_dir() / name).read_bytes()
    except OSError:
        return None


def delete_photo_files(spot_id: str) -> None:
    if not is_valid_id(spot_id):
        return
    for name in (f"{spot_id}.orig", f"{spot_id}.jpg", f"{spot_id}_t.jpg"):
        try:
            (photos_dir() / name).unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- mã truy cập
_code_lock = threading.Lock()


def get_access_code() -> str:
    env = (os.environ.get("SURVEY_ACCESS_CODE") or "").strip()
    if _CODE_RE.match(env):
        return env
    p = data_dir() / "access_code.txt"
    with _code_lock:
        try:
            v = p.read_text(encoding="utf-8").strip()
            if _CODE_RE.match(v):
                return v
        except OSError:
            pass
        v = f"{secrets.randbelow(1_000_000):06d}"
        write_bytes_atomic(p, v.encode("utf-8"))
        return v
