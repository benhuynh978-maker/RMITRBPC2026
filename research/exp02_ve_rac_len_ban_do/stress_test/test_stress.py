"""
Test nhanh (CPU, vài giây) cho bộ stress test ArUco.

Chạy: C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/test_stress.py
(tương thích pytest nếu sau này có: các hàm test_* dùng assert)
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

STRESS_DIR = Path(__file__).resolve().parent
if str(STRESS_DIR) not in sys.path:
    sys.path.insert(0, str(STRESS_DIR))

import detect_variants as dv  # noqa: E402
import run_stress as rs  # noqa: E402
import scene  # noqa: E402

Q95 = ("q95", 95, 0.0, 0.0)


def test_rotation_error_metric():
    R = scene.make_pose(2.0, 45.0, 30.0)[0]
    assert scene.rotation_error_deg(R, R) < 1e-6
    import cv2
    Rz, _ = cv2.Rodrigues(np.array([0.0, 0.0, np.deg2rad(5.0)]))
    assert abs(scene.rotation_error_deg(R, Rz @ R) - 5.0) < 1e-6


def test_clean_q95_2m_official_detector():
    """Đặc tả: ảnh sạch q95 ở 2 m (θ=45°, seed 0) -> calibrate_aruco.detect_and_solve_pnp detect được, xoay < 1°."""
    jb, _img, R, t, C, sl, _ = rs.build_image(2.0, 45, 0, 0, Q95)
    res = dv.detect_official(jb)
    assert res["ok"], f"không detect được: {res['msg']}"
    rot = scene.rotation_error_deg(R, res["R"])
    pos = float(np.linalg.norm(scene.camera_center(res["R"], res["t"]) - C))
    print(f"  A @2m θ45 q95: cạnh {sl.mean():.1f}px, xoay {rot:.3f}°, vị trí {pos:.3f} m")
    assert rot < 1.0, f"sai số xoay {rot:.3f}° >= 1°"
    assert not any((dv.TMP_DIR).glob("*.jpg")), "còn file tạm trong stress_test/tmp/"


def test_clean_q95_2m_subpix_all_angles():
    """Biến thể đề xuất SUBPIX: mọi θ (20/45/65°) × 10 seed ở 2 m q95 đều detect được và xoay < 1°."""
    worst = 0.0
    for th in rs.THETAS_DEG:
        for seed in range(rs.N_SEEDS):
            _jb, img, R, _t, _C, _sl, _ = rs.build_image(2.0, th, seed, 0, Q95)
            res = dv.detect_local(img, "B_subpix")
            assert res["ok"], f"θ={th} seed={seed}: không detect được"
            worst = max(worst, scene.rotation_error_deg(R, res["R"]))
    print(f"  B (SUBPIX) @2m q95, 30 cấu hình: xoay lớn nhất {worst:.3f}°")
    assert worst < 1.0


def main() -> int:
    tests = [test_rotation_error_metric, test_clean_q95_2m_official_detector, test_clean_q95_2m_subpix_all_angles]
    fails = 0
    for fn in tests:
        try:
            fn()
            print(f"[OK]   {fn.__name__}")
        except AssertionError as exc:
            fails += 1
            print(f"[FAIL] {fn.__name__} - {exc}")
    print(f"\n{len(tests) - fails}/{len(tests)} test đạt")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
