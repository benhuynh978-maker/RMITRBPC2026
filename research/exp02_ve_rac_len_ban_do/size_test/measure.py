"""
size_test/measure.py — Đo NGƯỢC kích thước (m²) và vị trí tâm của rác giả lập trong scene.py,
so với đáp án, để định lượng sai số của CHÍNH phép chiếu (hiệu chỉnh marker -> chiếu mask
xuống mặt đất -> diện tích), tách khỏi sai số model AI (mask ở đây là mask tự vẽ).

Luồng đo cho mỗi vật (mỗi vật render trong 1 ảnh riêng, có marker):
  1) Hiệu chỉnh camera TỪ CHÍNH ẢNH render bằng calibrate_aruco.detect_and_solve_pnp
     (ảnh tạm lưu trong size_test/tmp/) - KHÔNG dùng pose đáp án (trừ điều kiện d).
  2) Mask -> contour ngoài lớn nhất (cv2.findContours, CHAIN_APPROX_NONE: đỉnh = tâm pixel biên).
  3) Chiếu từng đỉnh xuống mặt đất ra MÉT bằng đúng các bước hình học của project_mask.py
     (camera_model.pixel_to_ray -> project_mask.ray_to_marker_frame ->
      project_mask.intersect_ray_with_ground), vì project_mask_to_geojson chỉ trả lat/lon.
  4) Diện tích = shoelace (m²), tâm = trọng tâm đa giác (m).
  5) Kiểm tra chéo: chạy project_mask.project_mask_to_geojson (calib dict trong bộ nhớ,
     không ghi file), đổi lon/lat ngược về mét -> shoelace, so với diện tích bằng mét.
     Thêm: diện tích cầu kiểu geojson-area/turf.js (cách bản đồ web tính) để tham khảo.

Điều kiện:
  a_sach         ảnh PNG sạch, mask đáp án, pose hiệu chỉnh từ marker
  b_q25 / b_q12  ảnh JPEG OpenCV chất lượng 25 / 12, pose hiệu chỉnh từ ảnh JPEG, mask đáp án
  c_q25 / c_q12  như b nhưng mask = ngưỡng màu HSV trên ảnh JPEG (thành phần liên thông lớn nhất)
  d_pose_dap_an  ảnh sạch, mask đáp án, pose ĐÁP ÁN (bỏ hiệu chỉnh) - sai số "trần" do lượng tử pixel

Chạy: python -B measure.py   (từ thư mục size_test hoặc bất kỳ đâu)
Kết quả: size_test/ketqua/*.csv, *.md, *.png
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import scene  # noqa: E402  (scene tự thêm thư mục exp02 vào sys.path)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import calibrate_aruco  # noqa: E402
import camera_model  # noqa: E402
import config  # noqa: E402
import project_mask  # noqa: E402

CONDITIONS = ["a_sach", "b_q25", "b_q12", "c_q25", "c_q12", "d_pose_dap_an"]
CALIB_SOURCES = {"a_sach": "png", "b_q25": "q25", "b_q12": "q12", "c_q25": "q25", "c_q12": "q12"}
JPEG_QUALITIES = {"q25": 25, "q12": 12}
DISTANCES = [1.0, 2.0, 3.0, 5.0, 8.0]

# Tiêu chí tham khảo - ĐẶT TRƯỚC KHI CHẠY (trùng REPORT.md), không chỉnh sau
CRIT_AREA_NEAR_PCT = 5.0  # vật 1–3 m
CRIT_AREA_FAR_PCT = 15.0  # vật 5–8 m
CRIT_CENTROID_NEAR_M = 0.1  # vật 1–3 m
CRIT_GEO_DIFF_PCT = 0.5

# Ngưỡng màu cho điều kiện (c) - chọn TRƯỚC khi chạy: magenta H≈150 (thang OpenCV 0–180),
# S >= 128 (= nửa độ bão hoà của vật 255, nền cỏ S≈33, caro/marker S=0), V >= 64.
HSV_LO = np.array([135, 128, 64], dtype=np.uint8)
HSV_HI = np.array([165, 255, 255], dtype=np.uint8)

GEO_LATLON0 = config.DEMO_MARKER_LATLON  # chỉ để chạy đường lat/lon, không phải vị trí thật


# ----------------------------------------------------------------------------------------
# Hình học
# ----------------------------------------------------------------------------------------

def pixels_to_ground_m(uv: np.ndarray, camera_matrix: np.ndarray, R: np.ndarray, t: np.ndarray):
    """
    Chiếu từng điểm ảnh (u,v) xuống mặt đất z=0, trả toạ độ MÉT trong hệ marker (X~Đông, Y~Bắc).
    Dùng đúng các hàm của project_mask.py / camera_model.py. Điểm không cắt mặt đất bị bỏ.
    Trả (mảng (M,2), số điểm bị bỏ).
    """
    cam_origin = project_mask.camera_origin_in_marker_frame(R, t.reshape(3))
    out = []
    n_skip = 0
    for u, v in uv:
        ray_cam = camera_model.pixel_to_ray(camera_matrix, float(u), float(v))
        dir_marker = project_mask.ray_to_marker_frame(ray_cam, R)
        g = project_mask.intersect_ray_with_ground(cam_origin, dir_marker)
        if g is None:
            n_skip += 1
            continue
        out.append(g)
    return np.array(out, dtype=np.float64).reshape(-1, 2), n_skip


def shoelace_area(poly: np.ndarray) -> float:
    """Diện tích đa giác (không cần khép kín), công thức shoelace, trị tuyệt đối."""
    p = np.asarray(poly, dtype=np.float64)
    if len(p) < 3:
        return 0.0
    x, y = p[:, 0], p[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def polygon_centroid(poly: np.ndarray) -> np.ndarray:
    """Trọng tâm diện tích của đa giác đơn (shoelace có trọng số)."""
    p = np.asarray(poly, dtype=np.float64)
    x, y = p[:, 0], p[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    a = cross.sum() / 2.0
    if abs(a) < 1e-15:
        return p.mean(axis=0)
    cx = ((x + x1) * cross).sum() / (6.0 * a)
    cy = ((y + y1) * cross).sum() / (6.0 * a)
    return np.array([cx, cy])


def mask_to_contour(mask: np.ndarray) -> Optional[np.ndarray]:
    """Contour ngoài lớn nhất của mask (đỉnh = toạ độ tâm pixel biên), dạng (N,2) float."""
    contours, _ = cv2.findContours((mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    return c.reshape(-1, 2).astype(np.float64)


def pixel_area_map(camera_matrix: np.ndarray, R: np.ndarray, t: np.ndarray, shape) -> np.ndarray:
    """
    (Phụ, chỉ để so sánh) Diện tích mặt đất (m²) mà từng pixel phủ: chiếu 4 GÓC pixel
    (u±0.5, v±0.5) xuống z=0 (cùng công thức project_mask, viết vector hoá) rồi shoelace.
    Tổng trên mask = diện tích của đúng vùng pixel, không bị co nửa pixel như contour qua tâm pixel.
    """
    h, w = shape
    us = np.arange(w + 1, dtype=np.float64) - 0.5
    vs = np.arange(h + 1, dtype=np.float64) - 0.5
    U, V = np.meshgrid(us, vs)
    fx, fy = camera_matrix[0, 0], camera_matrix[1, 1]
    cx, cy = camera_matrix[0, 2], camera_matrix[1, 2]
    rays = np.stack([(U - cx) / fx, (V - cy) / fy, np.ones_like(U)], axis=-1)
    d = rays @ R  # = (R^T @ ray)^T
    C = -R.T @ t.reshape(3)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = -C[2] / d[..., 2]
    s = np.where(s > 0, s, np.nan)
    X = C[0] + s * d[..., 0]
    Y = C[1] + s * d[..., 1]
    x0, x1, x2, x3 = X[:-1, :-1], X[:-1, 1:], X[1:, 1:], X[1:, :-1]
    y0, y1, y2, y3 = Y[:-1, :-1], Y[:-1, 1:], Y[1:, 1:], Y[1:, :-1]
    area = 0.5 * np.abs((x0 * y1 - x1 * y0) + (x1 * y2 - x2 * y1) + (x2 * y3 - x3 * y2) + (x3 * y0 - x0 * y3))
    return area


def geojson_ring_to_m(ring_lonlat, lat0: float, lon0: float) -> np.ndarray:
    """Đổi ngược lon/lat -> (Đông, Bắc) mét: nghịch đảo đúng của project_mask.meters_to_latlon."""
    r = np.asarray(ring_lonlat, dtype=np.float64)
    east = np.radians(r[:, 0] - lon0) * config.EARTH_RADIUS_M * math.cos(math.radians(lat0))
    north = np.radians(r[:, 1] - lat0) * config.EARTH_RADIUS_M
    return np.stack([east, north], axis=1)


def spherical_ring_area(ring_lonlat) -> float:
    """Diện tích trên mặt cầu bán kính 6378137 m - cùng công thức thư viện geojson-area/turf.js."""
    coords = list(ring_lonlat)
    n = len(coords)
    if n <= 2:
        return 0.0
    total = 0.0
    for i in range(n):
        if i == n - 2:
            lo, mi, up = n - 2, n - 1, 0
        elif i == n - 1:
            lo, mi, up = n - 1, 0, 1
        else:
            lo, mi, up = i, i + 1, i + 2
        total += (math.radians(coords[up][0]) - math.radians(coords[lo][0])) * math.sin(math.radians(coords[mi][1]))
    return abs(total * config.EARTH_RADIUS_M ** 2 / 2.0)


def geojson_area_check(contour_uv: np.ndarray, R: np.ndarray, t: np.ndarray, camera_matrix: np.ndarray):
    """Chạy đường lat/lon thật của exp02 (project_mask_to_geojson) rồi tính lại diện tích."""
    lat0, lon0 = GEO_LATLON0
    calib = {
        "camera_id": "SIZE-TEST",
        "marker_latlon": [lat0, lon0],
        "R": R.tolist(),
        "t": t.reshape(3).tolist(),
        "camera_matrix": camera_matrix.tolist(),
        "image_size": [scene.WIDTH, scene.HEIGHT],
    }
    poly_norm = [(u / scene.WIDTH, v / scene.HEIGHT) for u, v in contour_uv]
    feat = project_mask.project_mask_to_geojson(poly_norm, (scene.WIDTH, scene.HEIGHT), calib)
    if feat is None:
        return float("nan"), float("nan")
    ring = feat["geometry"]["coordinates"][0]
    area_inv = shoelace_area(geojson_ring_to_m(ring[:-1], lat0, lon0))
    area_sph = spherical_ring_area(ring)
    return area_inv, area_sph


def convex_hull_area(points: np.ndarray) -> float:
    hull = cv2.convexHull(points.astype(np.float64).astype(np.float32)).reshape(-1, 2)
    return shoelace_area(hull)


def box_theory(obj: scene.SceneObject, cam_center: np.ndarray):
    """
    Lý thuyết cho hộp cao h dưới giả định mặt đất phẳng: mặt trên (z=h) bị chiếu xuống đất theo
    tia từ tâm camera: P_g = C + (P - C) * C.z/(C.z - h). Vết chiếu = bao lồi(đáy, mặt trên chiếu).
    Trả (diện tích vết lý thuyết m², cạnh xa kéo dài thêm theo hướng xuyên tâm m).
    """
    sx, sy = obj.size_xy
    h = obj.height_m
    base = obj.footprint_world
    k = cam_center[2] / (cam_center[2] - h)
    top_proj = cam_center[:2] + (base - cam_center[:2]) * k
    area = convex_hull_area(np.vstack([base, top_proj]))
    u_r = _radial_unit(obj)
    far_true = float(np.max((base - scene.CAMERA_FOOT_WORLD) @ u_r))
    far_theory = float(np.max((np.vstack([base, top_proj]) - scene.CAMERA_FOOT_WORLD) @ u_r))
    return area, far_theory - far_true


def _radial_unit(obj: scene.SceneObject) -> np.ndarray:
    v = obj.center_world - scene.CAMERA_FOOT_WORLD
    return v / np.linalg.norm(v)


def rotation_angle_deg(R_a: np.ndarray, R_b: np.ndarray) -> float:
    c = (np.trace(R_a @ R_b.T) - 1.0) / 2.0
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def threshold_mask(img_bgr: np.ndarray) -> np.ndarray:
    """Mask (c): ngưỡng màu HSV cố định, giữ thành phần liên thông lớn nhất."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    raw = cv2.inRange(hsv, HSV_LO, HSV_HI)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(raw, connectivity=8)
    if n <= 1:
        return np.zeros_like(raw)
    best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == best, 255, 0).astype(np.uint8)


# ----------------------------------------------------------------------------------------
# Đo 1 vật
# ----------------------------------------------------------------------------------------

_AREA_MAP_CACHE: Dict[bytes, np.ndarray] = {}


def _area_map_cached(R, t):
    key = np.round(np.concatenate([R.ravel(), t.ravel()]), 12).tobytes()
    if key not in _AREA_MAP_CACHE:
        if len(_AREA_MAP_CACHE) > 64:
            _AREA_MAP_CACHE.clear()
        _AREA_MAP_CACHE[key] = pixel_area_map(scene.CAMERA_MATRIX, R, t, (scene.HEIGHT, scene.WIDTH))
    return _AREA_MAP_CACHE[key]


def measure_object(mask: np.ndarray, R: np.ndarray, t: np.ndarray, obj: scene.SceneObject,
                   do_geo: bool = True) -> dict:
    """Đo diện tích/tâm 1 vật từ mask + pose. Trả dict chỉ số (NaN nếu không đo được)."""
    out = {"n_dinh": 0, "n_bo": 0}
    contour = mask_to_contour(mask)
    if contour is None or len(contour) < 3:
        out["loi"] = "khong_co_contour"
        return out
    ground, n_skip = pixels_to_ground_m(contour, scene.CAMERA_MATRIX, R, t)
    out["n_dinh"] = int(len(contour))
    out["n_bo"] = int(n_skip)
    if len(ground) < 3:
        out["loi"] = "khong_du_diem"
        return out
    area = shoelace_area(ground)
    cen = polygon_centroid(ground)
    err_vec = cen - obj.center_world
    u_r = _radial_unit(obj)
    u_l = np.array([u_r[1], -u_r[0]])  # vuông góc, dương = sang phải
    out.update(
        dien_tich_do_m2=area,
        sai_so_dien_tich_pct=100.0 * (area - obj.true_area_m2) / obj.true_area_m2,
        tam_do_x=float(cen[0]),
        tam_do_y=float(cen[1]),
        sai_so_tam_m=float(np.linalg.norm(err_vec)),
        sai_so_tam_xuyen_tam_m=float(err_vec @ u_r),
        sai_so_tam_ngang_m=float(err_vec @ u_l),
    )
    amap = _area_map_cached(R, t)
    a_pix = float(np.nansum(amap[mask > 0]))
    out["dien_tich_vung_pixel_m2"] = a_pix
    out["sai_so_vung_pixel_pct"] = 100.0 * (a_pix - obj.true_area_m2) / obj.true_area_m2
    if do_geo:
        a_inv, a_sph = geojson_area_check(contour, R, t, scene.CAMERA_MATRIX)
        out["geo_dien_tich_nguoc_m2"] = a_inv
        out["geo_lech_nguoc_pct"] = 100.0 * (a_inv - area) / area
        out["geo_dien_tich_cau_m2"] = a_sph
        out["geo_lech_cau_pct"] = 100.0 * (a_sph - area) / area
    if obj.kind == "box":
        rr = (ground - scene.CAMERA_FOOT_WORLD) @ u_r
        base_r = (obj.footprint_world - scene.CAMERA_FOOT_WORLD) @ u_r
        out["hop_chieu_dai_xuyen_tam_do_m"] = float(rr.max() - rr.min())
        out["hop_keo_dai_mep_xa_m"] = float(rr.max() - base_r.max())
        out["hop_lech_mep_gan_m"] = float(rr.min() - base_r.min())
    return out


def calibrate_from_image(path: Path):
    """Hiệu chỉnh bằng hàm dùng chung calibrate_aruco.detect_and_solve_pnp. Lỗi -> None."""
    try:
        res = calibrate_aruco.detect_and_solve_pnp(path, config.MARKER_ID, config.MARKER_SIZE_MM, legacy=True)
    except RuntimeError as exc:
        return None, str(exc)
    return res, ""


# ----------------------------------------------------------------------------------------
# Chạy toàn bộ
# ----------------------------------------------------------------------------------------

def _write_images(img: np.ndarray, stem: str) -> Dict[str, Path]:
    scene.TMP_DIR.mkdir(parents=True, exist_ok=True)
    paths = {"png": scene.TMP_DIR / f"{stem}.png"}
    cv2.imwrite(str(paths["png"]), img)
    for key, q in JPEG_QUALITIES.items():
        p = scene.TMP_DIR / f"{stem}_{key}.jpg"
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, q])
        paths[key] = p
    return paths


def run_all():
    rows: List[dict] = []
    calib_rows: List[dict] = []
    excluded: List[dict] = []
    for family in scene.POSE_FAMILIES:
        objs = scene.objects_for_family(family)
        for vi in range(len(scene.POSE_VARIANTS)):
            pose = scene.make_pose(family, vi)
            print(f"[{pose.label}] cao {pose.height_m} m, cúi {pose.pitch_deg}°, yaw {pose.yaw_deg:+}° - {len(objs)} vật")
            for obj in objs:
                if not scene.object_in_frame(obj, pose):
                    excluded.append({"pose": pose.label, "vat": obj.uid, "ly_do": "ngoai_khung_hinh"})
                    continue
                img, masks = scene.render_scene(pose, [obj])
                gt_mask = masks[obj.uid]
                paths = _write_images(img, "canh")
                calibs = {}
                decoded = {}
                for src, p in paths.items():
                    res, err = calibrate_from_image(p)
                    calibs[src] = res
                    if src != "png":
                        decoded[src] = cv2.imread(str(p))
                    crow = {"pose": pose.label, "ho": family, "bien_the": vi, "vat": obj.uid, "nguon": src,
                            "ok": res is not None, "loi": err}
                    if res is not None:
                        C_est = -res["R"].T @ res["t"]
                        crow.update(
                            sai_so_vi_tri_camera_m=float(np.linalg.norm(C_est - pose.cam_center)),
                            sai_so_cao_camera_m=float(C_est[2] - pose.cam_center[2]),
                            sai_so_goc_deg=rotation_angle_deg(res["R"], pose.R),
                            reproj_rms_px=res["reproj_error_rms_px"],
                        )
                    calib_rows.append(crow)

                for cond in CONDITIONS:
                    base = {
                        "dieu_kien": cond, "ho": family, "bien_the": vi, "pose": pose.label,
                        "vat": obj.name, "loai": obj.kind, "d_m": obj.d_m, "a_m": obj.a_m,
                        "dien_tich_that_m2": obj.true_area_m2,
                        "tam_that_x": float(obj.center_world[0]), "tam_that_y": float(obj.center_world[1]),
                    }
                    if cond == "d_pose_dap_an":
                        R, t = pose.R, pose.t
                        mask = gt_mask
                    else:
                        src = CALIB_SOURCES[cond]
                        res = calibs[src]
                        if res is None:
                            base["loi"] = "hieu_chinh_that_bai"
                            rows.append(base)
                            continue
                        R, t = res["R"], res["t"]
                        if cond.startswith("c_"):
                            mask = threshold_mask(decoded[src])
                            inter = np.logical_and(mask > 0, gt_mask > 0).sum()
                            union = np.logical_or(mask > 0, gt_mask > 0).sum()
                            base["iou_mask"] = float(inter / union) if union else 0.0
                        else:
                            mask = gt_mask
                    m = measure_object(mask, R, t, obj)
                    if obj.kind == "box":
                        th_area, th_stretch = box_theory(obj, pose.cam_center)
                        m["hop_dien_tich_ly_thuyet_m2"] = th_area
                        m["hop_keo_dai_ly_thuyet_m"] = th_stretch
                    base.update(m)
                    rows.append(base)
    return rows, calib_rows, excluded


# ----------------------------------------------------------------------------------------
# Tổng hợp
# ----------------------------------------------------------------------------------------

def _f(x, nd=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x:.{nd}f}"


def _vals(rows, key):
    return np.array([r[key] for r in rows if key in r and r[key] is not None and not
                     (isinstance(r[key], float) and math.isnan(r[key]))], dtype=np.float64)


def _group(rows, *keys):
    g = defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in keys)].append(r)
    return g


def write_csv(path: Path, rows: List[dict]):
    keys: List[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def summarize(rows, calib_rows, excluded) -> Tuple[str, dict]:
    md: List[str] = []
    verdict = {}
    flat = [r for r in rows if r["loai"] == "flat"]
    box = [r for r in rows if r["loai"] == "box"]

    # --- 0. số mẫu ---
    n_fail = sum(1 for r in rows if r.get("loi"))
    md.append("### Số mẫu\n")
    md.append(f"- Tổng số dòng đo: {len(rows)} (vật phẳng {len(flat)}, hộp {len(box)}); "
              f"dòng không đo được: {n_fail}; vật bị loại vì ra ngoài khung hình: {len(excluded)}")
    if excluded:
        ex = defaultdict(list)
        for e in excluded:
            ex[e["vat"]].append(e["pose"])
        md.append("- Bị loại (ngoài khung): " + "; ".join(f"{k} ở {', '.join(v)}" for k, v in sorted(ex.items())))
    md.append("")

    # --- 1. hiệu chỉnh ---
    md.append("### Sai số hiệu chỉnh marker (so với pose đáp án)\n")
    md.append("| Họ pose | Ảnh | Dò được | Sai số vị trí camera TB / max (m) | Sai số độ cao TB (m) | Sai số góc TB / max (°) | Reproj RMS TB (px) |")
    md.append("|---|---|---|---|---|---|---|")
    for (fam, src), grp in sorted(_group(calib_rows, "ho", "nguon").items()):
        ok = [r for r in grp if r["ok"]]
        pe = _vals(ok, "sai_so_vi_tri_camera_m")
        he = _vals(ok, "sai_so_cao_camera_m")
        ae = _vals(ok, "sai_so_goc_deg")
        rp = _vals(ok, "reproj_rms_px")
        md.append(f"| {fam} | {src} | {len(ok)}/{len(grp)} | {_f(pe.mean() if len(pe) else None, 3)} / {_f(pe.max() if len(pe) else None, 3)} | "
                  f"{_f(he.mean() if len(he) else None, 3)} | {_f(ae.mean() if len(ae) else None, 2)} / {_f(ae.max() if len(ae) else None, 2)} | "
                  f"{_f(rp.mean() if len(rp) else None, 3)} |")
    md.append("")
    # theo biến thể (để thấy hiệu chỉnh là 1 mẫu/biến thể)
    md.append("Sai số vị trí camera theo từng biến thể pose (m, TB trên các ảnh của biến thể):\n")
    md.append("| Pose | png | q25 | q12 |")
    md.append("|---|---|---|---|")
    for (pose_lbl,), grp in sorted(_group(calib_rows, "pose").items()):
        cells = []
        for src in ["png", "q25", "q12"]:
            v = _vals([r for r in grp if r["nguon"] == src and r["ok"]], "sai_so_vi_tri_camera_m")
            nok = sum(1 for r in grp if r["nguon"] == src and not r["ok"])
            cells.append((_f(v.mean(), 3) if len(v) else "–") + (f" ({nok} lỗi dò)" if nok else ""))
        md.append(f"| {pose_lbl} | " + " | ".join(cells) + " |")
    md.append("")

    # --- 2. sai số diện tích theo điều kiện × khoảng cách (vật phẳng) ---
    md.append("### Sai số diện tích theo điều kiện × khoảng cách (vật phẳng, gộp mọi hình/vị trí/biến thể)\n")
    md.append("Ô = TB có dấu / TB |.| / max |.| (%), n = số mẫu đo được.\n")
    md.append("| Điều kiện | " + " | ".join(f"{d:g} m" for d in DISTANCES) + " |")
    md.append("|---|" + "---|" * len(DISTANCES))
    g = _group(flat, "dieu_kien", "d_m")
    for cond in CONDITIONS:
        cells = []
        for d in DISTANCES:
            v = _vals(g.get((cond, d), []), "sai_so_dien_tich_pct")
            cells.append(f"{v.mean():+.1f} / {np.abs(v).mean():.1f} / {np.abs(v).max():.1f} (n={len(v)})" if len(v) else "–")
        md.append(f"| {cond} | " + " | ".join(cells) + " |")
    md.append("")

    md.append("### Sai số vị trí tâm theo điều kiện × khoảng cách (vật phẳng)\n")
    md.append("Ô = TB / max (m).\n")
    md.append("| Điều kiện | " + " | ".join(f"{d:g} m" for d in DISTANCES) + " |")
    md.append("|---|" + "---|" * len(DISTANCES))
    for cond in CONDITIONS:
        cells = []
        for d in DISTANCES:
            v = _vals(g.get((cond, d), []), "sai_so_tam_m")
            cells.append(f"{v.mean():.3f} / {v.max():.3f}" if len(v) else "–")
        md.append(f"| {cond} | " + " | ".join(cells) + " |")
    md.append("")

    # --- 3. theo hình × khoảng cách cho từng điều kiện ---
    shapes = list(scene.FLAT_SHAPES)
    gs = _group(flat, "dieu_kien", "vat", "d_m")
    for cond in CONDITIONS:
        md.append(f"#### Theo hình × khoảng cách — {cond} (TB có dấu % [max |.| %])\n")
        md.append("| Hình | " + " | ".join(f"{d:g} m" for d in DISTANCES) + " |")
        md.append("|---|" + "---|" * len(DISTANCES))
        for s in shapes:
            cells = []
            for d in DISTANCES:
                v = _vals(gs.get((cond, s, d), []), "sai_so_dien_tich_pct")
                cells.append(f"{v.mean():+.1f} [{np.abs(v).max():.1f}]" if len(v) else "–")
            md.append(f"| {s} | " + " | ".join(cells) + " |")
        md.append("")

    # --- 4. phụ: diện tích theo vùng pixel ---
    md.append("### (Phụ) Diện tích tính theo VÙNG PIXEL (chiếu 4 góc từng pixel) thay vì contour qua tâm pixel\n")
    md.append("Ô = TB có dấu / max |.| (%).\n")
    md.append("| Điều kiện | " + " | ".join(f"{d:g} m" for d in DISTANCES) + " |")
    md.append("|---|" + "---|" * len(DISTANCES))
    for cond in CONDITIONS:
        cells = []
        for d in DISTANCES:
            v = _vals(g.get((cond, d), []), "sai_so_vung_pixel_pct")
            cells.append(f"{v.mean():+.1f} / {np.abs(v).max():.1f}" if len(v) else "–")
        md.append(f"| {cond} | " + " | ".join(cells) + " |")
    md.append("")

    # --- 5. hộp cao ---
    md.append("### Ca hộp 0.3×0.3 m cao 0.2 m (đáy thật 0.09 m², chiều dài xuyên tâm thật 0.30 m)\n")
    md.append("TB trên các biến thể pose. 'Lý thuyết' = vết chiếu hình học của hộp lên mặt phẳng (bao lồi đáy + mặt trên chiếu theo tia camera).\n")
    md.append("| Điều kiện | Họ | d (m) | Diện tích đo (m²) | Sai số so với đáy (%) | Diện tích lý thuyết (m²) | Dài xuyên tâm đo (m) | Kéo dài mép xa đo (m) | Kéo dài lý thuyết (m) | Lệch tâm (m) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    gb = _group(box, "dieu_kien", "ho", "d_m")
    for cond in ["a_sach", "c_q25", "c_q12", "d_pose_dap_an"]:
        for fam in scene.POSE_FAMILIES:
            for d in DISTANCES:
                grp = gb.get((cond, fam, d), [])
                if not grp:
                    continue
                a = _vals(grp, "dien_tich_do_m2")
                if not len(a):
                    continue
                md.append(
                    f"| {cond} | {fam} | {d:g} | {a.mean():.4f} | {_vals(grp, 'sai_so_dien_tich_pct').mean():+.1f} | "
                    f"{_vals(grp, 'hop_dien_tich_ly_thuyet_m2').mean():.4f} | {_vals(grp, 'hop_chieu_dai_xuyen_tam_do_m').mean():.3f} | "
                    f"{_vals(grp, 'hop_keo_dai_mep_xa_m').mean():.3f} | {_vals(grp, 'hop_keo_dai_ly_thuyet_m').mean():.3f} | "
                    f"{_vals(grp, 'sai_so_tam_m').mean():.3f} |"
                )
    md.append("")

    # --- 6. kiểm tra chéo lat/lon ---
    # Loại mẫu suy biến (diện tích đo < 1e-6 m², ví dụ mask ngưỡng chỉ còn 1 đường thẳng) khỏi
    # sai lệch TƯƠNG ĐỐI - mẫu số ~0 làm % vô nghĩa; báo riêng sai lệch tuyệt đối của chúng.
    geo_rows = [r for r in rows if r.get("dien_tich_do_m2", 0) is not None and r.get("dien_tich_do_m2", 0) >= 1e-6]
    degen = [r for r in rows if "dien_tich_do_m2" in r and r["dien_tich_do_m2"] < 1e-6]
    gi = np.abs(_vals(geo_rows, "geo_lech_nguoc_pct"))
    gsph = np.abs(_vals(geo_rows, "geo_lech_cau_pct"))
    geo_ok = bool(len(gi) and gi.max() < CRIT_GEO_DIFF_PCT)
    verdict["GEO"] = geo_ok
    md.append("### Kiểm tra chéo đường lat/lon (GeoJSON của project_mask_to_geojson)\n")
    md.append(f"- Lon/lat → mét (nghịch đảo meters_to_latlon) → shoelace: lệch |max| = {gi.max():.2e} % trên {len(gi)} mẫu "
              f"(ngưỡng < {CRIT_GEO_DIFF_PCT}%) → **{'ĐẠT' if geo_ok else 'KHÔNG ĐẠT'}**")
    md.append(f"- Diện tích mặt cầu kiểu geojson-area/turf.js: lệch |max| = {gsph.max():.2e} %, TB = {gsph.mean():.2e} % (tham khảo)")
    for r in degen:
        md.append(f"- Mẫu suy biến bị loại khỏi % ({r['dieu_kien']}, {r['pose']}, {r['vat']}@{r['d_m']:g}m): diện tích đo "
                  f"{r['dien_tich_do_m2']:.1e} m², lệch tuyệt đối ngược {abs(r['geo_dien_tich_nguoc_m2'] - r['dien_tich_do_m2']):.1e} m², "
                  f"cầu {abs(r['geo_dien_tich_cau_m2'] - r['dien_tich_do_m2']):.1e} m²")
    md.append("")

    # --- 7. tiêu chí ---
    a_flat = [r for r in flat if r["dieu_kien"] == "a_sach"]
    near = [r for r in a_flat if r["d_m"] <= 3.0]
    far = [r for r in a_flat if r["d_m"] in (5.0, 8.0)]

    def crit(rs, key, thr, absval=True):
        v = []
        fails = []
        missing = 0
        for r in rs:
            if key not in r or r.get("loi"):
                missing += 1
                continue
            x = abs(r[key]) if absval else r[key]
            v.append(x)
            if x > thr:
                fails.append(r)
        ok = (not fails) and missing == 0 and len(v) > 0
        return ok, len(v) - len(fails), len(v), missing, fails

    md.append("### Đánh giá tiêu chí (điều kiện a)\n")
    md.append("| Mã | Tiêu chí | Kết quả | Mẫu đạt | Max thực tế | Vật không đạt (số mẫu không đạt) |")
    md.append("|---|---|---|---|---|---|")
    for code, rs, key, thr, desc in [
        ("T1", near, "sai_so_dien_tich_pct", CRIT_AREA_NEAR_PCT, f"|sai số diện tích| ≤ {CRIT_AREA_NEAR_PCT:g}% (1–3 m)"),
        ("T2", far, "sai_so_dien_tich_pct", CRIT_AREA_FAR_PCT, f"|sai số diện tích| ≤ {CRIT_AREA_FAR_PCT:g}% (5–8 m)"),
        ("T3", near, "sai_so_tam_m", CRIT_CENTROID_NEAR_M, f"sai số tâm ≤ {CRIT_CENTROID_NEAR_M:g} m (1–3 m)"),
    ]:
        ok, npass, n, missing, fails = crit(rs, key, thr)
        verdict[code] = ok
        mx = np.abs(_vals(rs, key)).max() if len(_vals(rs, key)) else float("nan")
        fl = defaultdict(int)
        for r in fails:
            fl[f"{r['vat']}@{r['d_m']:g}m"] += 1
        fl_s = ", ".join(f"{k} ({v})" for k, v in sorted(fl.items())) or "–"
        if missing:
            fl_s += f"; {missing} mẫu không đo được"
        md.append(f"| {code} | {desc} | **{'ĐẠT' if ok else 'KHÔNG ĐẠT'}** | {npass}/{n} | {mx:.3f} | {fl_s} |")
    md.append("")
    # tiêu chí theo từng hình (để thấy hình nào kéo trượt)
    md.append("Tỉ lệ đạt theo từng hình (điều kiện a):\n")
    md.append("| Hình | T1 (1–3 m) | T2 (5–8 m) | T3 (1–3 m) |")
    md.append("|---|---|---|---|")
    for s in shapes:
        cells = []
        for rs, key, thr in [(near, "sai_so_dien_tich_pct", CRIT_AREA_NEAR_PCT),
                             (far, "sai_so_dien_tich_pct", CRIT_AREA_FAR_PCT),
                             (near, "sai_so_tam_m", CRIT_CENTROID_NEAR_M)]:
            sub = [r for r in rs if r["vat"] == s]
            ok, npass, n, missing, _ = crit(sub, key, thr)
            cells.append(f"{'ĐẠT' if ok else 'KHÔNG'} {npass}/{n}")
        md.append(f"| {s} | " + " | ".join(cells) + " |")
    md.append("")
    return "\n".join(md), verdict


# ----------------------------------------------------------------------------------------
# Biểu đồ + ảnh ví dụ
# ----------------------------------------------------------------------------------------

def make_charts(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    flat = [r for r in rows if r["loai"] == "flat"]
    shapes = list(scene.FLAT_SHAPES)
    g = _group(flat, "dieu_kien", "vat", "d_m")
    colors = {"a_sach": "tab:blue", "b_q25": "tab:orange", "b_q12": "tab:red",
              "c_q25": "tab:green", "c_q12": "tab:olive", "d_pose_dap_an": "black"}
    fig, axes = plt.subplots(2, 4, figsize=(18, 8.5), sharex=True)
    for ax, s in zip(axes.ravel(), shapes + ["__all__"]):
        for cond in CONDITIONS:
            xs, ys, lo, hi = [], [], [], []
            for d in DISTANCES:
                if s == "__all__":
                    grp = [r for r in flat if r["dieu_kien"] == cond and r["d_m"] == d]
                else:
                    grp = g.get((cond, s, d), [])
                v = _vals(grp, "sai_so_dien_tich_pct")
                if not len(v):
                    continue
                xs.append(d)
                ys.append(v.mean())
                lo.append(v.mean() - v.min())
                hi.append(v.max() - v.mean())
            if xs:
                ax.errorbar(xs, ys, yerr=[lo, hi], marker="o", ms=3, capsize=2, lw=1.2,
                            color=colors[cond], label=cond)
        ax.axhline(0, color="gray", lw=0.6)
        for thr, x0, x1 in [(CRIT_AREA_NEAR_PCT, 0.5, 3.5), (CRIT_AREA_FAR_PCT, 4.5, 8.5)]:
            ax.hlines([thr, -thr], x0, x1, colors="gray", linestyles="dashed", lw=0.8)
        ax.set_ylim(-80, 50)  # q12 có ca lật pose tới +2000% - cắt trục cho đọc được, số đủ xem bảng
        ax.set_title("Tất cả vật phẳng" if s == "__all__" else s)
        ax.set_xticks(DISTANCES)
        ax.grid(alpha=0.3)
    for ax in axes[1]:
        ax.set_xlabel("khoảng cách từ chân camera (m)")
    for ax in axes[:, 0]:
        ax.set_ylabel("sai số diện tích (%)")
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Sai số diện tích (đo − thật)/thật theo khoảng cách — điểm = TB, thanh = min..max; nét đứt = ngưỡng tiêu chí (a)\n"
                 "Trục y cắt ở [-80%, +50%]: b_q12/c_q12 ở 1–2 m vượt trục (tới +2000%, do hiệu chỉnh lật pose) - xem bảng")
    fig.tight_layout()
    p1 = scene.RESULTS_DIR / "chart_sai_so_dien_tich.png"
    fig.savefig(p1, dpi=110)
    plt.close(fig)

    # centroid
    fig, ax = plt.subplots(figsize=(7, 4.5))
    gg = _group(flat, "dieu_kien", "d_m")
    for cond in CONDITIONS:
        xs = [d for d in DISTANCES if len(_vals(gg.get((cond, d), []), "sai_so_tam_m"))]
        ys = [_vals(gg[(cond, d)], "sai_so_tam_m").mean() for d in xs]
        mx = [_vals(gg[(cond, d)], "sai_so_tam_m").max() for d in xs]
        ax.plot(xs, ys, marker="o", color=colors[cond], label=f"{cond} (TB)")
        ax.plot(xs, mx, ls=":", color=colors[cond], lw=1)
    ax.hlines(CRIT_CENTROID_NEAR_M, 0.5, 3.5, colors="gray", linestyles="dashed", lw=0.8)
    ax.set_xlabel("khoảng cách từ chân camera (m)")
    ax.set_ylabel("sai số vị trí tâm (m)")
    ax.set_title("Sai số vị trí tâm — nét liền TB, chấm = max")
    ax.set_xticks(DISTANCES)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    p2 = scene.RESULTS_DIR / "chart_sai_so_tam.png"
    fig.savefig(p2, dpi=110)
    plt.close(fig)

    # hộp cao
    box = [r for r in rows if r["loai"] == "box"]
    gb = _group(box, "dieu_kien", "d_m")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for cond in ["a_sach", "c_q25", "d_pose_dap_an"]:
        xs = [d for d in DISTANCES if len(_vals(gb.get((cond, d), []), "dien_tich_do_m2"))]
        axes[0].plot(xs, [_vals(gb[(cond, d)], "dien_tich_do_m2").mean() for d in xs], marker="o",
                     color=colors[cond], label=f"đo — {cond}")
        axes[1].plot(xs, [_vals(gb[(cond, d)], "hop_keo_dai_mep_xa_m").mean() for d in xs], marker="o",
                     color=colors[cond], label=f"đo — {cond}")
    xs = [d for d in DISTANCES if len(_vals(gb.get(("d_pose_dap_an", d), []), "hop_dien_tich_ly_thuyet_m2"))]
    axes[0].plot(xs, [_vals(gb[("d_pose_dap_an", d)], "hop_dien_tich_ly_thuyet_m2").mean() for d in xs],
                 ls="--", color="purple", label="lý thuyết (vết chiếu hình học)")
    axes[0].axhline(0.09, color="gray", ls="-.", label="đáy thật 0.09 m²")
    axes[1].plot(xs, [_vals(gb[("d_pose_dap_an", d)], "hop_keo_dai_ly_thuyet_m").mean() for d in xs],
                 ls="--", color="purple", label="lý thuyết")
    axes[0].set_title("Hộp 0.3×0.3×0.2 m: diện tích đo vs đáy thật")
    axes[0].set_ylabel("m²")
    axes[1].set_title("Hộp: mép xa bị kéo dài thêm về phía xa camera")
    axes[1].set_ylabel("m")
    for ax in axes:
        ax.set_xlabel("khoảng cách từ chân camera (m)")
        ax.set_xticks(DISTANCES)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout()
    p3 = scene.RESULTS_DIR / "chart_hop_cao.png"
    fig.savefig(p3, dpi=110)
    plt.close(fig)
    return [p1, p2, p3]


def make_example_image(family: str, cond: str) -> Path:
    """Ảnh minh hoạ: nhiều vật trong 1 cảnh, vẽ viền mask dùng để đo + diện tích đo/thật."""
    pose = scene.make_pose(family, 0)
    objs = scene.overview_objects(family)
    img, masks = scene.render_scene(pose, objs)
    paths = _write_images(img, "vidu")
    src = "png" if cond in ("a_sach", "d_pose_dap_an") else cond.split("_")[1]
    res, err = calibrate_from_image(paths[src])
    if res is None:
        raise RuntimeError(f"Không hiệu chỉnh được ảnh ví dụ: {err}")
    show = cv2.imread(str(paths[src]))
    big = cv2.resize(show, (scene.WIDTH * 2, scene.HEIGHT * 2), interpolation=cv2.INTER_NEAREST)
    lines = []
    for obj in objs:
        gt = masks[obj.uid]
        if cond.startswith("c_"):
            # ngưỡng màu toàn ảnh rồi giữ thành phần chồng lên vật này (ảnh có nhiều vật)
            hsv = cv2.cvtColor(show, cv2.COLOR_BGR2HSV)
            raw = cv2.inRange(hsv, HSV_LO, HSV_HI)
            n, labels, stats, _ = cv2.connectedComponentsWithStats(raw, connectivity=8)
            ov = labels[gt > 0]
            ov = ov[ov > 0]
            mask = np.where(labels == np.bincount(ov).argmax(), 255, 0).astype(np.uint8) if len(ov) else np.zeros_like(gt)
        else:
            mask = gt
        m = measure_object(mask, res["R"], res["t"], obj, do_geo=False)
        contour = mask_to_contour(mask)
        if contour is not None:
            cv2.polylines(big, [np.round(contour * 2 + 0.5).astype(np.int32).reshape(-1, 1, 2)], True, (0, 200, 255), 2)
        x0, y0 = contour.min(axis=0) * 2 if contour is not None else (0, 0)
        txt1 = f"do {m.get('dien_tich_do_m2', float('nan')):.4f} m2"
        txt2 = f"that {obj.true_area_m2:.4f} ({m.get('sai_so_dien_tich_pct', float('nan')):+.1f}%)"
        for k, txt in enumerate([txt1, txt2]):
            org = (int(max(2, x0)), int(max(14, y0 - 22 + 16 * k)))
            cv2.putText(big, txt, org, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(big, txt, org, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        lines.append((obj.uid, m.get("dien_tich_do_m2"), obj.true_area_m2, m.get("sai_so_dien_tich_pct"), m.get("sai_so_tam_m")))
    cv2.putText(big, f"{pose.label} - {cond} (vien cam = mask dung de do)", (8, scene.HEIGHT * 2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(big, f"{pose.label} - {cond} (vien cam = mask dung de do)", (8, scene.HEIGHT * 2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    out = scene.RESULTS_DIR / f"vidu_{family}_{cond}.png"
    cv2.imwrite(str(out), big)
    print(f"Ảnh ví dụ {out.name}:")
    for uid, a, ta, e, ce in lines:
        print(f"   {uid:32s} đo {a:.4f} m² | thật {ta:.4f} m² | {e:+.1f}% | lệch tâm {ce:.3f} m")
    return out


def _parse_cell(v: str):
    if v == "":
        return None
    if v in ("True", "False"):
        return v == "True"
    try:
        return int(v) if v.lstrip("-").isdigit() else float(v)
    except ValueError:
        return v


def read_csv(path: Path) -> List[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return [{k: _parse_cell(v) for k, v in r.items() if _parse_cell(v) is not None}
                for r in csv.DictReader(f)]


def main():
    """Mặc định chạy toàn bộ. '--tu-csv': chỉ tổng hợp lại bảng/biểu đồ từ CSV đã có (không render lại)."""
    scene.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if "--tu-csv" in sys.argv:
        rows = read_csv(scene.RESULTS_DIR / "ketqua_chi_tiet.csv")
        for r in rows:
            r["d_m"] = float(r["d_m"])
        calib_rows = read_csv(scene.RESULTS_DIR / "hieu_chinh_chi_tiet.csv")
        excluded = [r for r in read_csv(scene.RESULTS_DIR / "vat_bi_loai.csv") if r.get("vat")]
        md, verdict = summarize(rows, calib_rows, excluded)
        (scene.RESULTS_DIR / "bang_tom_tat.md").write_text(md, encoding="utf-8")
        (scene.RESULTS_DIR / "ket_luan_tieu_chi.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
        make_charts(rows)
        print(md)
        print("Kết luận tiêu chí:", verdict)
        return
    rows, calib_rows, excluded = run_all()
    write_csv(scene.RESULTS_DIR / "ketqua_chi_tiet.csv", rows)
    write_csv(scene.RESULTS_DIR / "hieu_chinh_chi_tiet.csv", calib_rows)
    write_csv(scene.RESULTS_DIR / "vat_bi_loai.csv", excluded or [{"pose": "", "vat": "", "ly_do": ""}])
    md, verdict = summarize(rows, calib_rows, excluded)
    (scene.RESULTS_DIR / "bang_tom_tat.md").write_text(md, encoding="utf-8")
    (scene.RESULTS_DIR / "ket_luan_tieu_chi.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    charts = make_charts(rows)
    for fam, cond in [("GAN", "a_sach"), ("XA", "a_sach"), ("XA", "c_q12")]:
        make_example_image(fam, cond)
    print(md)
    print("Biểu đồ:", ", ".join(str(p) for p in charts))
    print("Kết luận tiêu chí:", verdict)


if __name__ == "__main__":
    main()
