"""
Tạo trang IN bảng ArUco để dán tại hiện trường, dùng cho hiệu chỉnh camera (calibrate_aruco.py).

MẶC ĐỊNH (quyết định 2026-10-12): trang A3 DỌC (297 x 420 mm) ở 300 dpi = 3508 x 4961 px.
  - Marker ArUco DICT_4X4_50, id=0, cạnh VÙNG MÃ (khối vuông gồm viền đen + ô đen/trắng)
    = config.PRINT_MARKER_SIZE_MM = 250 mm, đặt giữa trang theo chiều ngang.
  - Phần giấy trắng quanh marker là vùng yên tĩnh (quiet zone); KHÔNG vẽ khung đen quanh trang.
  - Dưới marker: dòng nhắc in 100%, thước chuẩn 100 mm để kiểm tra sau khi in, ô ghi số đo tay.
  - Chữ dùng font Hershey của OpenCV (không dấu, không phụ thuộc font hệ thống).

CỠ BẢNG KHÁC (--size-mm): chỉ một tham số, mặc định 250. Trang in TỰ chọn khổ giấy dọc nhỏ nhất trong
A4 / A3 / A2 / A1 / A0 đủ chứa bảng + vùng trắng quanh + phần chữ/thước/ô điền:
  - Lề trắng tối thiểu mỗi bên: 23 mm (như bản A3 250 mm hiện có, lề thực 23,5 mm); với bảng LỚN HƠN 250 mm
    thì lề = max(23 mm, cạnh bảng / 6) (bằng 1 module). Riêng bảng <= 250 mm giữ lề 23 mm: nếu áp
    cạnh/6 = 41,7 mm cho 250 mm thì bảng không vừa A3, trái với yêu cầu giữ nguyên bản A3 250 mm.
  - Lớn hơn A0 (rộng bảng + 2 lề > 841 mm, tức bảng xấp xỉ > 630 mm): sinh trang kích thước TUỲ CHỈNH đúng tỉ
    lệ vật lý (PDF MediaBox đúng mm), ghi trên trang "IN KHO LON / BAT", file tên marker_Custom_<size>mm.*
  - A4/A3 ở 300 dpi; A2 trở lên (và khổ tuỳ chỉnh) ở 150 dpi cho file đỡ nặng (module vẫn >= 400 px).
  - Chữ, nét, thước, khoảng cách phóng to theo tỉ lệ cạnh bảng / 250 mm (khi bảng > 250 mm). Thước kiểm tra
    dài 100 mm, hoặc 500 mm khi bảng >= 500 mm.
  - Tên file: outputs/marker_<khổ>_<size>mm.{png,pdf} (+ _preview.png); riêng 250 mm khổ A3 giữ nguyên tên
    marker_A3.* và nội dung bản cũ.

Về làm tròn: DICT_4X4 có lưới 6x6 module (4 ô dữ liệu + 1 viền đen mỗi bên). 250 mm ở 300 dpi =
2952.76 px, không chia hết cho 6. Mỗi module phải là SỐ NGUYÊN pixel (phóng bằng INTER_NEAREST) để
cạnh sắc, nên module = floor(2952.76 / 6) = 492 px -> vùng mã = 2952 px = 249.94 mm (lệch -0.06 mm,
nhỏ hơn 1 pixel in = 0.085 mm). Cỡ khác làm tròn xuống cùng cách (lệch tối đa < 6 px = 0,5 mm ở 300 dpi,
< 1 mm ở 150 dpi). Kích thước thực sau làm tròn được in ra khi chạy, ghi trên trang và nằm trong
build_page()["info"]. Sau khi in vẫn PHẢI đo lại bằng thước và nhập số đo đó vào --marker-size-mm.

Chạy:
    python generate_marker.py                   # A3, 250 mm -> outputs/marker_A3.{png,pdf}, marker_A3_preview.png
    python generate_marker.py --size-mm 500     # tự chọn khổ -> outputs/marker_A0_500mm.{png,pdf}
    python generate_marker.py --legacy-a4       # bản cũ -> outputs/marker_to_print.png (chỉ để tương thích)
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import cv2
import cv2.aruco as aruco
import numpy as np
from PIL import Image

import config

DPI = 300  # dpi thiết kế gốc (A4/A3); các hằng số pixel bên dưới được viết cho 300 dpi
LARGE_DPI = 150  # A2 trở lên và khổ tuỳ chỉnh
MM_PER_INCH = 25.4
MARKER_MODULES = 6  # DICT_4X4: 4 ô dữ liệu + 2 viền đen
PREVIEW_HEIGHT_PX = 800
TOP_MARGIN_MM = 30.0  # từ mép trên tờ giấy tới mép trên vùng mã (bảng 250 mm)
TEXT_GAP_MM = 25.0  # khoảng trống giữa mép dưới vùng mã và phần chữ đầu tiên (>= 20 mm quiet zone)
MIN_SIDE_MARGIN_MM = 23.0  # lề trắng tối thiểu mỗi bên (như bản A3 hiện có)
BOTTOM_MARGIN_MM = 10.0  # chừa dưới nội dung (bảng 250 mm)

# Khổ giấy chuẩn dọc (rộng, cao) mm, theo thứ tự thử từ nhỏ đến lớn
PAPERS = (
    ("A4", (210.0, 297.0)),
    ("A3", (297.0, 420.0)),
    ("A2", (420.0, 594.0)),
    ("A1", (594.0, 841.0)),
    ("A0", (841.0, 1189.0)),
)
CUSTOM = "Custom"

FONT = cv2.FONT_HERSHEY_SIMPLEX


def mm_to_px(mm: float, dpi: float = DPI) -> float:
    return mm / MM_PER_INCH * dpi


def px_to_mm(px: float, dpi: float = DPI) -> float:
    return px / dpi * MM_PER_INCH


def _text_scale_to_width(text: str, width_px: int, thickness: int) -> float:
    """Tìm fontScale lớn nhất sao cho dòng chữ vừa bề rộng width_px."""
    (w1, _), _ = cv2.getTextSize(text, FONT, 1.0, thickness)
    return width_px / w1


def _put(img, text, org, scale, thickness):
    # LINE_8 (không khử răng cưa) để trang chỉ có 2 mức đen/trắng thuần -> PDF 1-bit lossless.
    cv2.putText(img, text, org, FONT, scale, 0, thickness, cv2.LINE_8)


def _si(value: float, s: float) -> int:
    """Hằng pixel (viết cho 300 dpi, bảng 250 mm) nhân hệ số s, làm tròn nguyên."""
    return int(round(value * s))


def _draw_ruler(page, x0: int, y_top: int, length_mm: float, dpi: float, f: float, s: float):
    """
    Thước chuẩn dài length_mm (100 hoặc 500 mm): 100 bước đều nhau; vạch bước nhỏ, bước thứ 5 (vừa),
    bước thứ 10 (dài, có số). Với 100 mm mỗi bước = 1 mm (đúng bản cũ). Trả về y đáy thước (gồm số).
    """
    px_per_mm = dpi / MM_PER_INCH
    unit_mm = length_mm / 100.0
    tick_w = max(1, _si(3, s))
    baseline_y = y_top
    x_end = x0 + int(round(100 * unit_mm * px_per_mm))
    cv2.rectangle(page, (x0, baseline_y), (x_end + tick_w - 1, baseline_y + tick_w - 1), 0, -1)
    for i in range(0, 101):
        x = x0 + int(round(i * unit_mm * px_per_mm))
        if i % 10 == 0:
            length = int(round(12 * f * px_per_mm * 0.9))
        elif i % 5 == 0:
            length = int(round(8 * f * px_per_mm * 0.9))
        else:
            length = int(round(5 * f * px_per_mm * 0.9))
        cv2.rectangle(page, (x, baseline_y), (x + tick_w - 1, baseline_y + length), 0, -1)
        if i % 10 == 0:
            label = str(int(round(i * unit_mm)))
            scale = 1.7 * s
            thick = max(1, _si(4, s))
            (tw, th), _ = cv2.getTextSize(label, FONT, scale, thick)
            _put(page, label, (x + tick_w // 2 - tw // 2, baseline_y + length + th + _si(20, s)), scale, thick)
    return baseline_y + int(round(12 * f * px_per_mm * 0.9)) + _si(90, s)


def _factors(size_mm: float, dpi: float) -> tuple[float, float]:
    """(f, s): f = hệ số phóng to theo mm (>= 1), s = hệ số cho hằng pixel (f * dpi / 300)."""
    f = max(1.0, size_mm / config.PRINT_MARKER_SIZE_MM)
    return f, f * dpi / DPI


def _side_margin_mm(size_mm: float) -> float:
    if size_mm <= config.PRINT_MARKER_SIZE_MM:
        return MIN_SIDE_MARGIN_MM
    return max(MIN_SIDE_MARGIN_MM, size_mm / MARKER_MODULES)


def _compose(page, page_w: int, size_mm: float, paper: str, dpi: float, dry: bool) -> dict:
    """
    Vẽ nội dung lên page (mảng 2 mức) rộng page_w px. dry=True: chỉ tính (page là mảng giả nhỏ, OpenCV tự
    cắt phần vẽ ngoài biên) để biết nội dung cao tới đâu. Trả dict kích thước + 'content_end'.
    """
    f, s = _factors(size_mm, dpi)
    target_px = mm_to_px(size_mm, dpi)  # 250 mm @300 dpi: 2952.76
    module_px = int(math.floor(target_px / MARKER_MODULES))  # 492
    marker_px = module_px * MARKER_MODULES  # 2952
    marker_mm = px_to_mm(marker_px, dpi)  # 249.94

    x0 = (page_w - marker_px) // 2
    y0 = int(round(mm_to_px(TOP_MARGIN_MM * f, dpi)))
    if not dry:
        dictionary = aruco.getPredefinedDictionary(config.ARUCO_DICT)
        small = aruco.generateImageMarker(dictionary, config.MARKER_ID, MARKER_MODULES)  # 6x6 px, 1 px = 1 module
        marker = cv2.resize(small, (marker_px, marker_px), interpolation=cv2.INTER_NEAREST)
        page[y0 : y0 + marker_px, x0 : x0 + marker_px] = marker
    y_marker_end = y0 + marker_px

    # --- Phần chữ + thước dưới marker ---
    text_w = marker_px  # canh theo bề rộng vùng mã
    y = y_marker_end + int(round(mm_to_px(TEXT_GAP_MM * f, dpi)))
    if paper == CUSTOM:
        paper_line = "IN KHO LON / BAT, TY LE 100% (dung kich thuoc that, khong co/gian)"
    else:
        paper_line = f"IN KHO {paper}, TY LE 100% (Actual size / Khong 'Fit to page')"
    lines = [
        "BANG DANH DAU ArUco DICT_4X4_50 id=0",
        paper_line,
    ]
    thick = max(1, _si(6, s))
    # cùng 1 fontScale cho cả các dòng: lấy scale vừa dòng dài nhất
    scale = min(_text_scale_to_width(t, text_w, thick) for t in lines)
    scale = min(scale, 3.2 * s)
    for t in lines:
        (tw, th), _ = cv2.getTextSize(t, FONT, scale, thick)
        y += th
        _put(page, t, (x0, y), scale, thick)
        y += int(th * 0.7)

    # Thước chuẩn (100 mm; 500 mm cho bảng >= 500 mm)
    ruler_mm = 500 if size_mm >= 500 else 100
    y += int(mm_to_px(8 * f, dpi))
    small_scale = 1.9 * s
    cap = f"THUOC KIEM TRA: khoang 0 -> {ruler_mm} phai dung {ruler_mm} mm (dat thuoc that len de so)"
    cap_thick = max(1, _si(4, s))
    small_scale = min(small_scale, _text_scale_to_width(cap, text_w, cap_thick))
    (tw, th), _ = cv2.getTextSize(cap, FONT, small_scale, cap_thick)
    y += th
    _put(page, cap, (x0, y), small_scale, cap_thick)
    y += int(mm_to_px(8 * f, dpi))
    y = _draw_ruler(page, x0, y, ruler_mm, dpi, f, s)

    # Ô ghi số đo tay
    y += int(mm_to_px(8 * f, dpi))
    fill = "Canh vung ma do duoc = ____________ mm"
    fill_thick = max(1, _si(6, s))
    fill_scale = min(3.0 * s, _text_scale_to_width(fill, text_w, fill_thick))
    (tw, th), _ = cv2.getTextSize(fill, FONT, fill_scale, fill_thick)
    y += th
    _put(page, fill, (x0, y), fill_scale, fill_thick)
    y += int(mm_to_px(6 * f, dpi))
    note = f"(Thiet ke: {size_mm:g} mm; sau lam tron module: {marker_mm:.2f} mm)"
    note_thick = max(1, _si(3, s))
    note_scale = min(1.6 * s, _text_scale_to_width(note, text_w, note_thick))
    (tw, th), _ = cv2.getTextSize(note, FONT, note_scale, note_thick)
    y += th
    _put(page, note, (x0, y), note_scale, note_thick)

    return {
        "module_px": module_px, "marker_px": marker_px, "marker_mm": marker_mm,
        "x0": x0, "y0": y0, "content_end": y, "f": f,
    }


def choose_paper(size_mm: float) -> tuple[str, float, float, float]:
    """
    Chọn khổ giấy cho bảng size_mm. Trả (tên khổ, rộng mm, cao mm, dpi). Khổ tuỳ chỉnh: rộng/cao mm tính
    theo nội dung (cao = nội dung + lề dưới), vẫn tính bằng mm đúng tỉ lệ vật lý.
    """
    if not size_mm > 0:
        raise ValueError(f"size_mm phải > 0, nhận được: {size_mm!r}")
    margin = _side_margin_mm(size_mm)
    f, _ = _factors(size_mm, DPI)
    for name, (w_mm, h_mm) in PAPERS:
        if size_mm + 2 * margin > w_mm + 1e-9:
            continue
        dpi = DPI if name in ("A4", "A3") else LARGE_DPI
        dummy = np.zeros((8, 8), dtype=np.uint8)
        page_w = int(round(mm_to_px(w_mm, dpi)))
        page_h = int(round(mm_to_px(h_mm, dpi)))
        c = _compose(dummy, page_w, size_mm, name, dpi, dry=True)
        if c["content_end"] < page_h - int(mm_to_px(BOTTOM_MARGIN_MM * f, dpi)):
            return name, w_mm, h_mm, float(dpi)
    # Lớn hơn A0: khổ tuỳ chỉnh
    dpi = float(LARGE_DPI)
    page_w = int(round(mm_to_px(size_mm + 2 * margin, dpi)))
    dummy = np.zeros((8, 8), dtype=np.uint8)
    c = _compose(dummy, page_w, size_mm, CUSTOM, dpi, dry=True)
    page_h = c["content_end"] + int(round(mm_to_px(max(margin, BOTTOM_MARGIN_MM * f), dpi)))
    return CUSTOM, px_to_mm(page_w, dpi), px_to_mm(page_h, dpi), dpi


def build_page(size_mm: float = config.PRINT_MARKER_SIZE_MM, paper: str | None = None) -> dict:
    """
    Dựng trang in (mảng uint8 2 mức 0/255) cho bảng cạnh size_mm + thông tin kích thước thật sau làm tròn.
    paper=None: tự chọn khổ (choose_paper). Cho paper cụ thể ("A3"...) thì ép dùng khổ đó (assert nếu tràn).
    """
    name, w_mm, h_mm, dpi = choose_paper(size_mm)
    if paper is not None and paper != name:
        sizes = dict(PAPERS)
        if paper not in sizes:
            raise ValueError(f"Khổ không hợp lệ: {paper}")
        name, (w_mm, h_mm) = paper, sizes[paper]
        dpi = float(DPI if paper in ("A4", "A3") else LARGE_DPI)
    page_w = int(round(mm_to_px(w_mm, dpi)))  # A3@300: 3508
    page_h = int(round(mm_to_px(h_mm, dpi)))  # A3@300: 4961
    page = np.full((page_h, page_w), 255, dtype=np.uint8)
    c = _compose(page, page_w, size_mm, name, dpi, dry=False)
    f = c["f"]
    assert c["content_end"] < page_h - int(mm_to_px(BOTTOM_MARGIN_MM * f, dpi)), f"Nội dung tràn khỏi trang {name}"
    x0, y0, marker_px = c["x0"], c["y0"], c["marker_px"]
    info = {
        "paper": name,
        "large_format": name == CUSTOM,
        "dpi": dpi,
        "page_px": (page_w, page_h),
        "page_mm": (w_mm, h_mm),
        "module_px": c["module_px"],
        "marker_px": marker_px,
        "marker_target_mm": float(size_mm),
        "marker_actual_mm": c["marker_mm"],
        "marker_origin_px": (x0, y0),
        "margin_left_mm": px_to_mm(x0, dpi),
        "margin_right_mm": px_to_mm(page_w - x0 - marker_px, dpi),
        "margin_top_mm": px_to_mm(y0, dpi),
        "content_end_px": c["content_end"],
    }
    return {"page": page, "info": info}


def build_a3_page() -> dict:
    """Trang A3 mặc định (bảng config.PRINT_MARKER_SIZE_MM = 250 mm). Giữ để tương thích."""
    return build_page(config.PRINT_MARKER_SIZE_MM, paper="A3")


def _read_pdf_mediabox(pdf_path) -> tuple[float, float]:
    """Đọc /MediaBox thô từ file PDF (không cần thư viện thêm)."""
    import re

    data = pdf_path.read_bytes()
    m = re.search(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]", data)
    if not m:
        raise ValueError("Không tìm thấy /MediaBox trong PDF")
    x0, y0, x1, y1 = (float(g) for g in m.groups())
    return x1 - x0, y1 - y0


def output_basename(paper: str, size_mm: float) -> str:
    """marker_A3 cho (A3, 250 mm); còn lại marker_<khổ>_<size>mm."""
    if paper == "A3" and size_mm == config.PRINT_MARKER_SIZE_MM:
        return "marker_A3"
    return f"marker_{paper}_{size_mm:g}mm"


def generate(size_mm: float = config.PRINT_MARKER_SIZE_MM, out_dir=None) -> dict:
    """Sinh PNG + PDF + ảnh xem nhanh cho bảng size_mm vào out_dir (mặc định config.OUTPUTS_DIR)."""
    built = build_page(size_mm)
    page, info = built["page"], built["info"]
    dpi = info["dpi"]

    out_dir = config.OUTPUTS_DIR if out_dir is None else Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = output_basename(info["paper"], size_mm)
    png_path = out_dir / f"{base}.png"
    pdf_path = out_dir / f"{base}.pdf"
    prev_path = out_dir / f"{base}_preview.png"

    # Ảnh khổ lớn có thể vượt giới hạn "decompression bomb" của Pillow khi người khác mở lại -> không ảnh hưởng ghi.
    pil = Image.fromarray(page, mode="L")
    pil.save(png_path, "PNG", dpi=(dpi, dpi))
    # PDF: ảnh 1-bit (lossless, nhỏ); mode L sẽ bị Pillow nén JPEG làm mờ cạnh. Ngưỡng cứng, không dither.
    pil.point(lambda v: 255 if v >= 128 else 0).convert("1", dither=Image.Dither.NONE).save(
        pdf_path, "PDF", resolution=float(dpi)
    )

    scale = PREVIEW_HEIGHT_PX / page.shape[0]
    prev = cv2.resize(page, (int(round(page.shape[1] * scale)), PREVIEW_HEIGHT_PX), interpolation=cv2.INTER_AREA)
    Image.fromarray(prev, mode="L").save(prev_path, "PNG")

    mb_w, mb_h = _read_pdf_mediabox(pdf_path)
    info["png_path"], info["pdf_path"], info["preview_path"] = png_path, pdf_path, prev_path
    info["pdf_mediabox_pt"] = (mb_w, mb_h)

    pw_mm, ph_mm = info["page_mm"]
    print(f"Đã tạo trang in {info['paper']}: {png_path}")
    print(f"           PDF : {pdf_path}  (MediaBox {mb_w:.1f} x {mb_h:.1f} pt = {mb_w / 72 * MM_PER_INCH:.1f} x "
          f"{mb_h / 72 * MM_PER_INCH:.1f} mm; trang {pw_mm:.1f} x {ph_mm:.1f} mm)")
    print(f"           Xem nhanh: {prev_path}")
    if info["large_format"]:
        print("- KHỔ LỚN / BẠT: vượt A0, trang tuỳ chỉnh đúng tỉ lệ vật lý - gửi PDF cho nơi in bạt, in 100%.")
    print(f"- Dict: DICT_4X4_50, id={config.MARKER_ID}; ảnh {info['page_px'][0]}x{info['page_px'][1]} px @ {dpi:g} dpi")
    print(
        f"- Vùng mã: module {info['module_px']} px x {MARKER_MODULES} = {info['marker_px']} px "
        f"= {info['marker_actual_mm']:.2f} mm (mục tiêu {info['marker_target_mm']:g} mm, "
        f"lệch {info['marker_actual_mm'] - info['marker_target_mm']:+.2f} mm)"
    )
    print(f"- Lề trắng: trái {info['margin_left_mm']:.1f} mm, phải {info['margin_right_mm']:.1f} mm, trên {info['margin_top_mm']:.1f} mm")
    print("- IN: chọn 'Kích thước thật / 100% / Actual size', TẮT 'Fit to page'. Sau khi in, đo cạnh vùng mã bằng thước "
          "rồi nhập số đo đó vào --marker-size-mm khi hiệu chỉnh.")
    print("- Xem docs/HUONG_DAN_IN_BANG.md")
    return info


def generate_a3(out_dir=None) -> dict:
    """Bản A3 mặc định (250 mm) -> outputs/marker_A3.*. Giữ để tương thích."""
    return generate(config.PRINT_MARKER_SIZE_MM, out_dir=out_dir)


def generate_legacy_a4():
    """Bản cũ (tương thích): outputs/marker_to_print.png, cạnh mã config.MARKER_SIZE_MM (200 mm)."""
    dictionary = aruco.getPredefinedDictionary(config.ARUCO_DICT)

    marker_px = 600
    marker_img = aruco.generateImageMarker(dictionary, config.MARKER_ID, marker_px)
    marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

    margin = 100
    canvas = cv2.copyMakeBorder(
        marker_bgr, margin, margin, margin, margin, cv2.BORDER_CONSTANT, value=(255, 255, 255)
    )
    cv2.rectangle(canvas, (2, 2), (canvas.shape[1] - 3, canvas.shape[0] - 3), (0, 0, 0), 2)

    text_h = 90
    final = cv2.copyMakeBorder(canvas, 0, text_h, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))

    size_mm = config.MARKER_SIZE_MM
    line1 = f"In dung {size_mm:.0f} x {size_mm:.0f} mm - do lai bang thuoc sau khi in"
    line2 = f"ArUco DICT_4X4_50, id={config.MARKER_ID} - vung ma (khong tinh khung trang) phai dung kich thuoc tren"

    y0 = canvas.shape[0] + 32
    cv2.putText(final, line1, (20, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(final, line2, (20, y0 + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.OUTPUTS_DIR / "marker_to_print.png"
    cv2.imwrite(str(out_path), final)

    print(f"[legacy] Đã tạo ảnh marker in được: {out_path}")
    print(f"- Dict: DICT_4X4_50, id={config.MARKER_ID}")
    print(f"- Kích thước THẬT cần in (vùng mã, không tính khung trắng): {size_mm:.0f} x {size_mm:.0f} mm")
    print("- LƯU Ý: bản cũ KHÔNG khớp khổ giấy cụ thể (cả tờ ~267 mm, không vừa A4). Dùng A3 mặc định thay thế.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Tạo trang in bảng ArUco (mặc định A3, vùng mã 250 mm; --size-mm để đổi cỡ, tự chọn khổ giấy)."
    )
    ap.add_argument("--size-mm", type=float, default=config.PRINT_MARKER_SIZE_MM,
                    help=f"Cạnh vùng mã cần in (mm), mặc định {config.PRINT_MARKER_SIZE_MM:g}. Tự chọn khổ giấy "
                         f"A4..A0, lớn hơn A0 thì sinh trang khổ lớn/bạt đúng tỉ lệ")
    ap.add_argument("--legacy-a4", action="store_true", help="Tạo ảnh cũ outputs/marker_to_print.png (chỉ để tương thích)")
    args = ap.parse_args(argv)
    if args.legacy_a4:
        generate_legacy_a4()
    else:
        generate(args.size_mm)


if __name__ == "__main__":
    main()
