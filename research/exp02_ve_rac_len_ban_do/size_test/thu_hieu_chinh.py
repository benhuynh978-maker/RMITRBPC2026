"""
size_test/thu_hieu_chinh.py — (PHỤ, chẩn đoán) So sánh cách hiệu chỉnh của code dùng chung
(calibrate_aruco.detect_and_solve_pnp: không tinh chỉnh góc, solvePnP ITERATIVE) với 2 biến thể
tự viết TRONG size_test (KHÔNG sửa code dùng chung), trên đúng ảnh marker của 10 biến thể pose:

  M0  code dùng chung                          (góc marker thô, SOLVEPNP_ITERATIVE)
  M1  góc marker CORNER_REFINE_SUBPIX          + SOLVEPNP_ITERATIVE
  M2  góc marker CORNER_REFINE_SUBPIX          + SOLVEPNP_IPPE_SQUARE (solvePnPGeneric, lấy nghiệm
      reprojection nhỏ nhất; in thêm tỉ số reprojection nghiệm 2/nghiệm 1 để thấy độ nhập nhằng)

Mục đích: tìm nguyên nhân sai số hiệu chỉnh (~2° ở ảnh sạch) và các ca "lật pose" ~80° ở JPEG q12.
Kết quả: size_test/ketqua/thu_hieu_chinh.md
"""
from __future__ import annotations

import sys

import scene  # noqa: E402

import cv2  # noqa: E402
import cv2.aruco as aruco  # noqa: E402
import numpy as np  # noqa: E402

import calibrate_aruco  # noqa: E402
import camera_model  # noqa: E402
import config  # noqa: E402
from measure import JPEG_QUALITIES, rotation_angle_deg  # noqa: E402


def detect_corners(gray: np.ndarray, subpix: bool):
    params = aruco.DetectorParameters()
    if subpix:
        params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
    det = aruco.ArucoDetector(aruco.getPredefinedDictionary(config.ARUCO_DICT), params)
    corners, ids, _ = det.detectMarkers(gray)
    if ids is None or config.MARKER_ID not in ids.flatten().tolist():
        return None
    return corners[ids.flatten().tolist().index(config.MARKER_ID)].reshape(4, 2).astype(np.float64)


def solve(img_pts: np.ndarray, method: str):
    obj = camera_model.get_marker_object_points(config.MARKER_SIZE_MM / 1000.0)
    K = scene.CAMERA_MATRIX
    dist = np.zeros((5, 1))
    if method == "iterative":
        ok, rvec, tvec = cv2.solvePnP(obj, img_pts, K, dist)
        R, _ = cv2.Rodrigues(rvec)
        return R, tvec.reshape(3), float("nan")
    n, rvecs, tvecs, errs = cv2.solvePnPGeneric(obj, img_pts, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)
    errs = np.array(errs).reshape(-1)
    best = int(np.argmin(errs))
    R, _ = cv2.Rodrigues(rvecs[best])
    ratio = float(errs.max() / max(errs.min(), 1e-12)) if n > 1 else float("inf")
    return R, tvecs[best].reshape(3), ratio


def main():
    lines = ["| Pose | Ảnh | M0 dùng chung: vị trí m / góc ° | M1 subpix+ITERATIVE: vị trí m / góc ° | "
             "M2 subpix+IPPE_SQUARE: vị trí m / góc ° | M2 tỉ số reproj nghiệm2/nghiệm1 |",
             "|---|---|---|---|---|---|"]
    stats = {k: [] for k in ("M0", "M1", "M2")}
    for fam in scene.POSE_FAMILIES:
        for vi in range(len(scene.POSE_VARIANTS)):
            pose = scene.make_pose(fam, vi)
            img, _ = scene.render_scene(pose, [])
            scene.TMP_DIR.mkdir(parents=True, exist_ok=True)
            paths = {"png": scene.TMP_DIR / "hc.png"}
            cv2.imwrite(str(paths["png"]), img)
            for key, q in JPEG_QUALITIES.items():
                paths[key] = scene.TMP_DIR / f"hc_{key}.jpg"
                cv2.imwrite(str(paths[key]), img, [cv2.IMWRITE_JPEG_QUALITY, q])
            for src, p in paths.items():
                cells = []
                res = calibrate_aruco.detect_and_solve_pnp(p, config.MARKER_ID, config.MARKER_SIZE_MM, legacy=True)
                variants = [("M0", res["R"], res["t"], None)]
                gray = cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2GRAY)
                c = detect_corners(gray, subpix=True)
                R1, t1, _ = solve(c, "iterative")
                R2, t2, ratio = solve(c, "ippe")
                variants += [("M1", R1, t1, None), ("M2", R2, t2, ratio)]
                for name, R, t, _r in variants:
                    C = -R.T @ t
                    pe = float(np.linalg.norm(C - pose.cam_center))
                    ae = rotation_angle_deg(R, pose.R)
                    stats[name].append((src, pe, ae))
                    cells.append(f"{pe:.3f} / {ae:.2f}")
                lines.append(f"| {pose.label} | {src} | " + " | ".join(cells) + f" | {ratio:.1f} |")
    lines.append("")
    lines.append("Tổng hợp (TB / max sai số vị trí camera m; TB / max sai số góc °):\n")
    lines.append("| Cách | png | q25 | q12 |")
    lines.append("|---|---|---|---|")
    for name, vals in stats.items():
        cells = []
        for src in ("png", "q25", "q12"):
            pe = np.array([v[1] for v in vals if v[0] == src])
            ae = np.array([v[2] for v in vals if v[0] == src])
            cells.append(f"{pe.mean():.3f}/{pe.max():.3f} m; {ae.mean():.2f}/{ae.max():.2f}°")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    md = "\n".join(lines)
    (scene.RESULTS_DIR / "thu_hieu_chinh.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    sys.exit(main())
