"""
Sinh bộ dữ liệu MÔ PHỎNG cho trang demo "bản đồ rác của một khách hàng đã lắp đặt xong" (xem README.md).

TẤT CẢ số liệu ở đây là GIẢ LẬP (có hạt giống cố định, chạy lại ra đúng dữ liệu cũ). Không phải đo thực tế, không phải khách hàng thật.
Cái gì là "thật" trong bộ dữ liệu: các LUẬT của sản phẩm, được dùng nguyên văn:
  - trạng thái cống = trung vị 5 lần đo gần nhất trong 15 phút, cần >= 3 lần, ngưỡng có trễ (vào 20/50, ra 12/35)  -> test_demo_data.py
    so sánh từng bước với mã thật ssc-v2/ssc-road-alerts/server/aggregation.js (chạy bằng Node);
  - các mức rác / mức che miệng cống theo ngưỡng trong server/config.js;
  - vùng nhìn thấy của camera tính bằng chính hàm của lõi vẽ rác lên bản đồ (project_mask.ground_footprint_polygon).

Mô hình (giả lập): 100 camera ở 6 khu, mỗi camera một miệng cống (ROI hình chữ nhật sát mép đường) + rác xung quanh. Trong 7 ngày:
rác tích tụ theo từng camera, 2 trận mưa (khung hình bị loại vì ngoài phạm vi, sau mưa rác tăng), đội dọn vệ sinh sáng mỗi ngày dọn
một phần camera (xác suất khác nhau theo camera); mỗi phút một khung ban ngày (06:00-18:00), có nhiễu đo, thỉnh thoảng một khung bị lệch hẳn
(để thấy tác dụng của trung vị). Một số camera mất kết nối, vài camera mới lắp (chưa đủ 3 lần đo).
Chỉ trạng thái HIỆN TẠI được xuất ra (không có lịch sử dài: backend thật chỉ giữ ~100 lần đo gần nhất mỗi camera).

Chạy:  python make_demo_data.py [--out ../../cleansight-site-v2/public/demo-data/city.json] [--seed 2026]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP02 = REPO / "research" / "exp02_ve_rac_len_ban_do"
if str(EXP02) not in sys.path:
    sys.path.append(str(EXP02))

import camera_model  # noqa: E402
import config as exp_config  # noqa: E402
import project_mask as pm  # noqa: E402

SITES = HERE / "camera_sites.json"
DEFAULT_OUT = REPO / "cleansight-site-v2" / "public" / "demo-data" / "city.json"

TZ = timezone(timedelta(hours=7))
AS_OF = datetime(2026, 11, 23, 14, 30, tzinfo=TZ)     # thời điểm "chụp" bộ dữ liệu (giả lập)
SIM_DAYS = 7
DAY_START_MIN, DAY_END_MIN = 6 * 60, 18 * 60          # camera chỉ chụp ban ngày (phạm vi sản phẩm)
IMG_W, IMG_H = 640, 480                               # ảnh ESP32
FOOTPRINT_RANGE_M = 12.0

# Luật của sản phẩm (ssc-v2/ssc-road-alerts/server/config.js) - test so sánh với bản thật
POLICY = {
    "waste": {"low": 1, "medium": 5, "high": 10, "critical": 20},
    "blockage": {"low": 20, "medium": 50, "high": 70, "critical": 90},
    "drain_state": {"window_size": 5, "min_readings": 3, "clean": {"enter": 50, "exit": 35}, "watch": {"enter": 20, "exit": 12}},
    "reading_max_age_min": 15,
}
DRAIN = POLICY["drain_state"]

# Loại camera (giả định): "good" = khu được dọn đều, "mid" = dọn có chọn lọc, "neglected" = hay bị bỏ sót (rác dồn lại, cống bị che dần).
# thr = mức che cống từ đó đội vệ sinh mới dọn (sáng ~08:30), service = xác suất được dọn khi vượt thr, rate = tích tụ (điểm %/giờ).
KINDS = {
    "good": {"rate": 0.10, "thr": 12.0, "service": 0.85, "x0": (0.0, 10.0)},
    "mid": {"rate": 0.24, "thr": 32.0, "service": 0.30, "x0": (0.0, 18.0)},
    "neglected": {"rate": 0.40, "thr": 35.0, "service": 0.14, "x0": (8.0, 30.0)},
}
# Xác suất (good, mid, neglected) theo khu (giả định: Z3 gần chợ, Z5 gần kênh bị bỏ sót nhiều hơn; Z2, Z6 thoáng hơn)
ZONE_KIND_P = {"Z1": (0.55, 0.27, 0.18), "Z2": (0.65, 0.24, 0.11), "Z3": (0.42, 0.30, 0.28),
               "Z4": (0.55, 0.27, 0.18), "Z5": (0.45, 0.28, 0.27), "Z6": (0.68, 0.22, 0.10)}

# Hai trận mưa giả lập (giờ địa phương): khung hình bị loại, sau mưa rác dồn vào cống
STORMS = [(datetime(2026, 11, 18, 15, 30, tzinfo=TZ), datetime(2026, 11, 18, 17, 30, tzinfo=TZ)),
          (datetime(2026, 11, 21, 6, 30, tzinfo=TZ), datetime(2026, 11, 21, 9, 0, tzinfo=TZ))]

N_OFFLINE_LONG, N_OFFLINE_RECENT, N_NEW = 3, 2, 3

SURGE_RANGE = (2.0, 12.0)                     # rác dồn vào cống sau mưa (điểm %), nhân với độ nhạy của camera


# ---------------------------------------------------------------------------------------
# Luật trạng thái cống (bản Python của server/aggregation.js: nextDrainState + computeDrainState)
# ---------------------------------------------------------------------------------------
def next_drain_state(previous: str | None, v: float) -> str:
    clean, watch = DRAIN["clean"], DRAIN["watch"]
    if previous == "clean":
        return "clean" if v >= clean["exit"] else "watch" if v >= watch["exit"] else "clear"
    if previous == "watch":
        return "clean" if v >= clean["enter"] else "clear" if v < watch["exit"] else "watch"
    return "clean" if v >= clean["enter"] else "watch" if v >= watch["enter"] else "clear"


def median_js(values: list[float]) -> float:
    s = sorted(values)
    m = len(s) >> 1
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def rank_of(value: float, thresholds: dict) -> int:
    return 4 if value >= thresholds["critical"] else 3 if value >= thresholds["high"] else 2 if value >= thresholds["medium"] else 1 if value >= thresholds["low"] else 0


LEVELS = ["normal", "low", "medium", "high", "critical"]


def waste_level(pct: float) -> str:
    return LEVELS[rank_of(pct, POLICY["waste"])]


def severity(waste: float, blockage: float | None) -> str:
    ranks = [rank_of(waste or 0, POLICY["waste"])]
    if isinstance(blockage, (int, float)):
        ranks.append(rank_of(blockage, POLICY["blockage"]))
    return LEVELS[max(ranks)]


class DrainTracker:
    """Một camera: nhận từng lần đo (phút, giá trị %), giữ drain_state như backend thật."""

    def __init__(self):
        self.readings: list[tuple[int, float]] = []   # mới nhất ở cuối
        self.state: str | None = None
        self.since: int | None = None
        self.smoothed: float | None = None
        self.reason: str = "no_data"
        self.window_count = 0

    def add(self, minute: int, value: float) -> None:
        self.readings.append((minute, value))
        if len(self.readings) > 100:                      # maxObservationsPerCamera
            self.readings = self.readings[-100:]
        recent = [r for r in reversed(self.readings) if minute - r[0] <= POLICY["reading_max_age_min"]][: DRAIN["window_size"]]
        self.window_count = len(recent)
        if len(recent) < DRAIN["min_readings"]:
            if self.state != "unknown":
                self.since = minute
            self.state, self.reason, self.smoothed = "unknown", "collecting", None
            return
        value_med = round(median_js([r[1] for r in recent]), 2)
        new_state = next_drain_state(self.state, value_med)
        if new_state != self.state:
            self.since = minute
        self.state, self.reason, self.smoothed = new_state, "ok", value_med


# ---------------------------------------------------------------------------------------
# Hình học cục bộ (mét, hệ Đông-Bắc quanh chân camera)
# ---------------------------------------------------------------------------------------
def shoelace(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def unit_from_bearing(deg: float) -> np.ndarray:
    r = math.radians(deg)
    return np.array([math.sin(r), math.cos(r)])


def inside(poly: np.ndarray, pts: np.ndarray, margin: float = 0.0) -> bool:
    contour = poly.astype(np.float32).reshape(-1, 1, 2)
    return all(cv2.pointPolygonTest(contour, (float(p[0]), float(p[1])), True) >= margin for p in pts)


def make_blob(rng: np.random.Generator, center: np.ndarray, area: float, axis_deg: float, elong: float = 1.0) -> np.ndarray:
    """Đa giác hình sao (luôn đơn, không tự cắt) có đúng diện tích `area` (m²), trục dài theo `axis_deg` (la bàn)."""
    m = int(rng.integers(10, 15))
    ang = np.linspace(0.0, 2.0 * math.pi, m, endpoint=False) + rng.normal(0.0, 0.1, m)
    ang.sort()
    p1, p2 = rng.uniform(0.0, 2.0 * math.pi, 2)
    r = 1.0 + 0.22 * np.cos(ang - p1) + 0.15 * np.cos(2 * ang - p2) + rng.normal(0.0, 0.07, m)
    r = np.clip(r, 0.45, None)
    local = np.stack([r * np.cos(ang) * elong, r * np.sin(ang) / elong], axis=1)
    local *= math.sqrt(area / max(shoelace(local), 1e-9))
    th = math.radians(90.0 - axis_deg)               # trục x địa phương -> hướng la bàn axis_deg
    rot = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    return local @ rot.T + center


RASTER_PX_PER_M = 100


def raster_overlap(roi: np.ndarray, blob: np.ndarray, center: np.ndarray) -> float:
    """Tỉ lệ diện tích ROI bị `blob` phủ (0..1), tính bằng tô pixel 1 cm quanh `center` (cửa sổ 4 m x 4 m)."""
    size = 4 * RASTER_PX_PER_M

    def draw(poly):
        pts = np.round((poly - center) * RASTER_PX_PER_M + size / 2).astype(np.int32).reshape(-1, 1, 2)
        m = np.zeros((size, size), np.uint8)
        cv2.fillPoly(m, [pts], 1)
        return m
    a, b = draw(roi), draw(blob)
    return float((a & b).sum()) / max(float(a.sum()), 1.0)


def fit_drain_blob(rng: np.random.Generator, roi: np.ndarray, roi_center: np.ndarray, axis_deg: float, coverage: float) -> np.ndarray:
    """Tạo một đám rác trên miệng cống sao cho phủ đúng `coverage` (0..1) diện tích ROI (tìm nhị phân theo kích thước)."""
    seed_state = rng.bit_generator.state
    center = roi_center + rng.normal(0.0, 0.03, 2)
    elong = float(rng.uniform(1.1, 1.7))
    lo, hi = 0.0004, 3.0
    best = None
    for _ in range(26):
        mid = 0.5 * (lo + hi)
        rng.bit_generator.state = seed_state            # cùng hình dạng, chỉ đổi kích thước
        rng.normal(0.0, 0.03, 2)
        rng.uniform(1.1, 1.7)
        blob = make_blob(rng, center, mid, axis_deg, elong)
        cov = raster_overlap(roi, blob, roi_center)
        best = blob
        if cov < coverage:
            lo = mid
        else:
            hi = mid
    return best


# ---------------------------------------------------------------------------------------
# Một camera
# ---------------------------------------------------------------------------------------
def camera_geometry(site: dict, rng: np.random.Generator) -> dict:
    """Vị trí, hướng, độ cao, vùng nhìn thấy (bằng hàm của sản phẩm), ROI cống, trục đường - tất cả theo mét Đông-Bắc quanh chân camera."""
    dist = float(site["camera_dist_m"])
    beta = (site["out_bearing_deg"] + 180.0) % 360.0                # hướng từ camera tới miệng cống
    height = float(rng.uniform(3.0, 3.8))
    heading = (beta + float(rng.uniform(-6.0, 6.0))) % 360.0        # camera nhìn gần đúng vào miệng cống
    pitch = math.atan2(height, dist) + math.radians(float(rng.uniform(-2.0, 2.0)))
    k = camera_model.build_camera_matrix(IMG_W, IMG_H, exp_config.DIAGONAL_FOV_DEG)
    r_mat = np.array([[1.0, 0.0, 0.0], [0.0, -math.sin(pitch), -math.cos(pitch)], [0.0, math.cos(pitch), -math.sin(pitch)]])
    c_world = np.array([0.0, 0.0, height])
    calib = {"R": r_mat.tolist(), "t": (-r_mat @ c_world).tolist(), "camera_matrix": k.tolist(), "image_size": [IMG_W, IMG_H],
             "marker_latlon": list(site["camera"]), "azimuth_deg": heading}
    poly_marker = pm.ground_footprint_polygon(calib, (IMG_W, IMG_H), FOOTPRINT_RANGE_M)
    e, n = pm.marker_xy_to_enu(poly_marker[:, 0], poly_marker[:, 1], heading)
    foot = np.stack([e, n], axis=1)
    n_in = unit_from_bearing(beta)                                  # pháp tuyến từ vỉa hè vào lòng đường
    drain = dist * n_in
    axis_deg = float(site["road_axis_bearing_deg"])
    u = unit_from_bearing(axis_deg)
    roi_len, roi_wid = float(rng.uniform(0.7, 1.0)), float(rng.uniform(0.4, 0.55))
    roi_center = drain + n_in * (roi_wid / 2.0 + 0.05)
    roi = np.array([roi_center + sx * (roi_len / 2.0) * u + sy * (roi_wid / 2.0) * n_in for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    return {"height": height, "heading": heading, "foot": foot, "foot_area": shoelace(foot), "drain": drain, "n_in": n_in, "u": u,
            "axis_deg": axis_deg, "roi": roi, "roi_center": roi_center, "R": r_mat, "t": -r_mat @ c_world, "K": k}


def roi_to_image(geo: dict) -> list[list[float]]:
    """Vùng cống (mét Đông-Bắc quanh chân camera) chiếu vào ảnh 640x480 bằng tư thế camera -> đa giác chuẩn hoá [0,1] (x phải, y xuống),
    đúng dạng `drain_roi.polygon` mà dashboard/backend lưu."""
    b = math.radians(geo["heading"])
    e, n = geo["roi"][:, 0], geo["roi"][:, 1]
    x = e * math.cos(b) - n * math.sin(b)
    y = e * math.sin(b) + n * math.cos(b)
    pts = np.stack([x, y, np.zeros_like(x)], axis=1)
    cam = pts @ geo["R"].T + geo["t"]
    uv = (cam @ geo["K"].T)
    uv = uv[:, :2] / uv[:, 2:3]
    norm = np.clip(uv / np.array([IMG_W, IMG_H]), 0.0, 1.0)
    return [[round(float(a), 4), round(float(c), 4)] for a, c in norm]


def litter_blobs(rng: np.random.Generator, geo: dict, target_area: float, avoid_center: np.ndarray, avoid_r: float = 0.55) -> list[np.ndarray]:
    """Rải các đám rác ngoài miệng cống, chủ yếu dọc rãnh/mép đường, đều nằm trong vùng camera thấy; tổng diện tích ~ target_area."""
    blobs: list[np.ndarray] = []
    total, tries = 0.0, 0
    while total < target_area * 0.97 and tries < 500 and len(blobs) < 30:
        tries += 1
        area = float(min(max(rng.lognormal(math.log(0.18), 0.8), 0.02), 1.8, target_area - total + 0.02))
        s = float(np.clip(rng.normal(0.0, 2.6), -6.5, 6.5))
        pick = rng.random()
        o = rng.uniform(-0.2, 0.9) if pick < 0.6 else rng.uniform(0.9, 4.2) if pick < 0.85 else rng.uniform(-1.3, -0.2)
        center = geo["drain"] + s * geo["u"] + o * geo["n_in"]
        if np.linalg.norm(center - avoid_center) < avoid_r + math.sqrt(area / math.pi):
            continue
        blob = make_blob(rng, center, area, geo["axis_deg"], float(rng.uniform(1.0, 1.9)))
        if not inside(geo["foot"], blob, 0.05):
            continue
        if any(np.linalg.norm(center - b.mean(axis=0)) < 0.22 + math.sqrt(area / math.pi) for b in blobs):
            continue
        blobs.append(blob)
        total += shoelace(blob)
    return blobs


def to_latlon_ring(site: dict, ring_en: np.ndarray) -> list[list[float]]:
    lat0, lon0 = site["camera"]
    out = []
    for e, n in ring_en:
        lat, lon = pm.meters_to_latlon(lat0, lon0, float(e), float(n))
        out.append([round(lat, 7), round(lon, 7)])
    return out


# ---------------------------------------------------------------------------------------
# Mô phỏng 7 ngày cho mọi camera
# ---------------------------------------------------------------------------------------
def simulate_camera(rng: np.random.Generator, site: dict, role: dict, start: datetime, n_minutes: int):
    """Trả (DrainTracker, danh sách lần đo (phút, blockage, waste) gần nhất). Chỉ giữ 100 lần đo gần nhất như backend thật."""
    n_steps = SIM_DAYS * 24 + 1                                      # mỗi giờ một bước, bắt đầu tại `start`
    kind = KINDS[role["kind"]]
    a = kind["rate"] * float(rng.lognormal(0.0, 0.5))
    susceptibility = float(rng.uniform(0.5, 1.5))
    x = np.empty(n_steps)
    x[0] = float(rng.uniform(*kind["x0"]))
    storm_end_steps = {int(round((end - start).total_seconds() / 3600.0)) for _s, end in STORMS}
    for k in range(1, n_steps):
        t_local = start + timedelta(hours=k)
        day_part = 1.0 if 6 <= t_local.hour < 20 else 0.3
        xk = x[k - 1] + a * day_part * float(rng.uniform(0.4, 1.6))
        if k in storm_end_steps:
            xk += susceptibility * float(rng.uniform(*SURGE_RANGE))
        if t_local.hour == 8 and xk > kind["thr"] and float(rng.random()) < kind["service"]:    # đội vệ sinh sáng ~08:30
            xk = float(rng.uniform(0.0, 6.0))
        x[k] = min(max(xk, 0.0), 100.0)
    base_waste = float(rng.gamma(1.1, 0.40)) * (1.6 if role["kind"] == "neglected" else 1.0)
    w_noise = np.zeros(n_steps)
    for k in range(1, n_steps):
        w_noise[k] = 0.8 * w_noise[k - 1] + float(rng.normal(0.0, 0.6))
    w = np.clip(0.10 * x + base_waste + w_noise, 0.0, 60.0)

    minutes = np.arange(n_minutes + 1)
    hours = minutes / 60.0
    xm = np.interp(hours, np.arange(n_steps), x)
    wm = np.interp(hours, np.arange(n_steps), w)
    start_min_of_day = start.hour * 60 + start.minute
    mod = (start_min_of_day + minutes) % 1440
    ok = (mod >= DAY_START_MIN) & (mod < DAY_END_MIN)
    for s, e in STORMS:                                              # mưa: khung bị loại (ngoài phạm vi)
        a_i, b_i = int((s - start).total_seconds() // 60), int((e - start).total_seconds() // 60)
        ok[a_i:b_i + 1] = False
    ok &= minutes >= role["first_min"]
    ok &= minutes < role["last_min"]
    ok &= rng.random(n_minutes + 1) > 0.012                          # khung hỏng / mất gói
    noise = rng.normal(0.0, 2.2, n_minutes + 1)
    spike = rng.random(n_minutes + 1)
    y = xm + noise
    y = np.where(spike < 0.012, y + rng.uniform(15.0, 35.0, n_minutes + 1), y)
    y = np.where((spike >= 0.012) & (spike < 0.024), y - rng.uniform(10.0, 25.0, n_minutes + 1), y)
    y = np.round(np.clip(y, 0.0, 100.0), 1)
    wr = np.round(np.clip(wm + rng.normal(0.0, 0.4, n_minutes + 1), 0.0, 100.0), 1)

    tracker = DrainTracker()
    last = []
    for m in np.nonzero(ok)[0].tolist():
        tracker.add(m, float(y[m]))
        last.append((m, float(y[m]), float(wr[m])))
    run: list = []
    for item in reversed(last):                       # đoạn đo liên tục cuối cùng (khe > 15 phút làm trạng thái cống bắt đầu lại)
        if run and run[-1][0] - item[0] > POLICY["reading_max_age_min"]:
            break
        run.append(item)
    run.reverse()
    return tracker, last[-100:], run


def _build(seed: int):
    sites = json.loads(SITES.read_text(encoding="utf-8"))["cameras"]
    start = AS_OF - timedelta(days=SIM_DAYS)
    n_minutes = SIM_DAYS * 24 * 60
    master = np.random.default_rng(np.random.SeedSequence([seed, 1]))
    ids = [s["id"] for s in sites]

    # vai trò đặc biệt (cố định theo hạt giống)
    order = master.permutation(len(sites)).tolist()
    offline_long = set(order[:N_OFFLINE_LONG])
    offline_recent = set(order[N_OFFLINE_LONG:N_OFFLINE_LONG + N_OFFLINE_RECENT])
    new_ones = set(order[N_OFFLINE_LONG + N_OFFLINE_RECENT:N_OFFLINE_LONG + N_OFFLINE_RECENT + N_NEW])

    cameras = []
    extras: dict = {}
    for idx, site in enumerate(sites):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 2, zlib.crc32(site["id"].encode())]))
        kind = str(rng.choice(list(KINDS), p=ZONE_KIND_P.get(site["zone"], (0.6, 0.27, 0.13))))
        role = {"kind": kind, "first_min": 0, "last_min": n_minutes + 1}
        if idx in offline_long:
            role["last_min"] = n_minutes - int(rng.uniform(180, 1800))
        elif idx in offline_recent:
            role["last_min"] = n_minutes - int(rng.uniform(20, 50))
        elif idx in new_ones:
            role["first_min"] = n_minutes - int(rng.integers(0, 2))     # mới lắp: 1-2 lần đo tại thời điểm chụp
        tracker, last, run = simulate_camera(rng, site, role, start, n_minutes)
        geo = camera_geometry(site, rng)

        cam = {
            "id": site["id"], "zone": site["zone"],
            "pos": [round(site["camera"][0], 7), round(site["camera"][1], 7)],
            "drain": [round(site["drain"][0], 7), round(site["drain"][1], 7)],
            "heading": round(geo["heading"], 1), "height_m": round(geo["height"], 1),
            "footprint": to_latlon_ring(site, geo["foot"]),
            "roi": to_latlon_ring(site, geo["roi"]),
        }
        if not last:
            cam.update(status="offline", last_frame=None, state="unknown", reason="no_data", since=None, blockage_pct=None, window=0,
                       recent=[], latest=None, regions=[])
            cameras.append(cam)
            continue

        last_min = last[-1][0]
        last_time = start + timedelta(minutes=last_min)
        online = (n_minutes - last_min) <= POLICY["reading_max_age_min"]
        # trạng thái hiển thị: quá 15 phút không có khung -> chưa rõ (stale), giống presentDrainState
        if online:
            state, reason, smoothed = tracker.state, tracker.reason, tracker.smoothed
            since = start + timedelta(minutes=tracker.since) if tracker.since is not None else None
        else:
            state, reason, smoothed, since = "unknown", "stale", None, None
        cam.update(status="online" if online else "offline", last_frame=last_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   state=state, reason=reason, since=since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if since else None,
                   blockage_pct=smoothed, window=tracker.window_count if online else 0,
                   recent=[{"at": (start + timedelta(minutes=m)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "v": v}
                           for m, v, _w in reversed(last[-DRAIN["window_size"]:])])

        # khung mới nhất: vẽ vùng rác khớp với số đo
        _m, y_last, w_last = last[-1]
        regions = []
        blobs: list[np.ndarray] = []
        if y_last > 0.5:
            blob = fit_drain_blob(rng, geo["roi"], geo["roi_center"], geo["axis_deg"], y_last / 100.0)
            if inside(geo["foot"], blob, 0.02):
                blobs.append(blob)
                regions.append(("drain", blob))
        drain_area = sum(shoelace(b) for b in blobs)
        target = max(0.0, w_last / 100.0 * geo["foot_area"] - drain_area)
        for b in litter_blobs(rng, geo, target, geo["roi_center"]):
            regions.append(("street", b))
        total_area = sum(shoelace(b) for _k, b in regions)
        waste_pct = round(total_area / geo["foot_area"] * 100.0, 1)
        measured = raster_overlap(geo["roi"], blobs[0], geo["roi_center"]) * 100.0 if blobs else 0.0
        cam["latest"] = {
            "at": cam["last_frame"], "blockage_pct": y_last, "blockage_measured_pct": round(measured, 1), "waste_pct": waste_pct,
            "waste_level": waste_level(waste_pct), "severity": severity(waste_pct, y_last),
            "total_area_m2": round(total_area, 3), "footprint_area_m2": round(geo["foot_area"], 1),
        }
        cam["regions"] = [{"kind": k, "area_m2": round(shoelace(b), 3), "ring": to_latlon_ring(site, b)} for k, b in regions]
        cameras.append(cam)
        iso = lambda m: (start + timedelta(minutes=m)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
        extras[site["id"]] = {
            "run": [[iso(m), v, w] for m, v, w in run],
            "latest_waste_pct": waste_pct,
            "roi_norm": roi_to_image(geo),
            "calibrated_at": (AS_OF - timedelta(hours=3 if idx in new_ones else 24 * 9)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "heading": round(geo["heading"], 1), "height_m": round(geo["height"], 1),
        }

    zones = []
    for zid in sorted({c["zone"] for c in cameras}):
        pts = [c["pos"] for c in cameras if c["zone"] == zid]
        zones.append({"id": zid, "center": [round(sum(p[0] for p in pts) / len(pts), 5), round(sum(p[1] for p in pts) / len(pts), 5)], "cameras": len(pts)})
    doc = {
        "version": 1,
        "simulated": True,
        "note": "SIMULATED data for illustration: camera positions, readings and litter outlines are generated, not measured.",
        "generator": "research/cleansight_customer_demo/make_demo_data.py",
        "seed": seed,
        "as_of": AS_OF.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": POLICY,
        "zones": zones,
        "cameras": cameras,
    }
    return doc, extras


def build(seed: int) -> dict:
    return _build(seed)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    doc = build(args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    counts: dict[str, int] = {}
    for c in doc["cameras"]:
        key = c["state"] + ("/offline" if c["status"] == "offline" else "")
        counts[key] = counts.get(key, 0) + 1
    print(f"Đã ghi {out} ({len(text) / 1024:.0f} KB, {len(doc['cameras'])} camera). Trạng thái: {counts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
