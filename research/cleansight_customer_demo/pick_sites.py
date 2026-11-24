"""
Chọn VỊ TRÍ camera cho bộ dữ liệu demo "khách hàng đã lắp xong" (xem README.md). Chạy MỘT LẦN, cần mạng; kết quả (camera_sites.json)
được lưu trong repo nên make_demo_data.py chạy offline.

Vì sao không lấy hình học đường từ OpenStreetMap (Overpass): dịch vụ đó bị chặn ở môi trường làm việc. Thay vào đó script tải một số ô bản đồ
(OpenStreetMap France, mức zoom 18, vài trăm ô, mỗi giây tối đa ~1.6 yêu cầu, có User-Agent mô tả, lưu cache để không tải lại) và dò mặt đường
bằng MÀU của kiểu bản đồ (đường vàng nhạt / cam / hồng đỏ là đường chính). Từ đó:
  - đặt "miệng cống" sát mép đường (lề đường), camera trên vỉa hè cách miệng cống vài mét, nhìn về phía miệng cống;
  - chỉ nhận đoạn đường THẲNG đủ dài, bề rộng hợp lý, không dính một đường khác ngay phía sau mép.
Vị trí camera là GIẢ ĐỊNH (không phải lắp đặt thật); dữ liệu bản đồ © OpenStreetMap contributors (ODbL).

Chạy:  python pick_sites.py [--cache-dir THƯ_MỤC_TẠM] [--seed 2026]
"""
from __future__ import annotations

import argparse
import io
import json
import math
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE / "camera_sites.json"

ZOOM = 18
TILE_URL = "https://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png"
USER_AGENT = "CleanSightDemoBuilder/1.0 (one-off development use, a few hundred tiles in total)"
REQUEST_GAP_S = 0.6

# Vùng triển khai giả định (6 khu, mỗi khu ~17 camera, cách nhau vài km). Tên khu là giả định, không phải đơn vị hành chính.
ZONES = [
    ("Z1", (10.7765, 106.7000), 2300, 17),
    ("Z2", (10.8040, 106.7150), 2300, 17),
    ("Z3", (10.7600, 106.6550), 2300, 17),
    ("Z4", (10.8000, 106.6650), 2300, 17),
    ("Z5", (10.7450, 106.7020), 2300, 16),
    ("Z6", (10.8020, 106.7340), 2300, 16),
]
MIN_SPACING_M = 160.0
MAX_TILE_REQUESTS = 600   # trần số ô tải mới trong một lần chạy (dùng bản đồ công cộng một cách nhẹ nhàng)

# Màu nền đường chính của kiểu bản đồ OpenStreetMap France (đã quan sát trên ô thật): tertiary, primary/secondary, trunk.
ROAD_COLORS = [(255, 255, 179), (254, 215, 165), (247, 250, 191), (236, 152, 154), (249, 178, 156)]
COLOR_TOL = 6
WATER_COLORS = [(181, 208, 208), (170, 211, 223)]   # màu mặt nước (sông, kênh) của kiểu bản đồ này: camera không được đặt xuống nước


def tile_of(lat: float, lon: float, z: int = ZOOM):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return int(x), int(y), x - int(x), y - int(y)


def pixel_to_latlon(tx: int, ty: int, px: float, py: float, z: int = ZOOM):
    n = 2 ** z
    lon = (tx + px / 256.0) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * (ty + py / 256.0) / n))))
    return lat, lon


def metres_per_pixel(lat: float, z: int = ZOOM) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)


def haversine_m(a, b) -> float:
    r = 6371008.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class TileCache:
    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self.requests = 0
        self._last = 0.0

    def get(self, z: int, x: int, y: int) -> Image.Image:
        f = self.dir / f"{z}_{x}_{y}.png"
        if f.exists():
            return Image.open(f).convert("RGB")
        wait = REQUEST_GAP_S - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(TILE_URL.format(z=z, x=x, y=y), headers={"User-Agent": USER_AGENT})
        data = None
        for attempt in range(4):                       # mạng đôi khi ngắt kết nối giữa chừng: thử lại có giãn cách
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if attempt == 3:
                    raise
                time.sleep(2.0 * (attempt + 1))
        self._last = time.time()
        self.requests += 1
        f.write_bytes(data)
        return Image.open(io.BytesIO(data)).convert("RGB")


def road_mask(img: Image.Image) -> np.ndarray:
    a = np.asarray(img).astype(np.int16)
    m = np.zeros(a.shape[:2], dtype=bool)
    for c in ROAD_COLORS:
        m |= (np.abs(a - np.array(c, dtype=np.int16)).max(axis=2) <= COLOR_TOL)
    m = m.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))   # lấp chữ/mũi tên nằm trên mặt đường
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))    # bỏ nét mảnh, biểu tượng
    return m


def on_water(img: Image.Image, x: float, y: float, radius: int = 3) -> bool:
    """True nếu quanh điểm (x, y) của ô có từ 3 pixel mang màu mặt nước (hoặc điểm nằm ngoài ô)."""
    xi, yi = int(round(x)), int(round(y))
    if not (radius <= xi < 256 - radius and radius <= yi < 256 - radius):
        return True
    a = np.asarray(img.crop((xi - radius, yi - radius, xi + radius + 1, yi + radius + 1))).astype(np.int16)
    hits = np.zeros(a.shape[:2], dtype=bool)
    for c in WATER_COLORS:
        hits |= (np.abs(a - np.array(c, dtype=np.int16)).max(axis=2) <= 8)
    return int(hits.sum()) >= 3


def local_axis(mask: np.ndarray, cx: int, cy: int, radius: int = 22):
    """Hướng chính của mặt đường quanh (cx, cy) bằng PCA; trả (góc rad theo ảnh, tỉ lệ giãn dài) hoặc None."""
    h, w = mask.shape
    ys, xs = np.nonzero(mask[max(0, cy - radius): cy + radius + 1, max(0, cx - radius): cx + radius + 1])
    if len(xs) < 80:
        return None
    xs = xs + max(0, cx - radius) - cx
    ys = ys + max(0, cy - radius) - cy
    inside = xs * xs + ys * ys <= radius * radius
    xs, ys = xs[inside].astype(np.float64), ys[inside].astype(np.float64)
    if len(xs) < 80:
        return None
    cov = np.cov(np.vstack([xs, ys]))
    vals, vecs = np.linalg.eigh(cov)          # tăng dần
    if vals[0] <= 1e-6:
        return math.atan2(vecs[1, 1], vecs[0, 1]), 99.0
    return math.atan2(vecs[1, 1], vecs[0, 1]), float(vals[1] / vals[0])


def try_snap(mask: np.ndarray, dt: np.ndarray, rng: random.Random, lat0: float):
    """Tìm một điểm mép đường hợp lệ trong ô. Trả dict (theo pixel) hoặc None."""
    mpp = metres_per_pixel(lat0)
    ridge = (dt >= 4.5) & (dt == cv2.dilate(dt, np.ones((7, 7), np.uint8)))
    ys, xs = np.nonzero(ridge)
    keep = (xs >= 34) & (xs <= 221) & (ys >= 34) & (ys <= 221)
    pts = list(zip(xs[keep].tolist(), ys[keep].tolist()))
    rng.shuffle(pts)
    for cx, cy in pts[:60]:
        ax = local_axis(mask, cx, cy)
        if ax is None or ax[1] < 5.0:
            continue
        ang = ax[0]
        half = float(dt[cy, cx])
        width_m = 2.0 * half * mpp
        if not (5.0 <= width_m <= 22.0):
            continue
        side = rng.choice((-1, 1))
        nx, ny = -math.sin(ang) * side, math.cos(ang) * side     # pháp tuyến hướng ra ngoài đường (theo ảnh)
        # đi từ tim đường ra mép
        edge = None
        for s in np.arange(0.0, 45.0, 0.5):
            x, y = cx + nx * s, cy + ny * s
            xi, yi = int(round(x)), int(round(y))
            if not (0 <= xi < 256 and 0 <= yi < 256):
                break
            if mask[yi, xi] == 0:
                edge = s
                break
        if edge is None or not (half - 1.5 <= edge <= half + 3.0):
            continue
        # phía ngoài mép: 9 px (~5 m) không được là mặt đường khác
        clear = True
        for s in np.arange(edge, edge + 9.0, 1.0):
            xi, yi = int(round(cx + nx * s)), int(round(cy + ny * s))
            if not (0 <= xi < 256 and 0 <= yi < 256) or mask[yi, xi] == 1:
                clear = False
                break
        if not clear:
            continue
        # đoạn đường phải thẳng dọc hai bên điểm này: lấy 3 điểm dọc trục, mép cách tim gần như như nhau
        tx, ty = math.cos(ang), math.sin(ang)
        ok = True
        for off in (-12.0, 12.0):
            ex, ey = cx + tx * off, cy + ty * off
            e2 = None
            for s in np.arange(0.0, 40.0, 0.5):
                xi, yi = int(round(ex + nx * s)), int(round(ey + ny * s))
                if not (0 <= xi < 256 and 0 <= yi < 256):
                    break
                if mask[yi, xi] == 0:
                    e2 = s
                    break
            if e2 is None or abs(e2 - edge) > 2.5:
                ok = False
                break
        if not ok:
            continue
        curb = (cx + nx * (edge - 0.6), cy + ny * (edge - 0.6))   # điểm miệng cống: ngay trong mép đường (~0.35 m)
        return {"curb_px": curb, "out": (nx, ny), "axis_rad": ang, "width_m": width_m, "elong": ax[1]}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default=str(Path("/tmp") / "cleansight_demo_tiles"))
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    cache = TileCache(Path(args.cache_dir))
    sites, tried = [], 0

    for zid, (zlat, zlon), radius_m, count in ZONES:
        got, fails = 0, 0
        while got < count and fails < 400 and cache.requests < MAX_TILE_REQUESTS:
            r = radius_m * math.sqrt(rng.random())
            th = rng.random() * 2 * math.pi
            lat = zlat + (r * math.cos(th)) / 111320.0
            lon = zlon + (r * math.sin(th)) / (111320.0 * math.cos(math.radians(zlat)))
            tx, ty, _, _ = tile_of(lat, lon)
            img = cache.get(ZOOM, tx, ty)
            tried += 1
            mask = road_mask(img)
            if mask.sum() < 3000:
                fails += 1
                continue
            dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
            tile_lat, _ = pixel_to_latlon(tx, ty, 128, 128)
            snap = try_snap(mask, dt, rng, tile_lat)
            if snap is None:
                fails += 1
                continue
            mpp = metres_per_pixel(tile_lat)
            cpx, cpy = snap["curb_px"]
            nx, ny = snap["out"]
            drain_lat, drain_lon = pixel_to_latlon(tx, ty, cpx, cpy)
            if any(haversine_m((drain_lat, drain_lon), (s["drain"][0], s["drain"][1])) < MIN_SPACING_M for s in sites):
                fails += 1
                continue
            dist_m = round(rng.uniform(3.1, 4.4), 2)                                   # camera cách miệng cống (trên vỉa hè)
            cam_px = (cpx + nx * dist_m / mpp, cpy + ny * dist_m / mpp)
            if on_water(img, cam_px[0], cam_px[1]) or on_water(img, cpx, cpy):
                fails += 1
                continue
            cam_lat, cam_lon = pixel_to_latlon(tx, ty, cam_px[0], cam_px[1])
            out_bearing = (math.degrees(math.atan2(nx, -ny)) + 360.0) % 360.0           # hướng từ miệng cống ra phía vỉa hè
            axis_bearing = (math.degrees(math.atan2(math.cos(snap["axis_rad"]), -math.sin(snap["axis_rad"]))) + 360.0) % 360.0
            sites.append({
                "zone": zid,
                "drain": [round(drain_lat, 7), round(drain_lon, 7)],
                "camera": [round(cam_lat, 7), round(cam_lon, 7)],
                "camera_dist_m": dist_m,
                "out_bearing_deg": round(out_bearing, 1),                               # camera -> miệng cống = out_bearing + 180
                "road_axis_bearing_deg": round(axis_bearing % 180.0, 1),
                "road_width_m": round(snap["width_m"], 1),
                "tile": [ZOOM, tx, ty],
            })
            got += 1
        print(f"{zid}: {got}/{count} camera (thử {fails} lần thất bại), đã tải {cache.requests} ô", file=sys.stderr)
        if got < count:
            print(f"  CẢNH BÁO: khu {zid} chỉ chọn được {got}/{count}", file=sys.stderr)

    # đánh số ổn định theo khu, rồi theo vĩ độ giảm dần (Bắc -> Nam), kinh độ tăng dần
    out = []
    for zid, _c, _r, _n in ZONES:
        zs = sorted((s for s in sites if s["zone"] == zid), key=lambda s: (-s["drain"][0], s["drain"][1]))
        for i, s in enumerate(zs, 1):
            out.append({"id": f"{zid}-{i:03d}", **s})
    doc = {
        "note": "Vị trí camera GIẢ ĐỊNH cho bộ demo, đặt sát lề đường thật dò từ màu ô bản đồ OpenStreetMap France (© OpenStreetMap contributors, ODbL). "
                "Không phải lắp đặt thật. Sinh bởi pick_sites.py.",
        "seed": args.seed, "zoom": ZOOM, "cameras": out,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Đã ghi {len(out)} camera vào {OUT} ({cache.requests} ô tải mới, {tried} lần thử).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
