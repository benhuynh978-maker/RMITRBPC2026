"""
Test phòng camera (cam.py) bằng fastapi TestClient, có chạy model THẬT trên ảnh mẫu trong lab_samples/.

Chạy (từ thư mục này; không cần pytest):
  python -B test_cam_api.py

Dữ liệu ghi vào một thư mục tạm NGOÀI repo (xoá khi xong). Mã truy cập và khoá dưới đây chỉ dùng cho test, không phải mã thật.

Kiểm: cấu hình (tắt khi không đặt, từ chối cấu hình thiếu / khoá ngắn / thư mục trong repo); đăng nhập, token (hết hạn, tối đa), không token thì không đọc được gì;
ingest (khoá riêng; chỉ JPEG; ảnh bom điểm ảnh không bị giải mã; quá lớn/quá nhỏ; lỗi đĩa); lưu NGUYÊN BYTE ảnh gốc + ảnh khoanh + JSON;
hiệu chỉnh tạm -> hiệu chỉnh thật từ khung hình; vẽ vùng rác; phân trang; chống đường dẫn lạ; song song; CORS; mọi ghi đĩa chỉ nằm trong thư mục dữ liệu;
phòng thử cũ (lab) vẫn KHÔNG ghi đĩa.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CODE = "test-code-123456"
KEY = "test-ingest-key-0123456789abcdef"
DATA_DIR = Path(tempfile.mkdtemp(prefix="cleansight_cam_test_"))

# Phải đặt biến môi trường của phòng camera TRƯỚC khi nạp server (test_demo_api nạp server khi import).
os.environ["CLEANSIGHT_CAM_ACCESS_CODE"] = CODE
os.environ["CLEANSIGHT_CAM_INGEST_KEY"] = KEY
os.environ["CLEANSIGHT_CAM_DATA_DIR"] = str(DATA_DIR)

import test_demo_api as base  # noqa: E402  (đặt CLEANSIGHT_ALLOWED_ORIGINS trước khi nạp server)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import cam  # noqa: E402
import lab  # noqa: E402
import server  # noqa: E402

ORIGIN = base.ORIGIN
SAMPLES = HERE / "lab_samples"
PASS = FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[OK]   {name} {detail}".rstrip())
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}".rstrip())


def jpeg_bytes(w: int, h: int, color=(128, 128, 128), quality=80) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def main() -> int:
    trash = (SAMPLES / "board-trash.jpg").read_bytes()
    board = (SAMPLES / "board-near.jpg").read_bytes()

    # ---------------- cấu hình ----------------
    check("cấu hình: không đặt gì -> tắt (None)", cam.load_settings({}) is None)
    for name, env in (("chỉ có mã", {"CLEANSIGHT_CAM_ACCESS_CODE": CODE}), ("chỉ có khoá", {"CLEANSIGHT_CAM_INGEST_KEY": KEY})):
        try:
            cam.load_settings(env)
            check(f"cấu hình thiếu một nửa ({name}) bị từ chối", False)
        except RuntimeError:
            check(f"cấu hình thiếu một nửa ({name}) bị từ chối", True)
    for name, env in (("khoá quá ngắn", {"CLEANSIGHT_CAM_ACCESS_CODE": CODE, "CLEANSIGHT_CAM_INGEST_KEY": "short"}),
                      ("mã quá ngắn", {"CLEANSIGHT_CAM_ACCESS_CODE": "ab", "CLEANSIGHT_CAM_INGEST_KEY": KEY}),
                      ("thư mục dữ liệu nằm trong repo", {"CLEANSIGHT_CAM_ACCESS_CODE": CODE, "CLEANSIGHT_CAM_INGEST_KEY": KEY,
                                                           "CLEANSIGHT_CAM_DATA_DIR": str(cam.REPO_ROOT / "camdata")})):
        try:
            cam.load_settings(env)
            check(f"cấu hình sai ({name}) bị từ chối", False)
        except RuntimeError:
            check(f"cấu hình sai ({name}) bị từ chối", True)
    check("thư mục dữ liệu của bài test nằm ngoài repo", not str(DATA_DIR.resolve()).startswith(str(cam.REPO_ROOT.resolve())), str(DATA_DIR))
    default_dir = cam.load_settings({"CLEANSIGHT_CAM_ACCESS_CODE": CODE, "CLEANSIGHT_CAM_INGEST_KEY": KEY}).data_dir
    check("thư mục dữ liệu mặc định ~/CleanSightCamData (ngoài repo)", default_dir.name == "CleanSightCamData" and default_dir.parent == Path.home().resolve())

    with TestClient(server.app) as c:
        H = {"Origin": ORIGIN}

        def login(code=CODE):
            return c.post("/api/cam/login", headers=H, json={"code": code})

        def ingest(raw: bytes, key=KEY, headers=None):
            h = {"Content-Type": "image/jpeg", "Origin": ORIGIN}
            if key is not None:
                h["X-Cam-Key"] = key
            h.update(headers or {})
            return c.post("/api/cam/ingest", content=raw, headers=h)

        # ---------------- đăng nhập / token ----------------
        r = c.get("/api/cam/latest", headers=H)
        check("không có token: 401 unauthorized, đúng dạng {ok:false,error,code}", r.status_code == 401 and r.json() == {
            "ok": False, "error": "Access code required.", "code": "unauthorized"}, str(r.json()))
        for path in ("/api/cam/frames", "/api/cam/calibration", "/api/cam/footprint", "/api/cam/frames/20260101T000000000000Z",
                     "/api/cam/frames/20260101T000000000000Z/image"):
            check(f"không có token: {path.split('/api/cam/')[1][:22]} -> 401", c.get(path, headers=H).status_code == 401)
        check("token sai -> 401", c.get("/api/cam/latest", headers={**H, "X-Cam-Token": "x" * 43}).status_code == 401)
        r = login("sai-roi")
        check("đăng nhập sai mã: 401 bad_code, không lộ token", r.status_code == 401 and r.json()["code"] == "bad_code" and "token" not in r.json())
        check("đăng nhập thiếu mã / sai kiểu: 401", c.post("/api/cam/login", headers=H, json={}).status_code == 401
              and c.post("/api/cam/login", headers=H, json={"code": 12345}).status_code == 401
              and c.post("/api/cam/login", headers=H, json={"code": CODE + "x"}).status_code == 401)
        r = login()
        TOKEN = r.json().get("token", "")
        check("đăng nhập đúng: 200, có token", r.status_code == 200 and r.json()["ok"] and len(TOKEN) >= 40)
        T = {**H, "X-Cam-Token": TOKEN}
        # theo yêu cầu: KHÔNG giới hạn số lần thử mã
        codes = [login(f"sai-{i}").status_code for i in range(60)]
        check("không giới hạn lần thử mã (60 lần sai đều 401, không 429)", set(codes) == {401}, str(set(codes)))
        check("sau 60 lần sai, mã đúng vẫn vào được", login().status_code == 200)
        # hết hạn
        r2 = login()
        t2 = r2.json()["token"]
        server.app.state.cam_tokens[t2] = time.monotonic() - 1
        check("token hết hạn bị từ chối", c.get("/api/cam/latest", headers={**H, "X-Cam-Token": t2}).status_code == 401)
        first = login().json()["token"]
        for _ in range(cam.MAX_TOKENS + 5):
            login()
        check(f"tối đa {cam.MAX_TOKENS} token (token cũ nhất bị bỏ)", len(server.app.state.cam_tokens) <= cam.MAX_TOKENS
              and c.get("/api/cam/latest", headers={**H, "X-Cam-Token": first}).status_code == 401)
        TOKEN = login().json()["token"]
        T = {**H, "X-Cam-Token": TOKEN}

        # ---------------- trạng thái ban đầu: hiệu chỉnh tạm ----------------
        r = c.get("/api/cam/latest", headers=T).json()
        check("chưa có khung: frame=None, hiệu chỉnh TẠM (provisional)", r["ok"] and r["frame"] is None and r["calibration"]["provisional"] is True, r["calibration"]["source"][:40])
        cal_file = DATA_DIR / "calibration.json"
        check("hiệu chỉnh tạm được lưu bền ra đĩa (trong thư mục dữ liệu)", cal_file.is_file() and json.loads(cal_file.read_text())["provisional"] is True)
        check("hiệu chỉnh tạm lấy từ ảnh bảng mẫu (cạnh ~146 px)", 140 < r["calibration"]["side_px_min"] < 150, f"{r['calibration']['side_px_min']:.1f}")

        # ---------------- ingest: xác thực và kiểm tra đầu vào ----------------
        n_before = len(list((DATA_DIR / "frames").rglob("*.json")))
        check("ingest không có khoá: 401 bad_key", ingest(trash, key=None).status_code == 401)
        r = ingest(trash, key="sai")
        check("ingest sai khoá: 401 bad_key, không lưu gì", r.status_code == 401 and r.json()["code"] == "bad_key" and not list((DATA_DIR / "frames").rglob("*.jpg")))
        check("ingest bằng token đăng nhập (không phải khoá): 401", ingest(trash, key=TOKEN).status_code == 401)
        check("ingest rỗng: 400", ingest(b"").status_code == 400)
        buf = io.BytesIO()
        Image.new("RGB", (200, 200)).save(buf, "PNG")
        check("ingest PNG: 415 unsupported_type", ingest(buf.getvalue()).status_code == 415)
        check("ingest văn bản: 415", ingest(b"hello world").status_code == 415)
        check("ingest JPEG hỏng: 400 invalid_image", ingest(b"\xff\xd8\xff" + b"junk" * 20).json().get("code") == "invalid_image")
        check("ingest ảnh quá nhỏ (32x32): 422 too_small", ingest(jpeg_bytes(32, 32)).json().get("code") == "too_small")
        calls = []
        real_imdecode = cv2.imdecode
        cv2.imdecode = lambda *a, **k: (calls.append(1), real_imdecode(*a, **k))[1]
        try:
            bomb = jpeg_bytes(7000, 7000)
            r = ingest(bomb)
        finally:
            cv2.imdecode = real_imdecode
        check("ảnh bom điểm ảnh (7000x7000): 422 too_large, KHÔNG giải mã", r.status_code == 422 and r.json()["code"] == "too_large" and not calls, f"{len(bomb)} byte")
        real_max = cam.MAX_INGEST_BYTES
        cam.MAX_INGEST_BYTES = 1000
        try:
            r = ingest(trash)
        finally:
            cam.MAX_INGEST_BYTES = real_max
        check("ingest quá lớn: 413 too_big", r.status_code == 413 and r.json()["code"] == "too_big")
        check("các lần ingest bị từ chối không để lại file nào", len(list((DATA_DIR / "frames").rglob("*"))) == n_before == 0)

        # ---------------- luồng chính: ingest -> lưu -> vẽ rác ----------------
        with base.WriteMonitor() as mon:
            r = ingest(trash)
            j = r.json()
            fid = j.get("id", "")
            r_latest = c.get("/api/cam/latest", headers=T)
            r_img = c.get(f"/api/cam/frames/{fid}/image", headers=T)
            r_ann = c.get(f"/api/cam/frames/{fid}/image?kind=annotated", headers=T)
        check("ingest ảnh có rác: 200, analysed, có vùng rác", r.status_code == 200 and j["ok"] and j["status"] == "analysed" and j["n_regions"] >= 1
              and 0.05 < j["total_area_m2"] < 0.5, f"{j.get('n_regions')} vùng, {j.get('total_area_m2')} m²")
        check("mọi lần ghi đĩa của ingest nằm trong thư mục dữ liệu (không ghi chỗ khác)", len(mon.events) > 0 and all(str(DATA_DIR) in e for e in mon.events),
              f"{len(mon.events)} lần ghi; ngoài: {[e for e in mon.events if str(DATA_DIR) not in e][:2]}")
        check("không có file tạm sót lại (.tmp)", not list(DATA_DIR.rglob("*.tmp")))
        day = DATA_DIR / "frames" / fid[:8]
        orig_path, ann_path, json_path = day / f"{fid}.jpg", day / f"{fid}.ann.jpg", day / f"{fid}.json"
        check("ảnh gốc lưu NGUYÊN BYTE", orig_path.is_file() and orig_path.read_bytes() == trash)
        ann = cv2.imdecode(np.frombuffer(ann_path.read_bytes(), np.uint8), cv2.IMREAD_COLOR) if ann_path.is_file() else None
        orig_img = cv2.imdecode(np.frombuffer(trash, np.uint8), cv2.IMREAD_COLOR)
        check("ảnh khoanh được lưu, giải mã được, cùng kích thước ảnh gốc", ann is not None and ann.shape == orig_img.shape)
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        check("JSON: id, thời điểm nhận, kích thước, trạng thái, cờ hiệu chỉnh tạm", meta["id"] == fid and meta["width"] == orig_img.shape[1]
              and meta["height"] == orig_img.shape[0] and meta["bytes"] == len(trash) and meta["provisional_calibration"] is True
              and meta["received_at"].endswith("Z") and meta["has_annotated"] is True and meta["inference_ms"] > 0)
        check("JSON: vùng rác là GeoJSON, có toạ độ so với tâm bảng (Y/X)", meta["regions"]["type"] == "FeatureCollection"
              and len(meta["regions"]["features"]) == meta["n_regions"] and "area_m2" in meta["regions"]["features"][0]["properties"])
        check("/latest trả đúng khung vừa gửi (kèm vùng) và hiệu chỉnh tạm", r_latest.json()["frame"]["id"] == fid and r_latest.json()["frame"]["regions"]["features"]
              and r_latest.json()["calibration"]["provisional"] is True)
        check("tải ảnh gốc qua API: đúng byte, image/jpeg", r_img.status_code == 200 and r_img.content == trash and r_img.headers["content-type"] == "image/jpeg")
        check("tải ảnh khoanh qua API: JPEG", r_ann.status_code == 200 and r_ann.content[:3] == b"\xff\xd8\xff")
        check("không phản hồi nào lộ mã truy cập hay khoá ingest", CODE not in r_latest.text and KEY not in r_latest.text and CODE not in json_path.read_text())

        # ---------------- danh sách, phân trang ----------------
        ids = [fid]
        for _ in range(2):
            ids.append(ingest(trash).json()["id"])
        check("id tăng dần theo thời gian gửi", ids == sorted(ids) and len(set(ids)) == 3, str(ids[-1]))
        r = c.get("/api/cam/frames?limit=2", headers=T).json()
        check("danh sách: mới nhất trước, limit=2, có next_before, KHÔNG kèm regions", [f["id"] for f in r["frames"]] == [ids[2], ids[1]] and r["next_before"] == ids[1]
              and all("regions" not in f for f in r["frames"]))
        r = c.get(f"/api/cam/frames?limit=2&before={r['next_before']}", headers=T).json()
        check("trang kế (before): còn đúng 1 khung cũ nhất, hết trang", [f["id"] for f in r["frames"]] == [ids[0]] and r["next_before"] is None)
        check("/latest = khung gửi sau cùng", c.get("/api/cam/latest", headers=T).json()["frame"]["id"] == ids[2])
        check("danh sách: limit lạ bị chặn trong khoảng cho phép, before sai định dạng: 422", c.get("/api/cam/frames?limit=100000", headers=T).status_code == 200
              and c.get("/api/cam/frames?before=../x", headers=T).status_code == 422)
        # sang ngày khác: danh sách vẫn đúng thứ tự (thư mục theo ngày)
        old_day = DATA_DIR / "frames" / "20200101"
        old_day.mkdir()
        old_meta = {**meta, "id": "20200101T120000000000Z"}
        (old_day / "20200101T120000000000Z.json").write_text(json.dumps(old_meta))
        r = c.get("/api/cam/frames?limit=10", headers=T).json()
        check("nhiều thư mục ngày: khung ngày cũ nằm cuối, thứ tự giảm dần", [f["id"] for f in r["frames"]] == [ids[2], ids[1], ids[0], "20200101T120000000000Z"])
        shutil.rmtree(old_day)

        # ---------------- chống đường dẫn lạ ----------------
        for bad in ("..%2F..%2Fcalibration.json", "%2e%2e", "20260101T000000000000Z%00", "nope", "../../etc/passwd"):
            rr = c.get(f"/api/cam/frames/{bad}", headers=T)
            ri = c.get(f"/api/cam/frames/{bad}/image", headers=T)
            check(f"id lạ {bad[:22]!r}: 404 (không đọc file ngoài)", rr.status_code == 404 and ri.status_code in (404,))
        check("kind lạ: 422; khung không tồn tại: 404", c.get(f"/api/cam/frames/{ids[0]}/image?kind=../../x", headers=T).status_code == 422
              and c.get("/api/cam/frames/20260101T000000000000Z", headers=T).status_code == 404)

        # ---------------- ảnh khác tỉ lệ so với hiệu chỉnh ----------------
        img = cv2.imdecode(np.frombuffer(trash, np.uint8), cv2.IMREAD_COLOR)
        small43 = cv2.imencode(".jpg", cv2.resize(img, (1200, 900)))[1].tobytes()
        r = ingest(small43)
        m = c.get(f"/api/cam/frames/{r.json()['id']}", headers=T).json()["frame"]
        check("khung khác tỉ lệ hiệu chỉnh: lưu + khoanh, KHÔNG đặt lên bản đồ, có cảnh báo rõ", r.status_code == 200 and m["status"] == "aspect_mismatch"
              and m["has_annotated"] and m["n_regions"] == 0 and any("aspect ratio" in w for w in m["warnings"]))

        # ---------------- hàng chờ đầy: giữ ảnh gốc, bỏ qua phân tích ----------------
        saved_pending = server._pending
        server._pending = server.MAX_WAITING + 1
        try:
            r = ingest(trash)
        finally:
            server._pending = saved_pending
        m = c.get(f"/api/cam/frames/{r.json()['id']}", headers=T).json()["frame"]
        check("model bận: 200, status busy, ảnh gốc vẫn được lưu, chưa có ảnh khoanh", r.status_code == 200 and m["status"] == "busy" and not m["has_annotated"]
              and (DATA_DIR / "frames" / m["id"][:8] / f"{m['id']}.jpg").read_bytes() == trash and any("not analysed" in w for w in m["warnings"]))

        # ---------------- lỗi đĩa ----------------
        n_json = len(list((DATA_DIR / "frames").rglob("*.json")))
        real_write = cam._atomic_write

        def failing(path, data):
            raise OSError("disk full")
        cam._atomic_write = failing
        try:
            r = ingest(trash)
        finally:
            cam._atomic_write = real_write
        check("lỗi ghi đĩa: 507 storage_failed rõ ràng, không xoá gì, không thêm khung dở", r.status_code == 507 and r.json()["code"] == "storage_failed"
              and len(list((DATA_DIR / "frames").rglob("*.json"))) == n_json and not list(DATA_DIR.rglob("*.tmp")))

        # ---------------- hiệu chỉnh thật từ khung hình của camera ----------------
        gray = ingest(jpeg_bytes(1280, 720)).json()["id"]
        r = c.post("/api/cam/calibration/detect", headers=T, json={"frame_id": "latest"})
        check("khung không có bảng: 422 board_not_found", r.status_code == 422 and r.json()["code"] == "board_not_found", str(r.json().get("error", ""))[:60])
        check("dò bảng với id khung lạ: 404", c.post("/api/cam/calibration/detect", headers=T, json={"frame_id": "../../x"}).status_code == 404
              and c.post("/api/cam/calibration/detect", headers=T, json={"frame_id": "20260101T000000000000Z"}).status_code == 404)
        ingest(board)
        r = c.post("/api/cam/calibration/detect", headers=T, json={"frame_id": "latest", "marker_size_mm": 250})
        d = r.json()
        check("khung có bảng: dò được, cạnh ~146 px, có overlay và calibration_id", r.status_code == 200 and 140 < d["side_px_min"] < 150 and d["overlay_jpg_b64"] and len(d["calibration_id"]) == 16)
        r = c.post("/api/cam/calibration/detect", headers=T, json={"frame_id": "latest", "marker_size_mm": "abc"})
        check("cạnh bảng không phải số: 422", r.status_code == 422)
        r = c.get(f"/api/cam/footprint?calibration_id={d['calibration_id']}&lat=10.77&lon=106.70&azimuth_deg=30", headers=T)
        check("xem trước vùng camera thấy (chưa lưu): 3 feature footprint/marker/camera", r.status_code == 200 and [f["properties"]["kind"] for f in r.json()["features"]] == ["footprint", "marker", "camera"])
        check("lưu hiệu chỉnh thiếu vị trí: 422; sai id: 404", c.post("/api/cam/calibration/save", headers=T, json={"calibration_id": d["calibration_id"]}).status_code == 422
              and c.post("/api/cam/calibration/save", headers=T, json={"calibration_id": "x" * 16, "lat": 10, "lon": 106, "azimuth_deg": 0}).status_code == 404)
        r = c.post("/api/cam/calibration/save", headers=T, json={"calibration_id": d["calibration_id"], "lat": 10.77, "lon": 106.70, "azimuth_deg": 370})
        sc = r.json().get("calibration", {})
        check("lưu hiệu chỉnh thật: provisional=false, azimuth chuẩn hoá 370->10, ghi rõ nguồn là khung camera", r.status_code == 200 and sc["provisional"] is False
              and abs(sc["azimuth_deg"] - 10.0) < 1e-9 and "camera frame" in sc["source"])
        check("hiệu chỉnh thật được lưu bền (đọc lại từ file)", json.loads(cal_file.read_text())["provisional"] is False
              and c.get("/api/cam/calibration", headers=T).json()["calibration"]["marker_latlon"] == [10.77, 106.70])
        r = ingest(trash)
        m = c.get(f"/api/cam/frames/{r.json()['id']}", headers=T).json()["frame"]
        check("khung sau hiệu chỉnh thật: provisional_calibration=false, vẫn vẽ vùng rác", m["provisional_calibration"] is False and m["status"] == "analysed" and m["n_regions"] >= 1)
        r = c.get("/api/cam/footprint", headers=T)
        check("footprint của hiệu chỉnh đã lưu: 200", r.status_code == 200 and len(r.json()["features"]) == 3)
        check("khung cũ giữ nguyên cờ hiệu chỉnh tạm của nó (không bị sửa ngầm)", c.get(f"/api/cam/frames/{ids[0]}", headers=T).json()["frame"]["provisional_calibration"] is True)

        # ---------------- gửi song song ----------------
        with ThreadPoolExecutor(3) as ex:
            res = list(ex.map(lambda _: ingest(trash), range(3)))
        pids = [x.json().get("id") for x in res]
        check("3 ảnh gửi cùng lúc: đều 200, id khác nhau, JSON không hỏng", all(x.status_code == 200 for x in res) and len(set(pids)) == 3
              and all(c.get(f"/api/cam/frames/{p}", headers=T).status_code == 200 for p in pids), str([x.json().get("status") for x in res]))

        # ---------------- CORS ----------------
        pre = c.options("/api/cam/latest", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-cam-token"})
        check("CORS: preflight cho header X-Cam-Token từ origin của site", pre.status_code == 200 and "x-cam-token" in pre.headers.get("access-control-allow-headers", "").lower())
        pre = c.options("/api/cam/latest", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-cam-token"})
        check("CORS: origin lạ bị từ chối preflight", pre.status_code == 400 and "access-control-allow-origin" not in pre.headers)

        # ---------------- phòng thử cũ vẫn KHÔNG ghi đĩa ----------------
        HL = {"X-Lab-Session": "L" * 24, "Origin": ORIGIN}
        with base.WriteMonitor() as mon:
            d = c.post("/api/lab/board/detect", headers=HL, json={"sample_id": "board-near", "marker_size_mm": 250}).json()
            c.post("/api/lab/board/calibration/save", headers=HL, json={"calibration_id": d["calibration_id"], "lat": 10.7769, "lon": 106.7009, "azimuth_deg": 0})
            ro = c.post("/api/lab/board/observe", headers=HL, json={"sample_id": "board-trash"})
        check("phòng thử cũ (lab) sau khi thêm phòng camera: vẫn chạy và KHÔNG ghi đĩa", ro.status_code == 200 and mon.events == [], str(mon.events[:2]))

    shutil.rmtree(DATA_DIR, ignore_errors=True)
    print(f"\nTổng: {PASS} đạt, {FAIL} hỏng")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(DATA_DIR, ignore_errors=True)
