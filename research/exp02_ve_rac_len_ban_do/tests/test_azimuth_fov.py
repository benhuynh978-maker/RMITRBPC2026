"""
Test (CPU, không model) cho: hướng bảng (azimuth_deg), FOV (diagonal_fov_deg / công thức EXIF) và
project_mask.ground_footprint_polygon.

  a) marker_xy_to_enu: beta=0 trả y hệt (x,y); beta=90: (1,0)->Nam, (0,1)->Đông; beta=30 đúng công thức, giữ độ dài
  b) beta=0 / thiếu khoá azimuth_deg cho kết quả GIỐNG HỆT ở mọi hàm chiếu; beta=90 xoay đúng
     (project_pixel_polygon_to_ground_m, project_mask_to_ground_m, project_mask_to_geojson (mask & polygon_norm),
      project_polygons_to_geojson, camera_position_geojson)
  c) FOV: công thức 35mm (f=26 -> ~79.6 độ); diagonal_fov_deg kwarg đổi camera_matrix đúng, lưu vào kết quả & JSON
  d) ground_footprint_polygon: hình thang khi nhìn xuống, quạt cắt bán kính khi thấy chân trời, đa giác đơn lồi

Chạy (từ thư mục exp02_ve_rac_len_ban_do):
  C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B tests/test_azimuth_fov.py
File tạm ghi vào scratchpad (không ghi vào project).
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np

EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP_DIR))
sys.path.insert(0, str(EXP_DIR / "webtest"))

import calibrate_aruco  # noqa: E402
import camera_model  # noqa: E402
import config  # noqa: E402
import project_mask as pm  # noqa: E402
from imaging import diagonal_fov_from_35mm  # noqa: E402

SCRATCH = Path(
    r"C:\Users\ASUS\AppData\Local\Temp\claude\c--Users-ASUS-Desktop-SSC\52bbd2c5-0ffd-43bb-a22e-8c0a29efff56\scratchpad\webtest_be"
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


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def load_pose_calib(**extra) -> dict:
    p = json.loads((EXP_DIR / "outputs" / "demo_pose_su_thuc.json").read_text(encoding="utf-8"))
    calib = {
        "camera_id": "T", "marker_latlon": [10.7769, 106.7009], "R": p["R"], "t": p["t"],
        "camera_matrix": p["camera_matrix"], "image_size": p["image_size"],
    }
    calib.update(extra)
    return calib


def horizontal_calib(height=1.5, back=2.0) -> dict:
    """Camera ở (0,-back,height) nhìn NGANG về +Y marker (thấy đường chân trời)."""
    R = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])
    C = np.array([0.0, -back, height])
    t = -R @ C
    cm = camera_model.build_camera_matrix(640, 480, 66.0)
    return {"camera_id": "H", "marker_latlon": [10.0, 106.0], "R": R.tolist(), "t": t.tolist(),
            "camera_matrix": cm.tolist(), "image_size": [640, 480]}


def segments_cross(p1, p2, p3, p4) -> bool:
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return (d1 * d2 < -1e-12) and (d3 * d4 < -1e-12)


def is_simple(poly: np.ndarray) -> bool:
    n = len(poly)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            if segments_cross(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                return False
    return True


def is_convex_ccw(poly: np.ndarray) -> bool:
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i], poly[(i + 1) % n], poly[(i + 2) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            return False
    return True


def main() -> int:
    # ---------------- a) marker_xy_to_enu ----------------
    check("beta=0 trả y hệt (x,y)", pm.marker_xy_to_enu(1.234, -5.6, 0.0) == (1.234, -5.6))
    e, n = pm.marker_xy_to_enu(1.0, 0.0, 0.0)
    check("beta=0: marker (1,0) -> phía ĐÔNG", e == 1.0 and n == 0.0)
    e, n = pm.marker_xy_to_enu(0.0, 1.0, 0.0)
    check("beta=0: marker (0,1) -> phía BẮC", e == 0.0 and n == 1.0)
    # +X nằm bên PHẢI của +Y khi nhìn từ trên xuống (+Y quay thuận chiều kim đồng hồ 90 độ ra +X), mọi beta
    ok_rot = True
    for beta in (0.0, 17.0, 90.0, 215.0):
        ye, yn = pm.marker_xy_to_enu(0.0, 1.0, beta)
        xe, xn = pm.marker_xy_to_enu(1.0, 0.0, beta)
        ok_rot &= abs(ye - math.sin(math.radians(beta))) < 1e-12 and abs(yn - math.cos(math.radians(beta))) < 1e-12
        ok_rot &= (ye * xn - yn * xe) < 0 and abs(ye * xe + yn * xn) < 1e-12  # tích có hướng Y x X < 0 = X nằm bên phải Y
    check("+X bên phải +Y (quay thuận chiều kim đồng hồ 90 độ), +Y có phương vị beta", ok_rot)
    # get_marker_object_points: trên-phải có x>0, y>0 -> X sang phải, Y lên trên
    op = camera_model.get_marker_object_points(1.0)
    check("get_marker_object_points: +X phải, +Y trên", op[1][0] > 0 and op[1][1] > 0 and op[0][0] < 0 and op[3][1] < 0)
    e, n = pm.marker_xy_to_enu(1.0, 0.0, 90.0)
    check("beta=90: (1,0) -> Nam", abs(e) < 1e-12 and abs(n + 1.0) < 1e-12, f"E={e:.3g} N={n:.3g}")
    e, n = pm.marker_xy_to_enu(0.0, 1.0, 90.0)
    check("beta=90: (0,1) -> Đông", abs(e - 1.0) < 1e-12 and abs(n) < 1e-12, f"E={e:.3g} N={n:.3g}")
    e, n = pm.marker_xy_to_enu(0.0, 1.0, 180.0)
    check("beta=180: (0,1) -> Nam", abs(e) < 1e-12 and abs(n + 1.0) < 1e-12)
    b = math.radians(30.0)
    e, n = pm.marker_xy_to_enu(2.0, 3.0, 30.0)
    e_ref, n_ref = 2.0 * math.cos(b) + 3.0 * math.sin(b), -2.0 * math.sin(b) + 3.0 * math.cos(b)
    check("beta=30 đúng công thức", abs(e - e_ref) < 1e-12 and abs(n - n_ref) < 1e-12)
    check("xoay giữ độ dài", abs(math.hypot(e, n) - math.hypot(2.0, 3.0)) < 1e-12)
    ea, na = pm.marker_xy_to_enu(np.array([1.0, 0.0]), np.array([0.0, 1.0]), 90.0)
    check("hỗ trợ mảng numpy", np.allclose(ea, [0.0, 1.0]) and np.allclose(na, [-1.0, 0.0]))
    e, n = pm.marker_xy_to_enu(1.0, 0.0, 360.0 + 90.0)
    check("beta=450 tương đương 90", abs(e) < 1e-12 and abs(n + 1.0) < 1e-12)
    check("calib_azimuth_deg mặc định 0", pm.calib_azimuth_deg({}) == 0.0 and pm.calib_azimuth_deg({"azimuth_deg": 12}) == 12.0)

    # ---------------- b) các hàm chiếu ----------------
    c_old = load_pose_calib()                       # không có khoá azimuth_deg
    c_0 = load_pose_calib(azimuth_deg=0.0)
    c_90 = load_pose_calib(azimuth_deg=90.0)
    c_30 = load_pose_calib(azimuth_deg=30.0)
    mask = np.zeros((480, 640), dtype=bool)
    mask[300:345, 280:370] = True
    mask[320:330, 300:310] = False  # có lỗ
    poly_norm = [(0.4, 0.6), (0.6, 0.6), (0.6, 0.8), (0.4, 0.8)]

    g_old = quiet(pm.project_mask_to_ground_m, mask, c_old)
    g_0 = quiet(pm.project_mask_to_ground_m, mask, c_0)
    g_90 = quiet(pm.project_mask_to_ground_m, mask, c_90)
    same = all(np.array_equal(a["outer_m"], b_["outer_m"]) for a, b_ in zip(g_old["polygons"], g_0["polygons"]))
    check("project_mask_to_ground_m: beta=0 == không có khoá", same and g_old["area_m2"] == g_0["area_m2"])
    ok90 = True
    for a, b_ in zip(g_0["polygons"], g_90["polygons"]):
        ex, ny = pm.marker_xy_to_enu(a["outer_m"][:, 0], a["outer_m"][:, 1], 90.0)
        ok90 &= np.allclose(np.stack([ex, ny], 1), b_["outer_m"], atol=1e-12)
        ok90 &= abs(a["area_m2"] - b_["area_m2"]) < 1e-9
    check("project_mask_to_ground_m: beta=90 xoay đúng, diện tích giữ", ok90)

    f_old = quiet(pm.project_mask_to_geojson, None, (640, 480), c_old, mask=mask)
    f_0 = quiet(pm.project_mask_to_geojson, None, (640, 480), c_0, mask=mask)
    check("project_mask_to_geojson(mask): beta=0 == không có khoá", f_old == f_0)
    f_30 = quiet(pm.project_mask_to_geojson, None, (640, 480), c_30, mask=mask)
    ring0 = np.array(f_0["geometry"]["coordinates"][0])
    ring30 = np.array(f_30["geometry"]["coordinates"][0])
    lat0, lon0 = c_0["marker_latlon"]

    def to_en(ring):  # [lon,lat] -> mét Đông/Bắc quanh marker
        east = np.radians(ring[:, 0] - lon0) * config.EARTH_RADIUS_M * math.cos(math.radians(lat0))
        north = np.radians(ring[:, 1] - lat0) * config.EARTH_RADIUS_M
        return np.stack([east, north], 1)
    en0, en30 = to_en(ring0), to_en(ring30)
    ex, ny = pm.marker_xy_to_enu(en0[:, 0], en0[:, 1], 30.0)
    check("project_mask_to_geojson(mask): beta=30 xoay quanh marker", np.allclose(np.stack([ex, ny], 1), en30, atol=1e-3),
          f"max lệch {np.abs(np.stack([ex, ny], 1) - en30).max():.2e} m")

    p_old = quiet(pm.project_mask_to_geojson, poly_norm, (640, 480), c_old)
    p_0 = quiet(pm.project_mask_to_geojson, poly_norm, (640, 480), c_0)
    p_90 = quiet(pm.project_mask_to_geojson, poly_norm, (640, 480), c_90)
    check("project_mask_to_geojson(polygon_norm): beta=0 == không có khoá", p_old == p_0)
    en0 = to_en(np.array(p_0["geometry"]["coordinates"][0]))
    en90 = to_en(np.array(p_90["geometry"]["coordinates"][0]))
    ex, ny = pm.marker_xy_to_enu(en0[:, 0], en0[:, 1], 90.0)
    check("project_mask_to_geojson(polygon_norm): beta=90 xoay đúng", np.allclose(np.stack([ex, ny], 1), en90, atol=1e-3))

    m_old = quiet(pm.project_polygons_to_geojson, [poly_norm], (640, 480), c_old)
    m_0 = quiet(pm.project_polygons_to_geojson, [poly_norm], (640, 480), c_0)
    m_90 = quiet(pm.project_polygons_to_geojson, [poly_norm], (640, 480), c_90)
    check("project_polygons_to_geojson: beta=0 == không có khoá", m_old == m_0)
    en0 = to_en(np.array(m_0["geometry"]["coordinates"][0]))
    en90 = to_en(np.array(m_90["geometry"]["coordinates"][0]))
    ex, ny = pm.marker_xy_to_enu(en0[:, 0], en0[:, 1], 90.0)
    check("project_polygons_to_geojson: beta=90 xoay đúng", np.allclose(np.stack([ex, ny], 1), en90, atol=1e-3))

    cam_old = pm.camera_position_geojson(c_old)
    cam_0 = pm.camera_position_geojson(c_0)
    cam_90 = pm.camera_position_geojson(c_90)
    check("camera_position_geojson: beta=0 == không có khoá", cam_old == cam_0)
    check("camera_position_geojson: beta=0 camera ở (0,-2) m, cao 1.5",
          abs(cam_0["properties"]["east_m"]) < 1e-9 and abs(cam_0["properties"]["north_m"] + 2.0) < 1e-9
          and abs(cam_0["properties"]["height_m"] - 1.5) < 1e-9)
    check("camera_position_geojson: beta=90 camera ở phía TÂY (-2,0)",
          abs(cam_90["properties"]["east_m"] + 2.0) < 1e-9 and abs(cam_90["properties"]["north_m"]) < 1e-9
          and abs(cam_90["properties"]["height_m"] - 1.5) < 1e-9)
    check("marker_point_geojson không đổi theo azimuth", pm.marker_point_geojson(c_90)["geometry"] == pm.marker_point_geojson(c_0)["geometry"])

    # ---------------- c) FOV ----------------
    fov = diagonal_fov_from_35mm(26.0)
    check("FOV từ f35=26 mm ~79.6 độ", abs(fov - 79.6) < 0.1, f"{fov:.3f}")
    check("FOV từ f35=26 khớp công thức 2*atan(43.267/(2f))",
          abs(fov - math.degrees(2 * math.atan(43.267 / 52.0))) < 1e-9)

    img = EXP_DIR / "outputs" / "demo_scene.png"
    r_def = calibrate_aruco.detect_and_solve_pnp(img, config.MARKER_ID, config.DEMO_MARKER_SIZE_MM)
    r_80 = calibrate_aruco.detect_and_solve_pnp(img, config.MARKER_ID, config.DEMO_MARKER_SIZE_MM, diagonal_fov_deg=80.0)
    expect_def = camera_model.build_camera_matrix(640, 480, config.DIAGONAL_FOV_DEG)
    expect_80 = camera_model.build_camera_matrix(640, 480, 80.0)
    check("mặc định dùng config.DIAGONAL_FOV_DEG", np.allclose(r_def["camera_matrix"], expect_def)
          and r_def["diagonal_fov_deg"] == config.DIAGONAL_FOV_DEG)
    check("diagonal_fov_deg=80 đổi camera_matrix", np.allclose(r_80["camera_matrix"], expect_80)
          and r_80["diagonal_fov_deg"] == 80.0 and r_80["camera_matrix"][0, 0] < r_def["camera_matrix"][0, 0])
    SCRATCH.mkdir(parents=True, exist_ok=True)
    out = SCRATCH / "t_fov_calib.json"
    data = calibrate_aruco.save_calibration("T", (10.0, 106.0), r_80, "aruco", out)
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    old_keys = {"camera_id", "marker_latlon", "R", "t", "camera_matrix", "image_size", "reproj_error_rms_px",
                "created_at", "source", "quality"}
    check("save_calibration lưu diagonal_fov_deg, giữ nguyên khoá cũ",
          on_disk.get("diagonal_fov_deg") == 80.0 and old_keys <= set(on_disk) and data == on_disk)
    out.unlink()
    r_old_style = {k: v for k, v in r_80.items() if k != "diagonal_fov_deg"}
    data2 = calibrate_aruco.save_calibration("T", (10.0, 106.0), r_old_style, "aruco", out)
    check("save_calibration với kết quả kiểu cũ (không có FOV) vẫn chạy", "diagonal_fov_deg" not in data2)
    out.unlink()
    try:
        calibrate_aruco.detect_and_solve_pnp(img, config.MARKER_ID, config.DEMO_MARKER_SIZE_MM, diagonal_fov_deg=0.0)
        check("FOV=0 bị từ chối", False)
    except ValueError:
        check("FOV=0 bị từ chối (ValueError)", True)

    # ---------------- d) ground_footprint_polygon ----------------
    ref = load_pose_calib()
    for rng in (3.0, 12.0):
        fp = pm.ground_footprint_polygon(ref, (640, 480), rng)
        foot = np.array([0.0, -2.0])
        dmax = float(np.linalg.norm(fp - foot, axis=1).max())
        check(f"footprint nhìn xuống (R={rng}): đa giác đơn, lồi, ngược chiều kim đồng hồ",
              len(fp) >= 3 and is_simple(fp) and is_convex_ccw(fp) and pm._ring_area(fp) > 0)
        check(f"footprint nhìn xuống (R={rng}): mọi đỉnh trong bán kính", dmax <= rng + 1e-9, f"max {dmax:.3f}")
    fp12 = pm.ground_footprint_polygon(ref, (640, 480), 12.0)
    # Không thấy chân trời: đúng hình thang 4 đỉnh. Cạnh gần = giao tia đáy ảnh với đất; cạnh xa = tia đỉnh ảnh.
    pts4, valid4 = pm.pixels_to_ground_xy(np.array([[-0.5, 479.5], [639.5, 479.5], [639.5, -0.5], [-0.5, -0.5]]),
                                          np.array(ref["camera_matrix"]), np.array(ref["R"]), np.array(ref["t"]))
    got = {tuple(np.round(p, 6)) for p in fp12}
    want = {tuple(np.round(p, 6)) for p in pts4}
    check("footprint (R lớn) khớp 4 góc ảnh chiếu xuống đất", valid4.all() and got == want, f"{sorted(got)}")
    # điểm giữa ảnh phải nằm trong đa giác
    ctr, _ = pm.pixels_to_ground_xy(np.array([[320.0, 240.0]]), np.array(ref["camera_matrix"]), np.array(ref["R"]), np.array(ref["t"]))
    check("điểm giữa ảnh nằm trong footprint", bool(
        all((fp12[(i + 1) % len(fp12)][0] - fp12[i][0]) * (ctr[0][1] - fp12[i][1])
            - (fp12[(i + 1) % len(fp12)][1] - fp12[i][1]) * (ctr[0][0] - fp12[i][0]) > 0 for i in range(len(fp12)))))
    fp3 = pm.ground_footprint_polygon(ref, (640, 480), 3.0)
    check("R nhỏ hơn: diện tích nhỏ hơn và có cung tròn (>4 đỉnh)", pm._ring_area(fp3) < pm._ring_area(fp12) and len(fp3) > 4)

    hc = horizontal_calib()
    foot = np.array([0.0, -2.0])
    fph = pm.ground_footprint_polygon(hc, (640, 480), 10.0)
    dist = np.linalg.norm(fph - foot, axis=1)
    half_angle = math.degrees(math.atan((320.0) / hc["camera_matrix"][0][0]))
    area_h = pm._ring_area(fph)
    check("footprint thấy chân trời: đa giác đơn, lồi", len(fph) >= 4 and is_simple(fph) and is_convex_ccw(fph) and area_h > 0)
    check("footprint thấy chân trời: mọi đỉnh trong bán kính R, đỉnh xa nằm đúng trên cung R",
          dist.max() <= 10.0 + 1e-9 and abs(dist.max() - 10.0) < 1e-9 and (dist > 10.0 - 1e-9).sum() >= 10, f"{(dist > 10.0 - 1e-9).sum()} đỉnh trên cung")
    check("footprint thấy chân trời: nằm hoàn toàn PHÍA TRƯỚC camera (y >= -2)", bool((fph[:, 1] >= -2.0 - 1e-9).all()))
    sector = 0.5 * 100.0 * math.radians(2 * half_angle)
    check("footprint thấy chân trời: diện tích trong (nửa quạt gần đúng, nhỏ hơn quạt đầy đủ)", 0.3 * sector < area_h < sector,
          f"area {area_h:.1f} < quạt {sector:.1f}")
    ang = np.degrees(np.arctan2(fph[:, 0] - foot[0], fph[:, 1] - foot[1]))
    check("góc mở footprint ~ góc mở ngang của ảnh", abs((ang.max() - ang.min()) - 2 * half_angle) < 1.0,
          f"{ang.max() - ang.min():.1f} vs {2 * half_angle:.1f}")

    # camera nhìn lên trời: không thấy mặt đất
    up = horizontal_calib()
    Rup = np.eye(3)  # trục quang = +Z marker (thẳng lên trời)
    up["R"] = Rup.tolist()
    up["t"] = (-Rup @ np.array([0.0, -2.0, 1.5])).tolist()
    check("camera nhìn lên trời -> footprint rỗng", len(pm.ground_footprint_polygon(up, (640, 480), 10.0)) == 0)
    try:
        pm.ground_footprint_polygon(ref, (640, 480), 0.0)
        check("max_range_m<=0 bị từ chối", False)
    except ValueError:
        check("max_range_m<=0 bị từ chối (ValueError)", True)

    print(f"\nTổng: {PASS} đạt, {FAIL} hỏng")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
