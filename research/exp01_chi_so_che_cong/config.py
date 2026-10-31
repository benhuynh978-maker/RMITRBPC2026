"""Cau hinh thi nghiem exp01: chi so che cong (ROI co dinh vs cong thuc hien tai)."""
from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXP_DIR.parent.parent

MODEL_PATH = PROJECT_ROOT / "runs" / "segment" / "runs" / "train" / "baseline_v1_rev2" / "weights" / "best.pt"
DATASET_DIR = PROJECT_ROOT / "datasets" / "Try1"
SPLITS = ("valid", "test")  # KHONG BAO GIO dung train
IMAGE_EXTS = (".jpg", ".jpeg", ".png")

CACHE_DIR = EXP_DIR / "cache"
OUT_DIR = EXP_DIR / "outputs"
CHART_DIR = OUT_DIR / "charts"
EXAMPLE_DIR = OUT_DIR / "examples"
REPORT_PATH = EXP_DIR / "REPORT.md"

GT_CSV = OUT_DIR / "ground_truth.csv"
PER_DRAIN_CSV = OUT_DIR / "per_drain.csv"
PER_FRAME_CSV = OUT_DIR / "per_frame.csv"
PERTURB_CSV = OUT_DIR / "perturbations.csv"
TIMING_CSV = OUT_DIR / "inference_times.csv"
CACHE_INDEX_CSV = CACHE_DIR / "index.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

TRASH_CLASS = 0
DRAIN_CLASS = 1

# Tham so predict giong production (inference/analysis.py)
PREDICT_IMGSZ = 1024
DETECT_CONF = 0.25
MASK_THRESHOLD = 0.5
DEFAULT_CONFIDENCE = 0.575  # production: khong co object nao
EXPECTED_NATIVE_SIZE = 1024

# So luong ky vong
EXPECTED_DRAIN_IMAGES = {"valid": 44, "test": 25}
EXPECTED_DRAIN_IMAGES_TOTAL = 69
EXPECTED_DRAIN_POLYGONS = 76

# Nguong muc (band): green < 20, yellow 20..<50, red >= 50
YELLOW_THRESHOLD = 20.0
RED_THRESHOLD = 50.0

# Hysteresis
HYST_RED_ENTER = 50.0
HYST_RED_EXIT = 35.0
HYST_YELLOW_ENTER = 20.0
HYST_YELLOW_EXIT = 12.0

# Lam muot
MEDIAN_WINDOW = 5
N_FRAMES = 20
WARMUP_FRAMES = 4  # danh gia tren frame index 4..19

# Co canh bao confidence
FLAG_THRESHOLD = 0.5

# ESP32-like (C1)
ESP32_SIZE = 640
ESP32_JPEG_QUALITY = 12

# C2 (PHAN TICH BO SUNG, dang ky truoc khi co ket qua C2; KHONG thay doi ket luan chinh tren C1).
# Ly do: firmware dung esp32-camera `jpeg_quality = 12`, nhung thang do cua esp32-camera nguoc voi OpenCV
# (esp32-camera: SO NHO = CHAT LUONG CAO; OpenCV: so lon = chat luong cao). Anh ESP32 VGA that ~12-15 KB;
# OpenCV quality 20-30 o 640x480 cho 13.1-16.4 KB tren anh tphcm cua Try1. Vay C1 (OpenCV q12) co le
# khac nghiet hon thuc te. C2 = resize 640x640 INTER_AREA + OpenCV JPEG q25 + decode; GT/ROI o 640x640
# (giong C1, chi khac quality).
C2_JPEG_QUALITY = 25
# Chuoi mo phong bo sung cho C2: giong het 04 (cung seed), chi doi JPEG cuoi tu 10..15 thanh 20..30 (inclusive)
SIM_C2_JPEG_QUALITY = (20, 30)
PER_FRAME_C2_CSV = OUT_DIR / "per_frame_C2.csv"
PERTURB_C2_CSV = OUT_DIR / "perturbations_C2.csv"

# ROI nhieu (M2)
M2_SHIFTS = (0.05, 0.10)
M2_DIRECTIONS = ("left", "right", "up", "down")
M2_SCALES = (0.9, 1.1)

# Tieu chi (4): sai so hieu chinh cho phep (diem %)
CALIB_TOLERANCE_PTS = 5.0
# Tieu chi (a): S2 flips <= 50% S0 flips
FLIP_RATIO_MAX = 0.5

# Phan tich phu (KHONG anh huong tieu chi chinh): bo cong rat nho
# Dien tich = so pixel polygon GT rasterize o 1024x1024 (cot gt_area_px_1024; chinh la ROI M1 dung).
# Da kiem: dinh nghia shoelace (gt_area_poly_px_1024) cho cung 16 cong bi loai.
SMALL_DRAIN_MIN_AREA_PX_1024 = 1024  # >= 32x32 px

SEED = 20261010
BOOTSTRAP_N = 2000

# Mo phong chuoi khung hinh (04)
SIM = {
    "contrast_range": (0.85, 1.15),
    "brightness_range": (0.85, 1.15),
    "gamma_range": (0.9, 1.1),
    "translate_frac": 0.015,
    "rotate_deg": 1.0,
    "shadow_p": 0.20,
    "shadow_factor": 0.6,
    "shadow_vertices": (3, 7),  # randint [lo, hi)
    "shadow_blur_frac": 0.04,
    "occluder_p": 0.15,
    "occluder_area_frac": (0.10, 0.40),
    "occluder_aspect": (0.5, 2.0),
    "occluder_noise_sigma": 6.0,
    "noise_sigma": (2.0, 6.0),
    "jpeg_quality": (10, 15),  # inclusive
    "size": 640,
}
