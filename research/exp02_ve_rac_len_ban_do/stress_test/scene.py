"""
Bộ dựng cảnh giả lập cho stress test ArUco (chỉ CPU, không ghi file nào).

Khác make_synthetic_test.py ở chỗ: pose tham số hoá theo (khoảng cách D, góc nghiêng θ, phương vị φ,
độ lệch tâm du/dv), render siêu lấy mẫu rồi thu nhỏ INTER_AREA, mức xám giấy/mực thực tế hơn,
quiet zone = 1 module (khớp generate_marker.py). Hàm ở đây chỉ trả về mảng numpy.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import cv2.aruco as aruco
import numpy as np

EXP02_DIR = Path(__file__).resolve().parent.parent
if str(EXP02_DIR) not in sys.path:
    sys.path.insert(0, str(EXP02_DIR))

import camera_model  # noqa: E402
import config  # noqa: E402

WIDTH, HEIGHT = config.CAMERA_RESOLUTION
K = camera_model.build_camera_matrix(WIDTH, HEIGHT, config.DIAGONAL_FOV_DEG)

PAPER_WHITE = 220
INK_BLACK = 35
GROUND_A = 120
GROUND_B = 140
BACKGROUND = 105
SUPERSAMPLE = 4


def look_at_pose(cam_center: np.ndarray, target: np.ndarray, world_up=(0.0, 0.0, 1.0)):
    """R (world->camera, hàng = trục phải/xuống/trước của camera trong hệ world), t = -R C."""
    forward = target - cam_center
    forward = forward / np.linalg.norm(forward)
    right = np.cross(forward, np.asarray(world_up, dtype=np.float64))
    right = right / np.linalg.norm(right)
    true_up = np.cross(right, forward)
    R = np.array([right, -true_up, forward])
    return R, -R @ cam_center


def make_pose(distance_m: float, theta_deg: float, azimuth_deg: float = 0.0,
              offset_px=(0.0, 0.0), camera_matrix: np.ndarray = K):
    """
    Pose đáp án: camera cách tâm marker distance_m, hướng lệch theta_deg so với pháp tuyến (+Z marker),
    phương vị azimuth_deg quanh pháp tuyến. Sau khi nhìn thẳng vào tâm marker, camera được xoay thêm
    (quanh trục của chính nó) để tâm marker hiện ở (cx+du, cy+dv). Trả (R, t, C).
    """
    th = np.deg2rad(theta_deg)
    ph = np.deg2rad(azimuth_deg)
    C = distance_m * np.array([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)])
    R0, _ = look_at_pose(C, np.zeros(3))
    du, dv = offset_px
    f = camera_matrix[0, 0]
    # Muốn hướng tới marker trong hệ camera mới là d = (du, dv, f)/|.| ; tìm Rc sao cho Rc @ (0,0,1) = d
    d = np.array([du, dv, f], dtype=np.float64)
    d /= np.linalg.norm(d)
    z = np.array([0.0, 0.0, 1.0])
    axis = np.cross(z, d)
    s = np.linalg.norm(axis)
    if s < 1e-12:
        Rc = np.eye(3)
    else:
        ang = np.arctan2(s, float(z @ d))
        Rc, _ = cv2.Rodrigues(axis / s * ang)
    R = Rc @ R0
    t = -R @ C
    return R, t, C


def project(points_w: np.ndarray, R: np.ndarray, t: np.ndarray, camera_matrix: np.ndarray) -> np.ndarray:
    cam = (R @ points_w.T).T + t
    uv = (camera_matrix @ cam.T).T
    return uv[:, :2] / uv[:, 2:3], cam[:, 2]


def ss_matrix(camera_matrix: np.ndarray, s: int) -> np.ndarray:
    """Ma trận nội tại cho ảnh siêu lấy mẫu s lần (giữ đúng quy ước tâm pixel khi INTER_AREA thu nhỏ)."""
    Ks = camera_matrix.copy()
    Ks[0, 0] *= s
    Ks[1, 1] *= s
    Ks[0, 2] = camera_matrix[0, 2] * s + (s - 1) / 2.0
    Ks[1, 2] = camera_matrix[1, 2] * s + (s - 1) / 2.0
    return Ks


def gt_corners(R, t, marker_size_m: float, camera_matrix: np.ndarray = K) -> np.ndarray:
    obj = camera_model.get_marker_object_points(marker_size_m)
    uv, _ = project(obj, R, t, camera_matrix)
    return uv


def side_lengths(corners: np.ndarray) -> np.ndarray:
    return np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1)


def _marker_texture(marker_id: int, module_px: int = 64) -> np.ndarray:
    dictionary = aruco.getPredefinedDictionary(config.ARUCO_DICT)
    raw = aruco.generateImageMarker(dictionary, marker_id, 6 * module_px)  # 4x4 + viền đen 1 module
    tex = np.where(raw > 127, PAPER_WHITE, INK_BLACK).astype(np.uint8)
    # quiet zone 1 module (khớp tỉ lệ generate_marker.py: 600 px mã + lề 100 px)
    return cv2.copyMakeBorder(tex, module_px, module_px, module_px, module_px,
                              cv2.BORDER_CONSTANT, value=PAPER_WHITE)


def render(R: np.ndarray, t: np.ndarray, marker_size_m: float = config.MARKER_SIZE_MM / 1000.0,
           marker_id: int = config.MARKER_ID, camera_matrix: np.ndarray = K,
           size=(WIDTH, HEIGHT), supersample: int = SUPERSAMPLE) -> np.ndarray:
    """Render ảnh BGR uint8 kích thước size (w,h): nền + mặt phẳng caro + marker, siêu lấy mẫu."""
    w, h = size
    s = supersample
    Ks = ss_matrix(camera_matrix, s)
    W, H = w * s, h * s
    canvas = np.full((H, W), BACKGROUND, dtype=np.uint8)

    # Mặt phẳng caro 0.5 m quanh marker (±6 m); bỏ ô có góc sau camera hoặc chiếu ra quá xa
    sq = 0.5
    for i in range(-12, 12):
        for j in range(-12, 12):
            x0, x1, y0, y1 = i * sq, (i + 1) * sq, j * sq, (j + 1) * sq
            pts = np.array([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]], dtype=np.float64)
            uv, z = project(pts, R, t, Ks)
            if np.any(z < 0.05) or np.any(np.abs(uv) > 4 * max(W, H)):
                continue
            col = GROUND_A if (i + j) % 2 == 0 else GROUND_B
            cv2.fillConvexPoly(canvas, np.round(uv).astype(np.int32), int(col), lineType=cv2.LINE_AA)

    tex = _marker_texture(marker_id)
    th_, tw_ = tex.shape[:2]
    padded_m = marker_size_m * 8.0 / 6.0
    half = padded_m / 2.0
    obj = np.array([[-half, half, 0], [half, half, 0], [half, -half, 0], [-half, -half, 0]], dtype=np.float64)
    dst, z = project(obj, R, t, Ks)
    if np.any(z <= 0):
        raise ValueError("Marker nằm sau camera")
    # Toạ độ pixel ảnh texture: góc ngoài của pixel (0,0) là (-0.5,-0.5)
    src = np.float32([[-0.5, -0.5], [tw_ - 0.5, -0.5], [tw_ - 0.5, th_ - 0.5], [-0.5, th_ - 0.5]])
    Hm = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
    warped = cv2.warpPerspective(tex, Hm, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=0)
    mask = cv2.warpPerspective(np.full_like(tex, 255), Hm, (W, H), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    a = mask.astype(np.float32) / 255.0
    canvas = (canvas.astype(np.float32) * (1 - a) + warped.astype(np.float32) * a)
    small = cv2.resize(canvas, (w, h), interpolation=cv2.INTER_AREA)
    small = np.clip(np.round(small), 0, 255).astype(np.uint8)
    return cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)


# ---------------- suy giảm ảnh ----------------

def jpeg_bytes(img: np.ndarray, quality: int) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("imencode JPEG thất bại")
    return buf.tobytes()


def degrade(img: np.ndarray, blur_sigma: float = 0.0, noise_sigma: float = 0.0,
            rng: np.random.Generator | None = None) -> np.ndarray:
    out = img.astype(np.float32)
    if blur_sigma > 0:
        out = cv2.GaussianBlur(out, (0, 0), blur_sigma)
    if noise_sigma > 0:
        if rng is None:
            rng = np.random.default_rng(0)
        # nhiễu độc lập từng kênh màu (giống cảm biến Bayer sau demosaic, đơn giản hoá)
        out = out + rng.normal(0.0, noise_sigma, size=out.shape).astype(np.float32)
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


# ---------------- sai số pose ----------------

def rotation_error_deg(R_gt: np.ndarray, R_est: np.ndarray) -> float:
    c = (np.trace(R_gt.T @ R_est) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def camera_center(R: np.ndarray, t: np.ndarray) -> np.ndarray:
    return -R.T @ np.asarray(t).reshape(3)
