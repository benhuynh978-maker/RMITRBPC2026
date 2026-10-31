"""
Tạo ảnh ví dụ (đạt / vừa gãy pose / vừa gãy detect) vào stress_test/examples/, chọn seed tự động
từ results.csv (biến thể A = code hiện tại). Khung đỏ = 4 góc đáp án, khung xanh = 4 góc detect.

Chạy: C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/make_examples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
import pandas as pd

STRESS_DIR = Path(__file__).resolve().parent
if str(STRESS_DIR) not in sys.path:
    sys.path.insert(0, str(STRESS_DIR))

import analyze as an  # noqa: E402

CASES = [
    # (tên file, D, θ, cond, điều kiện chọn seed, tiêu đề)
    ("01_dat_D2_th45_q25.png", 2, 45, "q25", lambda r: r.pass_strict == 1, "DAT: 200mm, 2 m, q25"),
    ("02_gay_pose_D3_th20_q25.png", 3, 20, "q25", lambda r: r.detected == 1 and r.rot_err_deg > 2,
     "GAY POSE: detect duoc nhung xoay sai > 2 deg"),
    ("03_gay_detect_D8_th45_q25.png", 8, 45, "q25", lambda r: r.detected == 0, "GAY DETECT: 200mm, 8 m, q25"),
    ("04_gay_detect_D3_th45_blur2.png", 3, 45, "q25+blur2.0", lambda r: r.detected == 0,
     "GAY DETECT: mo Gauss sigma 2 + q25, 3 m"),
]


def main():
    an.EX_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(STRESS_DIR / "results.csv")
    a = df[df.variant == "A_mac_dinh"]
    for fname, D, th, cond, pick, title in CASES:
        sub = a[(a.distance_m == D) & (a.theta_deg == th) & (a.cond == cond)]
        sel = sub[sub.apply(pick, axis=1)]
        if sel.empty:
            print(f"[BỎ QUA] không có seed phù hợp cho {fname}")
            continue
        seed = int(sel.seed.iloc[0])
        panel = an.example_panel(D, th, seed, cond, title)
        cv2.imwrite(str(an.EX_DIR / fname), panel)
        print(f"{fname}: seed {seed}")


if __name__ == "__main__":
    main()
