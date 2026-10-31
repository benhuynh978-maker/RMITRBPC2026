"""
Test cho doc_so_lieu.py: script phải đọc lại ĐÚNG vị trí và diện tích mà máy chủ đã chiếu lên bản đồ.

  1) Khứ hồi: dựng vùng rác ở vị trí biết trước trong hệ bảng -> chiếu sang lat/lon bằng CHÍNH hàm của hệ thống
     (project_mask.marker_xy_to_enu + meters_to_latlon) -> script đổi ngược -> phải ra đúng vị trí/diện tích.
  2) Khớp máy chủ: cho máy chủ tự tạo vùng rác từ một mặt nạ (mask_to_region_features) -> diện tích script tính
     phải khớp area_m2 máy chủ ghi.
Chạy: ..\\..\\..\\.venv\\Scripts\\python.exe -B test_doc_so_lieu.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import project_mask as pm  # noqa: E402
import doc_so_lieu as ds  # noqa: E402

fails = 0


def check(name, ok, info=""):
    global fails
    print(("[OK]   " if ok else "[FAIL] ") + name + (f"  {info}" if info else ""))
    if not ok:
        fails += 1


LAT0, LON0 = 10.7769, 106.7009


def to_lonlat(x, y, az):
    e, n = pm.marker_xy_to_enu(x, y, az)
    lat, lon = pm.meters_to_latlon(LAT0, LON0, e, n)
    return [lon, lat]


# 1) Khứ hồi với nhiều hướng mũi tên, có lỗ
for az in (0.0, 37.0, 90.0, 200.0, 315.5):
    cy, cx, s = 1.0, 0.5, 0.3   # tâm (Y=1.0, X=0.5), vuông 0,3 m, lỗ vuông 0,1 m ở giữa
    outer = [(cx - s / 2, cy - s / 2), (cx + s / 2, cy - s / 2), (cx + s / 2, cy + s / 2), (cx - s / 2, cy + s / 2)]
    hole = [(cx - 0.05, cy - 0.05), (cx - 0.05, cy + 0.05), (cx + 0.05, cy + 0.05), (cx + 0.05, cy - 0.05)]
    rings = [[to_lonlat(x, y, az) for x, y in r + [r[0]]] for r in (outer, hole)]
    obs = [{"id": "a", "captured_at": "t", "n_instances": 1, "total_area_m2": 0.08,
            "regions": {"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"area_m2": 0.08}, "geometry": {"type": "Polygon", "coordinates": rings}}]}}]
    calib = {"marker_latlon": [LAT0, LON0], "azimuth_deg": az, "created_at": "c"}
    r = ds.analyse(obs, calib)[0]
    check(f"khứ hồi hướng {az}°: tâm Y=1,0 X=0,5", abs(r["y"] - 1.0) < 1e-4 and abs(r["x"] - 0.5) < 1e-4,
          f"Y={r['y']:.6f} X={r['x']:.6f}")
    check(f"khứ hồi hướng {az}°: diện tích 0,08 m² (đã trừ lỗ)", abs(r["area"] - 0.08) < 1e-5, f"{r['area']:.6f}")

# 1b) Hai vùng -> có dòng "gộp" đúng tâm khối
two = []
for (x, y) in ((0.0, 1.0), (0.4, 1.0)):
    sq = [(x - 0.1, y - 0.1), (x + 0.1, y - 0.1), (x + 0.1, y + 0.1), (x - 0.1, y + 0.1), (x - 0.1, y - 0.1)]
    two.append({"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[to_lonlat(a, b, 0) for a, b in sq]]}})
rows = ds.analyse([{"id": "b", "regions": {"type": "FeatureCollection", "features": two}}],
                  {"marker_latlon": [LAT0, LON0], "azimuth_deg": 0})
g = [r for r in rows if r["vung"] == "gộp"]
check("hai vùng -> dòng gộp ở X=0,2 Y=1,0", len(g) == 1 and abs(g[0]["x"] - 0.2) < 1e-4 and abs(g[0]["y"] - 1.0) < 1e-4)

# 1c) Ảnh không có rác, và cảnh báo sai hiệu chỉnh
rows = ds.analyse([{"id": "c", "calibration_created_at": "khac", "regions": {"type": "FeatureCollection", "features": []}}],
                  {"marker_latlon": [LAT0, LON0], "azimuth_deg": 0, "created_at": "dung"})
check("ảnh không có vùng -> một dòng 'Vùng = -'", len(rows) == 1 and rows[0]["vung"] == "-")
check("hiệu chỉnh khác -> calib_khop = False", rows[0]["calib_khop"] is False)

# 2) Khớp diện tích máy chủ (máy chủ tự chiếu một mặt nạ chữ nhật)
import server  # noqa: E402

calib_path = HERE.parent / "calibration" / "DEMO-CAM.json"
calib = json.loads(calib_path.read_text(encoding="utf-8"))
calib.setdefault("azimuth_deg", 30.0)
w, h = calib["image_size"]
mask = np.zeros((h, w), dtype=bool)
mask[int(h * 0.62):int(h * 0.72), int(w * 0.40):int(w * 0.55)] = True
features, total, _ = server.mask_to_region_features(mask, calib, 0.9)
check("máy chủ tạo được vùng từ mặt nạ thử", len(features) >= 1, f"{len(features)} vùng, {total:.4f} m²")
rows = ds.analyse([{"id": "d", "total_area_m2": total, "regions": {"type": "FeatureCollection", "features": features}}], calib)
for r in rows:
    if r["vung"] not in ("-", "gộp") and r["area_server"]:
        rel = abs(r["area"] - r["area_server"]) / r["area_server"]
        check(f"vùng {r['vung']}: diện tích script khớp máy chủ (lệch < 0,5%)", rel < 0.005,
              f"script {r['area']:.5f} / máy chủ {r['area_server']:.5f} m²; tâm Y={r['y']:.3f} X={r['x']:.3f}")

# 2b) Tâm script khớp tâm thật trong hệ bảng (chiếu mặt nạ khi hướng 0° = toạ độ bảng nguyên gốc)
c0 = dict(calib, azimuth_deg=0.0)
polys = pm.mask_to_pixel_boundary_polygons(mask)
outer0, _ = pm.project_pixel_polygon_to_ground_m(polys[0]["outer"], (w, h), c0)
_, tx, ty = ds.polygon_area_centroid([[tuple(p) for p in outer0]])
r1 = [r for r in rows if r["vung"] == "1"][0]
# vùng vẽ dùng viền rút gọn nên tâm lệch rất ít so với viền đầy đủ
check("tâm script (hướng 30°) khớp tâm thật trong hệ bảng (lệch < 1 cm)", math.hypot(r1["x"] - tx, r1["y"] - ty) < 0.01,
      f"script ({r1['y']:.4f}, {r1['x']:.4f}) / thật ({ty:.4f}, {tx:.4f})")

# 3) Chạy CLI với file tạm + CSV
import tempfile  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    op, cp, csvp = Path(td) / "o.json", Path(td) / "c.json", Path(td) / "out.csv"
    op.write_text(json.dumps([{"id": "d", "captured_at": "2026-10-24T10:00:00Z", "processing_ms": 812.4,
                               "calibration_created_at": calib.get("created_at"), "total_area_m2": total,
                               "regions": {"type": "FeatureCollection", "features": features}}]), encoding="utf-8")
    cp.write_text(json.dumps(calib), encoding="utf-8")
    rc = ds.main(["--obs", str(op), "--calib", str(cp), "--csv", str(csvp)])
    txt = csvp.read_text(encoding="utf-8-sig")
    check("CLI chạy được, ghi CSV có 'sep=;' và dấu phẩy thập phân", rc == 0 and txt.startswith("sep=;") and ";0,8;" in txt)

# 4) Khối số để dán: 3 lần gửi (có vùng / hai vùng -> gộp / không vùng)
sqs = lambda cx, cy: {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[
    to_lonlat(a, b, 0) for a, b in [(cx - .1, cy - .1), (cx + .1, cy - .1), (cx + .1, cy + .1), (cx - .1, cy + .1), (cx - .1, cy - .1)]]]}}
obs3 = [{"id": "1", "regions": {"type": "FeatureCollection", "features": [sqs(0.0, 1.0)]}},
        {"id": "2", "regions": {"type": "FeatureCollection", "features": [sqs(0.0, 1.0), sqs(0.4, 1.0)]}},
        {"id": "3", "regions": {"type": "FeatureCollection", "features": []}}]
rows3 = ds.analyse(obs3, {"marker_latlon": [LAT0, LON0], "azimuth_deg": 0})
b = ds.dan_block(rows3, "yx").split("\n")
check("khối dán: 3 dòng, mỗi lần gửi một dòng", len(b) == 3, str(b))
check("khối dán: dòng 1 = '1,000<TAB>0,000' (dấu phẩy, TAB)", b[0] == "1,000\t0,000", repr(b[0]))
check("khối dán: lần 2 (hai vùng) lấy dòng gộp X=0,200", b[1] == "1,000\t0,200", repr(b[1]))
check("khối dán: lần 3 không vùng -> dòng trống", b[2] == "\t", repr(b[2]))
check("khối dán yxa có 3 cột; a có 1 cột; --dot dùng dấu chấm",
      ds.dan_block(rows3, "yxa").split("\n")[0].count("\t") == 2 and "\t" not in ds.dan_block(rows3, "a").split("\n")[0]
      and ds.dan_block(rows3, "a", ".").split("\n")[0] == "0.0400")

# 5) Đánh số vùng + ghi Y/X (board_coords.annotate_regions): KHÔNG loại vùng nào, kể cả vùng ở tâm bảng
import board_coords as bc  # noqa: E402


def sq_feat(cx, cy, half, az=0.0):
    ring = [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half), (cx - half, cy - half)]
    return {"type": "Feature", "properties": {"area_m2": (2 * half) ** 2},
            "geometry": {"type": "Polygon", "coordinates": [[to_lonlat(a, b, az) for a, b in ring]]}}


for az in (0.0, 40.0, 210.0):
    cal = {"marker_latlon": [LAT0, LON0], "azimuth_deg": az}
    feats = [sq_feat(0.02, -0.03, 0.15, az), sq_feat(0.5, 1.0, 0.1, az), sq_feat(-0.5, 1.1, 0.12, az)]  # tờ bảng + 2 vật (x, y)
    out = bc.annotate_regions(feats, cal)
    check(f"hướng {az}°: giữ nguyên cả 3 vùng (không loại tờ bảng)", len(out) == 3)
    p0, p1, p2 = (f["properties"] for f in out)
    check(f"hướng {az}°: vùng 1 (tờ bảng) Y=-0,030 X=0,020", p0["idx"] == 1 and abs(p0["y_m"] + 0.03) < 1e-3 and abs(p0["x_m"] - 0.02) < 1e-3, str(p0))
    check(f"hướng {az}°: vùng 2 Y=1,000 X=0,500", p1["idx"] == 2 and abs(p1["y_m"] - 1.0) < 1e-3 and abs(p1["x_m"] - 0.5) < 1e-3, str(p1))
    check(f"hướng {az}°: vùng 3 Y=1,100 X=-0,500", p2["idx"] == 3 and abs(p2["y_m"] - 1.1) < 1e-3 and abs(p2["x_m"] + 0.5) < 1e-3, str(p2))
check("không có vùng -> danh sách rỗng, không lỗi", bc.annotate_regions([], {"marker_latlon": [LAT0, LON0]}) == [])

# 6) Vùng nhỏ không còn bị bỏ oan: ngưỡng mới thấp; vùng nhiễu < 20 px bị bỏ và được báo
import os as _os  # noqa: E402

mk = np.zeros((h, w), dtype=bool)
mk[int(h * 0.80):int(h * 0.80) + 3, int(w * 0.20):int(w * 0.20) + 3] = True      # 9 px   -> nhiễu, bỏ
mk[int(h * 0.80):int(h * 0.80) + 18, int(w * 0.40):int(w * 0.40) + 18] = True    # 324 px -> giữ
mk[int(h * 0.70):int(h * 0.70) + 60, int(w * 0.60):int(w * 0.60) + 60] = True    # 3600 px -> giữ
st = {}
fs, tot, _ = server.mask_to_region_features(mk, calib, 0.9, st)
check("ngưỡng mới: giữ vùng 324 px và 3600 px, bỏ vùng 9 px", len(fs) == 2 and st["small_ignored"] == 1,
      f"giữ {len(fs)}, bỏ {st.get('small_ignored')}, ngưỡng {st.get('min_area_px'):.0f} px")
_os.environ["WEBTEST_MIN_AREA_FRAC"] = "0.005"   # ép ngưỡng cao: vùng 324 px phải bị bỏ
st2 = {}
fs2, _, _ = server.mask_to_region_features(mk, calib, 0.9, st2)
check("đặt WEBTEST_MIN_AREA_FRAC=0.005 -> ngưỡng cao hơn, bỏ thêm vùng nhỏ", len(fs2) < len(fs) and st2["small_ignored"] >= 2,
      f"giữ {len(fs2)}, bỏ {st2.get('small_ignored')}")
del _os.environ["WEBTEST_MIN_AREA_FRAC"]
check("không đặt biến -> ngưỡng mặc định thấp (<= 0,01% ảnh)", server._min_area_frac() <= 0.0001)

print(f"\nTổng: {'ĐẠT' if fails == 0 else f'{fails} HỎNG'}")
sys.exit(1 if fails else 0)
