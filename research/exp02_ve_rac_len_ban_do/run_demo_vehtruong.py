"""
Demo cuối: chạy thông cả luồng "chiếu vùng rác lên bản đồ" bằng dữ liệu giả lập + 1 ảnh
thật có nhãn tay (KHÔNG chạy model AI, giữ demo nhẹ, không cần GPU).

Các bước:
  1) Tạo ảnh giả lập (make_synthetic_test, bảng config.DEMO_MARKER_SIZE_MM = 400 mm để cạnh bảng trên
     ảnh >= 50 px, ghi vào outputs/demo_scene.png + outputs/demo_pose_su_thuc.json - KHÔNG đụng
     synthetic_scene.png / pose_su_thuc.json 200 mm mà các test khác đọc) + hiệu chỉnh 1 "camera demo"
     DEMO-CAM bằng marker trong ảnh đó, gán toạ độ (lat,lon) demo cho marker (config.DEMO_MARKER_LATLON).
  2) Chọn TẤT ĐỊNH 1 ảnh cảnh đường/cống từ datasets/Try1/test (chỉ đọc): xem select_demo_image()
     bên dưới (tiền tố tphcm/ssc, có nhãn Trash, tổng diện tích nhãn Trash lớn nhất). Dùng ĐỦ MỌI
     polygon nhãn tay lớp "Trash" (class 0) của ảnh đó làm "mask phát hiện được".
  3) Chiếu các polygon đó qua calibration của DEMO-CAM (MultiPolygon nếu > 1 polygon).
  4) Xuất outputs/demo_rac.geojson (vùng rác), outputs/demo_marker.geojson (vị trí BẢNG ĐÁNH DẤU)
     và outputs/demo_camera_position.geojson (vị trí camera tính từ R, t của hiệu chỉnh).
  5) In bảng toạ độ các đỉnh polygon kết quả để kiểm tra bằng mắt.

Chạy: python run_demo_vehtruong.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import cv2
import numpy as np

import calib_quality
import calibrate_aruco
import config
import make_synthetic_test
import project_mask

TRASH_CLASS_ID = 0  # xem classes.txt ở gốc project: 0=Trash, 1=Drain

# --- Quy tắc chọn ảnh demo (không sửa config.py; đặt hằng số ngay tại đây) ---
# Ảnh cảnh đường/cống: tên file bắt đầu bằng một trong các tiền tố này (tphcm* = quay ở TP.HCM,
# ssc* = ảnh hiện trường SSC). Ảnh g1lop* là ảnh trong nhà, chỉ dùng làm phương án dự phòng.
STREET_PREFIXES = ("tphcm", "ssc")
# Lưới tô nhãn để đo "tổng diện tích nhãn Trash" (hợp - union - của mọi polygon, theo % diện tích ảnh).
COVERAGE_GRID = 512
# Phương án dự phòng nếu không có ảnh tphcm/ssc nào có nhãn Trash.
FALLBACK_IMAGE_STEM = config.DEMO_LABELED_IMAGE_STEM
# demo ảnh dataset (1024x1024, tỉ lệ 1:1) khác tỉ lệ ảnh hiệu chỉnh 640x480 (4:3) -> chỉ demo mới bật cờ này.
ALLOW_ASPECT_MISMATCH_DEMO = True


def parse_yolo_seg_polygons(label_path: Path, target_class: int) -> list[list[tuple[float, float]]]:
    """
    Đọc TẤT CẢ dòng nhãn YOLO-segmentation thuộc target_class trong file nhãn.
    Định dạng mỗi dòng: "<class> x1 y1 x2 y2 ... xn yn" (toạ độ đã chuẩn hoá 0..1).
    Dòng không đủ 3 đỉnh hoặc lẻ toạ độ bị bỏ. Trả list polygon (có thể rỗng).
    """
    if not label_path.exists():
        raise FileNotFoundError(f"Không thấy file nhãn: {label_path}")

    polygons = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        cls = int(float(parts[0]))
        if cls != target_class:
            continue
        coords = [float(v) for v in parts[1:]]
        if len(coords) % 2 != 0 or len(coords) < 6:
            continue
        polygons.append(list(zip(coords[0::2], coords[1::2])))
    return polygons


def parse_yolo_seg_polygon(label_path: Path, target_class: int) -> list[tuple[float, float]]:
    """(Giữ để tương thích) Chỉ polygon ĐẦU TIÊN của lớp target_class; lỗi nếu không có."""
    polys = parse_yolo_seg_polygons(label_path, target_class)
    if not polys:
        raise RuntimeError(f"Không tìm thấy polygon lớp {target_class} trong {label_path}")
    return polys[0]


def trash_coverage_pct(polygons_norm, grid: int = COVERAGE_GRID) -> float:
    """% diện tích ảnh bị phủ bởi HỢP các polygon (tô trên lưới grid x grid, nhãn chồng nhau không đếm đôi)."""
    if not polygons_norm:
        return 0.0
    m = np.zeros((grid, grid), dtype=np.uint8)
    for p in polygons_norm:
        pts = np.round(np.array(p, dtype=np.float64) * grid).astype(np.int32)
        cv2.fillPoly(m, [pts], 1)
    return float(m.mean()) * 100.0


def rank_street_images(labels_dir: Path, prefixes=STREET_PREFIXES, target_class: int = TRASH_CLASS_ID) -> list[tuple[str, float, int]]:
    """
    Xếp hạng ảnh cảnh đường/cống trong thư mục nhãn (chỉ đọc nhãn, không đọc ảnh):
      - chỉ file .txt có tên bắt đầu bằng một tiền tố trong `prefixes`;
      - bỏ ảnh không có polygon Trash hợp lệ (nhãn trống / chỉ có lớp khác);
      - xếp theo % diện tích hợp nhãn Trash GIẢM DẦN, hoà thì theo tên TĂNG DẦN (tất định).
    Trả list (stem, coverage_pct, n_polygons).
    """
    rows = []
    for p in sorted(Path(labels_dir).glob("*.txt")):
        if not p.name.lower().startswith(tuple(prefixes)):
            continue
        polys = parse_yolo_seg_polygons(p, target_class)
        if not polys:
            continue
        rows.append((p.stem, trash_coverage_pct(polys), len(polys)))
    rows.sort(key=lambda r: (-round(r[1], 6), r[0]))
    return rows


def select_demo_image(
    labels_dir: Path = config.DATASET_TEST_LABELS_DIR,
    images_dir: Path = config.DATASET_TEST_IMAGES_DIR,
) -> tuple[str, str]:
    """
    Chọn tất định ảnh demo. QUY TẮC: trong datasets/Try1/test, lấy ảnh có tiền tố tphcm/ssc, có nhãn
    Trash, tồn tại file ảnh .jpg tương ứng, và tổng diện tích HỢP nhãn Trash (% ảnh) LỚN NHẤT
    (hoà -> tên nhỏ nhất theo thứ tự chữ cái). Không có -> fallback FALLBACK_IMAGE_STEM (ảnh g1lop trong nhà).
    Trả (stem, lý do/ghi chú để in ra).
    """
    for stem, cov, n_poly in rank_street_images(labels_dir):
        if (Path(images_dir) / f"{stem}.jpg").exists():
            return stem, f"hạng 1 trong ảnh {'/'.join(STREET_PREFIXES)} có nhãn Trash: phủ {cov:.2f}% ảnh, {n_poly} polygon"
    return FALLBACK_IMAGE_STEM, "KHÔNG có ảnh tphcm/ssc phù hợp -> dùng ảnh dự phòng g1lop (trong nhà)"


def main():
    print("=== Bước 1: tạo ảnh giả lập + hiệu chỉnh DEMO-CAM ===")
    synth = make_synthetic_test.main(demo=True)
    synthetic_image_path = synth["image_path"]
    try:
        result = calibrate_aruco.detect_and_solve_pnp(
            synthetic_image_path, config.MARKER_ID, synth["marker_size_mm"]
        )
    except Exception as exc:
        print(f"[LỖI] Không hiệu chỉnh được DEMO-CAM: {exc}")
        sys.exit(1)

    side_min = result["quality"]["marker_side_px_min"]
    print(f"Cạnh bảng {synth['marker_size_mm']:g} mm trên ảnh demo: ngắn nhất {side_min:.1f} px "
          f"(ngưỡng {calib_quality.MIN_SIDE_PX:.0f} px)")
    if calib_quality.is_too_small(side_min):
        print(f"[LỖI] Bảng demo chỉ {side_min:.1f} px (<{calib_quality.MIN_SIDE_PX:.0f} px): "
              f"không lưu DEMO-CAM")
        sys.exit(3)

    calib_path = config.CALIBRATION_DIR / f"{config.DEMO_CAMERA_ID}.json"
    calib_data = calibrate_aruco.save_calibration(
        config.DEMO_CAMERA_ID, config.DEMO_MARKER_LATLON, result, "synthetic", calib_path
    )
    print(f"Đã hiệu chỉnh '{config.DEMO_CAMERA_ID}' -> {calib_path}")
    print(f"Sai số reprojection: {result['reproj_error_rms_px']:.3f} px")
    print(
        f"Toạ độ marker demo (GIẢ ĐỊNH, không phải vị trí thật): "
        f"{config.DEMO_MARKER_LATLON}"
    )
    project_mask.warn_calibration_quality(calib_data)

    print("\n=== Bước 2: chọn ảnh cảnh đường + nhãn tay thật từ datasets/Try1/test ===")
    stem, reason = select_demo_image()
    image_path = config.DATASET_TEST_IMAGES_DIR / f"{stem}.jpg"
    label_path = config.DATASET_TEST_LABELS_DIR / f"{stem}.txt"
    print(f"Quy tắc chọn: ảnh tiền tố {STREET_PREFIXES}, có nhãn Trash, tổng diện tích hợp nhãn Trash lớn nhất")
    print(f"Ảnh demo: {stem} ({reason})")
    print(f"Đường dẫn ảnh: {image_path}")
    print(f"Đường dẫn nhãn: {label_path}")

    img = cv2.imread(str(image_path))
    if img is None:
        print(f"[LỖI] Không đọc được ảnh demo: {image_path}")
        sys.exit(1)
    h, w = img.shape[:2]
    print(f"Kích thước ảnh thật: {w}x{h}")

    try:
        polygons_norm = parse_yolo_seg_polygons(label_path, TRASH_CLASS_ID)
    except Exception as exc:
        print(f"[LỖI] Không đọc được polygon nhãn tay: {exc}")
        sys.exit(1)
    if not polygons_norm:
        print(f"[LỖI] Không có polygon lớp Trash trong {label_path}")
        sys.exit(1)
    print(f"Số polygon nhãn tay lớp Trash: {len(polygons_norm)} (tổng {sum(len(p) for p in polygons_norm)} đỉnh)")

    print("\n=== Bước 3: chiếu các polygon qua calibration DEMO-CAM ===")
    # allow_aspect_mismatch=True: CHỈ DEMO - ảnh dataset (1:1) khác tỉ lệ ảnh hiệu chỉnh (4:3).
    feature_rac = project_mask.project_polygons_to_geojson(
        polygons_norm,
        (w, h),
        calib_data,
        allow_aspect_mismatch=ALLOW_ASPECT_MISMATCH_DEMO,
        extra_properties={"image": stem, "source": "label"},
    )
    if feature_rac is None:
        print("[LỖI] project_mask không ra được polygon hợp lệ nào, dừng demo")
        sys.exit(1)

    feature_marker = project_mask.marker_point_geojson(calib_data)
    feature_camera = project_mask.camera_position_geojson(calib_data)

    print("\n=== Bước 4: xuất GeoJSON ===")
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    for name, feat in (
        ("demo_rac.geojson", feature_rac),
        ("demo_marker.geojson", feature_marker),
        ("demo_camera_position.geojson", feature_camera),
    ):
        out_path = config.OUTPUTS_DIR / name
        out_path.write_text(json.dumps(feat, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Đã ghi: {out_path}")

    cp = feature_camera["properties"]
    print(
        f"Camera tính từ hiệu chỉnh: Đông {cp['east_m']:+.3f} m, Bắc {cp['north_m']:+.3f} m, "
        f"cao {cp['height_m']:.3f} m so với marker"
    )

    print("\n=== Bước 5: bảng toạ độ polygon kết quả (để kiểm tra bằng mắt) ===")
    geom = feature_rac["geometry"]
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for pi, poly in enumerate(polys):
        ring = poly[0]
        print(f"-- polygon {pi} ({len(ring)} điểm) --")
        print(f"{'#':>3} | {'lon':>12} | {'lat':>12}")
        for i, (lon, lat) in enumerate(ring):
            print(f"{i:>3} | {lon:>12.7f} | {lat:>12.7f}")

    print(
        "\nLƯU Ý: đây là DEMO - toạ độ marker là GIẢ ĐỊNH (không đo thật tại hiện trường), "
        "pose camera lấy từ ảnh giả lập (không phải ảnh chụp thật), ảnh dataset khác tỉ lệ khung ảnh hiệu chỉnh. "
        "Chỉ dùng để kiểm tra luồng xử lý."
    )


if __name__ == "__main__":
    main()
