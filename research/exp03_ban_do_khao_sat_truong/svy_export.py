"""
Xuất BẢN TRÌNH BÀY chạy không cần mạng, không cần máy chủ: thư mục data/exports/trinh_bay/ (và trinh_bay.zip) gồm
  index.html + viewer.js + viewer.css   trang xem bản đồ (mở bằng cách bấm đúp, file://)
  data.js                               dữ liệu (window.SURVEY = {...}); là .js để mở được từ file://
  leaflet/                              thư viện bản đồ (bản sao trong web/vendor/leaflet)
  tiles/z/x/y.png                       ô bản đồ nền đã tải quanh khu vực khảo sát (Internet chỉ cần ở bước này, một lần)
  photos/<id>.jpg, _t.jpg, _ov.jpg      ảnh làm bằng chứng (đã bỏ EXIF/GPS, giữ giờ chụp trong data.js), ảnh thu nhỏ, ảnh + vùng AI

Ô bản đồ nền tải từ OpenStreetMap France (cùng nguồn với webtest). Số ô nhỏ (tối đa MAX_TILES), có giới hạn tốc độ,
có User-Agent mô tả, ô đã tải được giữ ở data/tiles để lần xuất sau không tải lại.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

import svy_core as core
import svy_store as store

HERE = Path(__file__).resolve().parent
VIEWER_DIR = HERE / "viewer"
LEAFLET_DIR = HERE / "web" / "vendor" / "leaflet"
DEFAULT_TILE_URL = "https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png"
USER_AGENT = "CleanSight-school-survey/1.0 (one-off offline cache for a small school survey; python-urllib)"
MARGIN_M = 60.0
ZOOM_MIN, ZOOM_MAX_NATIVE = 16, 20
MAX_TILES = 500

_lock = threading.Lock()
_status: dict = {"state": "idle"}
_thread = None


def tile_url_template() -> str:
    return os.environ.get("SURVEY_TILE_URL") or DEFAULT_TILE_URL


def tile_delay_s() -> float:
    try:
        return max(0.0, float(os.environ.get("SURVEY_TILE_DELAY", "0.7")))
    except ValueError:
        return 0.7


# ---------------------------------------------------------------- ô bản đồ
def lonlat_to_tile(lat: float, lon: float, z: int) -> Tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat = max(-85.0511, min(85.0511, lat))
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def plan_tiles(south: float, west: float, north: float, east: float) -> Tuple[List[Tuple[int, int, int]], int]:
    """Danh sách ô (z, x, y) phủ khung, từ zoom 16 đến mức cao nhất mà tổng không quá MAX_TILES (tối thiểu 17)."""
    best: List[Tuple[int, int, int]] = []
    zmax_used = ZOOM_MIN
    for zmax in range(ZOOM_MIN, ZOOM_MAX_NATIVE + 1):
        tiles = []
        for z in range(ZOOM_MIN, zmax + 1):
            x0, y1 = lonlat_to_tile(south, west, z)
            x1, y0 = lonlat_to_tile(north, east, z)
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    tiles.append((z, x, y))
        if len(tiles) > MAX_TILES and zmax > 17:
            break
        best, zmax_used = tiles, zmax
    return best, zmax_used


def _fetch_tile(z: int, x: int, y: int) -> bytes:
    url = tile_url_template().replace("{s}", "abc"[(x + y) % 3]).replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            if len(data) < 100:
                raise urllib.error.URLError("ô bản đồ rỗng")
            return data
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5)
    raise last  # type: ignore[misc]


# ---------------------------------------------------------------- dữ liệu cho trang xem
def _fmt_dt(local_iso: str) -> str:
    try:
        return datetime.strptime(local_iso, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return local_iso or ""


def build_dataset(snap: dict, tiles_info: dict) -> dict:
    settings = snap["settings"]
    spots = [s for s in snap["spots"] if s.get("status") == "ok" and s.get("include", True) and core.is_placed(s)]
    spots.sort(key=lambda s: s.get("seq", 0))
    summ = core.summarize(snap)
    out_spots = []
    for s in spots:
        p = s["placement"]
        az = core.effective_az(s, settings)
        lat0, lon0 = p["lat"], p["lon"]
        regions = []
        for r in core.visible_regions(s):
            regions.append({
                "kind": r["kind"], "area_m2": r["area_m2"],
                "ring": core.ring_to_lonlat(r["ring_m"], lat0, lon0, az),
                "holes": [core.ring_to_lonlat(h, lat0, lon0, az) for h in r.get("holes_m", [])],
                "conf": r.get("conf"),
            })
        a_manual = sum(r["area_m2"] for r in s["manual_regions"])
        total = core.spot_area_m2(s)
        out_spots.append({
            "id": s["id"], "seq": s["seq"], "name": s["name"], "lat": lat0, "lon": lon0, "az": round(az, 2),
            "captured": _fmt_dt(s.get("captured_local")), "captured_iso": s.get("captured_local"),
            "time_source": s.get("time_source"),
            "area_m2": round(total, 2), "area_manual_m2": round(a_manual, 2),
            "n_ai": sum(1 for r in s["ai_regions"] if not r.get("hidden")), "n_manual": len(s["manual_regions"]),
            "conf": s.get("mean_conf"), "fov_deg": s.get("fov_deg"), "fov_source": s.get("fov_source"),
            "side_px_min": s.get("side_px_min"),
            "regions": regions,
            "footprint": core.ring_to_lonlat(s["footprint_m"], lat0, lon0, az) if s.get("footprint_m") else [],
            "board": core.ring_to_lonlat(s["board_m"], lat0, lon0, az) if s.get("board_m") else [],
            "photo": f"photos/{s['id']}.jpg", "photo_overlay": f"photos/{s['id']}_ov.jpg", "thumb": f"photos/{s['id']}_t.jpg",
        })
    dates = sorted({(x.get("captured_iso") or "")[:10] for x in out_spots if x.get("captured_iso")})
    def d(s):
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    when = "" if not dates else (f" ngày {d(dates[0])}" if len(dates) == 1 else f" từ {d(dates[0])} đến {d(dates[-1])}")
    lines = [
        f"Khảo sát {len(out_spots)} điểm{when}. Số liệu chỉ tính ở những điểm đã chụp, không phải toàn bộ khu vực.",
        "Vùng rác do AI khoanh từ ảnh (AI còn bỏ sót rác)"
        + (f"; kèm {summ['n_manual_regions']} vùng vẽ tay bằng tay ({summ['area_manual_m2']:.2f} m²)." if summ["n_manual_regions"] else "."),
        "Vị trí mỗi điểm đặt bằng tay trên bản đồ nên sai số vài mét; diện tích tính từ một ảnh, mặt đất coi là phẳng.",
    ]
    n_def = sum(1 for x in out_spots if x["fov_source"] == "default")
    if n_def:
        lines.append(f"{n_def} ảnh không có thông tin tiêu cự nên dùng góc nhìn mặc định (diện tích có thể lệch).")
    if summ["overlaps"]:
        lines.append("Có điểm chụp trùng một vùng đất, diện tích có thể bị tính hai lần: "
                     + "; ".join(f"{o['a_name']} và {o['b_name']} ≈ {o['m2']} m²" for o in summ["overlaps"][:5]) + ".")
    return {
        "title": settings["title"], "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "totals": {"spots": len(out_spots), "area_m2": summ["area_m2"], "n_ai": summ["n_ai_regions"],
                   "n_manual": summ["n_manual_regions"], "area_manual_m2": summ["area_manual_m2"], "overlaps": summ["overlaps"]},
        "notes": lines, "tiles": tiles_info, "spots": out_spots,
    }


def _bounds(spots: List[dict]) -> Tuple[float, float, float, float]:
    pts = []
    for s in spots:
        pts.append([s["lat"], s["lon"]])
        for r in s["regions"]:
            pts += r["ring"]
        pts += s["footprint"]
    a = np.array(pts, dtype=np.float64)
    south, west = a.min(axis=0)
    north, east = a.max(axis=0)
    lat_c = (south + north) / 2
    dlat = MARGIN_M / 111_320.0
    dlon = MARGIN_M / (111_320.0 * math.cos(math.radians(lat_c)))
    return float(south - dlat), float(west - dlon), float(north + dlat), float(east + dlon)


# ---------------------------------------------------------------- chạy xuất
def status() -> dict:
    with _lock:
        return dict(_status)


def _set(**kw) -> None:
    with _lock:
        _status.update(kw)


def start(with_tiles: bool = True) -> Tuple[bool, str]:
    global _thread
    with _lock:
        if _status.get("state") == "running":
            return False, "Đang xuất, đợi xong đã."
        _status.clear()
        _status.update({"state": "running", "step": "Chuẩn bị", "done": 0, "total": 0, "message": ""})
    snap = store.snapshot()
    ok_spots = [s for s in snap["spots"] if s.get("status") == "ok" and s.get("include", True) and core.is_placed(s)]
    if not ok_spots:
        _set(state="error", message="Chưa có điểm nào đã đặt vị trí trên bản đồ.")
        return False, "Chưa có điểm nào đã đặt vị trí trên bản đồ."
    _thread = threading.Thread(target=_run, args=(with_tiles,), daemon=True, name="survey-export")
    _thread.start()
    return True, ""


def _run(with_tiles: bool) -> None:
    try:
        snap = store.snapshot()
        data0 = build_dataset(snap, {"have": False})
        if not data0["spots"]:
            raise RuntimeError("Chưa có điểm nào đã đặt vị trí trên bản đồ.")
        south, west, north, east = _bounds(data0["spots"])
        tiles_info = {"have": False}
        got: List[Tuple[int, int, int]] = []
        failed = 0
        planned: List[Tuple[int, int, int]] = []
        zmax = ZOOM_MIN
        if with_tiles:
            planned, zmax = plan_tiles(south, west, north, east)
            todo = [t for t in planned if not (store.tiles_dir() / str(t[0]) / str(t[1]) / f"{t[2]}.png").is_file()]
            _set(step="Tải bản đồ nền", done=0, total=len(todo))
            for i, (z, x, y) in enumerate(todo, 1):
                try:
                    png = _fetch_tile(z, x, y)
                    store.write_bytes_atomic(store.tiles_dir() / str(z) / str(x) / f"{y}.png", png)
                except Exception:  # noqa: BLE001
                    failed += 1
                _set(done=i)
                time.sleep(tile_delay_s())
            got = [t for t in planned if (store.tiles_dir() / str(t[0]) / str(t[1]) / f"{t[2]}.png").is_file()]
            tiles_info = {"have": bool(got), "min": ZOOM_MIN, "max": zmax, "wanted": len(planned), "got": len(got),
                          "failed": failed, "bounds": [[south, west], [north, east]]}

        _set(step="Ghi thư mục trình bày", done=0, total=0)
        data = build_dataset(snap, tiles_info)
        out = store.exports_dir() / "trinh_bay"
        tmp = store.exports_dir() / "trinh_bay.dang_ghi"
        if tmp.exists():
            shutil.rmtree(tmp)
        (tmp / "photos").mkdir(parents=True)
        for name in ("index.html", "viewer.js", "viewer.css"):
            shutil.copyfile(VIEWER_DIR / name, tmp / name)
        shutil.copytree(LEAFLET_DIR, tmp / "leaflet")
        for z, x, y in got:
            dst = tmp / "tiles" / str(z) / str(x) / f"{y}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(store.tiles_dir() / str(z) / str(x) / f"{y}.png", dst)
        by_id = {s["id"]: s for s in snap["spots"]}
        for sp in data["spots"]:
            full = store.read_photo(sp["id"], "full")
            if full is None:
                continue
            bgr = cv2.imdecode(np.frombuffer(full, np.uint8), cv2.IMREAD_COLOR)
            (tmp / sp["photo"]).write_bytes(core.encode_jpg(bgr, 1600, 85))           # đã bỏ EXIF (mã hoá lại từ pixel)
            (tmp / sp["thumb"]).write_bytes(core.encode_jpg(bgr, 360, 80))
            (tmp / sp["photo_overlay"]).write_bytes(core.encode_jpg(core.render_overlay(bgr, by_id[sp["id"]]), 1600, 85))
        (tmp / "data.js").write_text("window.SURVEY = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
        if out.exists():
            shutil.rmtree(out)
        os.replace(tmp, out)
        zip_base = store.exports_dir() / "trinh_bay"
        zpath = shutil.make_archive(str(zip_base), "zip", root_dir=str(out))
        _set(state="done", step="Xong", folder=str(out), index=str(out / "index.html"), zip=zpath,
             n_spots=len(data["spots"]), tiles=tiles_info, message="")
    except Exception as exc:  # noqa: BLE001
        _set(state="error", message=f"Xuất không thành công: {exc}")
