"""
Sinh dữ liệu "ảnh mẫu tính sẵn" cho trang Try the AI của website cleansight-site-v2.

Việc script làm (chạy MỘT LẦN trên máy có model, không chạy khi build website):
  1. Đọc 3 ảnh mẫu của đội, thu nhỏ về tối đa 1280 px chiều rộng, mã hoá lại JPEG
     (việc mã hoá lại bỏ toàn bộ EXIF, kể cả GPS nếu có).
  2. Chạy analyze() của ssc-v2/inference (model baseline_v1_rev2, công thức legacy, KHÔNG có ROI)
     ĐÚNG trên các byte của ảnh đã thu nhỏ, để ảnh khoanh khớp từng điểm ảnh với ảnh gốc hiển thị.
  3. Ghi ảnh gốc, ảnh khoanh, ảnh thu nhỏ vào cleansight-site-v2/public/img/samples/
     và kết quả vào cleansight-site-v2/src/data/samples.json.

Mọi con số trên trang đều lấy từ samples.json, không nhập tay.

Chạy (từ thư mục gốc repo):
  .venv/bin/python -B research/cleansight_samples/make_samples.py \
      --litter cleansight-site-v2/public/img/hero.jpg --clean <ảnh sạch> --drain <ảnh có cống>

Ảnh mẫu phải là ảnh của đội, không có người, biển số xe hay logo.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "cleansight-site-v2"
OUT_DIR = SITE / "public" / "img" / "samples"
OUT_JSON = SITE / "src" / "data" / "samples.json"

MAX_WIDTH = 1280
THUMB_WIDTH = 400
ORIGINAL_QUALITY = 85
THUMB_QUALITY = 80

# Ngưỡng nhãn mức rác (khớp POLICY.waste của backend: 1/5/10/20 % = low/medium/high/critical).
WASTE_THRESHOLDS = (1.0, 5.0, 10.0, 20.0)
MODEL_NAME = "baseline_v1_rev2"

sys.path.insert(0, str(ROOT / "ssc-v2" / "inference"))


def level_index(pct: float) -> int:
    """-1 = dưới ngưỡng Low (< 1 %); 0..3 = Low, Medium, High, Severe."""
    index = -1
    for i, threshold in enumerate(WASTE_THRESHOLDS):
        if pct >= threshold:
            index = i
    return index


def resize_to_width(image, width: int):
    h, w = image.shape[:2]
    if w <= width:
        return image
    return cv2.resize(image, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)


def encode(image, quality: int) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Không mã hoá được JPEG")
    return buf.tobytes()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--litter", required=True, type=Path, help="ảnh có rác")
    parser.add_argument("--clean", required=True, type=Path, help="ảnh gần như sạch")
    parser.add_argument("--drain", required=True, type=Path, help="ảnh có miệng cống")
    args = parser.parse_args()

    import analysis  # noqa: E402 - cần sys.path ở trên; nạp torch/ultralytics nên import muộn

    sources = [("litter", args.litter), ("clean", args.clean), ("drain", args.drain)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    samples = []
    for sample_id, path in sources:
        image = cv2.imread(str(path))
        if image is None:
            print(f"Không đọc được ảnh: {path}", file=sys.stderr)
            return 1
        image = resize_to_width(image, MAX_WIDTH)
        height, width = image.shape[:2]
        original_bytes = encode(image, ORIGINAL_QUALITY)

        result = analysis.analyze(original_bytes)
        if not result.get("usable"):
            print(f"{sample_id}: ảnh không dùng được ({result.get('quality_reason')})", file=sys.stderr)
            return 1

        waste = float(result["waste_coverage_pct"])
        drain = result.get("drain_blockage_pct")  # vắng khi model không thấy cống
        thumb = encode(resize_to_width(image, THUMB_WIDTH), THUMB_QUALITY)

        (OUT_DIR / f"{sample_id}.jpg").write_bytes(original_bytes)
        (OUT_DIR / f"{sample_id}-annotated.jpg").write_bytes(result["analyzed_bytes"])
        (OUT_DIR / f"{sample_id}-thumb.jpg").write_bytes(thumb)

        samples.append(
            {
                "id": sample_id,
                "width": width,
                "height": height,
                "wastePct": round(waste, 2),
                "levelIndex": level_index(waste),
                "drainPct": None if drain is None else round(float(drain), 2),
            }
        )
        print(f"{sample_id}: {width}x{height}  rác {waste:.2f}%  mức {level_index(waste)}  cống {drain}")

    payload = {
        "_comment": "Sinh bởi research/cleansight_samples/make_samples.py. Không sửa tay.",
        "model": MODEL_NAME,
        "method": "legacy (no drain zone)",
        "generated": date.today().isoformat(),
        "samples": samples,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
