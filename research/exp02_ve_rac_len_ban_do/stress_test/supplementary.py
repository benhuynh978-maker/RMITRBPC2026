"""
Phần bổ sung (chạy SAU lưới chính + analyze.py, seed MỚI 100-109, chỉ q20/q25/q30 gần ESP32):
  1) validation.csv: kiểm chứng kích thước marker khuyến nghị (đọc từ summary.json, quy tắc chốt trước)
     tại D = 3/5/8 m, θ = 20/45/65°, cho biến thể A (code hiện tại) và B (SUBPIX).
  2) sweep.csv: quét kích thước marker tại D = 5 m và 8 m để thấy ngưỡng px theo TỪNG góc θ
     (phân tích phụ, không thay quy tắc chính).
Chỉ ghi trong stress_test/.

Chạy: C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/supplementary.py
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STRESS_DIR = Path(__file__).resolve().parent
if str(STRESS_DIR) not in sys.path:
    sys.path.insert(0, str(STRESS_DIR))

import run_stress as rs  # noqa: E402

SEEDS = range(100, 110)
CONDS = [c for c in rs.conditions() if c[0] in ("q30", "q25", "q20")]
SWEEP_SIZES_MM = [200, 250, 300, 350, 400, 500, 600, 700, 800, 1000, 1200, 1500, 1900]
SWEEP_DISTANCES = [5, 8]
FIELDS = ["experiment", "reco_from"] + rs.FIELDS


def run(path: Path, jobs):
    t0 = time.time()
    n = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for exp, reco_from, D, th, size_mm, variants in jobs:
            for s in SEEDS:
                for row in rs.run_cell(D, th, s, CONDS, marker_mm=float(size_mm), variants=variants):
                    w.writerow({"experiment": exp, "reco_from": reco_from, **row})
                    n += 1
    print(f"Đã ghi {path} ({n} dòng, {time.time() - t0:.1f}s)")


def main():
    summary = json.loads((STRESS_DIR / "summary.json").read_text(encoding="utf-8"))
    jobs = []
    for var in ["A_mac_dinh", "B_subpix"]:
        reco = summary[var]["reco_mm"]  # {"D=3 m": {"θ=20°": mm, ...}, ...}
        for dkey, by_th in reco.items():
            D = float(dkey.split("=")[1].split()[0])
            for tkey, mm in by_th.items():
                th = int(tkey.split("=")[1].rstrip("°"))
                jobs.append(("validation", var, D, th, mm, (var,)))
    run(STRESS_DIR / "validation.csv", jobs)

    sweep = [("sweep", "", D, th, mm, ("A_mac_dinh", "B_subpix"))
             for D in SWEEP_DISTANCES for th in rs.THETAS_DEG for mm in SWEEP_SIZES_MM
             if rs.scene.K[0, 0] * mm / 1000.0 / D <= 200.0]  # giữ marker gọn trong khung 640x480
    run(STRESS_DIR / "sweep.csv", sweep)


if __name__ == "__main__":
    main()
