"""
Cấu hình chung cho thử nghiệm exp02: chiếu vùng rác lên bản đồ bằng hiệu chỉnh marker ArUco.

MỌI đường dẫn trong file này chỉ trỏ vào bên trong research/exp02_ve_rac_len_ban_do/
(và đọc-chỉ-đọc vào datasets/Try1 có sẵn của project) - không script nào trong exp02
được phép ghi ra ngoài 2 phạm vi đó.
"""
from __future__ import annotations

from pathlib import Path

import cv2.aruco as aruco

# --- Đường dẫn ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
CALIBRATION_DIR = BASE_DIR / "calibration"
VIEWER_DIR = BASE_DIR / "viewer"

# Thư mục dataset có sẵn của project - CHỈ ĐỌC, không ghi gì vào đây
PROJECT_ROOT = BASE_DIR.parent.parent
DATASET_TEST_IMAGES_DIR = PROJECT_ROOT / "datasets" / "Try1" / "test" / "images"
DATASET_TEST_LABELS_DIR = PROJECT_ROOT / "datasets" / "Try1" / "test" / "labels"

# --- Marker ArUco ---
ARUCO_DICT = aruco.DICT_4X4_50
MARKER_ID = 0
# Kích thước cạnh marker THẬT cần in ra giấy, đơn vị mm. Đây là số marker demo nhóm tự chọn
# (200x200mm) - khi in ra ngoài thực tế PHẢI đo lại bằng thước, sửa lại số này cho khớp.
MARKER_SIZE_MM = 200.0
# Bảng trong ảnh DEMO (run_demo_vehtruong.py): 400 mm để cạnh bảng trên ảnh >= 50 px (ngưỡng chặn duy nhất của
# calibrate_aruco, xem calib_quality.MIN_SIDE_PX). Riêng hằng này; MARKER_SIZE_MM (200) giữ nguyên cho các test.
DEMO_MARKER_SIZE_MM = 400.0

# --- Bảng IN THẬT (quyết định 2026-10-12: in khổ A3 để bảng lớn, rõ hơn khi camera ở xa/cao) ---
# MARKER_SIZE_MM ở trên là cỡ bảng trong ảnh GIẢ LẬP (các test cũ dựa vào nó, giữ nguyên).
# Bảng in thật: cạnh vùng mã 250 mm đặt giữa tờ A3 dọc (297x420 mm); phần giấy trắng quanh bảng
# đóng vai trò vùng yên tĩnh (quiet zone). Sau khi in PHẢI đo lại cạnh vùng mã bằng thước.
PRINT_PAPER = "A3"
PRINT_PAPER_MM = (297.0, 420.0)  # (rộng, cao), khổ dọc
PRINT_MARKER_SIZE_MM = 250.0

# --- Camera giả định (chưa có số đo thật từ hiện trường) ---
# Độ phân giải ảnh camera giả định dùng cho các bước hiệu chỉnh/thử nghiệm mặc định.
# calibrate_aruco.py và project_mask.py vẫn tự lấy đúng kích thước ảnh thật truyền vào,
# số này chỉ dùng làm mặc định khi tạo ảnh giả lập (make_synthetic_test.py).
CAMERA_RESOLUTION = (640, 480)  # (width, height)

# GIẢ ĐỊNH góc mở ống kính theo đường chéo, lấy tham khảo thông số module camera OV2640
# (ESP32-CAM hay dùng) ~66 độ. ĐÂY KHÔNG PHẢI SỐ ĐO THẬT - cần đo lại bằng ảnh checkerboard
# thật (camera calibration chuẩn) khi triển khai thật, số này chỉ để chạy thử luồng xử lý.
DIAGONAL_FOV_DEG = 66.0

# --- Toạ độ demo (KHÔNG phải vị trí thật) ---
# Không tìm thấy toạ độ GPS thật của camera/cống nào trong project tại thời điểm viết exp02.
# Dùng 1 điểm giả định hợp lý trong khu vực TP.HCM (nơi ảnh dataset Try1/các ảnh "tphcm1" được
# quay) làm vị trí marker demo - CHỈ để chạy thử toàn luồng, không đại diện vị trí cống thật.
DEMO_MARKER_LATLON = (10.7769, 106.7009)
DEMO_CAMERA_ID = "DEMO-CAM"

# Ảnh có nhãn tay lớp "Trash" (class 0) dùng làm demo project_mask - xem run_demo_vehtruong.py
DEMO_LABELED_IMAGE_STEM = "g1lop_000003_JPG.rf.54f58bb676977aea74419e3698ac6ac4"

# Bán kính Trái Đất (mét) dùng cho công thức xấp xỉ mét -> lat/lon (đủ dùng ở phạm vi vài trăm mét)
EARTH_RADIUS_M = 6378137.0
