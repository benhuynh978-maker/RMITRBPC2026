"""
Xử lý ảnh dùng chung cho webtest/server.py (calibrate và observe dùng CÙNG một đường tiền xử lý):

  decode_upload(raw) : giải mã bằng PIL (chỉ JPEG/PNG, kiểm bằng giải mã thật, không tin tên file), ĐỌC FOV từ EXIF
                       (FocalLengthIn35mmFilm) TRƯỚC khi xoay, áp EXIF orientation, đổi RGB, nếu cạnh dài > 2048 px
                       thì thu nhỏ giữ tỉ lệ (INTER_AREA). Trả (ảnh BGR uint8, f35_mm | None).
  diagonal_fov_from_35mm(f) : FOV chéo (độ) = 2*atan(43.267 / (2 f)), 43.267 mm = đường chéo phim 35 mm.
  draw_overlay(...)  : vẽ viền bảng (xanh lá), trục +Y (xanh dương, "+Y"), +X (đỏ, "+X") bằng cv2.projectPoints.
  encode_jpg_b64(...): JPEG -> base64 (không prefix), thu nhỏ cạnh dài <= max_side nếu cần.
"""
from __future__ import annotations

import base64
import io
import math
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

import camera_model

MAX_SIDE_PX = 2048          # cạnh dài tối đa sau tiền xử lý
OVERLAY_MAX_SIDE_PX = 1000  # cạnh dài tối đa của ảnh trả về cho trình duyệt
FULL_FRAME_DIAG_MM = 43.267
MAX_PIXELS = 120_000_000    # chặn ảnh khổng lồ (decompression bomb) trước khi giải mã
_EXIF_IFD = 0x8769
_TAG_F35 = 0xA405           # FocalLengthIn35mmFilm


class ImageError(ValueError):
    """Ảnh tải lên không dùng được; str(exc) là thông báo tiếng Anh trả cho người dùng."""


def diagonal_fov_from_35mm(f35_mm: float) -> float:
    """FOV chéo (độ) từ tiêu cự tương đương phim 35 mm."""
    if not f35_mm > 0:
        raise ValueError(f"Focal length must be > 0, got {f35_mm!r}")
    return math.degrees(2.0 * math.atan(FULL_FRAME_DIAG_MM / (2.0 * float(f35_mm))))


def _read_f35(im: Image.Image) -> Optional[float]:
    try:
        exif = im.getexif()
        value = None
        try:
            value = exif.get_ifd(_EXIF_IFD).get(_TAG_F35)
        except Exception:
            value = None
        if value is None:
            value = exif.get(_TAG_F35)
        if value is None:
            return None
        f = float(value)
        return f if 5.0 <= f <= 500.0 else None  # ngoài khoảng này coi như EXIF rác
    except Exception:
        return None


def decode_upload(raw: bytes) -> Tuple[np.ndarray, Optional[float]]:
    try:
        im = Image.open(io.BytesIO(raw))
        fmt = im.format
        size = im.size
    except Exception:
        raise ImageError("The uploaded file is not a valid image. Only JPEG or PNG is accepted.") from None
    if fmt not in ("JPEG", "PNG"):
        raise ImageError("Only JPEG or PNG images are accepted.")
    if size[0] * size[1] > MAX_PIXELS:
        raise ImageError("The image resolution is too large.")
    try:
        im.load()
    except Exception:
        raise ImageError("The image is corrupt and cannot be decoded.") from None

    f35 = _read_f35(im)  # đọc EXIF trước khi xoay/thu nhỏ
    try:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
    except Exception:
        raise ImageError("The image is corrupt and cannot be processed.") from None

    bgr = cv2.cvtColor(np.asarray(im, dtype=np.uint8), cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    if w < 2 or h < 2:
        raise ImageError("The image is too small.")
    longest = max(w, h)
    if longest > MAX_SIDE_PX:
        s = MAX_SIDE_PX / longest
        bgr = cv2.resize(bgr, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(bgr), f35


def _shrink(bgr: np.ndarray, max_side: int) -> Tuple[np.ndarray, float]:
    h, w = bgr.shape[:2]
    longest = max(w, h)
    if longest <= max_side:
        return bgr, 1.0
    s = max_side / longest
    return cv2.resize(bgr, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA), s


def encode_jpg_b64(bgr: np.ndarray, max_side: Optional[int] = None, quality: int = 85) -> str:
    if max_side:
        bgr, _ = _shrink(bgr, max_side)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        raise RuntimeError("Could not encode the JPEG image")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def draw_overlay(
    bgr: np.ndarray,
    rvec_R: np.ndarray,
    t: np.ndarray,
    camera_matrix: np.ndarray,
    marker_size_m: float,
    max_side: int = OVERLAY_MAX_SIDE_PX,
) -> np.ndarray:
    """
    Ảnh đã tiền xử lý (thu nhỏ cạnh dài <= max_side) + viền bảng (xanh lá), mũi tên +Y (xanh dương) và +X (đỏ).
    Chiếu bằng cv2.projectPoints trên ảnh GỐC (R, t, K đã giải) rồi nhân hệ số thu nhỏ vào toạ độ pixel.
    """
    small, s = _shrink(bgr, max_side)
    out = small.copy()
    rvec, _ = cv2.Rodrigues(np.asarray(rvec_R, dtype=np.float64))
    tvec = np.asarray(t, dtype=np.float64).reshape(3, 1)
    K = np.asarray(camera_matrix, dtype=np.float64)
    dist = np.zeros((5, 1))

    corners = camera_model.get_marker_object_points(marker_size_m)
    arrow_len = marker_size_m * 0.8
    axes = np.array([[0, 0, 0], [0, arrow_len, 0], [arrow_len, 0, 0]], dtype=np.float64)
    pc, _ = cv2.projectPoints(corners, rvec, tvec, K, dist)
    pa, _ = cv2.projectPoints(axes, rvec, tvec, K, dist)
    pc = pc.reshape(-1, 2) * s
    pa = pa.reshape(-1, 2) * s

    th = max(2, int(round(max(out.shape[:2]) / 400)))
    font_scale = max(0.6, max(out.shape[:2]) / 900.0)
    cv2.polylines(out, [np.round(pc).astype(np.int32).reshape(-1, 1, 2)], True, (0, 220, 0), th, cv2.LINE_AA)
    o = tuple(int(v) for v in np.round(pa[0]))
    ty = tuple(int(v) for v in np.round(pa[1]))
    tx = tuple(int(v) for v in np.round(pa[2]))
    cv2.arrowedLine(out, o, ty, (255, 0, 0), th + 1, cv2.LINE_AA, tipLength=0.2)   # +Y: xanh dương (BGR)
    cv2.arrowedLine(out, o, tx, (0, 0, 255), th + 1, cv2.LINE_AA, tipLength=0.2)   # +X: đỏ
    cv2.putText(out, "+Y", (ty[0] + 6, ty[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 0, 0), th, cv2.LINE_AA)
    cv2.putText(out, "+X", (tx[0] + 6, tx[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 255), th, cv2.LINE_AA)
    return out
