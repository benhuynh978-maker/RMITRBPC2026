"""
Đổi vùng rác (GeoJSON lon/lat) về HỆ TOẠ ĐỘ CỦA BẢNG: (Y dọc +Y, X dọc +X) tính bằng mét từ tâm bảng.
Đảo ngược đúng phép chiếu của máy chủ (project_mask.meters_to_latlon + marker_xy_to_enu).

Dùng chung cho máy chủ (server.py: đánh số vùng, ghi Y/X của từng vùng) và script doc_so_lieu.py.
KHÔNG loại vùng nào: tờ bảng (model hay khoanh nhầm thành rác) vẫn nằm trong danh sách, ở chỗ Y, X gần 0.
Hàm thuần, không đọc/ghi file.
"""
from __future__ import annotations

import math
from typing import List, Tuple

EARTH_RADIUS_M = 6378137.0  # cùng giá trị config.EARTH_RADIUS_M


def latlon_to_board(lat, lon, lat0, lon0, azimuth_deg):
    """lat/lon -> (x, y) mét trong hệ bảng (x dọc +X, y dọc +Y)."""
    north = math.radians(lat - lat0) * EARTH_RADIUS_M
    east = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    b = math.radians(float(azimuth_deg) % 360.0)
    c, s = math.cos(b), math.sin(b)
    # E = x c + y s ; N = -x s + y c  =>  x = E c - N s ; y = E s + N c
    return east * c - north * s, east * s + north * c


def _ring_area_centroid(pts):
    a = cx = cy = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cr = x1 * y2 - x2 * y1
        a += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    a *= 0.5
    if abs(a) < 1e-15:
        return 0.0, 0.0, 0.0
    return a, cx / (6 * a), cy / (6 * a)


def polygon_area_centroid(rings_xy):
    """rings_xy: [vòng ngoài, lỗ 1, ...] (mét). Trả (diện tích, tâm x, tâm y); lỗ được trừ ra."""
    tot = mx = my = 0.0
    for k, ring in enumerate(rings_xy):
        pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
        if len(pts) < 3:
            continue
        a, cx, cy = _ring_area_centroid(pts)
        w = abs(a) if k == 0 else -abs(a)
        tot += w
        mx += w * cx
        my += w * cy
    if abs(tot) < 1e-15:
        return 0.0, float("nan"), float("nan")
    return tot, mx / tot, my / tot


def feature_rings(geom):
    if not geom:
        return []
    if geom.get("type") == "Polygon":
        return [geom["coordinates"]]
    if geom.get("type") == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def feature_area_xy(feature, calib) -> Tuple[float, float, float]:
    """(diện tích m², x, y) của một Feature (Polygon/MultiPolygon, lon/lat) trong hệ bảng."""
    lat0, lon0 = calib["marker_latlon"]
    az = calib.get("azimuth_deg", 0.0)
    tot = mx = my = 0.0
    for poly in feature_rings((feature or {}).get("geometry")):
        rings = [[latlon_to_board(lat, lon, lat0, lon0, az) for lon, lat in ring] for ring in poly]
        a, cx, cy = polygon_area_centroid(rings)
        if a > 0 and not math.isnan(cx):
            tot += a
            mx += a * cx
            my += a * cy
    if tot <= 0:
        return 0.0, float("nan"), float("nan")
    return tot, mx / tot, my / tot


def annotate_regions(features: List[dict], calib: dict) -> List[dict]:
    """
    Ghi thêm cho MỌI vùng (kể cả vùng là tờ bảng — không loại gì): properties idx (số thứ tự 1..n),
    y_m, x_m (toạ độ tâm trong hệ bảng, mét, làm tròn 3 chữ số). Trả lại chính danh sách.
    """
    for i, f in enumerate(features, 1):
        _, x, y = feature_area_xy(f, calib)
        p = f.setdefault("properties", {})
        p["idx"] = i
        p["y_m"] = None if math.isnan(y) else round(y, 3)
        p["x_m"] = None if math.isnan(x) else round(x, 3)
    return features
