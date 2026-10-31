"""
Đọc số liệu các lần gửi ảnh rác (observations.json) và in VỊ TRÍ TÂM + DIỆN TÍCH từng vùng rác
theo hệ toạ độ của BẢNG: (dọc +Y, dọc +X) tính bằng mét từ tâm bảng.

Chỉ ĐỌC dữ liệu máy chủ đã tính và đã vẽ lên bản đồ, rồi đổi ngược lat/lon -> mét quanh bảng bằng đúng
công thức máy chủ dùng để vẽ (project_mask.meters_to_latlon + marker_xy_to_enu, đảo ngược). Không chạy model,
không sửa file nào. Dùng thay cho việc đọc vị trí bằng mắt trên bản đồ (TN3, TN6).

Cách chạy (PowerShell, trong thư mục webtest):
    ..\\..\\..\\.venv\\Scripts\\python.exe -B doc_so_lieu.py
    ..\\..\\..\\.venv\\Scripts\\python.exe -B doc_so_lieu.py --calib D:\\bang_chung\\B02\\may_tao\\WEB-DEMO.json --obs D:\\bang_chung\\B02\\may_tao\\observations.json --csv B02_vi_tri.csv
    ..\\..\\..\\.venv\\Scripts\\python.exe -B doc_so_lieu.py --last 5        (chỉ 5 lần gửi gần nhất)

PHẢI dùng đúng file hiệu chỉnh của buổi đã chụp: vị trí bảng/hướng mũi tên khác thì kết quả đổi ngược sai.
Mỗi lần gửi mới có ghi calibration_created_at; script cảnh báo nếu không khớp với file hiệu chỉnh đang dùng.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from board_coords import (  # noqa: E402  dùng chung với máy chủ
    feature_rings, latlon_to_board, polygon_area_centroid,
)


def analyse(observations, calib):
    lat0, lon0 = calib["marker_latlon"]
    az = calib.get("azimuth_deg", 0.0)
    rows = []
    for idx, o in enumerate(observations, 1):
        base = {"lan": idx, "id": o.get("id"), "captured_at": o.get("captured_at"),
                "processing_s": (o["processing_ms"] / 1000.0) if isinstance(o.get("processing_ms"), (int, float)) else None,
                "n_instances": o.get("n_instances"),
                "calib_khop": (None if o.get("calibration_created_at") is None
                               else o.get("calibration_created_at") == calib.get("created_at"))}
        regs = []
        for f in (o.get("regions") or {}).get("features", []):
            for poly in feature_rings(f.get("geometry")):
                rings = [[latlon_to_board(lat, lon, lat0, lon0, az) for lon, lat in ring] for ring in poly]
                area, cx, cy = polygon_area_centroid(rings)
                regs.append({"area": area, "x": cx, "y": cy,
                             "area_server": (f.get("properties") or {}).get("area_m2")})
        if not regs:
            rows.append({**base, "vung": "-", "y": None, "x": None, "area": None, "area_server": None, "dist": None})
            continue
        for k, r in enumerate(regs, 1):
            rows.append({**base, "vung": str(k), "y": r["y"], "x": r["x"], "area": r["area"],
                         "area_server": r["area_server"], "dist": math.hypot(r["x"], r["y"])})
        if len(regs) > 1:   # gộp mọi vùng của ảnh (khi một vật bị chia thành nhiều vùng)
            A = sum(r["area"] for r in regs)
            gx = sum(r["area"] * r["x"] for r in regs) / A
            gy = sum(r["area"] * r["y"] for r in regs) / A
            rows.append({**base, "vung": "gộp", "y": gy, "x": gx, "area": A,
                         "area_server": o.get("total_area_m2"), "dist": math.hypot(gx, gy)})
    return rows


def _f(v, nd=3, dec="."):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{v:.{nd}f}".replace(".", dec)


TAB, NL = chr(9), chr(10)


def dan_block(rows, mode, dec=","):
    """Khối số để DÁN vào Excel: mỗi lần gửi một dòng, các cột cách nhau bằng TAB.
    mode: 'yx' (Y, X) | 'yxa' (Y, X, diện tích) | 'a' (diện tích). Ảnh nhiều vùng dùng dòng 'gộp'; ảnh không có vùng -> dòng trống."""
    by = {}
    for r in rows:
        cur = by.get(r["lan"])
        if cur is None or r["vung"] == "gộp" or (cur["vung"] == "-" and r["vung"] != "-"):
            by[r["lan"]] = r
    lines = []
    for lan in sorted(by):
        r = by[lan]
        vals = {"y": r["y"], "x": r["x"], "a": r["area"]}
        cols = {"yx": "yx", "yxa": "yxa", "a": "a"}[mode]
        lines.append(TAB.join(_f(vals[c], 4 if c == "a" else 3, dec) for c in cols))
    return NL.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="In vị trí tâm (dọc +Y, dọc +X, mét) và diện tích từng vùng rác.")
    ap.add_argument("--obs", default=str(HERE / "data" / "observations.json"), help="file observations.json")
    ap.add_argument("--calib", default=str(HERE.parent / "calibration" / "WEB-DEMO.json"), help="file hiệu chỉnh của buổi đó")
    ap.add_argument("--last", type=int, default=0, help="chỉ lấy N lần gửi gần nhất")
    ap.add_argument("--csv", default="", help="ghi thêm ra file CSV (mở bằng Excel)")
    ap.add_argument("--dan", choices=["yx", "yxa", "a"], default="",
                    help="in khối số để DÁN vào Excel: yx = Y,X (TN3) | yxa = Y,X,diện tích (TN6) | a = diện tích (TN4)")
    ap.add_argument("--copy", action="store_true", help="tự chép khối số vào clipboard (Windows) — chỉ cần Ctrl+V trong Excel")
    ap.add_argument("--dot", action="store_true", help="dùng dấu chấm thập phân (mặc định dấu phẩy, hợp Excel tiếng Việt)")
    a = ap.parse_args(argv)

    try:
        obs = json.loads(Path(a.obs).read_text(encoding="utf-8"))
        calib = json.loads(Path(a.calib).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Không đọc được file: {e}")
        return 2
    if not isinstance(obs, list) or not obs:
        print("Chưa có lần gửi nào trong", a.obs)
        return 1
    start = max(0, len(obs) - a.last) if a.last > 0 else 0
    rows = analyse(obs, calib)
    rows = [r for r in rows if r["lan"] > start]

    print(f"Hiệu chỉnh: {a.calib}")
    print(f"  vị trí bảng {calib['marker_latlon']}, hướng mũi tên {calib.get('azimuth_deg', 0.0)}°, tạo lúc {calib.get('created_at')}")
    print("Vị trí tính từ TÂM BẢNG: Y = dọc theo +Y (mũi tên xanh dương), X = dọc theo +X (đỏ), đơn vị mét.\n")
    head = f"{'Lần':>4} {'Giờ gửi (UTC)':<21} {'Vùng':<5} {'Y (m)':>8} {'X (m)':>8} {'Cách bảng':>10} {'Diện tích m²':>13} {'Máy chủ xử lý':>14}"
    print(head)
    print("-" * len(head))
    canh_bao = 0
    for r in rows:
        tg = "" if r["processing_s"] is None else f"{r['processing_s']:.1f} s"
        print(f"{r['lan']:>4} {str(r['captured_at'] or ''):<21} {r['vung']:<5} {_f(r['y']):>8} {_f(r['x']):>8} "
              f"{_f(r['dist'], 2):>10} {_f(r['area'], 4):>13} {tg:>14}")
        if r["calib_khop"] is False:
            canh_bao += 1
    if canh_bao:
        print(f"\nCẢNH BÁO: {canh_bao} dòng được chụp với hiệu chỉnh KHÁC file đang dùng — vị trí của các dòng đó không đúng. "
              "Dùng --calib trỏ tới bản sao lưu WEB-DEMO.json của buổi đó.")
    print("\n'Vùng = gộp': tâm và diện tích của mọi vùng trong ảnh cộng lại (dùng khi một vật bị chia thành nhiều vùng).")
    print("'Vùng = -': model không thấy rác trong ảnh đó.")

    if a.dan:
        blk = dan_block(rows, a.dan, "." if a.dot else ",")
        ten = {"yx": "cột Y, X (TN3: dán vào ô Y trên bản đồ, hàng đầu của các lần vừa chụp)",
               "yxa": "cột Y, X, Diện tích (TN6: dán vào ô Y trên bản đồ của lần 1)",
               "a": "cột Diện tích (TN4: dán vào ô Diện tích máy báo)"}[a.dan]
        print(NL + f"===== KHỐI SỐ ĐỂ DÁN VÀO EXCEL — {ten}; mỗi dòng = một lần gửi, theo thứ tự =====")
        print(blk)
        print("===== hết khối số =====")
        if a.copy:
            try:
                import subprocess
                subprocess.run(["clip"], input=blk.encode("utf-16le"), check=True)
                print("Đã chép vào clipboard: mở Excel, bấm vào ô đầu tiên cần dán rồi Ctrl+V.")
            except Exception as e:  # noqa: BLE001
                print(f"Không chép được vào clipboard ({e}); bôi đen khối số ở trên rồi Ctrl+C.")

    if a.csv:
        with open(a.csv, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write("sep=;\n")
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Lần", "Mã lần gửi", "Giờ gửi (UTC)", "Vùng", "Y (m)", "X (m)", "Cách tâm bảng (m)",
                        "Diện tích (m²)", "Máy chủ xử lý (s)", "Đúng hiệu chỉnh?"])
            for r in rows:
                w.writerow([r["lan"], r["id"], r["captured_at"], r["vung"], _f(r["y"], 3, ","), _f(r["x"], 3, ","),
                            _f(r["dist"], 2, ","), _f(r["area"], 4, ","),
                            _f(r["processing_s"], 1, ","), {True: "có", False: "KHÔNG", None: "?"}[r["calib_khop"]]])
        print(f"\nĐã ghi {a.csv} (mở bằng Excel, chép cột Y, X, Diện tích sang trang TN3/TN4/TN6).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
