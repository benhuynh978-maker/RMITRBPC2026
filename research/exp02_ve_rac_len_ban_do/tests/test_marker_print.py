"""
Test trang in bảng ArUco A3 (outputs/marker_A3.png / .pdf) - CPU, nhanh.

Chạy: python tests/test_marker_print.py   (từ thư mục exp02_ve_rac_len_ban_do)
Nếu chưa có file in thì tự gọi generate_marker.generate_a3() (chỉ ghi vào outputs/).
Các ca --size-mm (500, 1000 mm...) CHỈ sinh vào thư mục tạm của hệ điều hành, KHÔNG ghi vào outputs/.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import cv2.aruco as aruco  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import config  # noqa: E402
import generate_marker  # noqa: E402

PASS = 0
FAIL = 0

DPI = 300
MM_PER_PX = 25.4 / DPI
PNG = config.OUTPUTS_DIR / "marker_A3.png"
PDF = config.OUTPUTS_DIR / "marker_A3.pdf"


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[OK]   {name}" + (f" ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name} - {detail}")


def ensure_files():
    if not (PNG.exists() and PDF.exists()):
        generate_marker.generate_a3()


def detect_marker(gray):
    dictionary = aruco.getPredefinedDictionary(config.ARUCO_DICT)
    detector = aruco.ArucoDetector(dictionary, aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)
    return corners, ids


def test_png_size_and_dpi():
    with Image.open(PNG) as im:
        w_mm, h_mm = config.PRINT_PAPER_MM
        exp_w = round(w_mm / 25.4 * DPI)
        exp_h = round(h_mm / 25.4 * DPI)
        check("PNG đúng kích thước A3@300dpi", im.size == (exp_w, exp_h), f"{im.size} vs ({exp_w}, {exp_h})")
        dpi = im.info.get("dpi", (0, 0))
        check("PNG metadata DPI = 300", all(abs(d - DPI) < 0.5 for d in dpi), f"{dpi}")


def test_marker_detected_and_size():
    gray = cv2.imread(str(PNG), cv2.IMREAD_GRAYSCALE)
    corners, ids = detect_marker(gray)
    found = ids is not None and 0 in ids.flatten().tolist()
    check("Phát hiện được marker id 0 trong marker_A3.png", found, f"ids={None if ids is None else ids.flatten().tolist()}")
    if not found:
        return None
    c = corners[ids.flatten().tolist().index(0)].reshape(4, 2)
    sides = [float(np.linalg.norm(c[i] - c[(i + 1) % 4])) for i in range(4)]
    side_mm = float(np.mean(sides)) * MM_PER_PX
    check(
        f"Cạnh vùng mã phát hiện = {config.PRINT_MARKER_SIZE_MM:.0f} ± 0.5 mm",
        abs(side_mm - config.PRINT_MARKER_SIZE_MM) <= 0.5,
        f"{side_mm:.2f} mm (4 cạnh px: {[round(s, 1) for s in sides]})",
    )
    return c


def test_pdf_mediabox():
    data = PDF.read_bytes()
    m = re.search(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]", data)
    check("PDF có /MediaBox", m is not None)
    if not m:
        return
    x0, y0, x1, y1 = (float(g) for g in m.groups())
    w_pt, h_pt = x1 - x0, y1 - y0
    exp_w = config.PRINT_PAPER_MM[0] / 25.4 * 72
    exp_h = config.PRINT_PAPER_MM[1] / 25.4 * 72
    check(
        "PDF khổ A3 (±1 pt)",
        abs(w_pt - exp_w) <= 1 and abs(h_pt - exp_h) <= 1,
        f"{w_pt:.1f} x {h_pt:.1f} pt (kỳ vọng {exp_w:.1f} x {exp_h:.1f})",
    )


def test_quiet_zone(corners):
    if corners is None:
        check("Vùng trắng quanh marker ≥ 20 mm", False, "không có marker để đo")
        return
    gray = cv2.imread(str(PNG), cv2.IMREAD_GRAYSCALE)
    h, w = gray.shape
    x_min, y_min = np.floor(corners.min(axis=0)).astype(int)
    x_max, y_max = np.ceil(corners.max(axis=0)).astype(int)
    q = int(round(20 / MM_PER_PX))
    # Lề tới mép giấy (trái/phải/trên) phải đủ 20 mm
    check(
        "Lề giấy trái/phải/trên ≥ 20 mm",
        min(x_min, w - 1 - x_max, y_min) * MM_PER_PX >= 20,
        f"trái {x_min * MM_PER_PX:.1f}, phải {(w - 1 - x_max) * MM_PER_PX:.1f}, trên {y_min * MM_PER_PX:.1f} mm",
    )
    # Dải 20 mm quanh marker (phía dưới gồm cả chữ) phải toàn trắng
    xa, xb = max(0, x_min - q), min(w, x_max + q + 1)
    ya, yb = max(0, y_min - q), min(h, y_max + q + 1)
    region = gray[ya:yb, xa:xb].copy()
    # Che chính marker (mở rộng 3 px để chừa răng cưa) rồi kiểm phần còn lại
    region[(y_min - ya - 3) : (y_max - ya + 4), (x_min - xa - 3) : (x_max - xa + 4)] = 255
    dark = int((region < 200).sum())
    check("Dải 20 mm quanh marker (4 phía) hoàn toàn trắng", dark == 0, f"{dark} pixel tối trong dải")


def _mediabox_mm(pdf_path: Path):
    data = pdf_path.read_bytes()
    m = re.search(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]", data)
    if not m:
        return None
    x0, y0, x1, y1 = (float(g) for g in m.groups())
    return (x1 - x0) / 72 * 25.4, (y1 - y0) / 72 * 25.4


def test_size_mm_cases():
    """--size-mm: tự chọn khổ giấy, tên file, cạnh đo lại bằng aruco <= 0.5 mm, MediaBox đúng, lề đủ. Chỉ ghi vào thư mục tạm."""
    # 1) Bảng mặc định qua đường tổng quát: giống HỆT outputs/marker_A3.png (bản cũ không đổi nội dung)
    with tempfile.TemporaryDirectory(prefix="exp02_marker_") as td:
        td = Path(td)
        info = generate_marker.generate(config.PRINT_MARKER_SIZE_MM, out_dir=td)
        check("250 mm -> khổ A3, tên file marker_A3.png", info["paper"] == "A3" and (td / "marker_A3.png").exists())
        if PNG.exists():
            a = cv2.imread(str(td / "marker_A3.png"), cv2.IMREAD_GRAYSCALE)
            b = cv2.imread(str(PNG), cv2.IMREAD_GRAYSCALE)
            check("250 mm: ảnh sinh lại giống hệt outputs/marker_A3.png", a.shape == b.shape and bool((a == b).all()))

        # 2) 500 mm (A0) và 1000 mm (khổ lớn/bạt, trang tuỳ chỉnh)
        for size, exp_paper, exp_name in ((500.0, "A0", "marker_A0_500mm"), (1000.0, "Custom", "marker_Custom_1000mm")):
            info = generate_marker.generate(size, out_dir=td)
            png, pdf = td / f"{exp_name}.png", td / f"{exp_name}.pdf"
            check(f"{size:g} mm -> khổ {exp_paper}, tên {exp_name}.*", info["paper"] == exp_paper and png.exists() and pdf.exists(),
                  f"{info['paper']}")
            check(f"{size:g} mm: cờ khổ lớn/bạt đúng", info["large_format"] == (exp_paper == "Custom"))
            dpi = info["dpi"]
            gray = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
            check(f"{size:g} mm: PNG đúng kích thước trang", gray.shape[::-1] == tuple(info["page_px"]), f"{gray.shape[::-1]}")
            corners, ids = detect_marker(gray)
            found = ids is not None and 0 in ids.flatten().tolist()
            check(f"{size:g} mm: dò được marker id 0", found)
            if not found:
                continue
            c = corners[ids.flatten().tolist().index(0)].reshape(4, 2)
            sides = [float(np.linalg.norm(c[i] - c[(i + 1) % 4])) for i in range(4)]
            side_mm = float(np.mean(sides)) * 25.4 / dpi
            check(f"{size:g} mm: cạnh vùng mã đo được = {size:g} ± 0.5 mm", abs(side_mm - size) <= 0.5, f"{side_mm:.3f} mm")
            check(f"{size:g} mm: module là số nguyên px, cạnh thực ghi đúng",
                  info["marker_px"] == info["module_px"] * 6 and abs(info["marker_actual_mm"] - info["marker_px"] / dpi * 25.4) < 1e-9)
            mb = _mediabox_mm(pdf)
            pw, ph = info["page_mm"]
            check(f"{size:g} mm: PDF MediaBox đúng mm khổ ({pw:.1f} x {ph:.1f})",
                  mb is not None and abs(mb[0] - pw) <= 0.3 and abs(mb[1] - ph) <= 0.3, f"{mb}")
            margin_need = max(23.0, size / 6.0)
            m_lr = min(info["margin_left_mm"], info["margin_right_mm"])
            check(f"{size:g} mm: lề trái/phải >= max(23, cạnh/6) = {margin_need:.1f} mm", m_lr >= margin_need - 0.5, f"{m_lr:.1f} mm")
            # Dải trắng quanh marker (phía trên/trái/phải, trừ phần chữ dưới) phải toàn trắng
            x_min, y_min = np.floor(c.min(axis=0)).astype(int)
            x_max, y_max = np.ceil(c.max(axis=0)).astype(int)
            q = int(round(20 / (25.4 / dpi)))
            region = gray[max(0, y_min - q): y_max + 1, max(0, x_min - q): x_max + q + 1].copy()
            region[(y_min - max(0, y_min - q) - 3):, (x_min - max(0, x_min - q) - 3):(x_max - max(0, x_min - q) + 4)] = 255
            check(f"{size:g} mm: vùng trắng >= 20 mm quanh bảng (trên/trái/phải)", int((region < 200).sum()) == 0)

    # 3) Chọn khổ (tất định): không ghi file
    expect = {100: "A4", 250: "A3", 300: "A2", 400: "A1", 500: "A0", 700: "Custom"}
    got = {s_: generate_marker.choose_paper(s_)[0] for s_ in expect}
    check("chọn khổ theo cỡ bảng", got == expect, f"{got}")
    check("đặt tên: chỉ (A3, 250 mm) giữ marker_A3",
          generate_marker.output_basename("A3", 250.0) == "marker_A3"
          and generate_marker.output_basename("A3", 200.0) == "marker_A3_200mm"
          and generate_marker.output_basename("A0", 500.0) == "marker_A0_500mm")
    try:
        generate_marker.choose_paper(0)
        check("size_mm <= 0 bị từ chối", False)
    except ValueError:
        check("size_mm <= 0 bị từ chối", True)


def main():
    ensure_files()
    test_png_size_and_dpi()
    c = test_marker_detected_and_size()
    test_pdf_mediabox()
    test_quiet_zone(c)
    test_size_mm_cases()
    print(f"\nKết quả: {PASS} pass, {FAIL} fail")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
