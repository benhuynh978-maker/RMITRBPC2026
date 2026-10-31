"""
Mô hình camera pinhole đơn giản (bỏ méo ống kính, dist_coeffs = 0).

Dùng để:
  1) Suy ma trận nội tại (camera_matrix) gần đúng từ góc mở ống kính giả định + độ phân
     giải ảnh thật (xem config.DIAGONAL_FOV_DEG - đây là GIẢ ĐỊNH, không phải số đo thật).
  2) Dựng tia nhìn (ray) từ tâm camera đi qua 1 điểm ảnh, trong hệ toạ độ camera.
  3) Sinh 4 góc marker trong hệ toạ độ riêng của marker (dùng chung cho calibrate_aruco.py
     và make_synthetic_test.py để đảm bảo cùng 1 quy ước).

Quy ước hệ toạ độ camera (theo OpenCV): gốc tại tâm quang học, X hướng phải, Y hướng
xuống (theo chiều pixel), Z hướng ra phía trước ống kính (trục quang).
"""
from __future__ import annotations

import numpy as np


def build_camera_matrix(width: int, height: int, diagonal_fov_deg: float) -> np.ndarray:
    """
    Suy ma trận nội tại (camera_matrix 3x3) từ độ phân giải ảnh thật + góc mở ống kính
    theo đường chéo (giả định).

    Công thức:
        d   = sqrt(width^2 + height^2)          # đường chéo ảnh, đơn vị pixel
        f   = (d/2) / tan(fov_diag/2)            # tiêu cự, đơn vị pixel
        fx = fy = f (giả định pixel vuông, không méo ống kính)
        cx = width/2, cy = height/2 (tâm quang học ở giữa ảnh)
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Kích thước ảnh không hợp lệ: {width}x{height}")
    if not (0 < diagonal_fov_deg < 180):
        raise ValueError(f"Góc mở ống kính không hợp lệ: {diagonal_fov_deg} độ")

    diag_px = float(np.hypot(width, height))
    half_fov_rad = np.deg2rad(diagonal_fov_deg) / 2.0
    f = (diag_px / 2.0) / np.tan(half_fov_rad)
    cx = width / 2.0
    cy = height / 2.0

    return np.array(
        [
            [f, 0.0, cx],
            [0.0, f, cy],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def pixel_to_ray(camera_matrix: np.ndarray, u: float, v: float, normalize: bool = True) -> np.ndarray:
    """
    Dựng tia (vector hướng, hệ camera) từ tâm camera đi qua điểm ảnh (u,v) pixel.

    Công thức pinhole ngược:
        x = (u - cx) / fx
        y = (v - cy) / fy
        z = 1
    Điểm chính giữa ảnh (u=cx, v=cy) luôn cho tia (0,0,1) - đúng trục quang (optical axis).
    """
    fx = camera_matrix[0, 0]
    fy = camera_matrix[1, 1]
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]

    x = (u - cx) / fx
    y = (v - cy) / fy
    z = 1.0

    vec = np.array([x, y, z], dtype=np.float64)
    if normalize:
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
    return vec


def get_marker_object_points(marker_size_m: float) -> np.ndarray:
    """
    4 góc marker trong hệ toạ độ RIÊNG của marker: marker nằm phẳng trên mặt đất (z=0),
    tâm marker tại gốc toạ độ (0,0,0).

    Thứ tự trả về: trên-trái, trên-phải, dưới-phải, dưới-trái - khớp đúng thứ tự
    cv2.aruco.detectMarkers() trả về cho mỗi marker phát hiện được.

    Quy ước trục: X marker = hướng "phải" khi nhìn thẳng vào mặt marker,
                  Y marker = hướng "lên/trên" khi nhìn thẳng vào mặt marker,
                  Z marker = pháp tuyến mặt đất (hướng lên trời).
    (project_mask.py dùng thêm quy ước: X marker ~ hướng Đông, Y marker ~ hướng Bắc -
     đây là ĐƠN GIẢN HOÁ cho giai đoạn thử nghiệm, không đo compass thật).
    """
    if marker_size_m <= 0:
        raise ValueError(f"Kích thước marker không hợp lệ: {marker_size_m} m")
    half = marker_size_m / 2.0
    return np.array(
        [
            [-half, half, 0.0],
            [half, half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ],
        dtype=np.float64,
    )
