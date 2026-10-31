"""
Đánh giá CHẤT LƯỢNG của một lần hiệu chỉnh bằng marker ArUco (khối `quality` trong kết quả
calibrate_aruco.detect_and_solve_pnp và trong calibration/<camera_id>.json).

Tách riêng khỏi calibrate_aruco.py để phần "đo + cảnh báo" thuần tính toán, test được độc lập.
Khối này CHỈ THÊM thông tin; không đổi các khoá cũ (R, t, camera_matrix, reproj_error_rms_px...)
mà project_mask.py đọc.

Các khoá của khối `quality`
  marker_side_px_min / marker_side_px_mean : cạnh ngắn nhất / trung bình của tứ giác dò được (px).
  reproj_rms             : sai số reprojection RMS (px) của nghiệm đã chọn.
  ambiguity_ratio        : reproj(nghiệm tệ hơn) / reproj(nghiệm tốt hơn) của 2 nghiệm IPPE_SQUARE.
                           Càng gần 1 càng mơ hồ (pose có thể bị lật). None nếu chỉ có 1 nghiệm / legacy.
                           Mẫu số được chặn dưới ở REPROJ_FLOOR_PX để không chia cho ~0.
  solution_chosen_by     : "height" | "reproj" | "above_plane_only" (| "legacy" khi legacy=True).
  camera_height_m_est    : độ cao camera so với mặt phẳng marker của nghiệm đã chọn (m).
  camera_height_m_given  : độ cao người dùng nhập (m) hoặc None.
  sharpness              : phương sai Laplacian của ảnh xám trong hộp bao tứ giác marker.
  sharpness_norm         : sharpness đã chuẩn hoá (xem bên dưới) - đây là số được so với ngưỡng.
  jpeg_quality_est       : ước lượng chất lượng JPEG (1..100, thang libjpeg) từ bảng lượng tử hoá, hoặc
                           None nếu không phải file JPEG.
  warnings               : list[str] cảnh báo tiếng Việt có dấu (rỗng = không có gì đáng ngại).

QUY TẮC CẢNH BÁO (ĐẶT CỐ ĐỊNH TRƯỚC KHI XEM KẾT QUẢ - không chỉnh theo kết quả sau này)
  1. marker_side_px_min < MIN_SIDE_PX (= 50) : "Bảng quá nhỏ trên ảnh (<50 px): pose có thể sai".
     ĐÂY CŨNG LÀ QUY TẮC CHẶN DUY NHẤT: calibrate_aruco CLI KHÔNG lưu file hiệu chỉnh và thoát mã 3
     khi cạnh ngắn nhất < 50 px (hàm is_too_small). Từ 50 px trở lên thì lưu bình thường. Không còn mức
     30 px và không còn cờ ghi đè. Dùng như thư viện thì detect_and_solve_pnp vẫn trả kết quả (kèm cảnh
     báo này), việc chặn chỉ nằm ở CLI, để stress_test/size_test còn đo được ảnh bảng nhỏ.
  2. ambiguity_ratio < 3 VÀ cả hai nghiệm đều nằm TRÊN mặt phẳng marker (tức nghiệm được chọn chỉ
     nhờ reproj) : "Hai nghiệm pose gần như ngang nhau (có thể lật)...". Bật BẤT KỂ có nhập
     camera_height_m hay không, vì độ cao không phân biệt được hai nghiệm (cùng độ cao, xem
     calibrate_aruco.py). (Nếu một nghiệm bị loại vì camera nằm dưới mặt phẳng thì đã hết mơ hồ.)
  3. Có camera_height_m mà |độ cao nghiệm chọn - camera_height_m| > 20% camera_height_m : cảnh báo.
  4. Nét: sharpness_norm < SHARPNESS_NORM_MIN : "Ảnh bị mờ ...". Ngưỡng được xác định BẰNG THỰC NGHIỆM
     trên ảnh giả lập, xem mục "Chọn ngưỡng độ nét" bên dưới.
  5. jpeg_quality_est < 60 : khuyến nghị chụp ảnh hiệu chỉnh ở chất lượng JPEG cao nhất.

CHỌN NGƯỠNG ĐỘ NÉT (SHARPNESS_NORM_MIN)
  Phương sai Laplacian THÔ phụ thuộc mạnh vào kích thước bảng trên ảnh (bảng càng nhỏ, mật độ cạnh
  trên một đơn vị diện tích càng cao) và vào độ tương phản giấy/mực, nên một ngưỡng thô duy nhất
  KHÔNG phân tách được ảnh nét với ảnh mờ (đo: ảnh mờ sigma=1 có thể lớn hơn ảnh nét ở bảng khác cỡ).
  Vì vậy ngưỡng so trên đại lượng đã chuẩn hoá:
        sharpness_norm = sharpness * (side_mean / 6) / contrast^2
  trong đó side_mean/6 là cạnh 1 module (marker 4x4 = lưới 6x6 module kể cả viền đen) tính bằng px và
  contrast = (phân vị 95 - phân vị 5) của mức xám bên trong tứ giác marker. Đại lượng này gần như
  không đổi theo cỡ bảng và độ tương phản đối với ảnh nét, và giảm mạnh khi mờ.
  Số đo cụ thể và cách chọn số: xem phần ghi chú ở ngay trên hằng số SHARPNESS_NORM_MIN.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

# ---------------- Ngưỡng cố định (xem docstring) ----------------
MIN_SIDE_PX = 50.0  # ngưỡng DUY NHẤT về cỡ bảng: dưới mức này vừa cảnh báo vừa bị CLI chặn lưu
AMBIGUITY_MIN_RATIO = 3.0
HEIGHT_TOLERANCE_REL = 0.20
JPEG_QUALITY_MIN = 60
REPROJ_FLOOR_PX = 1e-3  # chặn dưới mẫu số của ambiguity_ratio
# Ghi chú chọn ngưỡng (đo 2026-10-12 trên stress_test/scene.py, bảng 250 mm, D = 0,7..5 m,
# theta = 20/45/65 deg, 3 seed, 2 độ tương phản giấy/mực 220/35 và 170/90, mờ Gauss sigma 0/1/2 px
# áp trước khi nén JPEG q95 hoặc q25; chỉ tính ảnh dò được marker):
#   sharpness_norm   nét (n=124/q)     sigma=1 (n=121/116)   sigma=2 (n=84/79)
#   q95              min 1,058         max 0,281             max 0,061
#   q25              min 0,391         max 0,324             max 0,122
# Quy tắc chọn (đặt trước khi chốt số): ngưỡng = trung bình nhân giữa min(nét) và max(sigma=1) gộp
# cả hai mức JPEG = sqrt(0,391 * 0,324) = 0,356, làm tròn 0,35. Tức cờ "mờ" bật cho mờ từ sigma=1 px
# (mức bắt đầu gây hại theo stress_test) và không bật cho ảnh nét trong tập đo. Khoảng cách giữa hai
# lớp ở q25 hẹp (0,391 vs 0,324), và ảnh thật (ống kính OV2640, nhiễu) có thể nét kém hơn ảnh giả lập:
# ngưỡng này cần được kiểm lại trên ảnh thật khi có.
SHARPNESS_NORM_MIN = 0.35

# Bảng lượng tử hoá độ sáng chuẩn của libjpeg (Annex K) - dùng để ước lượng chất lượng JPEG.
_STD_LUMA_QTABLE = np.array([
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
], dtype=np.float64)


def side_lengths(corners: np.ndarray) -> np.ndarray:
    """Độ dài 4 cạnh của tứ giác (4x2) theo thứ tự các góc."""
    c = np.asarray(corners, dtype=np.float64).reshape(4, 2)
    return np.linalg.norm(c - np.roll(c, -1, axis=0), axis=1)


def marker_sharpness(gray: np.ndarray, corners: np.ndarray) -> tuple[float, float]:
    """
    Trả (sharpness, sharpness_norm). sharpness = var(Laplacian) trong hộp bao tứ giác marker;
    sharpness_norm = sharpness * (side_mean/6) / contrast^2 (xem docstring đầu file).
    """
    c = np.asarray(corners, dtype=np.float64).reshape(4, 2)
    h, w = gray.shape[:2]
    x0 = int(max(np.floor(c[:, 0].min()), 0))
    y0 = int(max(np.floor(c[:, 1].min()), 0))
    x1 = int(min(np.ceil(c[:, 0].max()) + 1, w))
    y1 = int(min(np.ceil(c[:, 1].max()) + 1, h))
    crop = gray[y0:y1, x0:x1]
    if crop.shape[0] < 3 or crop.shape[1] < 3:
        return 0.0, 0.0
    sharp = float(cv2.Laplacian(crop, cv2.CV_64F).var())

    # Độ tương phản = p95 - p5 mức xám bên trong tứ giác (viền đen + mã + mực/giấy chiếm đa số).
    mask = np.zeros(gray.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.round(c).astype(np.int32), 255)
    vals = gray[mask > 0]
    if vals.size < 4:
        return sharp, 0.0
    contrast = float(np.percentile(vals, 95) - np.percentile(vals, 5))
    if contrast < 1.0:
        return sharp, 0.0
    module_px = float(side_lengths(c).mean()) / 6.0
    return sharp, float(sharp * module_px / contrast ** 2)


def estimate_jpeg_quality(image_path: Path) -> Optional[int]:
    """
    Ước lượng chất lượng JPEG (thang libjpeg 1..100) từ bảng lượng tử hoá độ sáng bằng PIL:
    chọn Q sao cho bảng chuẩn co giãn theo Q gần bảng của file nhất. Trả None nếu không phải JPEG
    hoặc không đọc được bảng. Chỉ là ƯỚC LƯỢNG: bộ mã hoá phần cứng (ví dụ ESP32/OV2640) dùng bảng
    riêng nên con số chỉ mang tính tham khảo.
    """
    try:
        from PIL import Image
        with Image.open(image_path) as im:
            if im.format != "JPEG":
                return None
            tables = getattr(im, "quantization", None)
        if not tables:
            return None
        table = np.asarray(tables[0], dtype=np.float64)
        if table.size != 64:
            return None
    except Exception:
        return None
    best_q, best_err = None, None
    for q in range(1, 101):
        scale = 5000.0 / q if q < 50 else 200.0 - 2.0 * q
        cand = np.clip(np.floor((_STD_LUMA_QTABLE * scale + 50.0) / 100.0), 1, 255)
        err = float(np.abs(cand - table).sum())
        if best_err is None or err < best_err:
            best_q, best_err = q, err
    return int(best_q)


def build_warnings(
    side_min_px: float,
    ambiguity_ratio: Optional[float],
    two_solutions_unresolved: bool,
    camera_height_given_m: Optional[float],
    camera_height_est_m: Optional[float],
    sharpness_norm: float,
    jpeg_quality_est: Optional[int],
) -> List[str]:
    """Áp dụng đúng các quy tắc cảnh báo cố định trong docstring đầu file. Trả list[str] tiếng Việt."""
    warns: List[str] = []
    if is_too_small(side_min_px):
        warns.append("Bảng quá nhỏ trên ảnh (<50 px): pose có thể sai")
    if (ambiguity_ratio is not None and ambiguity_ratio < AMBIGUITY_MIN_RATIO
            and two_solutions_unresolved):
        warns.append(
            "Hai nghiệm pose gần như ngang nhau (có thể lật; độ cao camera không phân biệt được hai "
            "nghiệm): chụp lại từ góc xiên hơn / gần hơn / bảng lớn hơn và đối chiếu vị trí camera "
            "tính ra với thực tế"
        )
    if camera_height_given_m is not None and camera_height_est_m is not None:
        rel = abs(camera_height_est_m - camera_height_given_m) / max(abs(camera_height_given_m), 1e-9)
        if rel > HEIGHT_TOLERANCE_REL:
            warns.append(
                f"Độ cao camera của nghiệm đã chọn ({camera_height_est_m:.2f} m) lệch "
                f"{rel * 100:.0f}% so với giá trị nhập ({camera_height_given_m:.2f} m): "
                f"kiểm tra lại số đo tay, kích thước bảng hoặc chất lượng ảnh"
            )
    if sharpness_norm < SHARPNESS_NORM_MIN:
        warns.append(
            "Ảnh bị mờ trong vùng bảng (lệch nét/rung tay): chụp lại cho nét - mờ là nhiễu "
            "gây sai pose nặng nhất"
        )
    if jpeg_quality_est is not None and jpeg_quality_est < JPEG_QUALITY_MIN:
        warns.append(
            f"Ảnh JPEG chất lượng thấp (ước lượng ~{jpeg_quality_est} < {JPEG_QUALITY_MIN}): "
            f"nên chụp ảnh hiệu chỉnh ở chất lượng JPEG cao nhất (hoặc PNG)"
        )
    return warns


def is_too_small(side_min_px: float) -> bool:
    """Quy tắc chặn duy nhất: cạnh ngắn nhất của bảng trên ảnh < MIN_SIDE_PX (50 px)."""
    return side_min_px < MIN_SIDE_PX
