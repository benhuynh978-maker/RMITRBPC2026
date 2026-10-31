"""
Bộ dò + giải pose dùng trong stress test.

- "A_mac_dinh": gọi THẲNG calibrate_aruco.detect_and_solve_pnp(path, ...) (file JPEG tạm trong
  stress_test/tmp/, xoá ngay sau khi đọc) - đúng logic production của exp02.
- "B_subpix", "C_subpix_ippe": tái hiện cùng logic nhưng bật cornerRefinementMethod=SUBPIX
  (và với C: solvePnP flag SOLVEPNP_IPPE_SQUARE). Chỉ là ĐỀ XUẤT để đo, không sửa code dùng chung.
- "A_local": bản sao 1-1 logic của A trong bộ nhớ (dùng để kiểm tra tương đương + lấy toạ độ góc).
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import cv2
import cv2.aruco as aruco
import numpy as np

STRESS_DIR = Path(__file__).resolve().parent
EXP02_DIR = STRESS_DIR.parent
if str(EXP02_DIR) not in sys.path:
    sys.path.insert(0, str(EXP02_DIR))

import calibrate_aruco  # noqa: E402
import camera_model  # noqa: E402
import config  # noqa: E402

TMP_DIR = STRESS_DIR / "tmp"
VARIANTS = ("A_mac_dinh", "B_subpix", "C_subpix_ippe")

_DICT = aruco.getPredefinedDictionary(config.ARUCO_DICT)


def _make_detector(subpix: bool) -> aruco.ArucoDetector:
    p = aruco.DetectorParameters()
    if subpix:
        p.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
    return aruco.ArucoDetector(_DICT, p)


_DET_DEFAULT = _make_detector(False)
_DET_SUBPIX = _make_detector(True)


def detect_official(jpeg: bytes, marker_size_mm: float = config.MARKER_SIZE_MM) -> dict:
    """Ghi JPEG tạm -> calibrate_aruco.detect_and_solve_pnp -> xoá file."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    path = TMP_DIR / f"img_{os.getpid()}_{uuid.uuid4().hex[:8]}.jpg"
    path.write_bytes(jpeg)
    try:
        res = calibrate_aruco.detect_and_solve_pnp(path, config.MARKER_ID, marker_size_mm, legacy=True)
    except RuntimeError as exc:
        return {"ok": False, "msg": str(exc)}
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    res["ok"] = True
    res["msg"] = ""
    return res


def detect_local(img_bgr: np.ndarray, variant: str, marker_size_mm: float = config.MARKER_SIZE_MM) -> dict:
    """Tái hiện logic detect_and_solve_pnp, đổi detector/flag theo biến thể."""
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    K = camera_model.build_camera_matrix(w, h, config.DIAGONAL_FOV_DEG)
    dist = np.zeros((5, 1), dtype=np.float64)
    det = _DET_DEFAULT if variant == "A_local" else _DET_SUBPIX
    corners, ids, _ = det.detectMarkers(gray)
    if ids is None or len(ids) == 0:
        return {"ok": False, "msg": "no_marker"}
    ids_flat = ids.flatten().tolist()
    if config.MARKER_ID not in ids_flat:
        return {"ok": False, "msg": f"wrong_ids={ids_flat}"}
    img_pts = corners[ids_flat.index(config.MARKER_ID)].reshape(4, 2).astype(np.float64)
    obj = camera_model.get_marker_object_points(marker_size_mm / 1000.0)
    flag = cv2.SOLVEPNP_IPPE_SQUARE if variant == "C_subpix_ippe" else cv2.SOLVEPNP_ITERATIVE
    ok, rvec, tvec = cv2.solvePnP(obj, img_pts, K, dist, flags=flag)
    if not ok:
        return {"ok": False, "msg": "solvepnp_fail"}
    R, _ = cv2.Rodrigues(rvec)
    proj, _ = cv2.projectPoints(obj, rvec, tvec, K, dist)
    rep = float(np.sqrt(np.mean(np.sum((proj.reshape(4, 2) - img_pts) ** 2, axis=1))))
    return {"ok": True, "msg": "", "R": R, "t": tvec.reshape(3), "reproj_error_rms_px": rep,
            "corners": img_pts}


def detected_corners_default(img_bgr: np.ndarray) -> np.ndarray | None:
    """Góc detect với tham số mặc định (giống hàm chính thức) - chỉ để đo cạnh trên ảnh."""
    r = detect_local(img_bgr, "A_local")
    return r.get("corners") if r["ok"] else None
