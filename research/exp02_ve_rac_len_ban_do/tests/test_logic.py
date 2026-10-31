"""
Test thuần logic hình học - KHÔNG cần ảnh/model, chạy nhanh.

Chạy: python tests/test_logic.py   (từ thư mục exp02_ve_rac_len_ban_do)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np

# Cho phép chạy trực tiếp "python tests/test_logic.py" từ thư mục exp02
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import camera_model  # noqa: E402
import project_mask  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[OK]   {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} - {detail}")


def test_pixel_to_ray_center_is_optical_axis():
    camera_matrix = camera_model.build_camera_matrix(640, 480, 66.0)
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]
    ray = camera_model.pixel_to_ray(camera_matrix, cx, cy)
    check(
        "pixel_to_ray: điểm chính giữa ảnh -> tia trục quang (0,0,1)",
        np.allclose(ray, [0.0, 0.0, 1.0], atol=1e-9),
        f"ray={ray}",
    )


def test_pixel_to_ray_offset_direction():
    """Điểm ảnh lệch phải/xuống so với tâm phải cho tia có thành phần x,y dương."""
    camera_matrix = camera_model.build_camera_matrix(640, 480, 66.0)
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]
    ray = camera_model.pixel_to_ray(camera_matrix, cx + 50, cy + 30)
    check(
        "pixel_to_ray: lệch phải/xuống -> tia có x>0, y>0",
        ray[0] > 0 and ray[1] > 0,
        f"ray={ray}",
    )


def test_intersect_ground_straight_down():
    """
    Camera cao h=2m, nhìn thẳng xuống (trục quang trùng -Z thế giới).
    Điểm chính giữa ảnh (tia = trục quang = (0,0,1) hệ camera) phải giao đất ngay dưới chân camera.
    """
    h = 2.0
    cam_origin_marker = np.array([0.0, 0.0, h])
    # Camera nhìn thẳng xuống: trục quang (0,0,1) hệ camera ứng với hướng (0,0,-1) hệ marker
    dir_marker = np.array([0.0, 0.0, -1.0])
    point = project_mask.intersect_ray_with_ground(cam_origin_marker, dir_marker)
    check(
        "intersect_ray_with_ground: nhìn thẳng xuống -> giao ngay gốc (0,0)",
        point is not None and math.isclose(point[0], 0.0, abs_tol=1e-9) and math.isclose(point[1], 0.0, abs_tol=1e-9),
        f"point={point}",
    )


def test_intersect_ground_tilted_angle():
    """
    Camera cao h, 1 tia lệch góc theta so với phương thẳng đứng (nhìn gần thẳng xuống nhưng
    lệch theta) -> khoảng cách tới điểm giao = h * tan(theta) (tính tay, hình học tam giác vuông).
    """
    h = 3.0
    theta_deg = 20.0
    theta = math.radians(theta_deg)
    cam_origin_marker = np.array([0.0, 0.0, h])
    # Tia lệch theta so với phương thẳng đứng (-Z), trong mặt phẳng X-Z: hướng (sin, 0, -cos)
    dir_marker = np.array([math.sin(theta), 0.0, -math.cos(theta)])
    point = project_mask.intersect_ray_with_ground(cam_origin_marker, dir_marker)
    expected_dist = h * math.tan(theta)
    check(
        "intersect_ray_with_ground: lệch góc theta -> khoảng cách = h*tan(theta)",
        point is not None and math.isclose(point[0], expected_dist, rel_tol=1e-9)
        and math.isclose(point[1], 0.0, abs_tol=1e-9),
        f"point={point}, expected_dist={expected_dist}",
    )


def test_intersect_ground_parallel_ray_returns_none():
    """Tia song song mặt đất (dir.z = 0) -> không có giao điểm, phải trả None, không crash."""
    cam_origin_marker = np.array([0.0, 0.0, 2.0])
    dir_marker = np.array([1.0, 0.0, 0.0])
    point = project_mask.intersect_ray_with_ground(cam_origin_marker, dir_marker)
    check("intersect_ray_with_ground: tia song song mặt đất -> None", point is None, f"point={point}")


def test_intersect_ground_ray_pointing_up_returns_none():
    """Tia hướng lên trời (dir.z > 0, s<=0) -> bỏ qua, trả None."""
    cam_origin_marker = np.array([0.0, 0.0, 2.0])
    dir_marker = np.array([0.0, 0.1, 1.0])  # hướng lên trên (z dương) -> nhìn lên trời
    point = project_mask.intersect_ray_with_ground(cam_origin_marker, dir_marker)
    check("intersect_ray_with_ground: tia hướng lên trời -> None", point is None, f"point={point}")


def test_project_mask_skips_points_behind_camera():
    """
    project_mask_to_geojson phải BỎ đúng các điểm chiếu ra sau/lên trời, không crash,
    và vẫn trả polygon hợp lệ từ các điểm còn lại (nếu đủ >=3 điểm).
    """
    camera_matrix = camera_model.build_camera_matrix(100, 100, 66.0)
    # Camera cao 2m, nhìn thẳng xuống đất (R = xoay 180 độ quanh trục X so với "nhìn ngang")
    # Chọn R sao cho tia trục quang (0,0,1) hệ camera -> (0,0,-1) hệ marker (nhìn thẳng xuống).
    R = np.array([
        [1.0, 0.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, -1.0],
    ])
    t = -R @ np.array([0.0, 0.0, 2.0])  # camera tại (0,0,2) hệ marker

    calib = {
        "camera_id": "TEST",
        "marker_latlon": [10.0, 106.0],
        "R": R.tolist(),
        "t": t.tolist(),
        "camera_matrix": camera_matrix.tolist(),
        "image_size": [100, 100],
    }

    # Polygon có 1 điểm ở tâm ảnh (nhìn thẳng xuống đất, hợp lệ) và nhiều điểm hợp lệ khác
    # quanh tâm để đủ >=3 điểm tạo polygon. Không đưa điểm "lên trời" vào vì pixel luôn nằm
    # trong ảnh 0..1 - thay vào đó kiểm tra gián tiếp qua intersect_ray_with_ground ở trên,
    # và kiểm tra project_mask không crash + ra polygon hợp lệ.
    polygon_norm = [(0.5, 0.5), (0.52, 0.5), (0.52, 0.52), (0.5, 0.52)]
    feature = project_mask.project_mask_to_geojson(polygon_norm, (100, 100), calib)
    check(
        "project_mask_to_geojson: không crash, trả Feature Polygon hợp lệ",
        feature is not None and feature["geometry"]["type"] == "Polygon",
        f"feature={feature}",
    )

    # Giờ thử 1 polygon có điểm nằm ở nửa trên ảnh ứng với hướng nhìn lên trời (dir.z>0)
    # bằng cách đặt camera nhìn NGANG (không nghiêng xuống) - khi đó nửa trên ảnh là bầu trời.
    R_horizontal = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ])
    t_horizontal = -R_horizontal @ np.array([0.0, -2.0, 1.0])
    calib_horizontal = {
        "camera_id": "TEST2",
        "marker_latlon": [10.0, 106.0],
        "R": R_horizontal.tolist(),
        "t": t_horizontal.tolist(),
        "camera_matrix": camera_matrix.tolist(),
        "image_size": [100, 100],
    }
    # Điểm ở nửa trên ảnh (y chuẩn hoá < 0.5, tức v < cy) khi nhìn ngang sẽ là bầu trời -> bị bỏ
    sky_polygon = [(0.5, 0.1), (0.52, 0.1), (0.52, 0.12), (0.5, 0.12)]
    feature_sky = project_mask.project_mask_to_geojson(sky_polygon, (100, 100), calib_horizontal)
    check(
        "project_mask_to_geojson: toàn bộ điểm là bầu trời -> trả None (không crash)",
        feature_sky is None,
        f"feature_sky={feature_sky}",
    )


def test_meters_to_latlon_direction():
    """Dịch về phía Bắc làm tăng lat; dịch về phía Đông làm tăng lon (ở Việt Nam)."""
    lat0, lon0 = 10.7769, 106.7009
    lat_n, lon_n = project_mask.meters_to_latlon(lat0, lon0, east_m=0.0, north_m=100.0)
    lat_e, lon_e = project_mask.meters_to_latlon(lat0, lon0, east_m=100.0, north_m=0.0)
    check(
        "meters_to_latlon: dịch Bắc -> lat tăng, lon không đổi",
        lat_n > lat0 and math.isclose(lon_n, lon0, abs_tol=1e-9),
        f"lat_n={lat_n}, lon_n={lon_n}",
    )
    check(
        "meters_to_latlon: dịch Đông -> lon tăng, lat không đổi",
        lon_e > lon0 and math.isclose(lat_e, lat0, abs_tol=1e-9),
        f"lat_e={lat_e}, lon_e={lon_e}",
    )


def main():
    test_pixel_to_ray_center_is_optical_axis()
    test_pixel_to_ray_offset_direction()
    test_intersect_ground_straight_down()
    test_intersect_ground_tilted_angle()
    test_intersect_ground_parallel_ray_returns_none()
    test_intersect_ground_ray_pointing_up_returns_none()
    test_project_mask_skips_points_behind_camera()
    test_meters_to_latlon_direction()

    print(f"\nKết quả: {PASS} PASS / {FAIL} FAIL")
    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
