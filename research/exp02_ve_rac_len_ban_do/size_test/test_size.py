"""
size_test/test_size.py — Test nhanh (CPU, < 5 giây, không model AI, không ghi file ngoài tmp/).

  1) Shoelace / trọng tâm trên các đa giác biết trước.
  2) Hình vuông 0.3 m ở 2 m, pose ĐÁP ÁN, mask hoàn hảo (2 pose danh nghĩa GAN-v0 và XA-v0):
     2a) Diện tích theo VÙNG PIXEL (chiếu 4 góc mỗi pixel - kiểm tra hình học chiếu thuần) phải
         nằm trong ±3% của 0.09 m².
     2b) Diện tích theo CONTOUR (cv2.findContours, đỉnh = tâm pixel biên - cách luồng thật lấy
         polygon từ mask) bị co ~0.5 px quanh viền. Test kiểm (contour − vùng pixel) của cùng mask
         khớp mức co dự đoán −0.5·chu_vi_px/diện_tích_px trong ±1.5 điểm %, và IN RA (không ép)
         việc contour có lọt ±3% của 0.09 m² không.
     2c) Sai số tâm ≤ 0.01 m.
  3) Đường lat/lon (project_mask_to_geojson) đổi ngược về mét khớp diện tích mét < 0.5%.

Chạy: C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B size_test/test_size.py
"""
from __future__ import annotations

import math
import sys

import scene  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import measure  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[OK]   {name} {detail}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


def test_shoelace():
    sq = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    check("shoelace: vuông 1x1 = 1", abs(measure.shoelace_area(sq) - 1.0) < 1e-12)
    check("shoelace: đảo chiều (CW) vẫn = 1", abs(measure.shoelace_area(sq[::-1]) - 1.0) < 1e-12)
    rect = np.array([[2, 5], [3, 5], [3, 5.3], [2, 5.3]], dtype=float)
    check("shoelace: chữ nhật 1.0x0.3 lệch gốc = 0.3", abs(measure.shoelace_area(rect) - 0.3) < 1e-12)
    tri = np.array([[0, 0], [4, 0], [0, 3]], dtype=float)
    check("shoelace: tam giác vuông 4x3 = 6", abs(measure.shoelace_area(tri) - 6.0) < 1e-12)
    concave = np.array([[0, 0], [2, 0], [2, 2], [1, 1], [0, 2]], dtype=float)
    check("shoelace: đa giác lõm = 3", abs(measure.shoelace_area(concave) - 3.0) < 1e-12)
    circ = scene._circle_polygon(0.0, 0.0, 0.2, 720)
    exp = 0.5 * 720 * 0.2 ** 2 * math.sin(2 * math.pi / 720)
    check("shoelace: đa giác đều 720 cạnh r=0.2 đúng công thức", abs(measure.shoelace_area(circ) - exp) < 1e-12)
    c = measure.polygon_centroid(rect)
    check("trọng tâm chữ nhật = (2.5, 5.15)", np.allclose(c, [2.5, 5.15], atol=1e-12), f"{c}")


def test_square_03_at_2m():
    for fam in ("GAN", "XA"):
        pose = scene.make_pose(fam, 0)
        obj = scene.make_flat_object("vuong_0.3", 2.0, 0.0)
        img, masks = scene.render_scene(pose, [obj])
        mask = masks[obj.uid]
        r = measure.measure_object(mask, pose.R, pose.t, obj)
        e_pix = r["sai_so_vung_pixel_pct"]
        e_cnt = r["sai_so_dien_tich_pct"]
        check(f"[{fam}] 2a vuông 0.3 m @2 m, vùng pixel ±3%", abs(e_pix) <= 3.0,
              f"đo {r['dien_tich_vung_pixel_m2']:.5f} m² ({e_pix:+.2f}%)")
        uv = scene.object_image_points(obj, pose).astype(np.float32)
        perim_px = cv2.arcLength(uv.reshape(-1, 1, 2), True)
        area_px = measure.shoelace_area(uv)
        pred = -100.0 * 0.5 * perim_px / area_px
        shrink = e_cnt - e_pix  # contour so với CHÍNH vùng pixel của mask đó (loại sai số lượng tử của mask)
        check(f"[{fam}] 2b contour co nửa pixel so với vùng pixel đúng dự đoán (±1.5 điểm %)", abs(shrink - pred) <= 1.5,
              f"contour {e_cnt:+.2f}% − vùng pixel {e_pix:+.2f}% = {shrink:+.2f}%, dự đoán {pred:+.2f}%")
        print(f"[INFO] [{fam}] contour {'LỌT' if abs(e_cnt) <= 3.0 else 'KHÔNG lọt'} ±3% ({e_cnt:+.2f}%)")
        check(f"[{fam}] 2c sai số tâm ≤ 0.01 m", r["sai_so_tam_m"] <= 0.01, f"{r['sai_so_tam_m']:.4f} m")
        check(f"[{fam}] 3 GeoJSON lat/lon -> mét lệch < 0.5%", abs(r["geo_lech_nguoc_pct"]) < 0.5,
              f"{r['geo_lech_nguoc_pct']:+.2e}%")


def main():
    test_shoelace()
    test_square_03_at_2m()
    print(f"\nKết quả: {PASS} OK, {FAIL} FAIL")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
