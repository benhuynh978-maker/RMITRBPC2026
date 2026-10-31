"""
size_test/scene.py — Dựng cảnh 3D đơn giản có "rác" KÍCH THƯỚC THẬT BIẾT TRƯỚC rồi render
bằng đúng phép chiếu pinhole của exp02 (cv2.projectPoints, camera_matrix suy từ
config.DIAGONAL_FOV_DEG, dist = 0) với pose ĐÁP ÁN (R, t) biết trước.

Quy ước (giống hệt code dùng chung của exp02):
  - Hệ toạ độ "mặt đất" = hệ toạ độ marker: marker nằm phẳng tại gốc (0,0,0), mặt đất là z = 0,
    X marker ~ Đông, Y marker ~ Bắc, Z hướng lên trời (camera_model.get_marker_object_points).
  - R, t: biến đổi marker -> camera, X_cam = R @ X_marker + t (calibrate_aruco.py).
  - Camera dựng kiểu "look-at" như make_synthetic_test.build_ground_truth_pose: hàng của R là
    (phải, xuống, trước) của camera biểu diễn trong hệ marker.
  - Mặt đất caro + marker được vẽ bằng CHÍNH hàm dùng chung make_synthetic_test.draw_checkerboard
    và make_synthetic_test.draw_marker (chỉ import, không ghi gì vào outputs/).

Bố trí cảnh (giả định tự chọn, ghi rõ trong REPORT.md):
  - Chân camera đặt tại (0.6, -2.5, 0) trong hệ marker => marker nằm cách chân camera 2.5 m về
    phía trước và lệch trái 0.6 m (để không đè lên hàng vật đặt ở giữa).
  - Camera nhìn về hướng +Y (Bắc). Vị trí vật cho theo (lệch ngang a, khoảng cách d) so với
    chân camera: world = (0.6 + a, -2.5 + d).
  - Với ống kính FOV chéo 66° (FOV dọc ~42.6°), camera cao 3 m KHÔNG thể phủ cùng lúc dải
    1–8 m (cần ~53°) => dùng 2 "họ pose":
        GAN: cúi 60° dưới phương ngang, phủ mặt đất ~0.46–3.7 m  -> vật ở 1, 2, 3 m
        XA : cúi 40° dưới phương ngang, phủ mặt đất ~1.64–8.9 m  -> vật ở 2, 3, 5, 8 m
    Mỗi họ có 5 biến thể pose (độ cao 2.9–3.1 m, xoay ngang ±2.5°) để sai số hiệu chỉnh marker
    không chỉ là 1 mẫu duy nhất.

Quy tắc raster (quan trọng cho "mask đáp án"):
  - Mask đáp án: pixel thuộc vật <=> TÂM pixel nằm trong đa giác chiếu của vật (quy tắc lấy mẫu
    tại tâm - không thiên lệch về diện tích). KHÔNG dùng cv2.fillPoly làm mask vì fillPoly tô
    "bao hàm" mọi pixel bị cạnh chạm vào => mask béo thêm ~0.5 px quanh viền.
  - Ảnh: render siêu lấy mẫu 4x (SS=4) rồi thu nhỏ INTER_AREA => mỗi pixel là trung bình diện
    tích như cảm biến thật (viền vật/marker có mức xám trung gian), vật vẽ cùng quy tắc tâm pixel
    ở độ phân giải 4x.

Module này chỉ dựng/render trong bộ nhớ, không ghi file (trừ khi chạy main để xem trước,
ảnh xem trước ghi vào size_test/ketqua/).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SIZE_TEST_DIR = Path(__file__).resolve().parent
EXP_DIR = SIZE_TEST_DIR.parent
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

import camera_model  # noqa: E402
import config  # noqa: E402
import make_synthetic_test  # noqa: E402  (chỉ dùng draw_checkerboard / draw_marker)

TMP_DIR = SIZE_TEST_DIR / "tmp"
RESULTS_DIR = SIZE_TEST_DIR / "ketqua"

WIDTH, HEIGHT = config.CAMERA_RESOLUTION
CAMERA_MATRIX = camera_model.build_camera_matrix(WIDTH, HEIGHT, config.DIAGONAL_FOV_DEG)
MARKER_SIZE_M = config.MARKER_SIZE_MM / 1000.0
# draw_marker() vẽ marker kèm khung trắng 60px quanh mã 300px => cạnh ngoài = 420/300 cạnh mã
MARKER_PADDED_SIZE_M = MARKER_SIZE_M * (420.0 / 300.0)

# Chân camera trong hệ marker (mặt đất). Vị trí vật cho tương đối so với điểm này.
CAMERA_FOOT_WORLD = np.array([0.6, -2.5], dtype=np.float64)

# Màu rác giả lập (BGR) - magenta bão hoà, tách biệt nền xanh nhạt / caro xám / marker đen trắng
OBJ_COLOR_TOP = (255, 0, 255)
OBJ_COLOR_SIDE_A = (200, 0, 200)
OBJ_COLOR_SIDE_B = (150, 0, 150)

BACKGROUND_BGR = (200, 230, 200)
SUPERSAMPLE = 4
CIRCLE_SEGMENTS = 720

# --- Họ pose camera ---
POSE_FAMILIES: Dict[str, dict] = {
    "GAN": {
        "pitch_deg": 60.0,
        "rows_d": [1.0, 2.0, 3.0],
        "lateral": [(1.0, -0.8), (1.0, 0.8), (3.0, -1.2), (3.0, 1.2)],
        "box_d": [1.0, 2.0, 3.0],
    },
    "XA": {
        "pitch_deg": 40.0,
        "rows_d": [2.0, 3.0, 5.0, 8.0],
        "lateral": [(3.0, -1.2), (3.0, 1.2), (5.0, -1.5), (5.0, 1.5)],
        "box_d": [2.0, 3.0, 5.0, 8.0],
    },
}
# (độ cao camera m, xoay ngang yaw độ) - biến thể 0 là pose danh nghĩa
POSE_VARIANTS: List[Tuple[float, float]] = [
    (3.0, 0.0),
    (3.0, 2.5),
    (3.0, -2.5),
    (2.9, 1.0),
    (3.1, -1.0),
]

# --- Vật phẳng: tên -> (kích thước X m, kích thước Y m, loại) ---
FLAT_SHAPES: Dict[str, Tuple[float, float, str]] = {
    "vuong_0.1": (0.1, 0.1, "rect"),
    "vuong_0.2": (0.2, 0.2, "rect"),
    "vuong_0.3": (0.3, 0.3, "rect"),
    "vuong_0.5": (0.5, 0.5, "rect"),
    "cn_1.0x0.3_ngang": (1.0, 0.3, "rect"),  # cạnh dài 1.0 m nằm ngang (trục X)
    "cn_0.3x1.0_doc": (0.3, 1.0, "rect"),  # cạnh dài 1.0 m dọc hướng nhìn (trục Y)
    "tron_0.4": (0.4, 0.4, "circle"),
}
BOX_NAME = "hop_0.3x0.3_cao0.2"
BOX_SIZE = (0.3, 0.3, 0.2)


@dataclass
class Pose:
    family: str
    variant: int
    height_m: float
    pitch_deg: float
    yaw_deg: float
    R: np.ndarray  # marker -> camera
    t: np.ndarray  # (3,)
    cam_center: np.ndarray  # (3,) trong hệ marker

    @property
    def label(self) -> str:
        return f"{self.family}-v{self.variant}"


@dataclass
class SceneObject:
    name: str  # tên hình
    kind: str  # "flat" hoặc "box"
    d_m: float  # khoảng cách danh nghĩa từ chân camera theo hướng nhìn
    a_m: float  # lệch ngang (âm = trái, dương = phải)
    center_world: np.ndarray  # (2,) tâm thật trên mặt đất (hệ marker)
    footprint_world: np.ndarray  # (N,2) đa giác đáy thật trên mặt đất
    true_area_m2: float
    height_m: float = 0.0
    size_xy: Tuple[float, float] = (0.0, 0.0)
    extra: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.name}@d{self.d_m:g}_a{self.a_m:+g}"


def make_pose(family: str, variant: int) -> Pose:
    """Pose đáp án dạng look-at: camera đặt trên chân camera, cúi pitch độ, xoay ngang yaw độ."""
    fam = POSE_FAMILIES[family]
    height_m, yaw_deg = POSE_VARIANTS[variant]
    pitch = math.radians(fam["pitch_deg"])
    yaw = math.radians(yaw_deg)

    cam_center = np.array([CAMERA_FOOT_WORLD[0], CAMERA_FOOT_WORLD[1], height_m], dtype=np.float64)
    horiz = np.array([math.sin(yaw), math.cos(yaw), 0.0])  # yaw dương = xoay sang phải (về phía Đông)
    forward = math.cos(pitch) * horiz + np.array([0.0, 0.0, -math.sin(pitch)])
    forward /= np.linalg.norm(forward)
    world_up = np.array([0.0, 0.0, 1.0])
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    true_up = np.cross(right, forward)
    # Giống make_synthetic_test.build_ground_truth_pose: hàng R = (phải, xuống, trước)
    R = np.array([right, -true_up, forward], dtype=np.float64)
    t = -R @ cam_center
    return Pose(family, variant, height_m, fam["pitch_deg"], yaw_deg, R, t, cam_center)


def rel_to_world(a_m: float, d_m: float) -> np.ndarray:
    return CAMERA_FOOT_WORLD + np.array([a_m, d_m], dtype=np.float64)


def _rect_polygon(cx: float, cy: float, sx: float, sy: float) -> np.ndarray:
    hx, hy = sx / 2.0, sy / 2.0
    return np.array(
        [[cx - hx, cy - hy], [cx + hx, cy - hy], [cx + hx, cy + hy], [cx - hx, cy + hy]],
        dtype=np.float64,
    )


def _circle_polygon(cx: float, cy: float, radius: float, n: int = CIRCLE_SEGMENTS) -> np.ndarray:
    ang = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    return np.stack([cx + radius * np.cos(ang), cy + radius * np.sin(ang)], axis=1)


def make_flat_object(name: str, d_m: float, a_m: float) -> SceneObject:
    sx, sy, kind = FLAT_SHAPES[name]
    c = rel_to_world(a_m, d_m)
    if kind == "rect":
        poly = _rect_polygon(c[0], c[1], sx, sy)
        area = sx * sy
    else:
        poly = _circle_polygon(c[0], c[1], sx / 2.0)
        area = math.pi * (sx / 2.0) ** 2  # diện tích hình tròn THẬT (không phải đa giác 720 cạnh)
    return SceneObject(name, "flat", d_m, a_m, c, poly, area, 0.0, (sx, sy))


def make_box_object(d_m: float, a_m: float = 0.0) -> SceneObject:
    sx, sy, sz = BOX_SIZE
    c = rel_to_world(a_m, d_m)
    poly = _rect_polygon(c[0], c[1], sx, sy)
    return SceneObject(BOX_NAME, "box", d_m, a_m, c, poly, sx * sy, sz, (sx, sy))


def objects_for_family(family: str) -> List[SceneObject]:
    """Toàn bộ vật cần đo cho 1 họ pose: mỗi hình phẳng × mỗi vị trí, cộng hộp cao ở hàng giữa."""
    fam = POSE_FAMILIES[family]
    positions = [(d, 0.0) for d in fam["rows_d"]] + list(fam["lateral"])
    objs: List[SceneObject] = []
    for name in FLAT_SHAPES:
        for d, a in positions:
            objs.append(make_flat_object(name, d, a))
    for d in fam["box_d"]:
        objs.append(make_box_object(d, 0.0))
    return objs


# ----------------------------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------------------------

def project_world_points(points_xyz: np.ndarray, pose: Pose) -> np.ndarray:
    rvec, _ = cv2.Rodrigues(pose.R)
    proj, _ = cv2.projectPoints(
        np.ascontiguousarray(points_xyz, dtype=np.float64), rvec, pose.t.reshape(3, 1), CAMERA_MATRIX, None
    )
    return proj.reshape(-1, 2)


def _fill_subpixel(img: np.ndarray, pts_uv: np.ndarray, color) -> None:
    """(Chỉ dùng cho vùng marker để kiểm tra chồng lấn) fillPoly dấu phẩy tĩnh shift=8."""
    shift = 8
    pts = np.round(pts_uv * (1 << shift)).astype(np.int32).reshape(-1, 1, 2)
    cv2.fillPoly(img, [pts], color, lineType=cv2.LINE_8, shift=shift)


def raster_center_rule(pts_uv: np.ndarray, shape) -> np.ndarray:
    """
    Mask bool: pixel (x,y) thuộc đa giác <=> tâm pixel (toạ độ nguyên x,y theo quy ước OpenCV/
    projectPoints) nằm trong đa giác. Chỉ xét trong khung bao để nhanh.
    """
    h, w = shape
    out = np.zeros((h, w), dtype=bool)
    x0 = max(0, int(math.floor(pts_uv[:, 0].min())))
    x1 = min(w - 1, int(math.ceil(pts_uv[:, 0].max())))
    y0 = max(0, int(math.floor(pts_uv[:, 1].min())))
    y1 = min(h - 1, int(math.ceil(pts_uv[:, 1].max())))
    if x1 < x0 or y1 < y0:
        return out
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    inside = MplPath(pts_uv).contains_points(np.stack([xs.ravel(), ys.ravel()], axis=1))
    out[y0:y1 + 1, x0:x1 + 1] = inside.reshape(xs.shape)
    return out


def supersampled_camera_matrix(k: int = SUPERSAMPLE) -> np.ndarray:
    """
    camera_matrix cho ảnh phóng k lần sao cho thu nhỏ INTER_AREA về đúng ảnh gốc:
    pixel gốc u (tâm tại số nguyên) <-> pixel con j = k*u + (k-1)/2.
    """
    K = CAMERA_MATRIX.copy()
    K[0, 0] *= k
    K[1, 1] *= k
    K[0, 2] = k * K[0, 2] + (k - 1) / 2.0
    K[1, 2] = k * K[1, 2] + (k - 1) / 2.0
    return K


def to_supersampled_uv(uv: np.ndarray, k: int = SUPERSAMPLE) -> np.ndarray:
    return uv * k + (k - 1) / 2.0


def _box_vertices(obj: SceneObject) -> Tuple[np.ndarray, List[Tuple[List[int], np.ndarray]]]:
    sx, sy = obj.size_xy
    sz = obj.height_m
    cx, cy = obj.center_world
    xs = (cx - sx / 2, cx + sx / 2)
    ys = (cy - sy / 2, cy + sy / 2)
    zs = (0.0, sz)
    v = np.array([[x, y, z] for z in zs for y in ys for x in xs], dtype=np.float64)
    # chỉ số: z0: 0(x0y0) 1(x1y0) 2(x0y1) 3(x1y1); z1: +4
    faces = [
        ([4, 5, 7, 6], np.array([0, 0, 1.0])),  # mặt trên
        ([0, 1, 5, 4], np.array([0, -1.0, 0])),  # mặt gần (phía Nam, về phía camera)
        ([2, 3, 7, 6], np.array([0, 1.0, 0])),  # mặt xa
        ([0, 2, 6, 4], np.array([-1.0, 0, 0])),  # mặt trái
        ([1, 3, 7, 5], np.array([1.0, 0, 0])),  # mặt phải
    ]
    return v, faces


def object_image_points(obj: SceneObject, pose: Pose) -> np.ndarray:
    """Toàn bộ đỉnh của vật chiếu lên ảnh (để kiểm vật có nằm trọn trong khung hình)."""
    if obj.kind == "box":
        v, _ = _box_vertices(obj)
    else:
        v = np.hstack([obj.footprint_world, np.zeros((len(obj.footprint_world), 1))])
    return project_world_points(v, pose)


def object_in_frame(obj: SceneObject, pose: Pose, margin_px: float = 2.0) -> bool:
    if obj.kind == "box":
        v, _ = _box_vertices(obj)
    else:
        v = np.hstack([obj.footprint_world, np.zeros((len(obj.footprint_world), 1))])
    cam_pts = (pose.R @ v.T).T + pose.t
    if np.any(cam_pts[:, 2] <= 1e-6):
        return False
    uv = project_world_points(v, pose)
    return bool(
        np.all(uv[:, 0] >= margin_px)
        and np.all(uv[:, 0] <= WIDTH - 1 - margin_px)
        and np.all(uv[:, 1] >= margin_px)
        and np.all(uv[:, 1] <= HEIGHT - 1 - margin_px)
    )


def draw_object(canvas_ss: np.ndarray, obj: SceneObject, pose: Pose) -> np.ndarray:
    """
    Vẽ vật lên canvas SIÊU LẤY MẪU (kích thước SS*H x SS*W), trả mask ĐÁP ÁN ở độ phân giải
    gốc (uint8 0/255) = các pixel có tâm nằm trong hình chiếu của vật.
    """
    k = SUPERSAMPLE
    ss_shape = canvas_ss.shape[:2]
    if obj.kind == "flat":
        uv = project_world_points(
            np.hstack([obj.footprint_world, np.zeros((len(obj.footprint_world), 1))]), pose
        )
        mask = raster_center_rule(uv, (HEIGHT, WIDTH))
        canvas_ss[raster_center_rule(to_supersampled_uv(uv, k), ss_shape)] = OBJ_COLOR_TOP
        return mask.astype(np.uint8) * 255

    # Hộp: hình bóng = bao lồi của 8 đỉnh chiếu (vật lồi, mọi đỉnh ở trước camera)
    v, faces = _box_vertices(obj)
    uv = project_world_points(v, pose)
    hull = project_world_points(v, pose)[_hull_indices(uv)]  # đỉnh bao lồi với toạ độ float64 gốc
    mask = raster_center_rule(hull, (HEIGHT, WIDTH))
    sil_ss = raster_center_rule(to_supersampled_uv(hull, k), ss_shape)
    canvas_ss[sil_ss] = OBJ_COLOR_SIDE_B  # lót nền hình bóng
    face_colors = [OBJ_COLOR_TOP, OBJ_COLOR_SIDE_A, OBJ_COLOR_SIDE_A, OBJ_COLOR_SIDE_B, OBJ_COLOR_SIDE_B]
    order = list(range(1, len(faces))) + [0]  # mặt trên vẽ cuối
    for fi in order:
        idx, normal = faces[fi]
        face_center = v[idx].mean(axis=0)
        if float(np.dot(normal, pose.cam_center - face_center)) <= 0:
            continue  # mặt quay lưng về camera
        layer = raster_center_rule(to_supersampled_uv(uv[idx], k), ss_shape) & sil_ss
        canvas_ss[layer] = face_colors[fi]
    return mask.astype(np.uint8) * 255


def _hull_indices(uv: np.ndarray) -> np.ndarray:
    return cv2.convexHull(uv.astype(np.float32), returnPoints=False).reshape(-1)


def marker_region_mask(pose: Pose) -> np.ndarray:
    """Vùng ảnh marker (kể cả khung trắng) chiếm - để kiểm vật không đè lên marker."""
    half = MARKER_PADDED_SIZE_M / 2.0
    pts = np.array([[-half, half, 0], [half, half, 0], [half, -half, 0], [-half, -half, 0]], dtype=np.float64)
    uv = project_world_points(pts, pose)
    m = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    _fill_subpixel(m, uv, 255)
    return m


def render_background_ss(pose: Pose) -> np.ndarray:
    """
    Nền ở độ phân giải siêu lấy mẫu: cỏ xanh nhạt + caro 0.5 m + marker ArUco tại gốc, vẽ bằng
    CHÍNH hàm dùng chung make_synthetic_test.draw_checkerboard / draw_marker (truyền camera_matrix 4x).
    """
    k = SUPERSAMPLE
    K_ss = supersampled_camera_matrix(k)
    canvas = np.full((HEIGHT * k, WIDTH * k, 3), BACKGROUND_BGR, dtype=np.uint8)
    make_synthetic_test.draw_checkerboard(
        canvas, K_ss, pose.R, pose.t, square_m=0.5, x_half=8.0, y_min=-3.0, y_max=12.0
    )
    make_synthetic_test.draw_marker(canvas, K_ss, pose.R, pose.t, MARKER_SIZE_M, config.MARKER_ID)
    return canvas


_BG_CACHE: Dict[str, np.ndarray] = {}


def render_scene(pose: Pose, objects: List[SceneObject], check_overlap: bool = True):
    """
    Render ảnh 640x480 có marker + các vật. Trả (ảnh BGR, {uid: mask đáp án uint8}).
    Raise ValueError nếu vật đè lên marker hoặc đè lên nhau (cảnh không hợp lệ).
    """
    key = pose.label
    if key not in _BG_CACHE:
        if len(_BG_CACHE) > 4:
            _BG_CACHE.clear()
        _BG_CACHE[key] = render_background_ss(pose)
    canvas_ss = _BG_CACHE[key].copy()
    masks: Dict[str, np.ndarray] = {}
    marker_m = marker_region_mask(pose)
    kernel = np.ones((5, 5), np.uint8)
    occupied = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    for obj in objects:
        m = draw_object(canvas_ss, obj, pose)
        if check_overlap:
            grown = cv2.dilate(m, kernel)
            if np.any((grown > 0) & (marker_m > 0)):
                raise ValueError(f"Vật {obj.uid} đè lên marker ở pose {pose.label}")
            if np.any((grown > 0) & (occupied > 0)):
                raise ValueError(f"Vật {obj.uid} đè lên vật khác ở pose {pose.label}")
            occupied |= grown
        masks[obj.uid] = m
    img = cv2.resize(canvas_ss, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)
    return img, masks


# Bố cục ảnh minh hoạ (nhiều vật cùng lúc, không chồng nhau) - chỉ để đưa vào REPORT
OVERVIEW_LAYOUT = {
    "GAN": [
        ("vuong_0.5", 1.0, 0.0),
        ("vuong_0.2", 1.0, 0.8),
        ("cn_0.3x1.0_doc", 1.0, -0.8),
        (BOX_NAME, 2.0, 0.0),
        ("cn_1.0x0.3_ngang", 3.0, 0.0),
        ("vuong_0.3", 3.0, 1.2),
        ("tron_0.4", 3.0, -1.2),
    ],
    "XA": [
        ("cn_1.0x0.3_ngang", 2.0, 0.0),
        ("vuong_0.5", 3.0, 0.0),
        ("tron_0.4", 3.0, 1.2),
        ("vuong_0.2", 3.0, -1.2),
        (BOX_NAME, 5.0, 0.0),
        ("vuong_0.3", 5.0, 1.5),
        ("cn_0.3x1.0_doc", 5.0, -1.5),
        ("vuong_0.5", 8.0, 0.0),
    ],
}


def overview_objects(family: str) -> List[SceneObject]:
    out = []
    for name, d, a in OVERVIEW_LAYOUT[family]:
        out.append(make_box_object(d, a) if name == BOX_NAME else make_flat_object(name, d, a))
    return out


def main():
    """Xem trước: in vùng phủ mặt đất của từng pose + lưu ảnh cảnh minh hoạ vào size_test/ketqua/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    half_v = math.degrees(math.atan((HEIGHT / 2) / CAMERA_MATRIX[1, 1]))
    print(f"camera_matrix f = {CAMERA_MATRIX[0, 0]:.2f}px, FOV dọc = {2 * half_v:.2f}°")
    for fam in POSE_FAMILIES:
        for vi in range(len(POSE_VARIANTS)):
            p = make_pose(fam, vi)
            lo = p.height_m / math.tan(math.radians(p.pitch_deg + half_v))
            hi = p.height_m / math.tan(math.radians(p.pitch_deg - half_v))
            objs = objects_for_family(fam)
            n_in = sum(object_in_frame(o, p) for o in objs)
            print(
                f"{p.label}: cao {p.height_m} m, cúi {p.pitch_deg}°, yaw {p.yaw_deg:+}° -> "
                f"phủ mặt đất (trục giữa) {lo:.2f}–{hi:.2f} m; vật trong khung {n_in}/{len(objs)}"
            )
        p0 = make_pose(fam, 0)
        img, _ = render_scene(p0, overview_objects(fam))
        out = RESULTS_DIR / f"canh_xem_truoc_{fam}.png"
        cv2.imwrite(str(out), img)
        print(f"  -> {out}")


if __name__ == "__main__":
    main()
