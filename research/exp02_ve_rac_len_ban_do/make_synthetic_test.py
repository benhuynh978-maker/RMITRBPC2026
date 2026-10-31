"""
Tạo ảnh giả lập để kiểm thử toàn luồng khi CHƯA CÓ ảnh bảng ArUco thật chụp tại hiện trường.

Vẽ 1 "mặt đất" caro (để nhìn bằng mắt thấy rõ mặt phẳng) + marker ArUco đặt vào ảnh ở 1 pose
GIẢ ĐỊNH NHƯNG BIẾT TRƯỚC (tự chọn R, t), dùng đúng phép chiếu hình học (cv2.projectPoints
với camera_matrix suy từ config.py) - để khi chạy calibrate_aruco.py lên ảnh này, kết quả
(R, t) phải khớp lại gần đúng đáp án đã dùng để vẽ (lưu trong outputs/pose_su_thuc.json).

Chạy: python make_synthetic_test.py [--marker-size-mm <mm>] [--demo]
Kết quả mặc định: outputs/synthetic_scene.png, outputs/pose_su_thuc.json (bảng config.MARKER_SIZE_MM = 200 mm;
các test cũ đọc hai file này làm đáp án nên KHÔNG đổi nội dung của chúng).
Với --demo (hoặc main(demo=True)): bảng config.DEMO_MARKER_SIZE_MM = 400 mm (cạnh >= 50 px trên ảnh) và ghi
vào TÊN FILE RIÊNG outputs/demo_scene.png, outputs/demo_pose_su_thuc.json - không đụng hai file mặc định.
Pose camera (đáp án) giống hệt nhau ở mọi chế độ, chỉ khác kích thước bảng; marker_size_mm trong file đáp
án luôn là cỡ bảng đã dùng để vẽ.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import cv2
import cv2.aruco as aruco
import numpy as np

import camera_model
import config


def build_ground_truth_pose():
    """
    Pose camera GIẢ ĐỊNH (biết trước), chọn tay để dễ kiểm tra bằng tay:
      - Camera đặt tại (0, -2, 1.5) mét trong hệ marker (lùi 2m về phía "Nam", cao 1.5m).
      - Nhìn thẳng vào tâm marker (0, 0, 0) - marker nằm giữa ảnh.
    Dựng R (world/marker -> camera) bằng phương pháp "look-at" thủ công (right/up/forward).
    """
    cam_origin = np.array([0.0, -2.0, 1.5])
    target = np.array([0.0, 0.0, 0.0])
    world_up = np.array([0.0, 0.0, 1.0])

    forward = target - cam_origin
    forward = forward / np.linalg.norm(forward)
    right = np.cross(forward, world_up)
    right = right / np.linalg.norm(right)
    true_up = np.cross(right, forward)

    # Hàng của R = trục camera (phải, xuống, trước) biểu diễn trong hệ world/marker
    # (xuống = -true_up vì trục Y ảnh hướng xuống theo quy ước OpenCV)
    R_wc = np.array([right, -true_up, forward])
    t = -R_wc @ cam_origin
    return R_wc, t, cam_origin


def points_in_front(points_world: np.ndarray, R: np.ndarray, t: np.ndarray) -> np.ndarray:
    """True nếu điểm (hệ world/marker) nằm phía trước camera (z_cam > 0)."""
    cam_pts = (R @ points_world.T).T + t
    return cam_pts[:, 2] > 1e-6


def draw_checkerboard(canvas, camera_matrix, R, t, square_m=0.5, x_half=4.0, y_min=-1.5, y_max=6.0):
    """Vẽ caro trên mặt đất z=0 (hệ marker), chỉ vẽ ô nào có đủ 4 góc ở phía trước camera."""
    rvec, _ = cv2.Rodrigues(R)
    tvec = t.reshape(3, 1)

    i_min, i_max = int(round(-x_half / square_m)), int(round(x_half / square_m))
    j_min, j_max = int(round(y_min / square_m)), int(round(y_max / square_m))

    for i in range(i_min, i_max):
        for j in range(j_min, j_max):
            x0, x1 = i * square_m, (i + 1) * square_m
            y0, y1 = j * square_m, (j + 1) * square_m
            corners_world = np.array(
                [[x0, y0, 0.0], [x1, y0, 0.0], [x1, y1, 0.0], [x0, y1, 0.0]]
            )
            if not np.all(points_in_front(corners_world, R, t)):
                continue
            proj, _ = cv2.projectPoints(corners_world, rvec, tvec, camera_matrix, None)
            proj = proj.reshape(4, 2)
            if not np.all(np.isfinite(proj)):
                continue
            color = (235, 235, 235) if (i + j) % 2 == 0 else (150, 150, 150)
            cv2.fillConvexPoly(canvas, proj.astype(np.int32), color)


def draw_marker(canvas, camera_matrix, R, t, marker_size_m, marker_id):
    """Vẽ marker ArUco (có viền trắng/quiet zone) đặt phẳng tại gốc toạ độ marker (0,0,0)."""
    rvec, _ = cv2.Rodrigues(R)
    tvec = t.reshape(3, 1)

    dictionary = aruco.getPredefinedDictionary(config.ARUCO_DICT)
    raw = aruco.generateImageMarker(dictionary, marker_id, 300)
    raw_bgr = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)

    pad = 60
    padded = cv2.copyMakeBorder(raw_bgr, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    ph, pw = padded.shape[:2]

    padded_size_m = marker_size_m * (pw / 300.0)
    half = padded_size_m / 2.0
    obj_pts = np.array(
        [[-half, half, 0.0], [half, half, 0.0], [half, -half, 0.0], [-half, -half, 0.0]]
    )
    proj, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, None)
    dst_pts = proj.reshape(4, 2).astype(np.float32)

    src_pts = np.float32([[0, 0], [pw, 0], [pw, ph], [0, ph]])
    H = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(
        padded, H, (canvas.shape[1], canvas.shape[0]), borderValue=(255, 255, 255)
    )

    mask = np.zeros(canvas.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask, dst_pts.astype(np.int32), 255)
    canvas[mask > 0] = warped[mask > 0]


DEMO_IMAGE_NAME = "demo_scene.png"
DEMO_POSE_NAME = "demo_pose_su_thuc.json"
DEFAULT_IMAGE_NAME = "synthetic_scene.png"
DEFAULT_POSE_NAME = "pose_su_thuc.json"


def main(marker_size_mm: float = config.MARKER_SIZE_MM, demo: bool = False,
         image_name: str | None = None, pose_name: str | None = None, out_dir=None) -> dict:
    """
    Tạo ảnh giả lập + file đáp án pose. marker_size_mm: cạnh bảng (mm) dùng để vẽ, ghi đúng vào file đáp án.
    demo=True: dùng config.DEMO_MARKER_SIZE_MM và tên file demo_* (xem docstring đầu file).
    image_name/pose_name/out_dir ghi đè tên/thư mục đầu ra (mặc định config.OUTPUTS_DIR).
    Trả dict {image_path, pose_path, marker_size_mm}.
    """
    if demo:
        marker_size_mm = config.DEMO_MARKER_SIZE_MM
        image_name = image_name or DEMO_IMAGE_NAME
        pose_name = pose_name or DEMO_POSE_NAME
    image_name = image_name or DEFAULT_IMAGE_NAME
    pose_name = pose_name or DEFAULT_POSE_NAME
    if not marker_size_mm > 0:
        raise ValueError(f"marker_size_mm phải > 0, nhận được: {marker_size_mm!r}")

    width, height = config.CAMERA_RESOLUTION
    camera_matrix = camera_model.build_camera_matrix(width, height, config.DIAGONAL_FOV_DEG)

    R_wc, t, cam_origin = build_ground_truth_pose()

    canvas = np.full((height, width, 3), (200, 230, 200), dtype=np.uint8)  # nền xanh nhạt (cỏ)
    draw_checkerboard(canvas, camera_matrix, R_wc, t)
    draw_marker(canvas, camera_matrix, R_wc, t, marker_size_mm / 1000.0, config.MARKER_ID)

    out_dir = config.OUTPUTS_DIR if out_dir is None else Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / image_name
    cv2.imwrite(str(img_path), canvas)

    pose_answer = {
        "note": "Đáp án pose dùng để vẽ ảnh giả lập - so sánh với kết quả calibrate_aruco.py",
        "R": R_wc.tolist(),
        "t": t.tolist(),
        "camera_origin_marker_frame_m": cam_origin.tolist(),
        "camera_matrix": camera_matrix.tolist(),
        "image_size": [width, height],
        "marker_size_mm": float(marker_size_mm),
        "marker_id": config.MARKER_ID,
    }
    pose_path = out_dir / pose_name
    pose_path.write_text(json.dumps(pose_answer, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Đã tạo ảnh giả lập: {img_path} (bảng {marker_size_mm:g} mm)")
    print(f"Đã lưu đáp án pose: {pose_path}")
    print("R (đáp án, world/marker -> camera) =")
    print(R_wc)
    print(f"t (đáp án) = {t}")
    print(f"Vị trí camera trong hệ marker (đáp án) = {cam_origin}")
    return {"image_path": img_path, "pose_path": pose_path, "marker_size_mm": float(marker_size_mm)}


def _cli(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Tạo ảnh giả lập (mặt đất caro + bảng ArUco ở pose biết trước)")
    ap.add_argument("--marker-size-mm", type=float, default=config.MARKER_SIZE_MM,
                    help=f"Cạnh bảng (mm) dùng để vẽ, mặc định {config.MARKER_SIZE_MM:g}")
    ap.add_argument("--demo", action="store_true",
                    help=f"Bảng {config.DEMO_MARKER_SIZE_MM:g} mm, ghi ra {DEMO_IMAGE_NAME} / {DEMO_POSE_NAME}")
    a = ap.parse_args(argv)
    main(marker_size_mm=a.marker_size_mm, demo=a.demo)


if __name__ == "__main__":
    _cli()
