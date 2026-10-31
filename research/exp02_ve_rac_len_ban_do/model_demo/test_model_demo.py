"""
Test nhanh (CPU, không cần model/GPU) cho chuỗi mask -> contour -> polygon -> GeoJSON
trong model_demo/run_demo_model.py. Dùng mask tổng hợp, calibration DEMO-CAM chỉ đọc.

Chạy (từ thư mục exp02_ve_rac_len_ban_do/):
  C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B model_demo/test_model_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_demo_model as rdm  # noqa: E402  (không import ultralytics ở mức module)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[OK]   {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} - {detail}")


def make_mask(h=400, w=400):
    return np.zeros((h, w), dtype=bool)


def test_two_squares_give_two_polygons():
    m = make_mask()
    m[50:150, 50:150] = True     # 100x100 = 10000 px
    m[200:260, 250:330] = True   # 60x80  = 4800 px
    cs = rdm.mask_to_contours(m)
    check("2 hình vuông rời -> 2 polygon", len(cs) == 2, f"được {len(cs)}")
    check("mỗi polygon có >= 3 đỉnh", all(len(c["polygon_px"]) >= 3 for c in cs),
          str([len(c["polygon_px"]) for c in cs]))
    check("hình vuông -> approxPolyDP còn đúng 4 đỉnh", all(len(c["polygon_px"]) == 4 for c in cs),
          str([len(c["polygon_px"]) for c in cs]))
    check("sắp theo diện tích giảm dần", cs[0]["area_px"] >= cs[1]["area_px"],
          str([c["area_px"] for c in cs]))
    check("area_px = số pixel mask thật", [c["area_px"] for c in cs] == [10000, 4800],
          str([c["area_px"] for c in cs]))
    check("component của 2 polygon không chồng nhau",
          not np.logical_and(cs[0]["component"], cs[1]["component"]).any())


def test_tiny_blob_is_dropped():
    m = make_mask()                # 160000 px -> ngưỡng 0.05% = 80 px
    m[10:110, 10:110] = True       # giữ
    m[300:308, 300:308] = True     # 8x8 = 64 px (contourArea 49) -> bỏ
    cs = rdm.mask_to_contours(m)
    check("hình quá nhỏ (< 0.05% ảnh) bị bỏ", len(cs) == 1, f"được {len(cs)}")
    cs_all = rdm.mask_to_contours(m, min_area_frac=0.0)
    check("tắt ngưỡng thì hình nhỏ được giữ lại", len(cs_all) == 2, f"được {len(cs_all)}")


def test_hole_is_ignored_outer_ring_only():
    m = make_mask()
    m[50:250, 50:250] = True
    m[100:200, 100:200] = False    # lỗ 100x100
    cs = rdm.mask_to_contours(m)
    check("vành khuyên -> 1 polygon (chỉ viền ngoài)", len(cs) == 1, f"được {len(cs)}")
    c = cs[0]
    check("area_px trừ lỗ (40000-10000)", c["area_px"] == 30000, str(c["area_px"]))
    check("contour_area_px gồm cả lỗ (~199*199)", abs(c["contour_area_px"] - 199 * 199) < 1, str(c["contour_area_px"]))


def test_empty_mask():
    check("mask rỗng -> 0 polygon", rdm.mask_to_contours(make_mask()) == [])


def test_mean_confidence():
    m = make_mask()
    m[50:150, 50:150] = True
    comp = rdm.mask_to_contours(m)[0]["component"]
    inst_a = make_mask(); inst_a[60:100, 60:100] = True     # giao
    inst_b = make_mask(); inst_b[300:350, 300:350] = True   # không giao
    conf = rdm.mean_confidence(comp, [inst_a, inst_b], [0.8, 0.3])
    check("confidence TB chỉ tính instance giao contour", conf == 0.8, str(conf))
    check("không instance nào giao -> None", rdm.mean_confidence(comp, [inst_b], [0.3]) is None)


def test_label_roundtrip_and_iou():
    polys = [[(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4)]]
    lm = rdm.rasterize_polygons(polys, 400, 400)
    check("rasterize polygon nhãn ra mask khác rỗng", lm.sum() > 0)
    check("IoU mask với chính nó = 1", rdm.mask_iou(lm, lm) == 1.0)
    check("IoU 2 mask rỗng -> None", rdm.mask_iou(make_mask(), make_mask()) is None)


def test_short_stem():
    s = rdm.short_stem("g1lop_000003_JPG.rf.54f58bb676977aea74419e3698ac6ac4")
    check("short_stem gọn", s == "g1lop_000003_54f58bb6", s)


def test_polygon_projects_to_geojson():
    calib = rdm.project_mask.load_calibration(rdm.config.DEMO_CAMERA_ID)  # chỉ đọc
    w, h = calib["image_size"]
    m = np.zeros((h, w), dtype=bool)
    m[300:400, 250:400] = True  # nửa dưới ảnh -> nhìn xuống mặt đất
    cs = rdm.mask_to_contours(m)
    norm = rdm.polygon_px_to_norm(cs[0]["polygon_px"], w, h)
    check("toạ độ chuẩn hoá trong [0,1]", all(0 <= x <= 1 and 0 <= y <= 1 for x, y in norm))
    feat = rdm.project_mask.project_mask_to_geojson(norm, (w, h), calib)
    ok = feat is not None and feat["geometry"]["type"] == "Polygon"
    check("contour chiếu ra GeoJSON Polygon", ok)
    if ok:
        ring = feat["geometry"]["coordinates"][0]
        check("ring khép kín, >= 4 điểm (>= 3 đỉnh)", ring[0] == ring[-1] and len(ring) >= 4, str(len(ring)))


def test_pixel_boundary_polygons():
    m = make_mask()
    m[50:150, 50:150] = True     # 10000 px
    m[200:260, 250:330] = True   # 4800 px
    m[300:304, 300:304] = True   # 16 px < 0.05% (80 px) -> bỏ
    ps = rdm.mask_to_polygons(m)
    check("biên pixel: 2 vùng (vùng 16 px bị bỏ)", len(ps) == 2, f"được {len(ps)}")
    check("biên pixel: area_px đúng số pixel", [p["area_px"] for p in ps] == [10000, 4800],
          str([p["area_px"] for p in ps]))
    check("biên pixel: component không chồng nhau", not np.logical_and(ps[0]["component"], ps[1]["component"]).any())
    ring = np.zeros((400, 400), dtype=bool); ring[50:250, 50:250] = True; ring[100:200, 100:200] = False
    pr = rdm.mask_to_polygons(ring)
    check("biên pixel: vành khuyên 1 vùng, 1 lỗ, area_px trừ lỗ (30000)",
          len(pr) == 1 and pr[0]["n_holes"] == 1 and pr[0]["area_px"] == 30000,
          str([(p["area_px"], p["n_holes"]) for p in pr]))
    check("biên pixel: mask rỗng -> []", rdm.mask_to_polygons(make_mask()) == [])
    # diện tích đa giác trên ảnh khớp số pixel (không co 0.5 px như contour)
    polys = rdm.project_mask.mask_to_pixel_boundary_polygons(m[:300, :])
    shoelace = abs(rdm.project_mask._ring_area(polys[0]["outer"]))
    check("biên pixel: diện tích đa giác == số pixel (hình 100x100)", abs(shoelace - 10000) < 1e-9, str(shoelace))


def test_project_mask_pixel_boundary_to_geojson():
    calib = rdm.project_mask.load_calibration(rdm.config.DEMO_CAMERA_ID)  # chỉ đọc
    w, h = 1024, 1024  # ảnh dataset: khác tỉ lệ 4:3 của DEMO-CAM
    m = np.zeros((h, w), dtype=bool)
    m[600:800, 300:600] = True
    comp = rdm.mask_to_polygons(m)[0]
    warn_log = {}
    rdm.project_mask.reset_warnings()
    ok_raised = False
    try:
        rdm.project_quiet(None, (w, h), calib, warn_log, mask=comp["component"])
    except ValueError:
        ok_raised = True
    check("ảnh khác tỉ lệ, không bật cờ -> ValueError", ok_raised)
    feat = rdm.project_quiet(None, (w, h), calib, warn_log, mask=comp["component"],
                             boundary=rdm.BOUNDARY, allow_aspect_mismatch=True, simplify_eps_px=comp["eps_px"])
    check("bật cờ demo -> ra GeoJSON Polygon", feat is not None and feat["geometry"]["type"] == "Polygon")
    check("cảnh báo lệch tỉ lệ được gom (1 lần)", sum(warn_log.values()) >= 1, str(warn_log))
    check("feature mang area_px đúng", feat is not None and feat["properties"]["area_px"] == comp["area_px"],
          str(feat and feat["properties"]))


def test_select_image_stems_by_labels():
    import tempfile
    scratch = Path(r"C:\Users\ASUS\AppData\Local\Temp\claude\c--Users-ASUS-Desktop-SSC\52bbd2c5-0ffd-43bb-a22e-8c0a29efff56\scratchpad\agent3")
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as td:
        td = Path(td)
        lbl, img = td / "labels", td / "images"
        lbl.mkdir(); img.mkdir()
        big = "0 0.1 0.1 0.9 0.1 0.9 0.9 0.1 0.9\n"
        small = "0 0.1 0.1 0.3 0.1 0.3 0.3 0.1 0.3\n"
        files = {
            "tphcm_a": small, "tphcm_b": big, "ssc_c": big, "ssc_empty": "", "tphcm_drain": "1 0.1 0.1 0.9 0.1 0.9 0.9\n",
            "g1lop_x": big, "g1lop_y": small,
        }
        for name, txt in files.items():
            (lbl / f"{name}.txt").write_text(txt, encoding="utf-8")
            (img / f"{name}.jpg").write_bytes(b"x")
        r = rdm.select_image_stems(lbl, img, n=3)
        check("chọn ảnh: 3 ảnh đường, hạng theo độ phủ rồi theo tên", r == [("ssc_c", "street"), ("tphcm_b", "street"), ("tphcm_a", "street")], str(r))
        check("chọn ảnh: loại ảnh nhãn trống / chỉ lớp Drain",
              all(s not in ("ssc_empty", "tphcm_drain") for s, _ in r))
        check("chọn ảnh: tất định (gọi 2 lần giống nhau)", r == rdm.select_image_stems(lbl, img, n=3))
        r5 = rdm.select_image_stems(lbl, img, n=5)
        check("thiếu ảnh đường -> bổ sung nguồn khác theo độ phủ", r5[3:] == [("g1lop_x", "other"), ("g1lop_y", "other")], str(r5))
        (img / "ssc_c.jpg").unlink()
        check("bỏ ảnh không có file .jpg", [s for s, _ in rdm.select_image_stems(lbl, img, n=2)] == ["tphcm_b", "tphcm_a"])


def test_select_image_stems_real_dataset():
    r = rdm.select_image_stems()
    check("dataset thật: chọn đủ N_IMAGES ảnh", len(r) == rdm.N_IMAGES, str(r))
    check("dataset thật: ảnh đầu là ảnh đường có nhiều rác nhất (tphcm2_20260926_181955)",
          bool(r) and r[0][0] == "tphcm2_20260926_181955" and r[0][1] == "street", str(r[:1]))
    check("dataset thật: mọi ảnh chọn thuộc tphcm/ssc", all(g == "street" for _, g in r), str(r))


def main() -> int:
    test_two_squares_give_two_polygons()
    test_tiny_blob_is_dropped()
    test_hole_is_ignored_outer_ring_only()
    test_empty_mask()
    test_mean_confidence()
    test_label_roundtrip_and_iou()
    test_short_stem()
    test_polygon_projects_to_geojson()
    test_pixel_boundary_polygons()
    test_project_mask_pixel_boundary_to_geojson()
    test_select_image_stems_by_labels()
    test_select_image_stems_real_dataset()
    print(f"\nKết quả: {PASS} đạt, {FAIL} lỗi")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
