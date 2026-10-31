"""
Dò marker ArUco trong 1 ảnh, tính pose camera so với marker, lưu kết quả hiệu chỉnh vào
calibration/<camera_id>.json kèm KHỐI CHẤT LƯỢNG `quality` (cỡ bảng trên ảnh, độ mơ hồ của pose,
độ nét, chất lượng JPEG và danh sách cảnh báo tiếng Việt).

Hình học:
  cv2.aruco.detectMarkers() trả 4 góc marker trên ảnh (pixel). Ta biết trước 4 góc đó
  trong hệ toạ độ riêng của marker (camera_model.get_marker_object_points - marker nằm
  phẳng trên mặt đất, z=0). Giải PnP ra (rvec, tvec) sao cho:

        X_camera = R @ X_marker + t      (R = Rodrigues(rvec))

  Đây chính là phép biến đổi từ hệ marker (cũng là hệ "mặt đất") sang hệ camera.
  project_mask.py sẽ dùng R, t theo chiều NGƯỢC LẠI: từ 1 điểm ảnh, dựng tia trong hệ
  camera rồi đổi về hệ marker để tìm giao điểm với mặt đất.

Cách giải MỚI (mặc định, legacy=False) - căn cứ stress_test/REPORT.md và size_test/REPORT.md:
  1. Tinh chỉnh góc dưới pixel (CORNER_REFINE_SUBPIX): bộ dò mặc định sai ~0,57 px.
  2. cv2.solvePnPGeneric + SOLVEPNP_IPPE_SQUARE trả 2 nghiệm (4 điểm đồng phẳng luôn có nghiệm
     "lật"; solvePnP ITERATIVE có thể rơi vào nghiệm lật lệch ~5 m mà reprojection vẫn nhỏ).
  3. Chọn nghiệm: (a) loại nghiệm có camera nằm DƯỚI mặt phẳng marker (z_camera trong hệ marker <= 0);
     (b) nếu vẫn còn 2 nghiệm: chọn nghiệm có reprojection nhỏ hơn và cảnh báo "có thể lật" khi hai
     nghiệm gần ngang nhau.
     ĐỘ CAO CAMERA KHÔNG DÙNG ĐỂ CHỌN NGHIỆM: hai nghiệm IPPE là ảnh phản chiếu của nhau qua một
     mặt phẳng đứng, nên có CÙNG độ cao (đo được: chênh trung vị 0,1%, tối đa 1,2%). Chọn theo độ cao
     nhập tay thực chất là tung đồng xu và đã gây chọn nhầm nghiệm lật 44/45 ca khi nhập thấp
     hơn thực tế (kiểm định exp02, 2026-10-12). --camera-height-m chỉ dùng để KIỂM TRA CHÉO độ cao
     ước lượng (cảnh báo khi lệch > 20%).
  Khối `quality` + quy tắc cảnh báo cố định: xem docstring calib_quality.py.

Chạy (từ thư mục exp02_ve_rac_len_ban_do, dùng python của venv, luôn kèm -B):
  python -B calibrate_aruco.py --image <ảnh> --camera-id <tên camera> \
      [--lat <vĩ độ thật của marker>] [--lon <kinh độ thật của marker>] [--source aruco|synthetic] \
      [--marker-size-mm 250] [--camera-height-m <độ cao camera đo bằng thước, mét>]

  --marker-size-mm  CẠNH THẬT của bảng (mm), đo bằng thước: đây là con số DUY NHẤT phải nhập tay.
                    Mặc định config.PRINT_MARKER_SIZE_MM (250 mm, bảng A3 in thật). Ảnh giả lập cũ
                    (make_synthetic_test mặc định) dùng bảng 200 mm: truyền --marker-size-mm 200; ảnh
                    demo dùng 400 mm (config.DEMO_MARKER_SIZE_MM).
  --camera-height-m độ cao camera so với mặt phẳng đặt bảng, ĐO BẰNG THƯỚC: chỉ để KIỂM TRA CHÉO độ
                    cao ước lượng (cảnh báo khi lệch > 20%), KHÔNG dùng để chọn nghiệm pose.
  QUY TẮC CHẶN DUY NHẤT: cạnh ngắn nhất của bảng trên ảnh < 50 px (calib_quality.MIN_SIDE_PX) thì CLI
  KHÔNG lưu file hiệu chỉnh, in lỗi tiếng Việt và thoát mã 3. Từ 50 px trở lên: lưu bình thường.
  Mã thoát: 0 = lưu xong (kể cả có cảnh báo khác); 1 = lỗi (không dò được marker...);
            3 = bảng chiếm < 50 px trên ảnh: KHÔNG ghi file hiệu chỉnh.

Dùng như thư viện (tương thích ngược): detect_and_solve_pnp(image_path, marker_id, marker_size_mm)
vẫn trả các khoá cũ (R, t, camera_matrix, image_size, reproj_error_rms_px) và THÊM `quality`, `corners_px`.
Thư viện KHÔNG raise vì bảng nhỏ (chỉ thêm cảnh báo "<50 px" vào quality.warnings); việc chặn nằm ở main().
Kwarg mới: camera_height_m=None, legacy=False. legacy=True tái hiện đúng hành vi cũ (không SUBPIX,
solvePnP ITERATIVE) để các báo cáo cũ còn tái lập được.

Nếu không nhập --lat/--lon, dùng config.DEMO_MARKER_LATLON (toạ độ demo, KHÔNG phải thật)
để tiện chạy thử.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import cv2
import cv2.aruco as aruco
import numpy as np

import calib_quality
import camera_model
import config

EXIT_TOO_SMALL = 3  # bảng < calib_quality.MIN_SIDE_PX trên ảnh: không lưu


def _reproj_rms(obj_pts, img_pts, rvec, tvec, camera_matrix, dist_coeffs) -> float:
    proj, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, dist_coeffs)
    return float(np.sqrt(np.mean(np.sum((proj.reshape(4, 2) - img_pts) ** 2, axis=1))))


def _solve_ippe(obj_pts, img_pts, camera_matrix, dist_coeffs, camera_height_m: Optional[float]) -> dict:
    """
    Giải bằng IPPE_SQUARE (2 nghiệm) rồi chọn nghiệm theo quy tắc (a)(b)(c) trong docstring đầu file.
    Trả dict: rvec, tvec, reproj, ambiguity_ratio, chosen_by, height, unresolved.
    """
    n, rvecs, tvecs, _errs = cv2.solvePnPGeneric(
        obj_pts, img_pts, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_IPPE_SQUARE
    )
    if n < 1:
        raise RuntimeError("solvePnPGeneric (IPPE_SQUARE) thất bại, không giải được pose từ marker phát hiện được")
    sols = []
    for rv, tv in zip(rvecs, tvecs):
        R, _ = cv2.Rodrigues(rv)
        cam_center = -R.T @ tv.reshape(3)  # vị trí camera trong hệ marker; z = độ cao so với mặt phẳng marker
        sols.append({
            "rvec": rv, "tvec": tv, "height": float(cam_center[2]),
            "reproj": _reproj_rms(obj_pts, img_pts, rv, tv, camera_matrix, dist_coeffs),
        })

    if len(sols) >= 2:
        errs = sorted(s["reproj"] for s in sols[:2])
        ratio = float(errs[1] / max(errs[0], calib_quality.REPROJ_FLOOR_PX))
    else:
        ratio = None

    above = [s for s in sols if s["height"] > 0.0]
    both_above = len(above) >= 2
    if len(above) == 0:
        cands, mark = sols, None  # cả hai dưới mặt phẳng (bất thường): vẫn chọn, quality sẽ thấy độ cao âm
    elif len(above) == 1:
        cands, mark = above, "above_plane_only"
    else:
        cands, mark = above, None

    if mark == "above_plane_only":
        best, chosen_by = cands[0], "above_plane_only"
    else:
        # Độ cao KHÔNG dùng để chọn: hai nghiệm IPPE là ảnh phản chiếu, cùng độ cao (xem docstring đầu
        # file) -> chọn theo reproj; độ cao nhập tay chỉ để cảnh báo ở calib_quality.build_warnings.
        best = min(cands, key=lambda s: s["reproj"])
        chosen_by = "reproj"
    # Còn mơ hồ chưa giải: có 2 nghiệm trên mặt phẳng và việc chọn chỉ dựa vào reproj.
    unresolved = both_above and chosen_by == "reproj"
    return {**best, "ambiguity_ratio": ratio, "chosen_by": chosen_by, "unresolved": unresolved}


def detect_and_solve_pnp(
    image_path: Path,
    marker_id: int,
    marker_size_mm: float,
    camera_height_m: Optional[float] = None,
    legacy: bool = False,
    diagonal_fov_deg: Optional[float] = None,
) -> dict:
    """
    Dò marker trong ảnh và giải pose camera so với marker. Lỗi -> raise RuntimeError.

    diagonal_fov_deg: góc mở chéo (độ) dùng dựng camera_matrix; None -> config.DIAGONAL_FOV_DEG (66).
      Giá trị dùng được lưu vào kết quả ("diagonal_fov_deg").

    legacy=True: đúng hành vi cũ (DetectorParameters mặc định, cv2.solvePnP ITERATIVE).
    legacy=False (mặc định): SUBPIX + IPPE_SQUARE + chọn nghiệm (xem docstring đầu file).
    camera_height_m: độ cao camera đo tay (m) so với mặt phẳng marker, CHỈ để kiểm tra chéo (cảnh báo
      khi lệch > 20%), không dùng chọn nghiệm. Phải > 0 (raise ValueError nếu không).
    Trả các khoá cũ + "quality" (dict, xem calib_quality.py) + "corners_px" (4x2).
    """
    if camera_height_m is not None and not camera_height_m > 0:
        raise ValueError(f"camera_height_m phải > 0 (mét), nhận được: {camera_height_m!r}")
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"Không đọc được ảnh: {image_path}")

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    fov_deg = config.DIAGONAL_FOV_DEG if diagonal_fov_deg is None else float(diagonal_fov_deg)
    camera_matrix = camera_model.build_camera_matrix(w, h, fov_deg)
    dist_coeffs = np.zeros((5, 1), dtype=np.float64)

    dictionary = aruco.getPredefinedDictionary(config.ARUCO_DICT)
    params = aruco.DetectorParameters()
    if not legacy:
        params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
    detector = aruco.ArucoDetector(dictionary, params)
    corners, ids, _rejected = detector.detectMarkers(gray)

    if ids is None or len(ids) == 0:
        raise RuntimeError(f"Không tìm thấy marker ArUco nào trong ảnh '{image_path.name}'")

    ids_flat = ids.flatten().tolist()
    if marker_id not in ids_flat:
        raise RuntimeError(
            f"Ảnh có các marker id={ids_flat} nhưng không có id={marker_id} cần dùng"
        )
    idx = ids_flat.index(marker_id)
    img_pts = corners[idx].reshape(4, 2).astype(np.float64)

    obj_pts = camera_model.get_marker_object_points(marker_size_mm / 1000.0)

    if legacy:
        ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, camera_matrix, dist_coeffs)
        if not ok:
            raise RuntimeError("solvePnP thất bại, không giải được pose camera từ marker phát hiện được")
        reproj = _reproj_rms(obj_pts, img_pts, rvec, tvec, camera_matrix, dist_coeffs)
        R_tmp, _ = cv2.Rodrigues(rvec)
        sol = {"rvec": rvec, "tvec": tvec, "reproj": reproj, "ambiguity_ratio": None,
               "chosen_by": "legacy", "unresolved": False,
               "height": float((-R_tmp.T @ tvec.reshape(3))[2])}
        camera_height_m = None
    else:
        sol = _solve_ippe(obj_pts, img_pts, camera_matrix, dist_coeffs, camera_height_m)

    rvec, tvec = sol["rvec"], sol["tvec"]
    R, _ = cv2.Rodrigues(rvec)
    reproj_error_rms = float(sol["reproj"])

    sides = calib_quality.side_lengths(img_pts)
    sharp, sharp_norm = calib_quality.marker_sharpness(gray, img_pts)
    jpeg_q = calib_quality.estimate_jpeg_quality(Path(image_path))
    warnings: List[str] = calib_quality.build_warnings(
        side_min_px=float(sides.min()),
        ambiguity_ratio=sol["ambiguity_ratio"],
        two_solutions_unresolved=sol["unresolved"],
        camera_height_given_m=camera_height_m,
        camera_height_est_m=sol["height"],
        sharpness_norm=sharp_norm,
        jpeg_quality_est=jpeg_q,
    )
    quality = {
        "marker_side_px_min": float(sides.min()),
        "marker_side_px_mean": float(sides.mean()),
        "reproj_rms": reproj_error_rms,
        "ambiguity_ratio": sol["ambiguity_ratio"],
        "solution_chosen_by": sol["chosen_by"],
        "camera_height_m_est": float(sol["height"]),
        "camera_height_m_given": None if camera_height_m is None else float(camera_height_m),
        "sharpness": float(sharp),
        "sharpness_norm": float(sharp_norm),
        "jpeg_quality_est": jpeg_q,
        "warnings": warnings,
    }

    return {
        "R": R,
        "t": tvec.reshape(3),
        "camera_matrix": camera_matrix,
        "image_size": (w, h),
        "reproj_error_rms_px": reproj_error_rms,
        "quality": quality,
        "corners_px": img_pts,
        "diagonal_fov_deg": fov_deg,
    }


def save_calibration(camera_id: str, marker_latlon, result: dict, source: str, out_path: Path) -> dict:
    data = {
        "camera_id": camera_id,
        "marker_latlon": [float(marker_latlon[0]), float(marker_latlon[1])],
        "R": result["R"].tolist(),
        "t": result["t"].tolist(),
        "camera_matrix": result["camera_matrix"].tolist(),
        "image_size": [int(result["image_size"][0]), int(result["image_size"][1])],
        "reproj_error_rms_px": result["reproj_error_rms_px"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }
    if result.get("quality") is not None:  # khoá THÊM; kết quả kiểu cũ không có thì bỏ qua
        data["quality"] = result["quality"]
    if result.get("diagonal_fov_deg") is not None:  # khoá THÊM (góc mở chéo đã dùng dựng camera_matrix)
        data["diagonal_fov_deg"] = float(result["diagonal_fov_deg"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _paint(text: str, code: str) -> str:
    """Tô màu ANSI khi xuất ra terminal thật (không tô khi chuyển hướng ra file / NO_COLOR)."""
    import os
    if sys.stdout.isatty() and not os.environ.get("NO_COLOR"):
        return f"\033[{code}m{text}\033[0m"
    return text


def print_warnings(warnings: List[str]) -> None:
    if not warnings:
        print(_paint("[OK] Không có cảnh báo chất lượng.", "32"))
        return
    for w in warnings:
        print(_paint(f"[!] CẢNH BÁO: {w}", "1;33"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Hiệu chỉnh camera bằng marker ArUco (SUBPIX + IPPE_SQUARE)")
    parser.add_argument("--image", required=True, help="Đường dẫn ảnh có marker")
    parser.add_argument("--camera-id", required=True, help="Mã camera, dùng làm tên file calibration")
    parser.add_argument("--lat", type=float, default=None, help="Vĩ độ thật của marker")
    parser.add_argument("--lon", type=float, default=None, help="Kinh độ thật của marker")
    parser.add_argument("--source", default="aruco", choices=["aruco", "synthetic"])
    parser.add_argument("--marker-id", type=int, default=config.MARKER_ID)
    parser.add_argument("--marker-size-mm", type=float, default=config.PRINT_MARKER_SIZE_MM,
                        help="CẠNH THẬT của bảng (mm), đo bằng thước sau khi in - con số duy nhất phải nhập "
                             "tay. Mặc định config.PRINT_MARKER_SIZE_MM. Bảng chiếm < 50 px trên ảnh thì "
                             "KHÔNG lưu (thoát mã 3)")
    parser.add_argument("--camera-height-m", type=float, default=None,
                        help="Độ cao camera so với mặt phẳng đặt bảng (mét, đo tay) - CHỈ để kiểm tra chéo "
                             "độ cao ước lượng, không dùng để chọn nghiệm pose")
    parser.add_argument("--fov-deg", type=float, default=None,
                        help="Góc mở ống kính theo đường chéo (độ). Mặc định config.DIAGONAL_FOV_DEG")
    args = parser.parse_args(argv)

    if args.fov_deg is not None and not (0 < args.fov_deg < 180):
        print("[LỖI] --fov-deg phải nằm trong (0, 180) độ")
        return 1
    if args.camera_height_m is not None and args.camera_height_m <= 0:
        print("[LỖI] --camera-height-m phải > 0 (mét)")
        return 1

    if args.lat is None or args.lon is None:
        lat, lon = config.DEMO_MARKER_LATLON
        print(
            f"[CẢNH BÁO] Không nhập --lat/--lon, dùng toạ độ demo mặc định ({lat}, {lon}) "
            f"- KHÔNG phải vị trí thật, chỉ để chạy thử luồng xử lý."
        )
    else:
        lat, lon = args.lat, args.lon

    image_path = Path(args.image)
    try:
        result = detect_and_solve_pnp(
            image_path, args.marker_id, args.marker_size_mm, camera_height_m=args.camera_height_m,
            diagonal_fov_deg=args.fov_deg,
        )
    except Exception as exc:  # không để exception trần, in lỗi rõ ràng
        print(f"[LỖI] Hiệu chỉnh thất bại: {exc}")
        return 1

    q = result["quality"]
    print(f"Cỡ bảng trên ảnh: cạnh ngắn nhất {q['marker_side_px_min']:.1f} px, trung bình {q['marker_side_px_mean']:.1f} px")
    print(f"Nghiệm pose chọn theo: {q['solution_chosen_by']} (độ cao camera ước lượng {q['camera_height_m_est']:.2f} m)")
    amb = q["ambiguity_ratio"]
    print(f"Sai số reprojection (RMS pixel): {result['reproj_error_rms_px']:.3f} px"
          + ("" if amb is None else f" | tỉ số mơ hồ 2 nghiệm: {amb:.1f}"))
    print_warnings(q["warnings"])

    if calib_quality.is_too_small(q["marker_side_px_min"]):
        print(_paint(
            f"[LỖI] Bảng chỉ chiếm {q['marker_side_px_min']:.1f} px (<{calib_quality.MIN_SIDE_PX:.0f} px): "
            f"không đủ tin cậy, hãy dùng bảng lớn hơn hoặc chụp gần hơn. KHÔNG lưu hiệu chỉnh.", "1;31"))
        return EXIT_TOO_SMALL

    out_path = config.CALIBRATION_DIR / f"{args.camera_id}.json"
    data = save_calibration(args.camera_id, (lat, lon), result, args.source, out_path)

    print(f"Đã lưu hiệu chỉnh cho camera '{args.camera_id}' -> {out_path}")
    print("R (marker -> camera) =")
    print(np.array(data["R"]))
    print(f"t = {data['t']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
