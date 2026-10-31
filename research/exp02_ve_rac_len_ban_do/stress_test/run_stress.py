"""
Chạy lưới stress test -> stress_test/results.csv. Chỉ CPU, chỉ ghi trong stress_test/.

Chạy:
  C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/run_stress.py
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

STRESS_DIR = Path(__file__).resolve().parent
if str(STRESS_DIR) not in sys.path:
    sys.path.insert(0, str(STRESS_DIR))

import detect_variants as dv  # noqa: E402
import scene  # noqa: E402

DISTANCES_M = [1, 2, 3, 5, 8, 12]
THETAS_DEG = [20, 45, 65]
JPEG_QS = [95, 50, 30, 25, 20, 15, 12, 8]
EXTRAS_AT_Q25 = [("blur1.0", 1.0, 0.0), ("blur2.0", 2.0, 0.0), ("noise5", 0.0, 5.0), ("noise10", 0.0, 10.0)]
N_SEEDS = 10
ESP32_LIKE_QS = (20, 25, 30)

FIELDS = ["variant", "distance_m", "theta_deg", "seed", "azimuth_deg", "du_px", "dv_px", "marker_mm",
          "cond", "jpeg_q", "blur_sigma", "noise_sigma", "esp32_like", "jpeg_kb",
          "detected", "fail_msg", "reproj_px", "rot_err_deg", "pos_err_m", "pos_err_rel",
          "side_mean_px", "side_min_px", "side_det_px", "pass_strict"]


def conditions():
    out = [(f"q{q}", q, 0.0, 0.0) for q in JPEG_QS]
    out += [(f"q25+{name}", 25, b, n) for name, b, n in EXTRAS_AT_Q25]
    return out


def geometry(distance_m: float, theta_deg: float, seed: int):
    """Phương vị + độ lệch tâm ngẫu nhiên nhưng tất định theo (seed, D, θ)."""
    rng = np.random.default_rng([seed, int(round(distance_m * 100)), int(theta_deg), 17])
    return float(rng.uniform(0, 360)), float(rng.uniform(-80, 80)), float(rng.uniform(-60, 60))


def evaluate(res: dict, R_gt, C_gt, distance_m) -> dict:
    out = {"detected": 0, "fail_msg": "", "reproj_px": "", "rot_err_deg": "", "pos_err_m": "",
           "pos_err_rel": "", "pass_strict": 0}
    if not res["ok"]:
        out["fail_msg"] = res.get("msg", "")[:60]
        return out
    rot = scene.rotation_error_deg(R_gt, res["R"])
    pos = float(np.linalg.norm(scene.camera_center(res["R"], res["t"]) - C_gt))
    out.update(detected=1, reproj_px=round(res["reproj_error_rms_px"], 4), rot_err_deg=round(rot, 4),
               pos_err_m=round(pos, 5), pos_err_rel=round(pos / distance_m, 5),
               pass_strict=int(rot <= 2.0 and pos <= 0.10 * distance_m))
    return out


def build_image(distance_m, theta_deg, seed, cond_index, cond, marker_mm=200.0):
    """Trả (jpeg_bytes, ảnh decode, R, t, C, side_lengths_gt, (az,du,dv)). Dùng lại cho ảnh ví dụ/test."""
    az, du, dvv = geometry(distance_m, theta_deg, seed)
    R, t, C = scene.make_pose(distance_m, theta_deg, az, (du, dvv))
    clean = scene.render(R, t, marker_size_m=marker_mm / 1000.0)
    _, q, blur, noise = cond
    rng = np.random.default_rng([seed, int(round(distance_m * 100)), int(theta_deg), cond_index, 99])
    img = scene.degrade(clean, blur, noise, rng) if (blur > 0 or noise > 0) else clean
    jb = scene.jpeg_bytes(img, q)
    decoded = cv2.imdecode(np.frombuffer(jb, np.uint8), cv2.IMREAD_COLOR)
    sl = scene.side_lengths(scene.gt_corners(R, t, marker_mm / 1000.0))
    return jb, decoded, R, t, C, sl, (az, du, dvv)


def run_cell(distance_m: float, theta_deg: float, seed: int, conds, marker_mm: float = 200.0,
             variants=dv.VARIANTS):
    """Render 1 hình học, áp mọi điều kiện, chạy mọi biến thể -> list dòng kết quả."""
    az, du, dvv = geometry(distance_m, theta_deg, seed)
    R, t, C = scene.make_pose(distance_m, theta_deg, az, (du, dvv))
    clean = scene.render(R, t, marker_size_m=marker_mm / 1000.0)
    sl = scene.side_lengths(scene.gt_corners(R, t, marker_mm / 1000.0))
    rows = []
    for ci, (cname, q, blur, noise) in enumerate(conds):
        rng = np.random.default_rng([seed, int(round(distance_m * 100)), int(theta_deg), ci, 99])
        img = scene.degrade(clean, blur, noise, rng) if (blur > 0 or noise > 0) else clean
        jb = scene.jpeg_bytes(img, q)
        decoded = cv2.imdecode(np.frombuffer(jb, np.uint8), cv2.IMREAD_COLOR)
        dc = dv.detected_corners_default(decoded)
        side_det = round(float(scene.side_lengths(dc).mean()), 3) if dc is not None else ""
        base = {"distance_m": distance_m, "theta_deg": theta_deg, "seed": seed, "azimuth_deg": round(az, 2),
                "du_px": round(du, 2), "dv_px": round(dvv, 2), "marker_mm": marker_mm, "cond": cname,
                "jpeg_q": q, "blur_sigma": blur, "noise_sigma": noise,
                "esp32_like": int(q in ESP32_LIKE_QS and blur == 0 and noise == 0),
                "jpeg_kb": round(len(jb) / 1024.0, 2), "side_mean_px": round(float(sl.mean()), 3),
                "side_min_px": round(float(sl.min()), 3), "side_det_px": side_det}
        for var in variants:
            if var == "A_mac_dinh":
                res = dv.detect_official(jb, marker_mm)
            else:
                res = dv.detect_local(decoded, var, marker_mm)
            rows.append({**base, "variant": var, **evaluate(res, R, C, distance_m)})
    return rows


def main():
    conds = conditions()
    out = STRESS_DIR / "results.csv"
    t0 = time.time()
    n = 0
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for D in DISTANCES_M:
            for th in THETAS_DEG:
                for s in range(N_SEEDS):
                    for row in run_cell(D, th, s, conds):
                        w.writerow(row)
                        n += 1
            print(f"D={D} m xong, {n} dòng, {time.time() - t0:.1f}s", flush=True)
    print(f"Đã ghi {out} ({n} dòng) trong {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
