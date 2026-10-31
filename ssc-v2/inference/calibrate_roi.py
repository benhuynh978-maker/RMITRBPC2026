"""
De xuat ROI mieng cong (drain_roi) cho 1 camera tu 1 anh SACH; nguoi xem anh
preview roi moi quyet dinh ap dung. KHONG BAO GIO tu ap dung.

Chay (tu thu muc ssc-v2\\inference):
    ..\\..\\.venv\\Scripts\\python.exe -B calibrate_roi.py --image anh.jpg --camera CAM01
    ..\\..\\.venv\\Scripts\\python.exe -B calibrate_roi.py --image anh.jpg --camera CAM01 --polygon "0.1,0.5 0.4,0.5 0.4,0.8"
    ... them --apply de PATCH /api/cameras/<camera_id> tren backend v2.

Ket qua: calibration/<camera_id>_<ten anh>_preview.jpg va .json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

for _stream in (sys.stdout, sys.stderr):  # console Windows cp1252 khong in duoc tieng Viet
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import cv2
import numpy as np

import analysis

HERE = Path(__file__).resolve().parent
CALIBRATION_DIR = HERE / "calibration"
API_URL = os.environ.get("SSC_API_URL", "http://127.0.0.1:8010").rstrip("/")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")
MAX_POINTS = 64
EPSILON_FRACTION = 0.01
REQUEST_TIMEOUT_S = 15

EXIT_NO_DRAIN = 2
EXIT_BAD_INPUT = 3
EXIT_APPLY_FAILED = 4


def parse_polygon_arg(text: str) -> list[list[float]]:
    """'x1,y1 x2,y2 ...' -> [[x1, y1], ...] (da kiem bang validate_roi_polygon)."""
    points = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) != 2:
            raise ValueError(f"Điểm không hợp lệ {token!r}: cần dạng x,y")
        try:
            points.append([float(parts[0]), float(parts[1])])
        except ValueError as error:
            raise ValueError(f"Điểm không hợp lệ {token!r}: {error}") from None
    return analysis.validate_roi_polygon(points)


def contour_to_polygon(mask: np.ndarray, max_points: int = MAX_POINTS) -> list[list[float]] | None:
    """Vien ngoai lon nhat cua mask -> polygon chuan hoa 0..1 (<= max_points diem)."""
    height, width = mask.shape[:2]
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    epsilon = EPSILON_FRACTION * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    while len(approx) > max_points:
        epsilon *= 1.5
        approx = cv2.approxPolyDP(contour, epsilon, True)
    if len(approx) < 3:
        approx = cv2.convexHull(contour)
        if len(approx) < 3:
            return None
    pts = approx.reshape(-1, 2).astype(np.float64)
    polygon = [
        [round(min(max(x / width, 0.0), 1.0), 4), round(min(max(y / height, 0.0), 1.0), 4)]
        for x, y in pts
    ]
    try:
        return analysis.validate_roi_polygon(polygon)
    except ValueError:
        return None


def propose_from_model(image: np.ndarray) -> tuple[list[list[float]] | None, dict]:
    r = analysis.predict(image)
    info: dict = {"n_drain": 0}
    if r.masks is None or r.boxes is None or len(r.boxes) == 0:
        return None, info
    masks = r.masks.data.cpu().numpy() > analysis.MASK_THRESHOLD
    classes = r.boxes.cls.cpu().numpy().astype(int)
    confs = r.boxes.conf.cpu().numpy()
    drains = [i for i in range(len(classes)) if classes[i] == analysis.DRAIN_CLASS]
    info["n_drain"] = len(drains)
    if not drains:
        return None, info
    best = max(drains, key=lambda i: (int(masks[i].sum()), -i))
    info["drain_conf"] = round(float(confs[best]), 4)
    info["drain_mask_pct"] = round(float(masks[best].sum()) / masks[best].size * 100, 2)
    polygon = contour_to_polygon(masks[best])
    if polygon is not None:
        roi = analysis.roi_mask(polygon, *masks[best].shape)
        union = np.logical_or(roi, masks[best]).sum()
        info["iou_polygon_vs_mask"] = round(float(np.logical_and(roi, masks[best]).sum() / union), 4) if union else 0.0
    return polygon, info


def write_preview(image: np.ndarray, polygon, camera_id: str, stem: str, source: str, extra: dict) -> tuple[Path, Path, float]:
    height, width = image.shape[:2]
    area_pct = round(float(analysis.roi_mask(polygon, height, width).sum()) / (height * width) * 100, 2)
    canvas = analysis.draw_roi(image, polygon)
    label = f"{camera_id} | ROI {source} | {len(polygon)} diem | {area_pct}% anh"
    scale = max(0.5, min(height, width) / 900)
    thick = max(1, int(round(scale * 2)))
    org = (int(10 * scale), int(35 * scale))
    cv2.putText(canvas, label, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(canvas, label, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 255, 0), thick, cv2.LINE_AA)

    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    base = f"{camera_id}_{stem}"
    jpg_path = CALIBRATION_DIR / f"{base}_preview.jpg"
    json_path = CALIBRATION_DIR / f"{base}_preview.json"
    ok, buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("Không mã hóa được ảnh preview")
    jpg_path.write_bytes(buffer.tobytes())
    data = {
        "camera_id": camera_id,
        "image": stem,
        "image_size": [width, height],
        "source": source,
        "polygon": polygon,
        "n_points": len(polygon),
        "area_pct_of_image": area_pct,
        **extra,
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return jpg_path, json_path, area_pct


def apply_roi(camera_id: str, polygon, source: str) -> dict:
    import requests  # chi can khi --apply

    headers = {"Content-Type": "application/json"}
    if ADMIN_API_KEY:
        headers["X-API-Key"] = ADMIN_API_KEY
    url = f"{API_URL}/api/cameras/{quote(camera_id, safe='')}"
    response = requests.patch(
        url,
        headers=headers,
        json={"drain_roi": {"polygon": polygon, "source": source}},
        timeout=REQUEST_TIMEOUT_S,
        allow_redirects=False,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"error": response.text}
    if not response.ok:
        raise RuntimeError(f"PATCH {url} -> {response.status_code}: {data.get('error', data)}")
    return data


def _quote_arg(value: str) -> str:
    return f'"{value}"' if re.search(r"\s", value) else value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Đề xuất / áp dụng ROI miệng cống cho 1 camera.")
    parser.add_argument("--image", required=True, help="Đường dẫn ảnh JPG sạch của camera.")
    parser.add_argument("--camera", required=True, help="camera_id trên backend.")
    parser.add_argument("--polygon", help='Nhập tay: "x1,y1 x2,y2 ..." (chuẩn hóa 0..1), bỏ qua model.')
    parser.add_argument("--apply", action="store_true", help="PATCH drain_roi lên backend v2 (chỉ khi đã xem preview).")
    args = parser.parse_args(argv)

    camera_id = args.camera.strip()
    if not camera_id:
        print("Lỗi: --camera rỗng.", file=sys.stderr)
        return EXIT_BAD_INPUT
    safe_camera = re.sub(r"[^A-Za-z0-9_.-]", "_", camera_id)
    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"Lỗi: không thấy ảnh {image_path}", file=sys.stderr)
        return EXIT_BAD_INPUT
    try:
        image = analysis.decode_image(image_path.read_bytes())
    except ValueError as error:
        print(f"Lỗi: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT

    extra: dict = {}
    if args.polygon:
        source = "manual"
        try:
            polygon = parse_polygon_arg(args.polygon)
        except ValueError as error:
            print(f"Lỗi --polygon: {error}", file=sys.stderr)
            return EXIT_BAD_INPUT
    else:
        source = "ai"
        polygon, extra = propose_from_model(image)
        if polygon is None:
            print(
                "Không phát hiện được miệng cống (Drain) nào trong ảnh này "
                f"(số Drain model thấy: {extra.get('n_drain', 0)}).\n"
                "Hãy thử ảnh khác rõ hơn (ban ngày, cống sạch), hoặc nhập ROI bằng tay:\n"
                f'  --polygon "x1,y1 x2,y2 x3,y3 ..."  (tọa độ chuẩn hóa 0..1, x sang phải, y xuống dưới)',
                file=sys.stderr,
            )
            return EXIT_NO_DRAIN

    # Polygon trong preview da xem truoc (neu co) - --apply chi duoc ap dung DUNG polygon do.
    previous = None
    previous_json = CALIBRATION_DIR / f"{safe_camera}_{image_path.stem}_preview.json"
    if args.apply and previous_json.exists():
        try:
            previous = json.loads(previous_json.read_text(encoding="utf-8")).get("polygon")
        except (OSError, ValueError):
            previous = None

    preview_jpg, preview_json, area_pct = write_preview(image, polygon, safe_camera, image_path.stem, source, extra)
    polygon_text = " ".join(f"{x},{y}" for x, y in polygon)
    print(f"Camera: {camera_id} | nguồn: {source} | {len(polygon)} điểm | ROI = {area_pct}% diện tích ảnh")
    if extra:
        print(f"Thông tin model: {json.dumps(extra, ensure_ascii=False)}")
    print(f"Preview: {preview_jpg}")
    print(f"JSON:    {preview_json}")
    print(f"Polygon: {json.dumps(polygon)}")

    if not args.apply:
        command = (
            f"..\\..\\.venv\\Scripts\\python.exe -B calibrate_roi.py --image {_quote_arg(str(image_path))} "
            f"--camera {_quote_arg(camera_id)}"
        )
        if source == "manual":
            command += f' --polygon "{polygon_text}"'
        command += " --apply"
        print("\nCHƯA áp dụng. Mở ảnh preview kiểm tra viền xanh ôm đúng miệng cống, rồi chạy:")
        print(f"  {command}")
        return 0

    if previous != polygon:
        reason = ("chưa có preview nào được xem trước" if previous is None
                  else "polygon vừa tính KHÁC polygon trong preview đã xem trước đó")
        print(
            f"Không áp dụng: {reason}. Mở preview vừa ghi để kiểm tra rồi chạy lại lệnh --apply.",
            file=sys.stderr,
        )
        return EXIT_APPLY_FAILED
    try:
        outcome = apply_roi(camera_id, polygon, source)
    except Exception as error:  # noqa: BLE001 - bao loi ro rang, khong traceback
        print(f"Áp dụng thất bại: {error}", file=sys.stderr)
        return EXIT_APPLY_FAILED
    roi = outcome.get("drain_roi") if isinstance(outcome, dict) else None
    print(f"Đã áp dụng drain_roi cho {camera_id}. Backend trả version: {roi.get('calibrated_at') if isinstance(roi, dict) else '?'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
