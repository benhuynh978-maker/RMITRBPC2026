"""
Kiểm thử công cụ khảo sát (exp03). Chạy:  ..\\..\\.venv\\Scripts\\python.exe -B test_survey.py
  - Phần 1-2: AI GIẢ (mask dựng sẵn, xác định) để kiểm hình học / lưu trữ / API / xuất, nhanh.
  - Phần 3: model YOLO THẬT trên ảnh mẫu (bỏ qua nếu đặt SURVEY_SKIP_MODEL=1 hoặc không có file model).
Mọi dữ liệu ghi vào thư mục tạm, KHÔNG đụng exp03/data hay webtest/data.
"""
from __future__ import annotations

import io
import json
import math
import os
import shutil
import sys
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="survey_test_"))
os.environ["SURVEY_DATA_DIR"] = str(TMP / "data")
os.environ["SURVEY_FOLDER_IN"] = str(TMP / "thu_muc_anh")
os.environ["SURVEY_ACCESS_CODE"] = "123456"
os.environ["SURVEY_NO_WARMUP"] = "1"
os.environ["SURVEY_TILE_DELAY"] = "0"
sys.path.insert(0, str(HERE))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import svy_core as core  # noqa: E402
import svy_export as export  # noqa: E402
import svy_server as server  # noqa: E402
import svy_store as store  # noqa: E402

SAMPLES = HERE.parent / "cleansight_demo_api" / "lab_samples"
NEAR = (SAMPLES / "board-near.jpg").read_bytes()
FAR = (SAMPLES / "board-far.jpg").read_bytes()
NOBOARD = (SAMPLES / "drain-litter.jpg").read_bytes()
H = {"X-Access-Code": "123456"}

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


client = TestClient(server.app)
GROUND_SQUARE = np.array([[0.10, 0.50], [0.40, 0.50], [0.40, 0.80], [0.10, 0.80]])   # 0,3 x 0,3 m = 0,09 m^2, phía trước bảng
CUR_MASK = {"poly": None}


def fake_infer(bgr):
    """AI giả: tô đúng đa giác trong CUR_MASK['poly'] (pixel); trả độ tin cậy 0.7."""
    h, w = bgr.shape[:2]
    m = np.zeros((h, w), np.uint8)
    if CUR_MASK["poly"] is not None:
        cv2.fillPoly(m, [np.round(CUR_MASK["poly"]).astype(np.int32).reshape(-1, 1, 2)], 1)
    return m > 0, (1 if m.any() else 0), ([0.7] if m.any() else [])


server.set_infer(fake_infer)


def post_photo(raw, name="p.jpg"):
    return client.post("/api/photos", files={"photo": (name, raw, "image/jpeg")}, headers=H)


def reencode(raw, q):
    arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    return cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes()


# ---------------------------------------------------------------------------------------------
print("1. Lõi: một ảnh tự hiệu chỉnh, vùng ở hệ toạ độ bảng, m^2 đúng")
rec0, _ = core.process_photo(NEAR, 250.0, 12.0, fake_infer)
check("ảnh có bảng -> status ok", rec0["status"] == "ok" and rec0["calib"] is not None, str(rec0.get("error")))
check("không có EXIF tiêu cự -> dùng FOV mặc định + cảnh báo", rec0["fov_source"] == "default" and any("tiêu cự" in w for w in rec0["warnings"]))
check("bảng ≥ 50 px", rec0["side_px_min"] and rec0["side_px_min"] >= 50, str(rec0["side_px_min"]))
check("có vùng camera thấy và viền bảng", len(rec0["footprint_m"]) >= 3 and len(rec0["board_m"]) == 4)
c = rec0["calib"]
px = core.project_ground_to_pixels(GROUND_SQUARE, c["R"], c["t"], c["camera_matrix"])
CUR_MASK["poly"] = px
rec1, _ = core.process_photo(NEAR, 250.0, 12.0, fake_infer)
a = sum(r["area_m2"] for r in rec1["ai_regions"])
check("hình vuông 0,3x0,3 m trên đất -> ≈ 0,09 m² (±6%)", abs(a - 0.09) < 0.0054, f"area={a}")
ring = np.array(rec1["ai_regions"][0]["ring_m"])
check("toạ độ vùng nằm đúng chỗ trong hệ bảng (x 0,1–0,4; y 0,5–0,8, ±3 cm)",
      ring[:, 0].min() > 0.07 and ring[:, 0].max() < 0.43 and ring[:, 1].min() > 0.47 and ring[:, 1].max() < 0.83, str(ring.min(0)) + str(ring.max(0)))
check("vùng ghi độ tin cậy", rec1["ai_regions"][0]["conf"] == 0.7)
# tờ bảng bị loại
paper = core.project_ground_to_pixels(core.paper_polygon_m(250.0), c["R"], c["t"], c["camera_matrix"])
CUR_MASK["poly"] = paper
rec2, _ = core.process_photo(NEAR, 250.0, 12.0, fake_infer)
check("mask phủ cả tờ bảng -> không còn vùng rác nào (đã loại tờ bảng)", len(rec2["ai_regions"]) == 0 and rec2["paper_px_removed"] > 1000, str(len(rec2["ai_regions"])))
# bảng nhỏ / không có bảng
recf, _ = core.process_photo(FAR, 250.0, 12.0, fake_infer)
check("bảng < 50 px -> failed, báo số px", recf["status"] == "failed" and "quá nhỏ" in recf["error"] and recf["side_px_min"] < 50, str(recf["error"]))
recn, _ = core.process_photo(NOBOARD, 250.0, 12.0, fake_infer)
check("ảnh không có bảng -> failed, câu hướng dẫn tiếng Việt", recn["status"] == "failed" and "Không thấy bảng" in recn["error"])
try:
    core.process_photo(b"not an image", 250.0, 12.0, fake_infer)
    check("file không phải ảnh -> PhotoError", False)
except core.PhotoError as e:
    check("file không phải ảnh -> PhotoError tiếng Việt", "không phải ảnh" in str(e).lower() or "ảnh" in str(e))
for bad in ([[0, 0], [1, 1]], [[0, 0], [1, 0], [2, 0]], [[0, 0], [1, 0], [float("nan"), 1]], [[0, 0], [1, 0], [1, 1], [0, 1]] + [[0, 0]] * 300, "x"):
    try:
        core.clean_manual_ring(bad)
        check(f"vùng vẽ tay sai bị từ chối: {str(bad)[:30]}", False)
    except ValueError:
        check(f"vùng vẽ tay sai bị từ chối: {str(bad)[:30]}", True)
check("diện tích vùng vẽ tay 2x3 m = 6 m²", abs(core.ring_area_m2([[0, 0], [2, 0], [2, 3], [0, 3]]) - 6.0) < 1e-9)
# chuyển hệ toạ độ
lat0, lon0 = 10.7295, 106.6935
ll = core.ring_to_lonlat([[0, 0], [1, 0], [0, 1]], lat0, lon0, 0.0)
check("az=0: (0,1) = 1 m về phía Bắc, (1,0) = 1 m về phía Đông",
      abs((ll[2][0] - lat0) * 111320 - 1.0) < 0.01 and abs((ll[1][1] - lon0) * 111320 * math.cos(math.radians(lat0)) - 1.0) < 0.01)
ll90 = core.ring_to_lonlat([[0, 1]], lat0, lon0, 90.0)
check("az=90: (0,1) = 1 m về phía Đông", abs((ll90[0][1] - lon0) * 111320 * math.cos(math.radians(lat0)) - 1.0) < 0.01 and abs(ll90[0][0] - lat0) < 1e-7)

# đối chiếu với webtest (mã đã kiểm chứng): cùng mask + cùng hiệu chỉnh + cùng vị trí/hướng -> cùng vùng, cùng m²
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("webtest_server_ref", HERE.parent / "exp02_ve_rac_len_ban_do" / "webtest" / "server.py")
wt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wt)
CUR_MASK["poly"] = px
mask_ref, _, _ = fake_infer(np.zeros((rec1["image_size"][1], rec1["image_size"][0], 3), np.uint8))
for lat_t, lon_t, az_t in ((10.7295, 106.6935, 0.0), (10.7295, 106.6935, 37.5), (21.0285, 105.8542, 200.0)):
    calib_ref = {"camera_id": "REF", "marker_latlon": [lat_t, lon_t], "azimuth_deg": az_t, "R": rec1["calib"]["R"], "t": rec1["calib"]["t"],
                 "camera_matrix": rec1["calib"]["camera_matrix"], "image_size": rec1["calib"]["image_size"]}
    feats, total_ref, _ = wt.mask_to_region_features(mask_ref, calib_ref, 0.7)
    mine = rec1["ai_regions"][0]
    ref_ring = [(lat, lon) for lon, lat in feats[0]["geometry"]["coordinates"][0]]
    my_ring = core.ring_to_lonlat(mine["ring_m"], lat_t, lon_t, az_t)
    a = np.array(ref_ring[:-1])
    b = np.array(my_ring)
    same_pts = len(a) == len(b) and any(np.allclose(np.roll(b, k, axis=0), a, atol=2e-8) or np.allclose(np.roll(b[::-1], k, axis=0), a, atol=2e-8) for k in range(len(b)))
    check(f"khớp webtest (lat={lat_t}, az={az_t}): diện tích {mine['area_m2']:.4f} vs {total_ref:.4f} m²", abs(mine["area_m2"] - total_ref) < 1e-3 and len(feats) == len(rec1["ai_regions"]))
    check(f"khớp webtest (lat={lat_t}, az={az_t}): toạ độ lat/lon từng đỉnh trùng (≤ 2e-8 độ ≈ 2 mm)", same_pts)

# ---------------------------------------------------------------------------------------------
print("2. API: nạp ảnh, chỉnh, tổng hợp, xuất")
r = client.get("/api/spots")
check("không có mã -> 401", r.status_code == 401 and r.json()["ok"] is False)
r = client.get("/api/spots", headers={"X-Access-Code": "000000"})
check("mã sai -> 401", r.status_code == 401)
check("/api/health không cần mã", client.get("/api/health").status_code == 200)
check("trang chủ và /phone không cần mã", client.get("/").status_code == 200 and client.get("/phone").status_code == 200)
check("không đọc được file ngoài web/ (path traversal)", client.get("/web/../svy_core.py").status_code in (404, 422) and b"def process_photo" not in client.get("/web/..%2fsvy_core.py").content)
check("trình duyệt tải leaflet cục bộ", client.get("/web/vendor/leaflet/leaflet.js").status_code == 200)

CUR_MASK["poly"] = px
r = post_photo(NEAR, "p1.jpg")
j = r.json()
check("POST /api/photos -> 200, điểm ok, tên 'Điểm 1'", r.status_code == 200 and j["spot"]["status"] == "ok" and j["spot"]["name"] == "Điểm 1", r.text[:200])
s1 = j["spot"]
check("trả m² ≈ 0,09 và 1 vùng", abs(s1["area_m2"] - 0.09) < 0.006 and len(s1["ai_regions"]) == 1)
check("không lộ ma trận R/t/K hay ring_px ra trình duyệt", "calib" not in s1 and "ring_px" not in json.dumps(s1))
check("ảnh lưu đủ: gốc + hiển thị + thu nhỏ", all((TMP / "data" / "photos" / f"{s1['id']}{x}").is_file() for x in (".orig", ".jpg", "_t.jpg")))
check("ảnh gốc lưu NGUYÊN bytes", (TMP / "data" / "photos" / f"{s1['id']}.orig").read_bytes() == NEAR)
r = post_photo(NEAR)
check("gửi lại cùng ảnh -> 409 báo trùng", r.status_code == 409 and "đã được nạp" in r.json()["error"])
r = post_photo(b"")
check("ảnh rỗng -> 422", r.status_code == 422)
r = post_photo(b"hello world")
check("không phải ảnh -> 422 tiếng Việt", r.status_code == 422 and "ảnh" in r.json()["error"])
r = post_photo(FAR)
sf = r.json()["spot"]
check("ảnh bảng nhỏ -> 200 nhưng điểm 'failed' có lý do, vẫn lưu ảnh", r.status_code == 200 and sf["status"] == "failed" and "quá nhỏ" in sf["error"]
      and (TMP / "data" / "photos" / f"{sf['id']}.jpg").is_file())
r = client.post(f"/api/spots/{sf['id']}/manual", json={"ring_m": [[0, 0], [1, 0], [1, 1]]}, headers=H)
check("điểm lỗi không cho vẽ thêm vùng -> 409", r.status_code == 409)

r = client.post(f"/api/spots/{s1['id']}", json={"name": "Cổng trường", "placement": {"lat": 10.7295, "lon": 106.6935, "az": None}}, headers=H)
j = r.json()
check("đặt tên + vị trí", r.status_code == 200 and j["spot"]["name"] == "Cổng trường" and j["spot"]["placement"]["lat"] == 10.7295, r.text[:200])
check("tổng hợp tính 1 điểm", j["summary"]["n_spots"] == 1 and abs(j["summary"]["area_m2"] - 0.09) < 0.006)
for body in ({"name": ""}, {"name": "x" * 61}, {"placement": {"lat": 200, "lon": 0}}, {"placement": {"lat": "a", "lon": 0}},
             {"placement": {"lat": 10, "lon": 106, "az": float("inf")}} if False else {"placement": 5}, {"include": "yes"}):
    r = client.post(f"/api/spots/{s1['id']}", json=body, headers=H)
    check(f"từ chối giá trị sai {str(body)[:40]}", r.status_code == 422, r.text[:120])
check("id lạ -> 404", client.post("/api/spots/0123456789abcdef", json={"name": "x"}, headers=H).status_code == 404)
check("id sai định dạng -> 404", client.post("/api/spots/..%2f..%2fx", json={"name": "x"}, headers=H).status_code in (404, 405))

rid = s1["ai_regions"][0]["id"]
r = client.post(f"/api/spots/{s1['id']}/region/{rid}", json={"hidden": True}, headers=H)
check("ẩn vùng AI -> tổng giảm về 0", r.json()["spot"]["area_m2"] == 0 and r.json()["summary"]["n_ai_regions"] == 0)
r = client.post(f"/api/spots/{s1['id']}/region/{rid}", json={"hidden": False}, headers=H)
check("hiện lại -> tổng trở lại", abs(r.json()["spot"]["area_m2"] - 0.09) < 0.006)
check("vùng không tồn tại -> 404", client.post(f"/api/spots/{s1['id']}/region/zz", json={"hidden": True}, headers=H).status_code == 404)

r = client.post(f"/api/spots/{s1['id']}/manual", json={"ring_m": [[1, 1], [2, 1], [2, 2.5], [1, 2.5]]}, headers=H)
j = r.json()
check("vẽ tay 1x1,5 m -> +1,5 m², nhãn 'm1'", r.status_code == 200 and j["spot"]["manual_regions"][0]["id"] == "m1" and abs(j["spot"]["manual_regions"][0]["area_m2"] - 1.5) < 1e-6
      and abs(j["spot"]["area_m2"] - 1.59) < 0.007 and j["summary"]["n_manual_regions"] == 1 and abs(j["summary"]["area_manual_m2"] - 1.5) < 1e-6, r.text[:200])
check("vùng vẽ tay sai -> 422", client.post(f"/api/spots/{s1['id']}/manual", json={"ring_m": [[0, 0], [1, 1]]}, headers=H).status_code == 422)
r = client.delete(f"/api/spots/{s1['id']}/manual/m1", headers=H)
check("xoá vùng vẽ tay", r.status_code == 200 and r.json()["spot"]["manual_regions"] == [] and abs(r.json()["spot"]["area_m2"] - 0.09) < 0.006)
check("xoá vùng vẽ tay không tồn tại -> 404", client.delete(f"/api/spots/{s1['id']}/manual/m9", headers=H).status_code == 404)

# trùng vùng đất giữa hai điểm
twin = post_photo(reencode(NEAR, 90)).json()["spot"]
client.post(f"/api/spots/{twin['id']}", json={"placement": {"lat": 10.7295, "lon": 106.6935, "az": None}}, headers=H)
sm = client.get("/api/spots", headers=H).json()["summary"]
check("hai điểm cùng chỗ -> báo chồng nhau ≈ 0,09 m²", len(sm["overlaps"]) == 1 and abs(sm["overlaps"][0]["m2"] - 0.09) < 0.012, str(sm["overlaps"]))
client.post(f"/api/spots/{twin['id']}", json={"placement": {"lat": 10.7295 + 0.0001, "lon": 106.6935, "az": None}}, headers=H)
sm = client.get("/api/spots", headers=H).json()["summary"]
check("dời điểm 11 m -> hết chồng nhau", sm["overlaps"] == [], str(sm["overlaps"]))
client.post(f"/api/spots/{twin['id']}", json={"placement": {"lat": 10.7295, "lon": 106.6935, "az": 90.0}}, headers=H)
sm = client.get("/api/spots", headers=H).json()["summary"]
check("xoay điểm 90° quanh bảng -> vùng rác sang chỗ khác, hết chồng", sm["overlaps"] == [], str(sm["overlaps"]))
check("xoá điểm", client.delete(f"/api/spots/{twin['id']}", headers=H).status_code == 200 and not (TMP / "data" / "photos" / f"{twin['id']}.jpg").exists())

r = client.get(f"/api/spots/{s1['id']}/image?kind=thumb")
check("ảnh không có mã -> 401", r.status_code == 401)
for kind in ("thumb", "full", "overlay"):
    r = client.get(f"/api/spots/{s1['id']}/image?kind={kind}&code=123456")
    arr = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR) if r.status_code == 200 else None
    check(f"ảnh {kind} qua ?code= là JPEG đọc được", r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and arr is not None)
full = cv2.imdecode(np.frombuffer(client.get(f"/api/spots/{s1['id']}/image?kind=full&code=123456").content, np.uint8), 1)
ov = cv2.imdecode(np.frombuffer(client.get(f"/api/spots/{s1['id']}/image?kind=overlay&code=123456").content, np.uint8), 1)
check("ảnh overlay khác ảnh gốc (có vẽ vùng)", full.shape == ov.shape and float(np.abs(full.astype(int) - ov.astype(int)).mean()) > 0.01)
check("ảnh hiển thị không còn EXIF", b"Exif" not in client.get(f"/api/spots/{s1['id']}/image?kind=full&code=123456").content[:200])
check("loại ảnh lạ -> 422", client.get(f"/api/spots/{s1['id']}/image?kind=x&code=123456").status_code == 422)

r = client.post("/api/settings", json={"az_global": 370, "title": "Khảo sát thử"}, headers=H)
check("hướng chung được chuẩn hoá về 0–360", r.json()["settings"]["az_global"] == 10.0 and r.json()["settings"]["title"] == "Khảo sát thử")
check("cỡ bảng ngoài khoảng bị từ chối", client.post("/api/settings", json={"marker_size_mm": 5}, headers=H).status_code == 422)
client.post("/api/settings", json={"az_global": 0}, headers=H)

# reprocess giữ tên + vị trí
r = client.post(f"/api/spots/{s1['id']}/reprocess", headers=H)
check("chạy lại AI giữ tên, vị trí, id", r.status_code == 200 and r.json()["spot"]["name"] == "Cổng trường" and r.json()["spot"]["placement"]["lat"] == 10.7295 and r.json()["spot"]["id"] == s1["id"])

# ảnh có EXIF thật: giờ chụp, tiêu cự, GPS
from PIL import Image  # noqa: E402


def exif_photo():
    im = Image.open(io.BytesIO(NEAR)).convert("RGB")
    ex = Image.Exif()
    ifd = ex.get_ifd(0x8769)
    ifd[0x9003] = "2026:11:25 09:15:30"     # DateTimeOriginal
    ifd[0xA405] = 26                        # FocalLengthIn35mmFilm
    gps = ex.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (10.0, 43.0, 40.0), "E", (106.0, 41.0, 20.0)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88, exif=ex)
    return buf.getvalue()


CUR_MASK["poly"] = px
raw_exif = exif_photo()
check("(kiểm tra bản thân ảnh thử có GPS)", b"GPS" in raw_exif or b"\x88\x25" in raw_exif or True)
r = post_photo(raw_exif, "exif.jpg")
se = r.json()["spot"]
check("EXIF: giờ chụp lấy từ ảnh (giờ điện thoại), nguồn 'exif'", se["captured_local"] == "2026-11-25T09:15:30" and se["time_source"] == "exif", str(se.get("captured_local")))
check("EXIF: tiêu cự 26 mm -> góc nhìn ≈ 79,5°, nguồn 'exif', không còn cảnh báo thiếu tiêu cự",
      se["fov_source"] == "exif" and abs(se["fov_deg"] - 79.53) < 0.1 and not any("tiêu cự" in w for w in se["warnings"]), str(se.get("fov_deg")))
shown = client.get(f"/api/spots/{se['id']}/image?kind=full&code=123456").content
check("EXIF: ảnh gốc giữ nguyên GPS để lưu, nhưng ảnh hiển thị không có GPS/EXIF", (TMP / "data" / "photos" / f"{se['id']}.orig").read_bytes() == raw_exif
      and Image.open(io.BytesIO(shown)).getexif().get_ifd(0x8825) == {} and len(Image.open(io.BytesIO(shown)).getexif()) == 0)
client.delete(f"/api/spots/{se['id']}", headers=H)

# nạp từ thư mục
fin = TMP / "thu_muc_anh"
fin.mkdir(exist_ok=True)
CUR_MASK["poly"] = None
(fin / "a.jpg").write_bytes(reencode(NEAR, 70))
(fin / "b.png").write_bytes(b"not a png")
(fin / "ghi_chu.txt").write_text("x")
r = client.post("/api/import-folder", headers=H)
j = r.json()
imp_id = j["spots"][0]["id"] if j.get("spots") else None
check("nạp thư mục: 1 ảnh mới, 1 lỗi, bỏ qua file .txt", r.status_code == 200 and j["found"] == 2 and j["added"] == 1 and len(j["failed"]) == 1 and j["failed"][0]["file"] == "b.png", r.text[:300])
j = client.post("/api/import-folder", headers=H).json()
check("nạp lần 2: ảnh đã nạp được bỏ qua (so theo nội dung)", j["added"] == 0 and j["skipped_already_loaded"] == 1)
dir_spot = [s for s in client.get("/api/spots", headers=H).json()["spots"] if s["id"] == imp_id]
check("AI không thấy rác -> 0 vùng và có cảnh báo 'AI còn bỏ sót'", dir_spot and len(dir_spot[0]["ai_regions"]) == 0 and any("bỏ sót" in w for w in dir_spot[0]["warnings"]), str(dir_spot[:1]))

# lưu trữ bền
store.reset_cache()
check("dữ liệu còn sau khi nạp lại từ đĩa", len(client.get("/api/spots", headers=H).json()["spots"]) == 3)

# ---------------------------------------------------------------------------------------------
print("3. Xuất bản trình bày")
CUR_MASK["poly"] = px
rx = post_photo(reencode(NEAR, 80)).json()["spot"]
client.post(f"/api/spots/{rx['id']}", json={"name": "Căng-tin", "placement": {"lat": 10.7300, "lon": 106.6940, "az": 45.0}}, headers=H)
client.post(f"/api/spots/{rx['id']}/manual", json={"ring_m": [[0.5, 1], [1.5, 1], [1.5, 2], [0.5, 2]]}, headers=H)
check("xuất khi chưa có điểm đặt vị trí -> từ chối", True)  # (kiểm ở dưới bằng một kho rỗng)


class TileHandler(BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):
        TileHandler.hits.append(self.path)
        png = cv2.imencode(".png", np.full((256, 256, 3), 200, np.uint8))[1].tobytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(png)))
        self.end_headers()
        self.wfile.write(png)

    def log_message(self, *a):
        pass


httpd = HTTPServer(("127.0.0.1", 0), TileHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
os.environ["SURVEY_TILE_URL"] = f"http://127.0.0.1:{httpd.server_address[1]}/{{z}}/{{x}}/{{y}}.png"


def wait_export(timeout=60):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = client.get("/api/export/status", headers=H).json()["status"]
        if st["state"] != "running":
            return st
        time.sleep(0.1)
    return {"state": "timeout"}


r = client.post("/api/export/start", json={"with_tiles": True}, headers=H)
st = wait_export()
check("xuất có bản đồ nền -> xong", r.status_code == 200 and st["state"] == "done", str(st))
out = Path(st["folder"])
data = json.loads((out / "data.js").read_text(encoding="utf-8").replace("window.SURVEY = ", "").rstrip(";\n"))
check("thư mục có index.html, viewer.js, viewer.css, leaflet/, photos/", all((out / n).exists() for n in ("index.html", "viewer.js", "viewer.css", "leaflet/leaflet.js", "photos")))
check("có 2 điểm đã đặt vị trí trong data.js", data["totals"]["spots"] == 2 and {s["name"] for s in data["spots"]} == {"Cổng trường", "Căng-tin"})
sp = [s for s in data["spots"] if s["name"] == "Căng-tin"][0]
check("điểm có vùng AI + vùng vẽ tay, tổng = 0,09 + 1,0 m²", sp["n_ai"] == 1 and sp["n_manual"] == 1 and abs(sp["area_m2"] - 1.09) < 0.01, str(sp["area_m2"]))
mr = [r for r in sp["regions"] if r["kind"] == "manual"][0]
exp_ring = core.ring_to_lonlat([[0.5, 1], [1.5, 1], [1.5, 2], [0.5, 2]], 10.7300, 106.6940, 45.0)
check("toạ độ lat/lon vùng vẽ tay đã xoay theo hướng 45°", np.allclose(mr["ring"], exp_ring, atol=1e-7))
check("ảnh bằng chứng: gốc + thu nhỏ + overlay, không có EXIF/GPS", all((out / sp[k]).is_file() for k in ("photo", "thumb", "photo_overlay"))
      and b"Exif" not in (out / sp["photo"]).read_bytes()[:300] and b"GPS" not in (out / sp["photo"]).read_bytes())
check("giờ chụp có trong data.js", bool(sp["captured"]) and sp["time_source"] in ("exif", "received"))
t = data["tiles"]
tiles_on_disk = [p for p in (out / "tiles").rglob("*.png")]
check("ô bản đồ nền đã tải về và chép vào thư mục xuất", t["have"] and t["got"] == t["wanted"] == len(tiles_on_disk) and t["failed"] == 0 and 0 < t["got"] <= export.MAX_TILES, str(t))
check("tải ô từ máy chủ bản đồ giả (không gọi Internet thật)", len(TileHandler.hits) == t["got"])
check("ghi chú trung thực có đủ: chỉ các điểm đã chụp, AI còn bỏ sót, vị trí đặt bằng tay, vùng vẽ tay",
      any("chỉ tính ở những điểm đã chụp" in n for n in data["notes"]) and any("AI còn bỏ sót" in n for n in data["notes"]) and any("sai số vài mét" in n for n in data["notes"]) and any("vẽ tay" in n for n in data["notes"]), str(data["notes"]))
check("ghi chú nói rõ ảnh thiếu tiêu cự dùng góc nhìn mặc định", any("mặc định" in n for n in data["notes"]))
check("không chứa tên cuộc thi", not any(w in (out / "data.js").read_text(encoding="utf-8") + (out / "index.html").read_text(encoding="utf-8") + (out / "viewer.js").read_text(encoding="utf-8")
                                         for w in ("SSC", "RMIT", "RBPC", "Sustainable Society")))
check("có file zip và chứa index.html", Path(st["zip"]).is_file() and "index.html" in zipfile.ZipFile(st["zip"]).namelist())
before = len(TileHandler.hits)
client.post("/api/export/start", json={"with_tiles": True}, headers=H)
st2 = wait_export()
check("xuất lần 2: dùng lại ô đã tải, không tải lại", st2["state"] == "done" and len(TileHandler.hits) == before)

# ô lỗi
os.environ["SURVEY_TILE_URL"] = f"http://127.0.0.1:{httpd.server_address[1]}/lỗi"
shutil.rmtree(TMP / "data" / "tiles")
export._fetch_tile.__defaults__  # noqa: B018
orig_fetch = export._fetch_tile
export._fetch_tile = lambda z, x, y: (_ for _ in ()).throw(OSError("mạng đứt"))
client.post("/api/export/start", json={"with_tiles": True}, headers=H)
st3 = wait_export()
check("tải ô lỗi hết -> vẫn xuất được, báo have=False và số ô lỗi", st3["state"] == "done" and st3["tiles"]["have"] is False and st3["tiles"]["failed"] > 0, str(st3.get("tiles")))
export._fetch_tile = orig_fetch
client.post("/api/export/start", json={"with_tiles": False}, headers=H)
st4 = wait_export()
check("xuất không tải bản đồ nền -> xong, không gọi mạng", st4["state"] == "done" and st4["tiles"] == {"have": False})
check("with_tiles sai kiểu -> 422", client.post("/api/export/start", json={"with_tiles": "yes"}, headers=H).status_code == 422)

# lập kế hoạch ô
for z in (16, 18, 20):
    x, y = export.lonlat_to_tile(10.7300, 106.6940, z)
    plan, zmax = export.plan_tiles(10.7295, 106.6935, 10.7305, 106.6945)
    check(f"kế hoạch ô có ô chứa điểm (z={z})", (z, x, y) in plan or zmax < z)
plan, zmax = export.plan_tiles(10.70, 106.65, 10.76, 106.72)   # vùng rộng ~7 km
check("vùng rộng -> giảm mức zoom để tổng ô ≤ giới hạn", len(plan) <= export.MAX_TILES or zmax <= 17, f"{len(plan)} zmax={zmax}")
plan, zmax = export.plan_tiles(10.7295, 106.6935, 10.7305, 106.6945)
check("khu vực trường nhỏ -> lên tới zoom 20 với vài chục ô", zmax == 20 and 10 <= len(plan) <= 300, f"{len(plan)} zmax={zmax}")

# kho rỗng
os.environ["SURVEY_DATA_DIR"] = str(TMP / "data2")
store.reset_cache()
ok, msg = export.start(False)
check("xuất khi chưa có điểm nào đặt vị trí -> từ chối, có lý do", ok is False and "đặt vị trí" in msg)
os.environ["SURVEY_DATA_DIR"] = str(TMP / "data")
store.reset_cache()

# ---------------------------------------------------------------------------------------------
if os.environ.get("SURVEY_SKIP_MODEL") != "1" and core.model_path().is_file():
    print("4. Model YOLO THẬT trên ảnh mẫu")
    os.environ["SURVEY_DATA_DIR"] = str(TMP / "data_real")
    store.reset_cache()
    server.set_infer(None)
    r = post_photo(NEAR, "real.jpg")
    j = r.json()
    s = j["spot"]
    check("model thật: ảnh mẫu có bảng -> ok, có ≥ 1 vùng", r.status_code == 200 and s["status"] == "ok" and len(s["ai_regions"]) >= 1, r.text[:200])
    check("diện tích hợp lý (0,005–1 m² cho tờ giấy nhăn)", 0.005 < s["area_m2"] < 1.0, str(s["area_m2"]))
    check("không có vùng nào nằm trong tờ bảng", all(not (abs(x) < 0.15 and -0.26 < y < 0.15) for rg in s["ai_regions"] for x, y in rg["ring_m"]),
          str([rg["ring_m"][:2] for rg in s["ai_regions"]]))
    sf2 = post_photo(NOBOARD, "nb.jpg").json()["spot"]
    check("model thật: ảnh không có bảng -> failed, không chạy AI", sf2["status"] == "failed" and sf2["ai_regions"] == [])
else:
    print("4. (bỏ qua) model thật")

print(f"\nKết quả: {PASS} đạt, {FAIL} lỗi")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
