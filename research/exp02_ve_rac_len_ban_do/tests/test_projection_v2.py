"""
Test v2 cho project_mask / run_demo_vehtruong (CPU, nhanh, không GPU, không model).

  a) polygon biên pixel của mask chữ nhật / tròn: diện tích pixel khớp số pixel (±1%)
  b) vuông 0.3 m ở 1-3 m, pose ĐÁP ÁN (size_test/scene.py, chỉ đọc): diện tích m² sai <= 2%
     (và đường cũ contour_center vẫn cho đúng số cũ, đầu ra polygon_norm GIỐNG HỆT vòng lặp gốc)
  c) lệch tỉ lệ khung -> ValueError; có cờ allow_aspect_mismatch -> chạy, cảnh báo in 1 lần, fx == fy
  d) parse nhãn đọc ĐỦ nhiều polygon (+ xếp hạng ảnh demo tất định)
  e) vị trí camera tính từ R, t khớp vị trí camera biết trước (outputs/pose_su_thuc.json, đọc-chỉ)
  f) alias camera_point_geojson trả cùng toạ độ marker như trước
  g) cảnh báo chất lượng hiệu chỉnh in 1 lần; file cũ không có khối quality thì im lặng

Chạy (từ thư mục exp02_ve_rac_len_ban_do):
  C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B tests/test_projection_v2.py
File tạm ghi vào thư mục scratchpad (không ghi vào project).
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np

EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP_DIR))
sys.path.insert(0, str(EXP_DIR / "size_test"))  # scene.py của size_test (chỉ đọc)

import camera_model  # noqa: E402
import config  # noqa: E402
import project_mask  # noqa: E402

SCRATCH = Path(
    r"C:\Users\ASUS\AppData\Local\Temp\claude\c--Users-ASUS-Desktop-SSC\52bbd2c5-0ffd-43bb-a22e-8c0a29efff56\scratchpad\agent3"
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[OK]   {name} {detail}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} - {detail}")


def capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


# ---------------------------------------------------------------------------------------
def test_a_pixel_boundary_area():
    m = np.zeros((200, 300), dtype=bool)
    m[20:50, 30:90] = True  # chữ nhật 30x60 = 1800
    polys = project_mask.mask_to_pixel_boundary_polygons(m)
    area = abs(project_mask._ring_area(polys[0]["outer"]))
    check("a) chữ nhật: diện tích biên pixel == số pixel", abs(area - m.sum()) / m.sum() <= 0.01, f"{area} vs {m.sum()}")

    yy, xx = np.mgrid[:200, :300]
    circle = (xx - 150) ** 2 + (yy - 100) ** 2 <= 40 ** 2
    polys = project_mask.mask_to_pixel_boundary_polygons(circle)
    area = abs(project_mask._ring_area(polys[0]["outer"]))
    check("a) tròn r=40: diện tích biên pixel khớp ±1%", abs(area - circle.sum()) / circle.sum() <= 0.01,
          f"{area} vs {circle.sum()}")
    cc = project_mask.mask_to_center_contour_polygons(circle)
    area_cc = abs(project_mask._ring_area(cc[0]["outer"]))
    check("a) đường cũ (contour tâm pixel) hụt diện tích, biên pixel thì không", area_cc < circle.sum() * 0.99,
          f"contour {area_cc:.0f} < pixel {circle.sum()}")

    small = np.zeros((100, 100), dtype=bool)
    small[10:32, 10:33] = True  # 22x23 = 506 px (>= 500)
    a_small = abs(project_mask._ring_area(project_mask.mask_to_pixel_boundary_polygons(small)[0]["outer"]))
    check("a) mask 506 px: sai số diện tích <= 1%", abs(a_small - 506) / 506 <= 0.01, f"{a_small}")

    ring = np.zeros((100, 100), dtype=bool)
    ring[10:60, 10:60] = True
    ring[20:40, 20:40] = False
    p = project_mask.mask_to_pixel_boundary_polygons(ring)
    check("a) có lỗ: 1 polygon, 1 lỗ, area_px trừ lỗ", len(p) == 1 and len(p[0]["holes"]) == 1 and p[0]["area_px"] == 2100,
          str([(q["area_px"], len(q["holes"])) for q in p]))

    rng = np.random.default_rng(1)
    ok = True
    for _ in range(20):
        r = rng.random((30, 40)) < 0.5
        ps = project_mask.mask_to_pixel_boundary_polygons(r)
        ok &= sum(q["area_px"] for q in ps) == int(r.sum())
        g = sum(abs(project_mask._ring_area(q["outer"])) - sum(abs(project_mask._ring_area(h)) for h in q["holes"]) for q in ps)
        ok &= abs(g - r.sum()) < 1e-9
    check("a) 20 mask ngẫu nhiên: tổng diện tích đa giác (trừ lỗ) == số pixel chính xác", ok)


# ---------------------------------------------------------------------------------------
def _calib_of(scene, pose):
    return {
        "camera_id": "T",
        "marker_latlon": list(config.DEMO_MARKER_LATLON),
        "R": pose.R.tolist(),
        "t": pose.t.tolist(),
        "camera_matrix": scene.CAMERA_MATRIX.tolist(),
        "image_size": [scene.WIDTH, scene.HEIGHT],
    }


def test_b_square_03m():
    import scene  # size_test/scene.py

    rows = []
    for fam, dists in (("GAN", (1.0, 2.0, 3.0)), ("XA", (2.0, 3.0))):
        pose = scene.make_pose(fam, 0)
        calib = _calib_of(scene, pose)
        for d in dists:
            obj = scene.make_flat_object("vuong_0.3", d, 0.0)
            _, masks = scene.render_scene(pose, [obj])
            mask = masks[obj.uid] > 0
            new = project_mask.project_mask_to_ground_m(mask, calib, boundary="pixel")["area_m2"]
            old = project_mask.project_mask_to_ground_m(mask, calib, boundary="contour_center")["area_m2"]
            e_new = 100 * (new - obj.true_area_m2) / obj.true_area_m2
            e_old = 100 * (old - obj.true_area_m2) / obj.true_area_m2
            rows.append((fam, d, e_old, e_new))
            check(f"b) [{fam} @{d:g} m] vuông 0.3 m, biên pixel sai số <= 2%", abs(e_new) <= 2.0,
                  f"{e_new:+.2f}% (contour tâm pixel cũ: {e_old:+.2f}%)")
            check(f"b) [{fam} @{d:g} m] biên pixel tốt hơn contour tâm pixel", abs(e_new) < abs(e_old))
            if (fam, d) == ("GAN", 2.0):
                # GeoJSON (đường mask) -> mét -> diện tích khớp diện tích mét
                feat = project_mask.project_mask_to_geojson(None, (scene.WIDTH, scene.HEIGHT), calib, mask=mask)
                ring = feat["geometry"]["coordinates"][0]
                lat0, lon0 = config.DEMO_MARKER_LATLON
                r = np.asarray(ring[:-1], dtype=np.float64)
                east = np.radians(r[:, 0] - lon0) * config.EARTH_RADIUS_M * math.cos(math.radians(lat0))
                north = np.radians(r[:, 1] - lat0) * config.EARTH_RADIUS_M
                a_geo = project_mask.polygon_area_m2(np.stack([east, north], axis=1))
                check("b) GeoJSON đường mask: diện tích đổi ngược về mét khớp < 0.5%", abs(a_geo - new) / new < 0.005,
                      f"{a_geo:.5f} vs {new:.5f}")
                check("b) properties có area_m2 / boundary", abs(feat["properties"]["area_m2"] - new) < 1e-12
                      and feat["properties"]["boundary"] == "pixel")
                # đường polygon_norm (cũ) giống hệt vòng lặp gốc từng điểm
                contour = project_mask.mask_to_center_contour_polygons(mask)[0]["outer"]
                norm = [(u / scene.WIDTH, v / scene.HEIGHT) for u, v in contour]
                f_old, _ = capture(project_mask.project_mask_to_geojson, norm, (scene.WIDTH, scene.HEIGHT), calib)
                f_flag, _ = capture(project_mask.project_mask_to_geojson, norm, (scene.WIDTH, scene.HEIGHT), calib,
                                    boundary="contour_center")
                K = np.array(calib["camera_matrix"])
                R = np.array(calib["R"]); t = np.array(calib["t"])
                C = project_mask.camera_origin_in_marker_frame(R, t)
                ref = []
                for xn, yn in norm:
                    ray = camera_model.pixel_to_ray(K, xn * scene.WIDTH, yn * scene.HEIGHT)
                    g = project_mask.intersect_ray_with_ground(C, project_mask.ray_to_marker_frame(ray, R))
                    la, lo = project_mask.meters_to_latlon(lat0, lon0, g[0], g[1])
                    ref.append([lo, la])
                ref.append(list(ref[0]))
                got = f_old["geometry"]["coordinates"][0]
                check("b) polygon_norm: đầu ra GIỐNG HỆT vòng lặp gốc (tương thích ngược)", got == ref)
                check("b) boundary='contour_center' (polygon_norm) cũng giống hệt", f_flag["geometry"]["coordinates"][0] == ref)
    return rows


# ---------------------------------------------------------------------------------------
def test_c_aspect():
    calib = {
        "camera_id": "ASP", "marker_latlon": [10.0, 106.0],
        "R": np.eye(3).tolist(), "t": [0.0, 0.0, 2.0],
        "camera_matrix": camera_model.build_camera_matrix(640, 480, 66.0).tolist(),
        "image_size": [640, 480],
    }
    # R,t sao cho camera nhìn xuống: X_cam = R X + t, dùng pose size_test cho chắc
    import scene
    pose = scene.make_pose("GAN", 0)
    calib["R"], calib["t"] = pose.R.tolist(), pose.t.tolist()

    poly = [(0.3, 0.6), (0.6, 0.6), (0.6, 0.9), (0.3, 0.9)]
    raised, msg = False, ""
    try:
        project_mask.project_mask_to_geojson(poly, (1024, 1024), calib)
    except ValueError as exc:
        raised, msg = True, str(exc)
    check("c) ảnh 1024x1024 vs hiệu chỉnh 640x480, không cờ -> ValueError", raised)
    check("c) thông báo lỗi tiếng Việt nêu tỉ lệ + cách xử lý", "tỉ lệ" in msg and "allow_aspect_mismatch" in msg, msg[:80])
    raised2 = False
    try:
        project_mask.project_mask_to_ground_m(np.ones((100, 100), bool), calib)
    except ValueError:
        raised2 = True
    check("c) project_mask_to_ground_m cũng ValueError khi lệch tỉ lệ", raised2)

    project_mask.reset_warnings()
    (f1, out1) = capture(project_mask.project_mask_to_geojson, poly, (1024, 1024), calib, allow_aspect_mismatch=True)
    (f2, out2) = capture(project_mask.project_mask_to_geojson, poly, (1024, 1024), calib, allow_aspect_mismatch=True)
    (_, out3) = capture(project_mask.project_polygons_to_geojson, [poly], (1024, 1024), calib, allow_aspect_mismatch=True)
    n_warn = (out1 + out2 + out3).count("tỉ lệ khung hình")
    check("c) có cờ: chạy được ra Polygon", f1 is not None and f1["geometry"]["type"] == "Polygon")
    check("c) có cờ: cảnh báo lệch tỉ lệ in ĐÚNG 1 lần cho 3 lần chiếu", n_warn == 1, f"{n_warn} lần")
    check("c) lần chiếu thứ 2 không in lại", "tỉ lệ khung hình" not in out2)
    check("c) 2 lần chiếu cho cùng kết quả", f1["geometry"] == f2["geometry"])

    K = project_mask._scaled_camera_matrix(calib, (1024, 1024), allow_aspect_mismatch=True)
    check("c) hệ số co giãn thống nhất: fx == fy (không méo pixel)", abs(K[0, 0] - K[1, 1]) < 1e-9, f"{K[0, 0]:.3f}/{K[1, 1]:.3f}")
    s = math.hypot(1024, 1024) / math.hypot(640, 480)
    check("c) hệ số = tỉ số đường chéo ảnh", abs(K[0, 0] - 615.9459855258331 * s) < 1e-6)

    K2, _ = capture(project_mask._scaled_camera_matrix, calib, (1280, 960))  # cùng 4:3 -> không cần cờ
    check("c) cùng tỉ lệ 4:3 (1280x960) không cần cờ, fx = 2x", abs(K2[0, 0] - 2 * 615.9459855258331) < 1e-6)
    K3 = project_mask._scaled_camera_matrix(calib, (640, 480))
    check("c) cùng kích thước: trả nguyên camera_matrix", np.allclose(K3, np.array(calib["camera_matrix"])))
    near, _ = capture(project_mask._scaled_camera_matrix, calib, (644, 480))  # lệch 0.6% < 1%
    check("c) lệch 0.6% (< 1%) vẫn chấp nhận", near is not None)


# ---------------------------------------------------------------------------------------
def test_d_parse_labels():
    import run_demo_vehtruong as rdv

    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
        p = Path(td) / "x.txt"
        p.write_text(
            "0 0.1 0.1 0.2 0.1 0.2 0.2\n"
            "1 0.5 0.5 0.6 0.5 0.6 0.6\n"      # lớp khác
            "0 0.3 0.3 0.4 0.3 0.4 0.4 0.3 0.4\n"
            "0 0.1 0.1 0.2\n"                   # thiếu đỉnh -> bỏ
            "\n"
            "0 0.7 0.7 0.8 0.7 0.8 0.8\n",
            encoding="utf-8",
        )
        polys = rdv.parse_yolo_seg_polygons(p, 0)
        check("d) đọc ĐỦ 3 polygon lớp Trash (không chỉ cái đầu)", len(polys) == 3, f"{len(polys)}")
        check("d) polygon thứ 2 có 4 đỉnh", len(polys[1]) == 4)
        check("d) parse_yolo_seg_polygon cũ vẫn trả polygon đầu", rdv.parse_yolo_seg_polygon(p, 0) == polys[0])
        empty = Path(td) / "e.txt"
        empty.write_text("", encoding="utf-8")
        check("d) nhãn trống -> []", rdv.parse_yolo_seg_polygons(empty, 0) == [])

    stem, reason = rdv.select_demo_image()
    lbl = config.DATASET_TEST_LABELS_DIR / f"{stem}.txt"
    n = len(rdv.parse_yolo_seg_polygons(lbl, 0)) if lbl.exists() else -1
    check("d) ảnh demo chọn: tphcm/ssc, nhiều polygon", stem.startswith(("tphcm", "ssc")) and n > 1, f"{stem}: {n} polygon ({reason})")
    check("d) chọn ảnh tất định", rdv.select_demo_image()[0] == stem)

    # chiếu đủ polygon -> MultiPolygon
    import scene
    pose = scene.make_pose("GAN", 0)
    calib = _calib_of(scene, pose)
    polys_real = rdv.parse_yolo_seg_polygons(lbl, 0)
    feat, _ = capture(project_mask.project_polygons_to_geojson, polys_real, (1024, 1024), calib, allow_aspect_mismatch=True)
    ok = feat is not None and feat["geometry"]["type"] in ("MultiPolygon", "Polygon") and feat["properties"]["n_polygons"] >= 1
    check("d) project_polygons_to_geojson ra MultiPolygon cho ảnh nhiều polygon",
          ok and feat["geometry"]["type"] == "MultiPolygon", str(feat and (feat["geometry"]["type"], feat["properties"]["n_polygons"])))


# ---------------------------------------------------------------------------------------
def test_e_camera_position():
    pose_path = EXP_DIR / "outputs" / "pose_su_thuc.json"
    if not pose_path.exists():
        check("e) có outputs/pose_su_thuc.json để đối chiếu", False, f"thiếu {pose_path}")
        return
    truth = json.loads(pose_path.read_text(encoding="utf-8"))
    lat0, lon0 = config.DEMO_MARKER_LATLON
    calib = {"camera_id": "TRUTH", "marker_latlon": [lat0, lon0], "R": truth["R"], "t": truth["t"], "source": "synthetic"}
    feat = project_mask.camera_position_geojson(calib)
    p = feat["properties"]
    expect = truth["camera_origin_marker_frame_m"]
    check("e) camera từ R,t khớp vị trí đáp án (Đông, Bắc, cao) <= 1e-9 m",
          max(abs(p["east_m"] - expect[0]), abs(p["north_m"] - expect[1]), abs(p["height_m"] - expect[2])) < 1e-9,
          f"({p['east_m']:.3f}, {p['north_m']:.3f}, {p['height_m']:.3f}) vs {expect}")
    la, lo = project_mask.meters_to_latlon(lat0, lon0, expect[0], expect[1])
    lon, lat = feat["geometry"]["coordinates"]
    check("e) toạ độ lon/lat của camera khớp meters_to_latlon của vị trí đáp án",
          abs(lon - lo) < 1e-12 and abs(lat - la) < 1e-12)
    check("e) camera nằm phía NAM marker (đáp án -2 m Bắc) nên lat < lat marker", lat < lat0)
    check("e) nhãn camera khác nhãn marker", p["label"] == "Camera (tính từ hiệu chỉnh)"
          and project_mask.marker_point_geojson(calib)["properties"]["label"] == "Vị trí bảng đánh dấu")

    demo = config.CALIBRATION_DIR / "DEMO-CAM.json"
    if demo.exists():
        d = json.loads(demo.read_text(encoding="utf-8"))
        dp = project_mask.camera_position_geojson(d)["properties"]
        err = math.dist([dp["east_m"], dp["north_m"], dp["height_m"]], expect)
        check("e) DEMO-CAM.json (hiệu chỉnh từ ảnh giả lập): vị trí camera lệch đáp án < 0.10 m (sai số PnP của chính file hiệu chỉnh)", err < 0.10, f"{err:.4f} m")


# ---------------------------------------------------------------------------------------
def test_f_alias():
    calib = {"camera_id": "A", "source": "synthetic", "marker_latlon": [10.7769, 106.7009]}
    old = project_mask.camera_point_geojson(calib)
    check("f) camera_point_geojson trả toạ độ marker [lon, lat] như cũ",
          old["geometry"] == {"type": "Point", "coordinates": [106.7009, 10.7769]})
    check("f) giữ nguyên camera_id, source", old["properties"]["camera_id"] == "A" and old["properties"]["source"] == "synthetic")
    check("f) alias == marker_point_geojson", old == project_mask.marker_point_geojson(calib))
    check("f) docstring ghi rõ deprecated", "DEPRECATED" in (project_mask.camera_point_geojson.__doc__ or ""))


# ---------------------------------------------------------------------------------------
def test_g_quality_warning():
    base = {"camera_id": "Q1", "marker_latlon": [10.0, 106.0]}
    project_mask.reset_warnings()
    (_, o1) = capture(project_mask.warn_calibration_quality, dict(base))
    check("g) không có khối quality (file cũ) -> im lặng", o1 == "")
    (_, o2) = capture(project_mask.warn_calibration_quality, dict(base, quality={"marker_side_px_min": 80, "warnings": []}))
    check("g) quality.warnings rỗng -> im lặng", o2 == "")
    q = dict(base, quality={"marker_side_px_min": 18.0, "warnings": ["marker quá nhỏ (18 px)", "reproj cao"]})
    (_, o3) = capture(project_mask.warn_calibration_quality, q)
    (_, o4) = capture(project_mask.warn_calibration_quality, q)
    check("g) có warnings -> in 1 lần, chứa nội dung", "marker quá nhỏ" in o3 and "reproj cao" in o3 and o4 == "", repr(o3[:80]))

    SCRATCH.mkdir(parents=True, exist_ok=True)
    import scene
    pose = scene.make_pose("GAN", 0)
    c = dict(_calib_of(scene, pose), camera_id="Q2", quality={"warnings": ["W-TEST"]})
    project_mask.reset_warnings()
    (_, o5) = capture(project_mask.project_mask_to_geojson, [(0.4, 0.6), (0.6, 0.6), (0.5, 0.8)], (640, 480), c)
    (_, o6) = capture(project_mask.project_mask_to_geojson, [(0.4, 0.6), (0.6, 0.6), (0.5, 0.8)], (640, 480), c)
    check("g) cảnh báo cũng in khi chiếu, chỉ 1 lần", o5.count("W-TEST") == 1 and o6.count("W-TEST") == 0)


def test_h_multi_and_holes_geojson():
    import scene
    pose = scene.make_pose("GAN", 0)
    calib = _calib_of(scene, pose)
    m = np.zeros((480, 640), dtype=bool)
    m[300:340, 200:260] = True
    m[400:440, 400:480] = True
    f, _ = capture(project_mask.project_mask_to_geojson, None, (640, 480), calib, mask=m)
    check("h) 2 thành phần -> MultiPolygon", f["geometry"]["type"] == "MultiPolygon" and len(f["geometry"]["coordinates"]) == 2)
    m2 = np.zeros((480, 640), dtype=bool)
    m2[300:400, 200:400] = True
    m2[330:370, 250:350] = False
    f2, _ = capture(project_mask.project_mask_to_geojson, None, (640, 480), calib, mask=m2)
    check("h) có lỗ -> Polygon 2 vòng (ngoài + trong)", f2["geometry"]["type"] == "Polygon" and len(f2["geometry"]["coordinates"]) == 2)
    full = project_mask.project_mask_to_ground_m(m2, calib)
    solid = np.zeros_like(m2); solid[300:400, 200:400] = True
    full_solid = project_mask.project_mask_to_ground_m(solid, calib)
    check("h) diện tích mét có lỗ < không lỗ", full["area_m2"] < full_solid["area_m2"])
    raised = False
    try:
        project_mask.project_mask_to_geojson(None, (640, 480), calib, boundary="xyz", mask=m)
    except ValueError:
        raised = True
    check("h) boundary không hợp lệ -> ValueError", raised)


def main() -> int:
    test_a_pixel_boundary_area()
    rows = test_b_square_03m()
    test_c_aspect()
    test_d_parse_labels()
    test_e_camera_position()
    test_f_alias()
    test_g_quality_warning()
    test_h_multi_and_holes_geojson()
    print("\nBảng sai số diện tích vuông 0.3 m (pose đáp án, variant 0): họ | d | contour tâm pixel cũ | biên pixel mới")
    for fam, d, eo, en in rows:
        print(f"  {fam} {d:g} m | {eo:+.2f}% | {en:+.2f}%")
    print(f"\nKết quả: {PASS} OK, {FAIL} FAIL")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
