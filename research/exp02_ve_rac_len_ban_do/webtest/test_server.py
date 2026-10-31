"""
Test máy chủ webtest bằng fastapi TestClient (không chạy uvicorn).

  - Thư mục calibration và data trỏ vào scratchpad (WEBTEST_CALIB_DIR / WEBTEST_DATA_DIR) - KHÔNG ghi vào calibration/ chung.
  - infer_trash_mask được thay bằng bản giả trả mask hình vuông 0.3x0.3 m BIẾT TRƯỚC (dựng từ pose đáp án
    outputs/demo_pose_su_thuc.json) để kiểm vị trí/diện tích; riêng 1 test chạy model THẬT (GPU nếu có) trên ảnh Try1.

Mọi request tới /api/* gửi kèm header X-Access-Code (WEBTEST_ACCESS_CODE=123456 đặt trước khi nạp server);
`anon` là client KHÔNG gửi mã, dùng để kiểm 401 / các đường dẫn miễn mã.

Chạy (từ thư mục webtest), một trong hai cách (file này không import pytest nên chạy được cả hai):
  ../../../.venv/Scripts/python.exe -B test_server.py
  ../../../.venv/Scripts/python.exe -B -m pytest test_server.py -q      (cần cài pytest; test_all gọi main())
"""
from __future__ import annotations

import base64
import contextlib
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
EXP_DIR = HERE.parent
SCRATCH = Path(tempfile.gettempdir()) / "webtest_be" / "server_test"
if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
CALIB_DIR = SCRATCH / "calibration"
DATA_DIR = SCRATCH / "data"
CALIB_DIR.mkdir(parents=True)
DATA_DIR.mkdir(parents=True)
os.environ["WEBTEST_CALIB_DIR"] = str(CALIB_DIR)
os.environ["WEBTEST_DATA_DIR"] = str(DATA_DIR)
ACCESS_CODE = "123456"
os.environ["WEBTEST_ACCESS_CODE"] = ACCESS_CODE

sys.path.insert(0, str(EXP_DIR))
sys.path.insert(0, str(HERE))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import config  # noqa: E402
import project_mask as pm  # noqa: E402
import server  # noqa: E402
import store  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[OK]   {name} {detail}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} - {detail}")


client = TestClient(server.app, raise_server_exceptions=False, headers={"X-Access-Code": ACCESS_CODE})
anon = TestClient(server.app, raise_server_exceptions=False)  # KHÔNG gửi mã truy cập
SHARED_CALIB = config.CALIBRATION_DIR
shared_before = sorted(p.name for p in SHARED_CALIB.glob("*"))

DEMO = EXP_DIR / "outputs" / "demo_scene.png"
SYNTH = EXP_DIR / "outputs" / "synthetic_scene.png"
POSE = json.loads((EXP_DIR / "outputs" / "demo_pose_su_thuc.json").read_text(encoding="utf-8"))
LAT0, LON0 = 10.7769, 106.7009


def post_photo(url: str, data: bytes, name="x.png", ctype="image/png", **form):
    return client.post(url, files={"photo": (name, data, ctype)}, data={k: str(v) for k, v in form.items()})


def b64_img(b64: str):
    return cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)


_VI_CHARS = re.compile("[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.IGNORECASE)


def is_error_json(r, status=None):
    try:
        j = r.json()
    except Exception:
        return False
    ok = (j.get("ok") is False and isinstance(j.get("error"), str) and "detail" not in j and "Traceback" not in r.text
          and 400 <= r.status_code < 600 and not _VI_CHARS.search(j["error"]))
    return ok and (status is None or r.status_code == status)


def to_en(lon, lat):
    east = math.radians(lon - LON0) * config.EARTH_RADIUS_M * math.cos(math.radians(LAT0))
    north = math.radians(lat - LAT0) * config.EARTH_RADIUS_M
    return east, north


def ring_centroid_area(ring):
    pts = np.array([to_en(lo, la) for lo, la in ring[:-1]])
    x, y = pts[:, 0], pts[:, 1]
    cr = x * np.roll(y, -1) - np.roll(x, -1) * y
    a = 0.5 * cr.sum()
    cx = ((x + np.roll(x, -1)) * cr).sum() / (6 * a)
    cy = ((y + np.roll(y, -1)) * cr).sum() / (6 * a)
    return (cx, cy), abs(a)


# --- mask đáp án: hình vuông 0.3 x 0.3 m tại (x0, y0) hệ marker, chiếu bằng pose ĐÁP ÁN (siêu lấy mẫu 8x) ---
def truth_mask(x0=0.4, y0=1.0, side=0.3, size=(640, 480), ss=8) -> np.ndarray:
    w, h = size
    R = np.array(POSE["R"]); t = np.array(POSE["t"]); K = np.array(POSE["camera_matrix"])
    hs = side / 2
    obj = np.array([[x0 - hs, y0 - hs, 0], [x0 + hs, y0 - hs, 0], [x0 + hs, y0 + hs, 0], [x0 - hs, y0 + hs, 0]], float)
    rvec, _ = cv2.Rodrigues(R)
    px, _ = cv2.projectPoints(obj, rvec, t.reshape(3, 1), K, np.zeros(5))
    px = px.reshape(-1, 2)
    big = np.zeros((h * ss, w * ss), np.uint8)
    pts = np.round((px + 0.5) * ss - 0.5).astype(np.int32)  # toạ độ pixel gốc -> toạ độ lưới siêu mẫu
    cv2.fillPoly(big, [pts], 255)
    small = cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA)
    return small > 127


def make_fake(mask640):
    def fake(image_bgr):
        h, w = image_bgr.shape[:2]
        m = mask640 if (w, h) == (640, 480) else cv2.resize(mask640.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        ann = image_bgr.copy()
        ann[m] = (0, 0, 255)
        return m, 1, [0.9], ann
    return fake


# ---------------------------------------------------------------------------------------
# Mã truy cập, inbox, calibrate bằng inbox_id, status, /phone (dùng thư mục dữ liệu RIÊNG, khôi phục sau khi xong)
# ---------------------------------------------------------------------------------------
@contextlib.contextmanager
def use_dirs(calib: Path, data: Path):
    calib.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    old = (os.environ.get("WEBTEST_CALIB_DIR"), os.environ.get("WEBTEST_DATA_DIR"))
    os.environ["WEBTEST_CALIB_DIR"], os.environ["WEBTEST_DATA_DIR"] = str(calib), str(data)
    try:
        yield
    finally:
        for k, v in zip(("WEBTEST_CALIB_DIR", "WEBTEST_DATA_DIR"), old):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def jpeg_bytes(w=640, h=480, f35=None, color=(30, 120, 200)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    exif = Image.Exif()
    if f35 is not None:
        exif.get_ifd(0x8769)[0xA405] = f35
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90, exif=exif)
    return buf.getvalue()


def demo_jpeg_with_f35(f35=26) -> bytes:
    im = Image.open(DEMO).convert("RGB")
    exif = Image.Exif()
    exif.get_ifd(0x8769)[0xA405] = f35
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=95, exif=exif)
    return buf.getvalue()


def phone_features() -> None:
    root = SCRATCH / "phone"
    with use_dirs(root / "calibration", root / "data"):
        pdata = root / "data"
        demo_bytes = DEMO.read_bytes()

        # ---------- mã truy cập: 401 / đúng mã / miễn mã ----------
        denied = {"ok": False, "error": "Missing or wrong access code."}
        for method, url in (("get", "/api/status"), ("get", "/api/inbox"), ("get", "/api/calibration"), ("get", "/api/observations"),
                            ("get", "/api/footprint"), ("delete", "/api/observations"), ("get", "/api/khong-co"), ("post", "/api/observe"),
                            ("post", "/api/inbox"), ("post", "/api/calibrate"), ("post", "/api/calibration/save")):
            server._fails.clear()  # mỗi lần kiểm đứng riêng, không chạm giới hạn 10 lần sai
            r = getattr(anon, method)(url)
            check(f"không mã: {method.upper()} {url} -> 401 đúng thông báo", r.status_code == 401 and r.json() == denied, f"{r.status_code} {r.text[:60]}")
        server._fails.clear()  # các lần "không mã" ở trên không được tính vào giới hạn của phần còn lại
        r = anon.get("/api/status", headers={"X-Access-Code": "000000"})
        check("sai mã -> 401", r.status_code == 401 and r.json() == denied)
        r = anon.get("/api/status", headers={"X-Access-Code": ACCESS_CODE + " "})
        check("mã thừa khoảng trắng -> 401 (so khớp tuyệt đối)", r.status_code == 401)
        r = anon.get("/api/status", headers={"X-Access-Code": "mã-tiếng-Việt".encode("utf-8")})
        check("mã có ký tự không phải ASCII -> 401, không lỗi 500", r.status_code == 401 and r.json() == denied, f"{r.status_code}")
        r = anon.get("/api/status", headers={"X-Access-Code": ACCESS_CODE})
        check("đúng mã -> 200", r.status_code == 200 and r.json()["ok"] is True, f"{r.status_code}")
        r = anon.post("/api/calibrate", content=b"--zzz\r\ngarbage-no-end", headers={"content-type": "multipart/form-data; boundary=zzz"})
        check("không mã + body hỏng -> 401 (kiểm mã chạy trước khi đọc body)", r.status_code == 401 and r.json() == denied)
        r = anon.post("/api/calibrate", files={"photo": ("big.jpg", b"\xff\xd8" + b"\0" * (27 * 1024 * 1024), "image/jpeg")})
        check("không mã + body > 26 MB -> 401 (không phải 413)", r.status_code == 401, f"{r.status_code}")
        r = anon.get("/api/health")
        check("/api/health không cần mã", r.status_code == 200 and r.json()["ok"] is True)

        # ---------- giới hạn dò mã: sai quá 10 lần/60 s -> 429, hết cửa sổ thì dùng lại được ----------
        server._fails.clear()
        for _ in range(server.FAIL_LIMIT):
            anon.get("/api/status", headers={"X-Access-Code": "000000"})
        r = anon.get("/api/status", headers={"X-Access-Code": "000000"})
        check("sai mã quá giới hạn -> 429 tiếng Việt", is_error_json(r, 429) and "1 minute" in r.json()["error"], f"{r.status_code} {r.text[:60]}")
        r = anon.get("/api/status", headers={"X-Access-Code": ACCESS_CODE})
        check("  đang bị chặn: mã ĐÚNG cũng 429 (chặn theo địa chỉ)", r.status_code == 429, f"{r.status_code}")
        r = anon.get("/api/health")
        check("  /api/health không bị chặn", r.status_code == 200)
        server._fails["testclient"] = [t - server.FAIL_WINDOW_S - 1 for t in server._fails["testclient"]]
        r = anon.get("/api/status", headers={"X-Access-Code": ACCESS_CODE})
        check("  hết cửa sổ 60 s -> mã đúng dùng lại được", r.status_code == 200, f"{r.status_code}")
        server._fails.clear()

        r = anon.get("/web/%00")
        check("GET /web/%00 (byte NUL) -> 404 JSON, không 500", is_error_json(r, 404), f"{r.status_code}")
        r = anon.get("/web/index.html%00.png")
        check("GET /web/index.html%00.png -> 404 JSON, không 500", is_error_json(r, 404), f"{r.status_code}")

        web = root / "web"
        web.mkdir(exist_ok=True)
        (web / "index.html").write_text("<!doctype html><title>laptop</title>", encoding="utf-8")
        old_web = server.WEB_DIR
        server.WEB_DIR = web
        try:
            r = anon.get("/phone")
            check("GET /phone khi chưa có phone.html -> 404 JSON tiếng Việt (không phải 401)", is_error_json(r, 404) and "phone.html" in r.json()["error"], r.text[:80])
            (web / "phone.html").write_text("<!doctype html><title>dien thoai</title>", encoding="utf-8")
            (web / "app.js").write_text("console.log(1)", encoding="utf-8")
            r = anon.get("/phone")
            check("GET /phone không cần mã -> 200 trả phone.html", r.status_code == 200 and "dien thoai" in r.text, f"{r.status_code}")
            r = anon.get("/")
            check("GET / không cần mã -> 200 trả index.html", r.status_code == 200 and "laptop" in r.text)
            r = anon.get("/web/app.js")
            check("GET /web/* không cần mã -> 200", r.status_code == 200 and "console.log" in r.text)
            r = anon.get("/web/khong-co.js")
            check("GET /web/<không có> -> 404 JSON (không phải 401)", is_error_json(r, 404))
        finally:
            server.WEB_DIR = old_web

        # ---------- mã tự sinh: lưu file, không đổi ----------
        saved_env = os.environ.pop("WEBTEST_ACCESS_CODE")
        try:
            code_file = pdata / "access_code.txt"
            check("chưa có file mã", not code_file.exists())
            c1 = store.get_access_code()
            c2 = store.get_access_code()
            check("mã tự sinh: 6 chữ số, lưu data/access_code.txt, các lần gọi sau giữ nguyên", len(c1) == 6 and c1.isdigit() and c1 == c2
                  and code_file.read_text(encoding="utf-8").strip() == c1, c1)
            r = anon.get("/api/status", headers={"X-Access-Code": c1})
            check("  mã tự sinh dùng được qua header", r.status_code == 200, f"{r.status_code}")
            code_file.write_text("abc", encoding="utf-8")
            c3 = store.get_access_code()
            check("  file mã hỏng -> sinh lại mã 6 số hợp lệ và ghi đè", len(c3) == 6 and c3.isdigit() and code_file.read_text(encoding="utf-8").strip() == c3)
            check("  không còn file .tmp", not list(pdata.glob("*.tmp")))
            os.environ["WEBTEST_ACCESS_CODE"] = "654321"
            check("  env WEBTEST_ACCESS_CODE ghi đè file", store.get_access_code() == "654321")
        finally:
            os.environ["WEBTEST_ACCESS_CODE"] = saved_env

        # ---------- status ban đầu ----------
        r = client.get("/api/status")
        check("status ban đầu: chưa hiệu chỉnh, 0 quan sát, 0 ảnh inbox", r.status_code == 200 and r.json() == {
            "ok": True, "calibrated": False, "observation_count": 0, "latest_observation_id": None,
            "inbox_count": 0, "latest_inbox_id": None}, r.text[:150])
        r = client.get("/api/inbox")
        check("inbox ban đầu rỗng", r.status_code == 200 and r.json() == {"ok": True, "items": []})

        # ---------- inbox: ảnh hợp lệ, giữ nguyên bytes ----------
        raw_exif = demo_jpeg_with_f35(26)
        r = post_photo("/api/inbox", raw_exif, "phone.jpg", "image/jpeg")
        j = r.json()
        iid = j.get("inbox_id", "")
        check("inbox: ảnh JPEG có EXIF -> 200 đúng khoá", r.status_code == 200 and j.get("ok") is True
              and set(j) == {"ok", "inbox_id", "created_at", "size_bytes", "image_size", "has_focal"}
              and len(iid) == 16 and all(c in "0123456789abcdef" for c in iid)
              and j["size_bytes"] == len(raw_exif) and j["image_size"] == [640, 480] and j["has_focal"] is True, str(j)[:150])
        check("  created_at ISO UTC đuôi Z", bool(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", j["created_at"])), j["created_at"])
        bin_p, json_p = pdata / "inbox" / f"{iid}.bin", pdata / "inbox" / f"{iid}.json"
        check("  lưu data/inbox/<id>.bin + .json, bytes GỐC nguyên vẹn (EXIF còn)", bin_p.is_file() and json_p.is_file()
              and bin_p.read_bytes() == raw_exif)
        check("  không còn file .tmp", not list((pdata / "inbox").glob("*.tmp")))
        r = post_photo("/api/inbox", demo_bytes)
        j_png = r.json()
        check("inbox: PNG không EXIF -> has_focal=false", r.status_code == 200 and j_png["has_focal"] is False and j_png["size_bytes"] == len(demo_bytes))
        check("  PNG gốc cũng được giữ nguyên bytes", (pdata / "inbox" / f"{j_png['inbox_id']}.bin").read_bytes() == demo_bytes)
        before = sorted(p.name for p in (pdata / "inbox").glob("*"))
        buf = io.BytesIO(); Image.new("RGB", (40, 40), "red").save(buf, format="GIF")
        for name, data in (("file rác", b"this is not an image"), ("rỗng", b""), ("GIF đội lốt", buf.getvalue()),
                           ("JPEG cụt", raw_exif[: len(raw_exif) // 3])):
            r = post_photo("/api/inbox", data, "x.jpg", "image/jpeg")
            check(f"inbox: {name} -> 400 JSON tiếng Việt, không lưu gì", is_error_json(r, 400)
                  and sorted(p.name for p in (pdata / "inbox").glob("*")) == before, f"{r.status_code} {r.text[:70]}")
        r = client.post("/api/inbox")
        check("inbox: thiếu photo -> 422 JSON", is_error_json(r, 422), r.text[:80])
        r = post_photo("/api/inbox", b"\xff\xd8" + b"\0" * (25 * 1024 * 1024 + 100), "big.jpg", "image/jpeg")
        check("inbox: > 25 MB -> 413 JSON", is_error_json(r, 413), f"{r.status_code}")

        # ---------- GET /api/inbox ----------
        r = client.get("/api/inbox")
        items = r.json()["items"]
        check("GET inbox: mới nhất trước, đúng khoá", r.status_code == 200 and [i["id"] for i in items] == [j_png["inbox_id"], iid]
              and all(set(i) == {"id", "created_at", "size_bytes", "image_size", "has_focal", "thumb_jpg_b64"} for i in items)
              and items[1]["has_focal"] is True and items[0]["has_focal"] is False and items[1]["size_bytes"] == len(raw_exif)
              and items[1]["image_size"] == [640, 480], str([i["id"] for i in items]))
        th = b64_img(items[0]["thumb_jpg_b64"])
        check("  thumb giải mã được, cạnh dài 240 px", th is not None and th.shape[:2] == (180, 240), str(None if th is None else th.shape))
        r = client.get("/api/status")
        check("status sau khi gửi 2 ảnh: inbox_count=2, latest_inbox_id là ảnh mới nhất", r.json()["inbox_count"] == 2
              and r.json()["latest_inbox_id"] == j_png["inbox_id"] and r.json()["calibrated"] is False)

        # ---------- calibrate: photo / inbox_id / cả hai / không có / id sai ----------
        r_up = post_photo("/api/calibrate", raw_exif, "d.jpg", "image/jpeg", marker_size_mm=400)
        r_ib = client.post("/api/calibrate", data={"inbox_id": iid, "marker_size_mm": "400"})
        ju, ji = r_up.json(), r_ib.json()
        check("calibrate bằng photo: 200", r_up.status_code == 200 and ju.get("ok") is True and ju["fov_source"] == "exif", f"{r_up.status_code} {str(ju)[:100]}")
        check("calibrate bằng inbox_id: 200, EXIF FOV được dùng (bytes gốc còn EXIF)", r_ib.status_code == 200 and ji.get("ok") is True
              and ji["fov_source"] == "exif" and abs(ji["fov_deg"] - 79.525) < 0.05 and ji["focal_35mm"] == 26.0, f"{r_ib.status_code} {str(ji)[:100]}")
        cmp_u = {k: v for k, v in ju.items() if k != "calibration_id"}
        cmp_i = {k: v for k, v in ji.items() if k != "calibration_id"}
        check("  kết quả GIỐNG HỆT tải trực tiếp cùng ảnh (trừ calibration_id)", cmp_u == cmp_i and ju["calibration_id"] != ji["calibration_id"])
        check("  pending lưu cho cả hai", (pdata / "pending" / f"{ji['calibration_id']}.json").is_file()
              and (pdata / "pending" / f"{ju['calibration_id']}.json").is_file())
        r = client.post("/api/calibrate", data={"inbox_id": j_png["inbox_id"], "marker_size_mm": "400"})
        jp = r.json()
        check("calibrate bằng inbox_id (PNG không EXIF): fov mặc định + cảnh báo", r.status_code == 200 and jp["fov_source"] == "default"
              and any("Could not read the focal length" in x for x in jp["warnings"]))
        r = post_photo("/api/calibrate", demo_bytes, marker_size_mm=400, inbox_id="")
        check("calibrate: photo + inbox_id rỗng -> coi như chỉ có photo, 200", r.status_code == 200 and r.json()["ok"] is True, f"{r.status_code}")

        both = "Provide exactly one photo: upload a file or pick a phone photo."
        n_pending = len(list((pdata / "pending").glob("*.json")))
        r = post_photo("/api/calibrate", demo_bytes, marker_size_mm=400, inbox_id=iid)
        check("calibrate: cả photo lẫn inbox_id -> 422 đúng thông báo, có side_px_min/overlay null",
              r.status_code == 422 and r.json() == {"ok": False, "error": both, "side_px_min": None, "overlay_jpg_b64": None}, r.text[:150])
        r = client.post("/api/calibrate", data={"marker_size_mm": "400"})
        check("calibrate: không có cái nào -> 422 đúng thông báo", r.status_code == 422 and r.json() == {
            "ok": False, "error": both, "side_px_min": None, "overlay_jpg_b64": None}, r.text[:150])
        r = client.post("/api/calibrate", files={"x": ("a.txt", b"1", "text/plain")})
        check("calibrate: multipart không có photo/inbox_id -> 422 đúng thông báo", r.status_code == 422 and r.json()["error"] == both, r.text[:120])
        missing = "Phone photo not found (expired or deleted). Please send it again."
        for bad in ("0" * 16, "../../x", "không-phải-id", "A" * 16, "f" * 15):
            r = client.post("/api/calibrate", data={"inbox_id": bad, "marker_size_mm": "400"})
            check(f"calibrate: inbox_id sai/không tồn tại ({bad[:16]!r}) -> 404 đúng thông báo",
                  r.status_code == 404 and r.json() == {"ok": False, "error": missing, "side_px_min": None, "overlay_jpg_b64": None}, r.text[:150])
        check("  các lần lỗi không tạo thêm pending", len(list((pdata / "pending").glob("*.json"))) == n_pending)

        # bảng quá nhỏ qua inbox: 422 vẫn mang side_px_min + overlay như cũ
        small_id = post_photo("/api/inbox", SYNTH.read_bytes()).json()["inbox_id"]
        r = client.post("/api/calibrate", data={"inbox_id": small_id, "marker_size_mm": "200"})
        j = r.json()
        check("calibrate bằng inbox_id, bảng quá nhỏ -> 422 có side_px_min + overlay_jpg_b64", r.status_code == 422
              and j["side_px_min"] is not None and 20 < j["side_px_min"] < 45 and isinstance(j["overlay_jpg_b64"], str), f"{r.status_code} {j.get('error')}")
        r = client.post("/api/calibrate", data={"inbox_id": iid, "marker_size_mm": "abc"})
        check("calibrate bằng inbox_id: tham số sai vẫn 422 như cũ", is_error_json(r, 422))

        # ---------- status sau lưu hiệu chỉnh + quan sát ----------
        r = client.post("/api/calibration/save", json={"calibration_id": ji["calibration_id"], "lat": LAT0, "lon": LON0, "azimuth_deg": 0})
        assert r.status_code == 200, r.text
        real_infer = server.infer_trash_mask
        server.infer_trash_mask = make_fake(truth_mask())
        try:
            oid1 = post_photo("/api/observe", demo_bytes).json()["observation_id"]
            oid2 = post_photo("/api/observe", demo_bytes).json()["observation_id"]
        finally:
            server.infer_trash_mask = real_infer
        r = client.get("/api/status")
        j = r.json()
        check("status: calibrated, observation_count=2, latest_observation_id = quan sát cuối", r.status_code == 200 and j["calibrated"] is True
              and j["observation_count"] == 2 and j["latest_observation_id"] == oid2 != oid1 and set(j) == {
                  "ok", "calibrated", "observation_count", "latest_observation_id", "inbox_count", "latest_inbox_id"}, str(j))
        client.delete("/api/observations")
        j = client.get("/api/status").json()
        check("status sau khi xoá quan sát: 0 và latest null", j["observation_count"] == 0 and j["latest_observation_id"] is None)

        # ---------- inbox: tối đa 10 mục, hết hạn > 24 giờ ----------
        shutil.rmtree(pdata / "inbox")
        ids = []
        for i in range(12):
            r = post_photo("/api/inbox", jpeg_bytes(64, 48, color=(i * 10, 50, 50)), "s.jpg", "image/jpeg")
            assert r.status_code == 200, r.text
            ids.append(r.json()["inbox_id"])
        items = client.get("/api/inbox").json()["items"]
        on_disk = {p.stem for p in (pdata / "inbox").glob("*.bin")}
        check("inbox giữ tối đa 10 mục mới nhất (bỏ 2 cũ nhất, xoá cả file)", [i["id"] for i in items] == ids[:1:-1] and on_disk == set(ids[2:])
              and {p.stem for p in (pdata / "inbox").glob("*.json")} == set(ids[2:]), f"n={len(items)}")
        j = client.get("/api/status").json()
        check("  status: inbox_count=10, latest_inbox_id = ảnh cuối", j["inbox_count"] == 10 and j["latest_inbox_id"] == ids[-1])
        r = client.post("/api/calibrate", data={"inbox_id": ids[0]})
        check("  mục đã bị loại -> calibrate 404", r.status_code == 404 and r.json()["error"] == missing)

        t_old = time.time() - 25 * 3600
        for suffix in (".json", ".bin"):
            os.utime(pdata / "inbox" / f"{ids[5]}{suffix}", (t_old, t_old))
        items = client.get("/api/inbox").json()["items"]
        check("inbox: mục > 24 giờ biến mất (GET), file bị xoá", ids[5] not in [i["id"] for i in items] and len(items) == 9
              and not (pdata / "inbox" / f"{ids[5]}.bin").exists() and not (pdata / "inbox" / f"{ids[5]}.json").exists())
        for suffix in (".json", ".bin"):
            os.utime(pdata / "inbox" / f"{ids[6]}{suffix}", (t_old, t_old))
        r = client.post("/api/calibrate", data={"inbox_id": ids[6]})
        check("  mục hết hạn -> calibrate 404 đúng thông báo", r.status_code == 404 and r.json()["error"] == missing)
        j = client.get("/api/status").json()
        check("  status phản ánh đã hết hạn (inbox_count=8)", j["inbox_count"] == 8, str(j["inbox_count"]))
        orphan = pdata / "inbox" / ("e" * 16 + ".bin")
        orphan.write_bytes(b"orphan")
        os.utime(orphan, (t_old, t_old))
        client.get("/api/inbox")
        check("  .bin mồ côi quá cũ bị dọn", not orphan.exists())
        check("  không còn file .tmp trong inbox", not list((pdata / "inbox").glob("*.tmp")))


def main() -> int:
    demo_bytes = DEMO.read_bytes()

    # ---------------- cơ bản ----------------
    r = client.get("/api/health")
    j = r.json()
    check("health ban đầu", r.status_code == 200 and j == {"ok": True, "model_loaded": False, "calibrated": False}, str(j))
    r = client.get("/api/footprint")
    check("footprint không calibration_id, chưa có hiệu chỉnh đã lưu -> 404 JSON", is_error_json(r, 404), r.text[:80])
    r = client.get("/api/calibration")
    check("GET calibration khi chưa có", r.status_code == 200 and r.json() == {"ok": False, "error": "Not calibrated"})
    r = post_photo("/api/observe", demo_bytes)
    check("observe chưa hiệu chỉnh -> 409", r.status_code == 409 and r.json() == {"ok": False, "error": "Camera not calibrated"})

    # ---------------- upload rác ----------------
    r = post_photo("/api/calibrate", b"this is not an image at all", "evil.jpg", "image/jpeg")
    j = r.json()
    check("calibrate: file rác -> 422 JSON, side_px_min/overlay = null", is_error_json(r, 422)
          and j["side_px_min"] is None and j["overlay_jpg_b64"] is None, f"{r.status_code} {r.text[:80]}")
    r = post_photo("/api/observe", b"this is not an image at all", "evil.jpg", "image/jpeg")
    check("observe: chưa hiệu chỉnh + file rác -> 4xx JSON", r.status_code == 409 or is_error_json(r, 400))
    r = post_photo("/api/calibrate", b"", "empty.png")
    check("calibrate: file rỗng -> 422 JSON (side_px_min null)", is_error_json(r, 422) and r.json()["side_px_min"] is None)
    buf = io.BytesIO(); Image.new("RGB", (40, 40), "red").save(buf, format="GIF")
    r = post_photo("/api/calibrate", buf.getvalue(), "a.png", "image/png")
    check("calibrate: GIF đội lốt png -> 422", is_error_json(r, 422) and r.json()["overlay_jpg_b64"] is None, r.text[:80])
    r = client.post("/api/calibrate", data={"marker_size_mm": "250"})
    check("calibrate: thiếu photo -> 422 JSON (không có 'detail')", is_error_json(r, 422), r.text[:100])
    r = post_photo("/api/calibrate", demo_bytes, marker_size_mm="abc")
    check("calibrate: marker_size_mm không phải số -> 422", is_error_json(r, 422))
    r = post_photo("/api/calibrate", demo_bytes, marker_size_mm=400, fov_deg=0)
    check("calibrate: fov_deg=0 -> 422", is_error_json(r, 422))
    r = post_photo("/api/calibrate", b"\xff\xd8" + b"\0" * (25 * 1024 * 1024 + 100), "big.jpg", "image/jpeg")
    check("upload > 25 MB -> 413 JSON", is_error_json(r, 413) and "side_px_min" in r.json(), f"{r.status_code}")
    r = post_photo("/api/calibrate", b"\xff\xd8" + b"\0" * (27 * 1024 * 1024), "big2.jpg", "image/jpeg")
    check("upload > 26 MB bị chặn theo Content-Length -> 413 JSON", is_error_json(r, 413), f"{r.status_code}")
    r = client.get("/api/khong-co")
    check("đường dẫn lạ -> 404 JSON", is_error_json(r, 404))
    r = client.post("/api/calibrate", content=b"--zzz\r\ngarbage-no-end", headers={"content-type": "multipart/form-data; boundary=zzz"})
    check("calibrate: body multipart hỏng -> JSON tiếng Việt, có side_px_min/overlay", is_error_json(r) and "parsing" not in r.text
          and "side_px_min" in r.json(), f"{r.status_code} {r.text[:100]}")
    r = client.post("/api/observe", content=b"--zzz\r\ngarbage", headers={"content-type": "multipart/form-data; boundary=zzz"})
    check("observe: body multipart hỏng -> JSON tiếng Việt", is_error_json(r) and "parsing" not in r.text, f"{r.status_code} {r.text[:100]}")
    r = client.post("/api/calibration/save", content=b"[1,2]", headers={"content-type": "application/json"})
    check("save: JSON không phải đối tượng -> tiếng Việt", is_error_json(r, 422) and "JSON object" in r.json()["error"], r.text[:100])
    r = client.post("/api/calibrate", content=b"x", headers={"content-type": "text/plain"})
    check("calibrate: sai content-type -> JSON tiếng Việt", is_error_json(r), r.text[:100])
    r = client.put("/api/health")
    check("sai phương thức -> 405 JSON", is_error_json(r, 405))
    for method, url, kw in (("get", "/api/footprint?lat=abc", {}), ("post", "/api/calibration/save", {"content": b"[]", "headers": {"content-type": "application/json"}}),
                            ("delete", "/api/calibrate", {}), ("get", "/api/observe", {}), ("post", "/api/observe", {})):
        r = getattr(client, method)(url, **kw)
        check(f"{method.upper()} {url}: lỗi tham số/phương thức/body -> JSON {{ok:false,error}} (không 'detail')", is_error_json(r), f"{r.status_code} {r.text[:70]}")

    # ---------------- calibrate ----------------
    r = post_photo("/api/calibrate", SYNTH.read_bytes(), marker_size_mm=200)
    j = r.json()
    check("calibrate synthetic_scene (~30 px) -> 422", r.status_code == 422 and j["ok"] is False
          and j["side_px_min"] is not None and 20 < j["side_px_min"] < 45 and "overlay_jpg_b64" in j,
          f"{r.status_code} side={j.get('side_px_min')} err={j.get('error')}")
    check("  thông báo cỡ bảng 1 chữ số thập phân, không làm tròn lên 50", "minimum 50.0 px" in j["error"]
          and f"{math.floor(j['side_px_min'] * 10) / 10:.1f} px" in j["error"], j["error"])
    check("  ... không lưu gì (pending rỗng, chưa có WEB-DEMO.json)",
          not list((DATA_DIR / "pending").glob("*.json")) and not (CALIB_DIR / "WEB-DEMO.json").exists())
    blank = np.full((480, 640, 3), 255, np.uint8)
    ok, enc = cv2.imencode(".png", blank)
    r = post_photo("/api/calibrate", enc.tobytes(), marker_size_mm=200)
    j = r.json()
    check("calibrate ảnh trắng (không có bảng) -> 422 JSON", r.status_code == 422 and j["ok"] is False
          and j["side_px_min"] is None and j["overlay_jpg_b64"] is None, j.get("error", ""))

    r = post_photo("/api/calibrate", demo_bytes, marker_size_mm=400)
    j = r.json()
    check("calibrate demo_scene (400 mm, ~59 px) -> 200", r.status_code == 200 and j.get("ok") is True, f"{r.status_code} {str(j)[:100]}")
    cid = j["calibration_id"]
    check("  khoá/kiểu trả về đúng hợp đồng",
          len(cid) == 16 and all(c in "0123456789abcdef" for c in cid)
          and set(j) == {"ok", "calibration_id", "side_px_min", "side_px_mean", "fov_deg", "fov_source", "focal_35mm", "warnings",
                         "camera_height_m_est", "image_size", "overlay_jpg_b64"}
          and j["image_size"] == [640, 480] and j["fov_source"] == "default" and j["focal_35mm"] is None and abs(j["fov_deg"] - 66.0) < 1e-9
          and 55 < j["side_px_min"] < 63 and abs(j["camera_height_m_est"] - 1.5) < 0.15 and isinstance(j["warnings"], list)
          and any("Could not read the focal length from the photo" in x and "70–85°" in x for x in j["warnings"]),
          f"side={j['side_px_min']:.1f} H={j['camera_height_m_est']:.3f} warn={j['warnings']}")
    ov = b64_img(j["overlay_jpg_b64"])
    check("  overlay giải mã được, đúng cỡ", ov is not None and ov.shape == (480, 640, 3))
    b, g, rr = ov[..., 0].astype(int), ov[..., 1].astype(int), ov[..., 2].astype(int)
    green = (g > 150) & (b < 90) & (rr < 90)
    blue = (b > 180) & (g < 80) & (rr < 80)
    red = (rr > 180) & (g < 80) & (b < 80)
    check("  overlay có viền xanh lá + mũi tên +Y xanh dương + +X đỏ", green.sum() > 50 and blue.sum() > 30 and red.sum() > 30,
          f"green={green.sum()} blue={blue.sum()} red={red.sum()}")
    gy, gx = np.nonzero(green); by, bx = np.nonzero(blue); ry, rx = np.nonzero(red)
    check("  +Y hướng LÊN ảnh, +X hướng PHẢI (đúng hướng bảng trong ảnh demo)",
          by.mean() < gy.mean() - 5 and rx.mean() > gx.mean() + 5, f"blue_y={by.mean():.0f} green_y={gy.mean():.0f} red_x={rx.mean():.0f} green_x={gx.mean():.0f}")
    pend_file = DATA_DIR / "pending" / f"{cid}.json"
    check("  pending đã lưu", pend_file.is_file())

    r = post_photo("/api/calibrate", demo_bytes, marker_size_mm=400, fov_deg=80)
    j2 = r.json()
    check("calibrate với fov_deg=80 -> fov_source input", r.status_code == 200 and j2["fov_source"] == "input" and j2["fov_deg"] == 80.0)

    # EXIF f35=26 -> ~79.5 độ ; và EXIF orientation=6 (ảnh lưu xoay) vẫn được xoay lại đúng
    im = Image.open(DEMO).convert("RGB")
    exif = Image.Exif()
    exif.get_ifd(0x8769)[0xA405] = 26
    buf = io.BytesIO(); im.save(buf, format="JPEG", quality=95, exif=exif.tobytes() if False else exif)
    r = post_photo("/api/calibrate", buf.getvalue(), "e.jpg", "image/jpeg", marker_size_mm=400)
    j3 = r.json()
    check("calibrate EXIF f35=26 -> fov_source exif, ~79.5 độ", r.status_code == 200 and j3.get("fov_source") == "exif"
          and abs(j3["fov_deg"] - 79.525) < 0.05 and j3["focal_35mm"] == 26.0, f"{r.status_code} {j3.get('fov_source')} {j3.get('fov_deg')}")
    exif2 = Image.Exif(); exif2[0x0112] = 6   # hiển thị = xoay 90 độ thuận chiều kim đồng hồ
    rot = im.transpose(Image.ROTATE_90)       # xoay ngược chiều kim đồng hồ -> ảnh lưu 480x640
    buf = io.BytesIO(); rot.save(buf, format="JPEG", quality=95, exif=exif2)
    r = post_photo("/api/calibrate", buf.getvalue(), "o.jpg", "image/jpeg", marker_size_mm=400)
    j4 = r.json()
    check("calibrate ảnh lưu xoay + EXIF orientation=6 -> xoay lại đúng (640x480)", r.status_code == 200 and j4.get("image_size") == [640, 480],
          f"{r.status_code} {j4.get('image_size')} {j4.get('error')}")

    # ảnh lớn bị thu nhỏ về cạnh dài 2048
    big = cv2.resize(cv2.imread(str(DEMO)), (3200, 2400), interpolation=cv2.INTER_CUBIC)
    ok, enc = cv2.imencode(".png", big)
    r = post_photo("/api/calibrate", enc.tobytes(), marker_size_mm=400)
    jb = r.json()
    check("calibrate ảnh 3200x2400 -> thu nhỏ còn 2048x1536, vẫn giải được", r.status_code == 200 and jb.get("image_size") == [2048, 1536]
          and abs(jb["camera_height_m_est"] - 1.5) < 0.15, f"{r.status_code} {jb.get('image_size')} H={jb.get('camera_height_m_est')}")
    ob = b64_img(jb["overlay_jpg_b64"])
    check("  overlay ảnh lớn có cạnh dài <= 1000 px", max(ob.shape[:2]) <= 1000, str(ob.shape))

    # ---------------- footprint ----------------
    r = client.get("/api/footprint", params={"calibration_id": cid, "lat": LAT0, "lon": LON0, "azimuth_deg": 0})
    j = r.json()
    kinds = [f["properties"]["kind"] for f in j.get("features", [])]
    check("footprint: FeatureCollection 3 feature đúng loại", r.status_code == 200 and j.get("type") == "FeatureCollection"
          and kinds == ["footprint", "marker", "camera"], str(kinds))
    fp, mk, cam = j["features"]
    ring = fp["geometry"]["coordinates"][0]
    check("  polygon khép kín, [lon,lat]", fp["geometry"]["type"] == "Polygon" and ring[0] == ring[-1] and len(ring) >= 5
          and all(abs(p[0] - LON0) < 0.01 and abs(p[1] - LAT0) < 0.01 for p in ring))
    check("  marker tại lat/lon", mk["geometry"]["coordinates"] == [LON0, LAT0])
    ce, cn = to_en(*cam["geometry"]["coordinates"])
    check("  camera cách marker ~2 m về phía Nam (azimuth 0), cao ~1.5 m",
          abs(ce) < 0.2 and abs(cn + 2.0) < 0.2 and abs(cam["properties"]["height_m"] - 1.5) < 0.15,
          f"E={ce:.2f} N={cn:.2f} H={cam['properties']['height_m']:.2f}")
    r = client.get("/api/footprint", params={"calibration_id": cid, "lat": LAT0, "lon": LON0, "azimuth_deg": 90})
    cam90 = r.json()["features"][2]
    ce, cn = to_en(*cam90["geometry"]["coordinates"])
    check("  azimuth 90: camera ở phía TÂY marker", abs(ce + 2.0) < 0.2 and abs(cn) < 0.2, f"E={ce:.2f} N={cn:.2f}")
    areas = {}
    for mr in (1, 3, 12, 1000, -5):
        r = client.get("/api/footprint", params={"calibration_id": cid, "lat": LAT0, "lon": LON0, "azimuth_deg": 0, "max_range_m": mr})
        ringm = [to_en(*p) for p in r.json()["features"][0]["geometry"]["coordinates"][0][:-1]]
        areas[mr] = abs(pm._ring_area(np.array(ringm)))
    check("  max_range_m kẹp 1..50 (1000 == 50, -5 == 1) và đơn điệu", r.status_code == 200 and areas[1000] >= areas[12] >= areas[3] >= areas[1]
          and abs(areas[-5] - areas[1]) < 1e-9, str({k: round(v, 2) for k, v in areas.items()}))
    r = client.get("/api/footprint", params={"calibration_id": "0" * 16, "lat": LAT0, "lon": LON0, "azimuth_deg": 0})
    check("  calibration_id không tồn tại -> 404 JSON", is_error_json(r, 404))
    r = client.get("/api/footprint", params={"calibration_id": "../../x", "lat": LAT0, "lon": LON0, "azimuth_deg": 0})
    check("  calibration_id kiểu đường dẫn -> 404 JSON", is_error_json(r, 404))
    r = client.get("/api/footprint", params={"calibration_id": cid, "lat": 123, "lon": LON0, "azimuth_deg": 0})
    check("  lat ngoài khoảng -> 422 JSON", is_error_json(r, 422))
    r = client.get("/api/footprint", params={"calibration_id": cid, "lat": "abc", "lon": LON0})
    check("  lat không phải số -> 422 JSON", is_error_json(r, 422))

    # ---------------- save / get ----------------
    for body, status in (({"calibration_id": cid, "lat": 91, "lon": LON0, "azimuth_deg": 0}, 422),
                         ({"calibration_id": cid, "lat": LAT0, "lon": 181, "azimuth_deg": 0}, 422),
                         ({"calibration_id": cid, "lat": LAT0, "lon": LON0}, 422),
                         ({"calibration_id": "f" * 16, "lat": LAT0, "lon": LON0, "azimuth_deg": 0}, 404)):
        r = client.post("/api/calibration/save", json=body)
        check(f"save sai đầu vào {list(body.values())[1:3]} -> {status}", is_error_json(r, status), f"{r.status_code} {r.text[:80]}")
    r = client.post("/api/calibration/save", content=b"{not json", headers={"content-type": "application/json"})
    check("save: JSON sai cú pháp -> 422 tiếng Việt cụ thể", is_error_json(r, 422) and "JSON" in r.json()["error"]
          and "Expecting" not in r.text and "decode" not in r.text.lower(), r.text[:100])
    check("  các lần save lỗi không tạo file", not (CALIB_DIR / "WEB-DEMO.json").exists())

    r = client.post("/api/calibration/save", json={"calibration_id": cid, "lat": LAT0, "lon": LON0, "azimuth_deg": 390})
    check("save hợp lệ (azimuth 390 -> 30)", r.status_code == 200 and r.json() == {"ok": True, "camera_id": "WEB-DEMO"}, r.text[:100])
    saved = json.loads((CALIB_DIR / "WEB-DEMO.json").read_text(encoding="utf-8"))
    need = {"camera_id", "marker_latlon", "R", "t", "camera_matrix", "image_size", "reproj_error_rms_px", "created_at",
            "source", "quality", "azimuth_deg", "diagonal_fov_deg"}
    check("  WEB-DEMO.json đủ khoá, source webtest, azimuth 30, FOV 66", need <= set(saved) and saved["source"] == "webtest"
          and saved["camera_id"] == "WEB-DEMO" and saved["azimuth_deg"] == 30.0 and saved["diagonal_fov_deg"] == 66.0
          and saved["marker_latlon"] == [LAT0, LON0] and saved["image_size"] == [640, 480])
    check("  không còn file .tmp", not list(CALIB_DIR.glob("*.tmp")))
    r = client.get("/api/calibration")
    c = r.json().get("calibration", {})
    check("GET calibration sau khi lưu", r.status_code == 200 and r.json()["ok"] is True and c.get("camera_id") == "WEB-DEMO"
          and c["marker_latlon"] == [LAT0, LON0] and c["azimuth_deg"] == 30.0 and c["fov_deg"] == 66.0
          and c["image_size"] == [640, 480] and 55 < c["side_px_min"] < 63 and c["created_at"], str(c)[:150])
    check("health: calibrated = true", client.get("/api/health").json()["calibrated"] is True)
    good_text = (CALIB_DIR / "WEB-DEMO.json").read_text(encoding="utf-8")
    (CALIB_DIR / "WEB-DEMO.json").write_text("{hong", encoding="utf-8")
    check("file hiệu chỉnh hỏng: health.calibrated=false, GET calibration 'Chưa có hiệu chỉnh', observe 409, footprint 404",
          client.get("/api/health").json()["calibrated"] is False
          and client.get("/api/calibration").json() == {"ok": False, "error": "Not calibrated"}
          and post_photo("/api/observe", demo_bytes).status_code == 409
          and client.get("/api/footprint").status_code == 404)
    (CALIB_DIR / "WEB-DEMO.json").write_text('{"camera_id": "WEB-DEMO"}', encoding="utf-8")
    check("file hiệu chỉnh thiếu khoá: health.calibrated=false", client.get("/api/health").json()["calibrated"] is False)
    (CALIB_DIR / "WEB-DEMO.json").write_text(good_text, encoding="utf-8")

    # footprint từ hiệu chỉnh ĐÃ LƯU (không truyền calibration_id)
    r = client.get("/api/footprint")
    j = r.json()
    cam_s = j["features"][2]["geometry"]["coordinates"] if r.status_code == 200 else None
    ce, cn = to_en(*cam_s) if cam_s else (9, 9)
    # azimuth đã lưu = 30: camera nằm ở (0,-2) hệ marker -> E=-2*sin30=-1, N=-2*cos30=-1.732
    check("footprint không có calibration_id: dùng hiệu chỉnh đã lưu (lat/lon/azimuth từ file)", r.status_code == 200
          and abs(ce + 1.0) < 0.2 and abs(cn + 1.732) < 0.2 and j["features"][1]["geometry"]["coordinates"] == [LON0, LAT0],
          f"{r.status_code} E={ce:.2f} N={cn:.2f}")
    r = client.get("/api/footprint", params={"azimuth_deg": 0, "lat": LAT0, "lon": LON0})
    ce, cn = to_en(*r.json()["features"][2]["geometry"]["coordinates"])
    check("  query ghi đè azimuth đã lưu", r.status_code == 200 and abs(ce) < 0.2 and abs(cn + 2.0) < 0.2)

    # ---------------- observe với model giả: vị trí / diện tích BIẾT TRƯỚC ----------------
    mask = truth_mask()
    true_px_area = int(mask.sum())
    real_infer = server.infer_trash_mask
    server.infer_trash_mask = make_fake(mask)
    try:
        sq = (0.4, 1.0)
        for az in (0.0, 30.0):
            r = client.post("/api/calibration/save", json={"calibration_id": cid, "lat": LAT0, "lon": LON0, "azimuth_deg": az})
            assert r.status_code == 200
            r = post_photo("/api/observe", demo_bytes)
            j = r.json()
            check(f"observe (model giả) azimuth {az:g}: 200 đúng khoá", r.status_code == 200 and j.get("ok") is True
                  and {"observation_id", "captured_at", "n_instances", "regions", "total_area_m2", "annotated_jpg_b64",
                       "inference_ms", "image_size", "warnings", "dropped_points"} <= set(j), f"{r.status_code} {str(j)[:100]}")
            feats = j["regions"]["features"]
            import re as _re
            check("  captured_at dạng ISO UTC có hậu tố Z", bool(_re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", j["captured_at"])), j["captured_at"])
            check("  1 vùng Polygon, properties đúng", len(feats) == 1 and feats[0]["geometry"]["type"] == "Polygon"
                  and set(feats[0]["properties"]) == {"area_m2", "area_px", "confidence", "kind", "idx", "y_m", "x_m"}
                  and feats[0]["properties"]["kind"] == "trash" and feats[0]["properties"]["confidence"] == 0.9
                  and feats[0]["properties"]["area_px"] == true_px_area, str(feats[0]["properties"]))
            pr = feats[0]["properties"]
            check(f"  Y/X ghi trong vùng khớp đáp án trong hệ bảng (azimuth {az:g}): Y≈{sq[1]}, X≈{sq[0]}, idx=1",
                  pr["idx"] == 1 and abs(pr["y_m"] - sq[1]) <= 0.05 and abs(pr["x_m"] - sq[0]) <= 0.05, f"Y={pr['y_m']} X={pr['x_m']}")
            check("  n_regions = 1, tổng m² = diện tích vùng, không có khoá board_regions_ignored", j.get("n_regions") == 1
                  and "board_regions_ignored" not in j and abs(j["total_area_m2"] - pr["area_m2"]) < 1e-9)
            (cx, cy), area = ring_centroid_area(feats[0]["geometry"]["coordinates"][0])
            ex, ey = pm.marker_xy_to_enu(sq[0], sq[1], az)
            dist = math.hypot(cx - ex, cy - ey)
            check(f"  tâm vùng lệch <= 0.05 m so với đáp án (azimuth {az:g})", dist <= 0.05,
                  f"lệch {dist * 100:.1f} cm; tâm ({cx:.3f},{cy:.3f}) đáp án ({ex:.3f},{ey:.3f})")
            ta = j["total_area_m2"]
            check(f"  diện tích trong ±5% của 0.09 m² (azimuth {az:g})", abs(ta - 0.09) <= 0.0045 and abs(feats[0]["properties"]["area_m2"] - ta) < 1e-9,
                  f"{ta:.4f} m² ({(ta / 0.09 - 1) * 100:+.1f}%)")
            check("  diện tích polygon trả về khớp area_m2 (shoelace GeoJSON)", abs(area - ta) / ta < 0.02, f"{area:.4f} vs {ta:.4f}")
            check("  annotated giải mã được; image_size; n_instances; warnings rỗng; dropped 0",
                  b64_img(j["annotated_jpg_b64"]) is not None and j["image_size"] == [640, 480] and j["n_instances"] == 1
                  and j["warnings"] == [] and j["dropped_points"] == 0 and j["inference_ms"] >= 0)

        # cùng tỉ lệ, kích thước khác (1280x960): vẫn chiếu đúng
        up = cv2.resize(cv2.imread(str(DEMO)), (1280, 960), interpolation=cv2.INTER_CUBIC)
        ok, enc = cv2.imencode(".jpg", up)
        r = post_photo("/api/observe", enc.tobytes(), "up.jpg", "image/jpeg")
        j = r.json()
        feats = j.get("regions", {}).get("features", [])
        (cx, cy), _ = ring_centroid_area(feats[0]["geometry"]["coordinates"][0]) if feats else ((9, 9), 0)
        ex, ey = pm.marker_xy_to_enu(*sq, 30.0)
        check("observe ảnh 1280x960 (cùng tỉ lệ) -> đúng vị trí/diện tích", r.status_code == 200 and j["image_size"] == [1280, 960]
              and math.hypot(cx - ex, cy - ey) <= 0.05 and abs(j["total_area_m2"] - 0.09) <= 0.0045,
              f"{r.status_code} lệch {math.hypot(cx - ex, cy - ey) * 100:.1f} cm, {j.get('total_area_m2')}")

        # khác tỉ lệ khung hình -> 422
        sq_img = cv2.resize(cv2.imread(str(DEMO)), (640, 640))
        ok, enc = cv2.imencode(".png", sq_img)
        r = post_photo("/api/observe", enc.tobytes())
        check("observe ảnh vuông (khác tỉ lệ 4:3) -> 422 có thông báo rõ", is_error_json(r, 422)
              and "same aspect ratio" in r.json()["error"], r.text[:120])

        # model không thấy gì
        server.infer_trash_mask = lambda im: (np.zeros(im.shape[:2], bool), 0, [], im)
        r = post_photo("/api/observe", demo_bytes)
        j = r.json()
        check("observe model không thấy rác -> ok, regions rỗng, cảnh báo", r.status_code == 200 and j["ok"] is True
              and j["regions"]["features"] == [] and j["total_area_m2"] == 0 and j["n_instances"] == 0
              and j["warnings"] == ["No trash detected in the image."], str(j.get("warnings")))

        # lỗi bất ngờ trong model -> 500 JSON không lộ traceback
        def boom(im):
            raise RuntimeError("secret internals")
        server.infer_trash_mask = boom
        r = post_photo("/api/observe", demo_bytes)
        check("lỗi model bất ngờ -> 500 JSON, không lộ traceback", is_error_json(r, 500) and "secret" not in r.text, r.text[:100])
    finally:
        server.infer_trash_mask = real_infer

    # ---------------- observations ----------------
    r = client.get("/api/observations")
    obs = r.json()["observations"]
    check("GET observations (cũ -> mới), captured_at đuôi Z, không chứa ảnh base64", r.status_code == 200 and len(obs) == 4
          and all(o["captured_at"].endswith("Z") for o in obs)
          and [o["captured_at"] for o in obs] == sorted(o["captured_at"] for o in obs)
          and all(set(o) == {"id", "captured_at", "received_at", "processed_at", "processing_ms", "calibration_created_at",
                             "n_instances", "n_regions", "total_area_m2", "regions"} for o in obs)
          and all(o["processed_at"].endswith("Z") and len(o["processed_at"]) == 24 and o["processing_ms"] >= 0 for o in obs)
          and "b64" not in json.dumps(obs), f"n={len(obs)}")
    for i in range(55):
        store.add_observation({"id": f"x{i}", "captured_at": "2026-01-01T00:00:00+00:00", "n_instances": 0, "total_area_m2": 0.0,
                               "regions": {"type": "FeatureCollection", "features": []}})
    obs = client.get("/api/observations").json()["observations"]
    check("giữ tối đa 50 quan sát mới nhất", len(obs) == 50 and obs[-1]["id"] == "x54")
    r = client.delete("/api/observations")
    check("DELETE observations", r.status_code == 200 and r.json() == {"ok": True}
          and client.get("/api/observations").json() == {"ok": True, "observations": []})

    # ---------------- dọn pending ----------------
    pdir = DATA_DIR / "pending"
    old = pdir / ("a" * 16 + ".json")
    old.write_text("{}", encoding="utf-8")
    t_old = time.time() - 25 * 3600
    os.utime(old, (t_old, t_old))
    for i in range(25):
        store.save_pending(f"{i:016x}", {"id": i})
    n_left = len(list(pdir.glob("*.json")))
    check("pending: xoá > 24h, giữ tối đa 20", not old.exists() and n_left <= 20, f"còn {n_left}")

    # ---------------- trang tĩnh ----------------
    r = client.get("/")
    check("GET / : 200 (có index.html) hoặc 404 JSON rõ ràng (chưa có)", r.status_code == 200 or is_error_json(r, 404), f"{r.status_code}")
    r = client.get("/web/%2e%2e/server.py")
    check("/web/ chặn thoát thư mục", r.status_code in (404, 400) and "uvicorn" not in r.text)

    # ---------------- mã truy cập, inbox, calibrate bằng inbox_id, status, /phone ----------------
    phone_features()

    # ---------------- observe THẬT (model, GPU nếu có) trên ảnh Try1 ----------------
    stem = config.DEMO_LABELED_IMAGE_STEM
    src = config.DATASET_TEST_IMAGES_DIR / f"{stem}.jpg"
    img = cv2.imread(str(src))
    small = cv2.resize(img, (640, 480), interpolation=cv2.INTER_AREA)
    ok, enc = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 92])
    t0 = time.time()
    r = post_photo("/api/observe", enc.tobytes(), "real.jpg", "image/jpeg")
    j = r.json()
    check("observe model THẬT (Try1 resize 640x480): 200, luồng đủ khoá", r.status_code == 200 and j.get("ok") is True
          and j["image_size"] == [640, 480] and isinstance(j["regions"]["features"], list)
          and b64_img(j["annotated_jpg_b64"]) is not None and j["inference_ms"] > 0,
          f"{r.status_code} n_inst={j.get('n_instances')} regions={len(j.get('regions', {}).get('features', []))} "
          f"area={j.get('total_area_m2')} infer={j.get('inference_ms')} ms, tổng {time.time() - t0:.1f}s, warnings={j.get('warnings')}")
    check("  health: model_loaded = true sau khi chạy", client.get("/api/health").json()["model_loaded"] is True)
    r2 = post_photo("/api/observe", enc.tobytes(), "real.jpg", "image/jpeg")
    j2 = r2.json()
    check("  lần 2 (đã nóng) trả cùng số instance", r2.status_code == 200 and j2["n_instances"] == j["n_instances"],
          f"infer={j2.get('inference_ms')} ms")

    # ---------------- không ghi vào calibration/ chung ----------------
    shared_after = sorted(p.name for p in SHARED_CALIB.glob("*"))
    check("không ghi gì vào calibration/ chung", shared_before == shared_after, str(shared_after))

    print(f"\nTổng: {PASS} đạt, {FAIL} hỏng")
    return 0 if FAIL == 0 else 1


def test_all():  # điểm vào cho pytest
    assert main() == 0, f"{FAIL} kiểm tra hỏng (xem log ở trên, chạy pytest -s)"


if __name__ == "__main__":
    sys.exit(main())
