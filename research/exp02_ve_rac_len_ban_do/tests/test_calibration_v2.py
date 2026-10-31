"""
Test cho calibrate_aruco phiên bản mới (SUBPIX + IPPE_SQUARE + khối quality + cảnh báo). CPU, vài giây.
KHÔNG ghi vào outputs/ hay calibration/ dùng chung: mọi file tạm nằm trong thư mục tạm của hệ điều hành,
CLI được test bằng cách trỏ config.CALIBRATION_DIR sang thư mục tạm.

Chạy: C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B tests/test_calibration_v2.py
(từ thư mục exp02_ve_rac_len_ban_do; các hàm test_* dùng assert nên cũng chạy được bằng pytest)
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import cv2
import numpy as np

EXP_DIR = Path(__file__).resolve().parent.parent
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import calib_quality  # noqa: E402
import calibrate_aruco  # noqa: E402
import config  # noqa: E402


def _load(name: str, path: Path):
    """Nạp module theo đường dẫn với tên riêng (stress_test/scene.py và size_test/scene.py trùng tên 'scene')."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


st = _load("_stress_scene", EXP_DIR / "stress_test" / "scene.py")
sz = _load("_size_scene", EXP_DIR / "size_test" / "scene.py")

TMP = Path(tempfile.mkdtemp(prefix="exp02_calib_v2_"))
BOARD_M = config.PRINT_MARKER_SIZE_MM / 1000.0  # 0.25 m


def _write(img: np.ndarray, name: str, jpeg_q: int | None = None) -> Path:
    p = TMP / name
    if jpeg_q is None:
        cv2.imwrite(str(p), img)
    else:
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_q)])
    return p


def _scene(D, theta, az=40.0, off=(20.0, -15.0), size_m=BOARD_M):
    R, t, C = st.make_pose(D, theta, az, off)
    return R, t, C, st.render(R, t, marker_size_m=size_m)


def _solve(path, size_mm=config.PRINT_MARKER_SIZE_MM, **kw):
    return calibrate_aruco.detect_and_solve_pnp(path, config.MARKER_ID, size_mm, **kw)


# ---------------------------------------------------------------------------------------------
def test_a_clean_2m_no_warnings():
    """(a) Ảnh sạch ở ~2 m (bảng 250 mm): sai số xoay < 1 deg và quality.warnings rỗng; PNG và JPEG q95."""
    R, t, C, img = _scene(2.0, 30.0)
    for name, q in (("a.png", None), ("a_q95.jpg", 95)):
        res = _solve(_write(img, name, q))
        rot = st.rotation_error_deg(R, res["R"])
        pos = float(np.linalg.norm(st.camera_center(res["R"], res["t"]) - C))
        qual = res["quality"]
        print(f"  {name}: xoay {rot:.3f} deg, vị trí {pos:.3f} m, cạnh ngắn {qual['marker_side_px_min']:.1f} px, "
              f"chọn theo {qual['solution_chosen_by']}, mơ hồ {qual['ambiguity_ratio']:.1f}, "
              f"nét {qual['sharpness_norm']:.2f}, jpeg~{qual['jpeg_quality_est']}")
        assert rot < 1.0, f"{name}: xoay {rot:.3f} deg >= 1"
        assert qual["warnings"] == [], f"{name}: có cảnh báo ngoài ý muốn: {qual['warnings']}"
        for k in ("marker_side_px_min", "marker_side_px_mean", "reproj_rms", "ambiguity_ratio",
                  "solution_chosen_by", "sharpness", "warnings"):
            assert k in qual, f"thiếu khoá quality.{k}"
        for k in ("R", "t", "camera_matrix", "image_size", "reproj_error_rms_px"):  # khoá cũ vẫn còn
            assert k in res


def test_b_small_board_warns():
    """(b) Bảng nhỏ trên ảnh: < 50 px (mức DUY NHẤT) -> cảnh báo + is_too_small; thư viện KHÔNG raise."""
    assert calib_quality.MIN_SIDE_PX == 50.0
    for D, name in ((4.0, "b4.png"), (6.0, "b6.png")):
        _R, _t, _C, img = _scene(D, 20.0)
        q = _solve(_write(img, name))["quality"]  # không raise dù bảng nhỏ
        print(f"  {D:g} m: cạnh ngắn {q['marker_side_px_min']:.1f} px -> {len(q['warnings'])} cảnh báo")
        assert q["marker_side_px_min"] < calib_quality.MIN_SIDE_PX
        assert calib_quality.is_too_small(q["marker_side_px_min"])
        assert any("Bảng quá nhỏ" in w for w in q["warnings"])
        assert not any("KHÔNG TIN CẬY" in w for w in q["warnings"])  # không còn mức 30 px


def test_c_flip_case_gan_v4_q12():
    """
    (c) Ca lật tái hiện từ size_test: GAN-v4 ở JPEG q12 (marker 200 mm).
      - legacy=True vẫn lật (xoay > 60 deg) -> đúng như báo cáo cũ.
      - mặc định: KHÔNG có độ cao -> có cảnh báo mơ hồ (ambiguity_ratio < 3).
      - có camera_height_m đúng: vì hai nghiệm IPPE có cùng độ cao (lật đối xứng), độ cao KHÔNG phân biệt được
        -> code không dùng độ cao để chọn: vẫn chọn theo reproj và vẫn cảnh báo. (Phát hiện ghi trong báo cáo.)
      - GAN-v2 / XA-v2 q12 (legacy lật 82-85 deg) -> bản mới ra xoay < 10 deg.
    """
    def case(fam, vi):
        pose = sz.make_pose(fam, vi)
        img, _ = sz.render_scene(pose, [])
        return pose, _write(img, f"c_{fam}{vi}.jpg", 12)

    pose, p = case("GAN", 4)
    size_mm = config.MARKER_SIZE_MM
    old = _solve(p, size_mm, legacy=True)
    rot_old = st.rotation_error_deg(pose.R, old["R"])
    new = _solve(p, size_mm)
    rot_new = st.rotation_error_deg(pose.R, new["R"])
    withh = _solve(p, size_mm, camera_height_m=pose.height_m)
    print(f"  GAN-v4 q12: legacy xoay {rot_old:.1f} deg; mới xoay {rot_new:.1f} deg, mơ hồ "
          f"{new['quality']['ambiguity_ratio']:.2f}; có độ cao đúng -> chọn theo {withh['quality']['solution_chosen_by']}, "
          f"xoay {st.rotation_error_deg(pose.R, withh['R']):.1f} deg")
    assert rot_old > 60.0, "không tái hiện được ca lật của bản cũ"
    assert new["quality"]["ambiguity_ratio"] < calib_quality.AMBIGUITY_MIN_RATIO
    assert any("có thể lật" in w for w in new["quality"]["warnings"])
    assert withh["quality"]["solution_chosen_by"] == "reproj"
    assert any("có thể lật" in w for w in withh["quality"]["warnings"]), "có độ cao mà vẫn mơ hồ phải còn cảnh báo"

    for fam, vi in (("GAN", 2), ("XA", 2)):
        pose, p = case(fam, vi)
        old = st.rotation_error_deg(pose.R, _solve(p, size_mm, legacy=True)["R"])
        new = st.rotation_error_deg(pose.R, _solve(p, size_mm)["R"])
        print(f"  {fam}-v{vi} q12: legacy xoay {old:.1f} deg -> mới {new:.1f} deg")
        assert old > 60.0 and new < 10.0


def test_c2_height_rules():
    """Độ cao đo tay chỉ để KIỂM TRA CHÉO: (i) độ cao ước lượng khớp thật; (ii) nhập sai xa -> cảnh báo lệch
    > 20% nhưng nghiệm chọn KHÔNG đổi (chọn theo reproj); (iii) nhập thấp/cao bất kỳ không làm pose khác
    kết quả khi không nhập độ cao (lỗi cũ: nhập thấp hơn thực tế làm chọn nhầm nghiệm lật 44/45 ca)."""
    _R, _t, C, img = _scene(2.0, 30.0)
    p = _write(img, "c2.png")
    ok = _solve(p, camera_height_m=float(C[2]))
    q = ok["quality"]
    print(f"  độ cao thật {C[2]:.2f} m, ước lượng {q['camera_height_m_est']:.2f} m, chọn theo {q['solution_chosen_by']}")
    assert abs(q["camera_height_m_est"] - C[2]) / C[2] < 0.05
    assert q["warnings"] == []  # độ cao khớp -> không cảnh báo lệch

    base = _solve(p)
    for factor in (0.5, 0.7, 1.0, 3.0):
        res = _solve(p, camera_height_m=float(C[2]) * factor)
        assert res["quality"]["solution_chosen_by"] != "height"
        assert np.array_equal(res["R"], base["R"]) and np.array_equal(res["t"], base["t"]), (
            f"độ cao nhập x{factor} làm đổi nghiệm pose được chọn")
        lech = any("lệch" in w for w in res["quality"]["warnings"])
        assert lech == (factor != 1.0), (factor, res["quality"]["warnings"])

    # thư viện từ chối độ cao không hợp lệ
    for bad_h in (0.0, -1.0):
        try:
            _solve(p, camera_height_m=bad_h)
        except ValueError:
            pass
        else:
            raise AssertionError(f"camera_height_m={bad_h} phải bị từ chối")


def test_d_legacy_identical_to_old():
    """(d) legacy=True giống hệt bản cũ: so với cv2.solvePnP viết tay + (nếu còn bản cũ) calibration/DEMO-CAM.json."""
    img_path = config.OUTPUTS_DIR / "synthetic_scene.png"
    assert img_path.exists(), "thiếu outputs/synthetic_scene.png"
    res = _solve(img_path, config.MARKER_SIZE_MM, legacy=True)

    # Bản sao logic cũ (không SUBPIX, solvePnP mặc định ITERATIVE)
    import cv2.aruco as aruco
    import camera_model
    gray = cv2.cvtColor(cv2.imread(str(img_path)), cv2.COLOR_BGR2GRAY)
    det = aruco.ArucoDetector(aruco.getPredefinedDictionary(config.ARUCO_DICT), aruco.DetectorParameters())
    corners, ids, _ = det.detectMarkers(gray)
    pts = corners[ids.flatten().tolist().index(config.MARKER_ID)].reshape(4, 2).astype(np.float64)
    K = camera_model.build_camera_matrix(gray.shape[1], gray.shape[0], config.DIAGONAL_FOV_DEG)
    ok, rvec, tvec = cv2.solvePnP(camera_model.get_marker_object_points(config.MARKER_SIZE_MM / 1000.0),
                                  pts, K, np.zeros((5, 1)))
    R_ref, _ = cv2.Rodrigues(rvec)
    assert ok and np.array_equal(res["R"], R_ref) and np.array_equal(res["t"], tvec.reshape(3))
    assert res["quality"]["solution_chosen_by"] == "legacy"

    ref_json = config.CALIBRATION_DIR / "DEMO-CAM.json"
    if ref_json.exists():
        data = json.loads(ref_json.read_text(encoding="utf-8"))
        if "quality" not in data:  # file do bản cũ sinh ra (nếu agent khác đã sinh lại bằng bản mới thì bỏ qua)
            dR = float(np.abs(res["R"] - np.array(data["R"])).max())
            dt = float(np.abs(res["t"] - np.array(data["t"])).max())
            print(f"  legacy so với DEMO-CAM.json (bản cũ): max|dR| {dR:.2e}, max|dt| {dt:.2e}")
            assert dR < 1e-9 and dt < 1e-9
            assert abs(res["reproj_error_rms_px"] - data["reproj_error_rms_px"]) < 1e-9
        else:
            print("  [bỏ qua so với DEMO-CAM.json: file đã được sinh lại bằng bản mới]")


def test_e_sharpness_threshold():
    """Ngưỡng độ nét: ảnh nét không bị cảnh báo mờ; mờ Gauss sigma 1.0 và 2.0 (rồi JPEG q25) bị cảnh báo."""
    flagged = {0.0: 0, 1.0: 0, 2.0: 0}
    n = 0
    for D, th, az in ((1.0, 20, 10), (1.5, 45, 100), (2.0, 30, 200), (3.0, 20, 300)):
        _R, _t, _C, img = _scene(D, th, az)
        n += 1
        for sg in flagged:
            im = st.degrade(img, blur_sigma=sg)
            res = _solve(_write(im, f"e_{D}_{sg}.jpg", 25))
            blur = any("bị mờ" in w for w in res["quality"]["warnings"])
            flagged[sg] += int(blur)
            print(f"  D={D} th={th} sigma={sg}: sharpness_norm={res['quality']['sharpness_norm']:.3f} mờ={blur}")
    assert flagged[0.0] == 0, "ảnh nét bị báo mờ"
    assert flagged[1.0] == n and flagged[2.0] == n, f"ảnh mờ không bị báo: {flagged}"


def test_f_jpeg_quality_estimate():
    """Ước lượng chất lượng JPEG từ bảng lượng tử hoá: đúng ±2 so với q của OpenCV; PNG -> None; < 60 -> cảnh báo."""
    _R, _t, _C, img = _scene(2.0, 30.0)
    for q in (95, 75, 50, 30, 12):
        est = calib_quality.estimate_jpeg_quality(_write(img, f"f{q}.jpg", q))
        print(f"  q={q}: ước lượng {est}")
        assert est is not None and abs(est - q) <= 2
    assert calib_quality.estimate_jpeg_quality(_write(img, "f.png")) is None
    w30 = _solve(_write(img, "f30b.jpg", 30))["quality"]["warnings"]
    w95 = _solve(_write(img, "f95b.jpg", 95))["quality"]["warnings"]
    assert any("JPEG chất lượng thấp" in w for w in w30) and not w95


def test_g_cli_exit_codes_and_json():
    """
    CLI: bảng >= 50 px -> mã 0 và GHI file (kể cả có cảnh báo khác); bảng < 50 px (~40 px) -> mã 3 và KHÔNG
    ghi file; không còn cờ --cho-phep-khong-tin-cay; ảnh không tồn tại -> mã 1.
    """
    old_dir = config.CALIBRATION_DIR
    config.CALIBRATION_DIR = TMP / "calib"
    try:
        _R, _t, _C, good = _scene(2.0, 30.0)
        pg = _write(good, "g_good.png")
        rc = calibrate_aruco.main(["--image", str(pg), "--camera-id", "T-GOOD"])
        data = json.loads((config.CALIBRATION_DIR / "T-GOOD.json").read_text(encoding="utf-8"))
        assert rc == 0
        for k in ("R", "t", "camera_matrix", "image_size", "reproj_error_rms_px", "marker_latlon", "source"):
            assert k in data
        assert data["quality"]["warnings"] == [] and data["quality"]["solution_chosen_by"] in ("reproj", "above_plane_only")
        assert data["quality"]["marker_side_px_min"] >= calib_quality.MIN_SIDE_PX

        # >= 50 px nhưng có cảnh báo khác (độ cao nhập tay lệch > 20%): vẫn lưu, mã 0
        rc = calibrate_aruco.main(["--image", str(pg), "--camera-id", "T-WARN", "--camera-height-m", "0.2"])
        w = json.loads((config.CALIBRATION_DIR / "T-WARN.json").read_text(encoding="utf-8"))["quality"]["warnings"]
        assert rc == 0 and any("lệch" in x for x in w)

        _R, _t, _C, small = _scene(4.0, 20.0)  # cạnh bảng ~40 px (< 50)
        ps = _write(small, "g_small.png")
        side = _solve(ps)["quality"]["marker_side_px_min"]
        print(f"  ảnh nhỏ: cạnh ngắn {side:.1f} px")
        assert 30 <= side < 50
        rc = calibrate_aruco.main(["--image", str(ps), "--camera-id", "T-SMALL", "--camera-height-m", "3"])
        assert rc == 3 == calibrate_aruco.EXIT_TOO_SMALL and not (config.CALIBRATION_DIR / "T-SMALL.json").exists()

        _R, _t, _C, tiny = _scene(6.0, 20.0)
        pt = _write(tiny, "g_tiny.png")
        rc = calibrate_aruco.main(["--image", str(pt), "--camera-id", "T-TINY"])
        assert rc == 3 and not (config.CALIBRATION_DIR / "T-TINY.json").exists()
        # cờ ghi đè đã bị bỏ: argparse từ chối (SystemExit 2) và vẫn không ghi file
        try:
            calibrate_aruco.main(["--image", str(pt), "--camera-id", "T-TINY", "--cho-phep-khong-tin-cay"])
            raise AssertionError("cờ --cho-phep-khong-tin-cay phải bị gỡ")
        except SystemExit as e:
            assert e.code == 2
        assert not (config.CALIBRATION_DIR / "T-TINY.json").exists()

        rc = calibrate_aruco.main(["--image", str(TMP / "khong_co.png"), "--camera-id", "T-X"])
        assert rc == 1
        # --marker-size-mm mặc định = config.PRINT_MARKER_SIZE_MM (ảnh good dựng bằng bảng 250 mm đã khớp ở trên)
        assert config.PRINT_MARKER_SIZE_MM == 250.0
    finally:
        config.CALIBRATION_DIR = old_dir


def test_g2_cli_error_message(capsys=None):
    """Thông báo lỗi tiếng Việt khi bảng < 50 px nêu đúng số px, ngưỡng 50 và cách xử lý."""
    import contextlib
    import io
    old_dir = config.CALIBRATION_DIR
    config.CALIBRATION_DIR = TMP / "calib2"
    try:
        _R, _t, _C, small = _scene(4.0, 20.0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = calibrate_aruco.main(["--image", str(_write(small, "g2_small.png")), "--camera-id", "T-MSG"])
        out = buf.getvalue()
        assert rc == 3
        assert "Bảng chỉ chiếm" in out and "(<50 px)" in out
        assert "không đủ tin cậy, hãy dùng bảng lớn hơn hoặc chụp gần hơn" in out
        assert not (config.CALIBRATION_DIR / "T-MSG.json").exists()
    finally:
        config.CALIBRATION_DIR = old_dir


def test_i_synthetic_marker_size_param():
    """make_synthetic_test nhận cỡ bảng: mặc định 200 mm (< 50 px, tương thích test cũ), demo 400 mm (>= 50 px)."""
    import contextlib
    import io
    import make_synthetic_test as mst

    assert config.MARKER_SIZE_MM == 200.0 and config.DEMO_MARKER_SIZE_MM == 400.0
    out = TMP / "synth"
    with contextlib.redirect_stdout(io.StringIO()):
        r200 = mst.main(out_dir=out)                    # mặc định: 200 mm, tên file cũ
        rdemo = mst.main(demo=True, out_dir=out)        # demo: 400 mm, tên file demo_*
        r300 = mst.main(marker_size_mm=300.0, image_name="s300.png", pose_name="s300.json", out_dir=out)
    assert r200["image_path"].name == "synthetic_scene.png" and r200["pose_path"].name == "pose_su_thuc.json"
    assert rdemo["image_path"].name == "demo_scene.png" and rdemo["pose_path"].name == "demo_pose_su_thuc.json"
    sides = {}
    for key, r in (("200", r200), ("400", rdemo), ("300", r300)):
        pose = json.loads(r["pose_path"].read_text(encoding="utf-8"))
        assert pose["marker_size_mm"] == float(key) == r["marker_size_mm"], f"{key}: {pose['marker_size_mm']}"
        res = _solve(r["image_path"], pose["marker_size_mm"])
        sides[key] = res["quality"]["marker_side_px_min"]
        # đáp án pose giống hệt nhau ở mọi cỡ bảng, và PnP khớp lại đáp án
        assert pose["camera_origin_marker_frame_m"] == [0.0, -2.0, 1.5]
        pos = float(np.linalg.norm(st.camera_center(res["R"], res["t"]) - np.array(pose["camera_origin_marker_frame_m"])))
        assert pos < 0.1, f"{key} mm: vị trí camera lệch {pos:.3f} m"
    print(f"  cạnh ngắn nhất trên ảnh: 200 mm {sides['200']:.1f} px, 300 mm {sides['300']:.1f} px, 400 mm {sides['400']:.1f} px")
    assert sides["200"] < calib_quality.MIN_SIDE_PX <= sides["400"]
    assert sides["200"] < sides["300"] < sides["400"]
    assert _solve(rdemo["image_path"], 400.0)["quality"]["warnings"] == []  # demo hết cảnh báo cỡ bảng

    old_dir = config.CALIBRATION_DIR
    config.CALIBRATION_DIR = TMP / "calib3"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rc400 = calibrate_aruco.main(["--image", str(rdemo["image_path"]), "--camera-id", "T-D400", "--marker-size-mm", "400"])
            rc200 = calibrate_aruco.main(["--image", str(r200["image_path"]), "--camera-id", "T-D200", "--marker-size-mm", "200"])
        assert rc400 == 0 and (config.CALIBRATION_DIR / "T-D400.json").exists()
        assert rc200 == 3 and not (config.CALIBRATION_DIR / "T-D200.json").exists()
    finally:
        config.CALIBRATION_DIR = old_dir
    try:
        mst.main(marker_size_mm=0, out_dir=out)
        raise AssertionError("marker_size_mm = 0 phải bị từ chối")
    except ValueError:
        pass


def test_h_warning_rules_pure():
    """Quy tắc cảnh báo thuần (không cần ảnh)."""
    W = calib_quality.build_warnings
    assert W(80, 5.0, False, None, 2.0, 1.0, None) == []
    M = calib_quality.MIN_SIDE_PX
    assert M == 50.0 and not hasattr(calib_quality, "MIN_SIDE_UNRELIABLE_PX") and not hasattr(calib_quality, "has_unreliable")
    assert W(M, 5.0, False, None, 2.0, 1.0, None) == []                  # đúng 50 px: không cảnh báo, không chặn
    assert not calib_quality.is_too_small(M) and calib_quality.is_too_small(M - 0.1)
    assert any("Bảng quá nhỏ" in w for w in W(M - 0.1, 5.0, False, None, 2.0, 1.0, None))
    assert len(W(10.0, 5.0, False, None, 2.0, 1.0, None)) == 1           # chỉ MỘT cảnh báo cỡ bảng, không còn mức 30 px
    assert any("có thể lật" in w for w in W(80, 2.9, True, None, 2.0, 1.0, None))
    assert not any("có thể lật" in w for w in W(80, 3.0, True, None, 2.0, 1.0, None))
    assert not any("có thể lật" in w for w in W(80, 2.0, False, None, 2.0, 1.0, None))  # đã giải bằng mặt phẳng
    assert any("lệch" in w for w in W(80, 5.0, False, 2.0, 2.5, 1.0, None))             # 25% > 20%
    assert not any("lệch" in w for w in W(80, 5.0, False, 2.0, 2.3, 1.0, None))         # 15%
    assert any("bị mờ" in w for w in W(80, 5.0, False, None, 2.0, 0.34, None))
    assert any("JPEG" in w for w in W(80, 5.0, False, None, 2.0, 1.0, 59))
    assert not any("JPEG" in w for w in W(80, 5.0, False, None, 2.0, 1.0, 60))


def main() -> int:
    tests = [test_a_clean_2m_no_warnings, test_b_small_board_warns, test_c_flip_case_gan_v4_q12,
             test_c2_height_rules, test_d_legacy_identical_to_old, test_e_sharpness_threshold,
             test_f_jpeg_quality_estimate, test_g_cli_exit_codes_and_json, test_g2_cli_error_message,
             test_i_synthetic_marker_size_param, test_h_warning_rules_pure]
    fails = 0
    for fn in tests:
        try:
            fn()
            print(f"[OK]   {fn.__name__}")
        except AssertionError as exc:
            fails += 1
            print(f"[FAIL] {fn.__name__} - {exc}")
        except Exception as exc:  # lỗi bất ngờ vẫn phải hiện rõ
            fails += 1
            print(f"[LỖI]  {fn.__name__} - {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - fails}/{len(tests)} test đạt")
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
