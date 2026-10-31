"""
Test dịch vụ CleanSight live demo (server.py) bằng fastapi TestClient (không mở cổng thật). Có chạy model THẬT.

Chạy (từ thư mục này; không cần pytest):
  python -B test_demo_api.py

Kiểm những điều dịch vụ đã cam kết: định dạng/kích thước/ảnh hỏng bị từ chối đúng mã, ảnh bom điểm ảnh KHÔNG bị giải mã,
giới hạn tần suất (kể cả chống giả mạo X-Forwarded-For), CORS chỉ cho origin được phép, không ghi gì ra đĩa,
không log IP, khởi động thất bại khi thiếu/ sai cấu hình CORS, trả đúng bộ khoá (không có độ tin cậy).
Ảnh mẫu lấy từ cleansight-site-v2/public/img/samples/ (ảnh của đội).
"""
from __future__ import annotations

import base64
import builtins
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SAMPLES = ROOT / "cleansight-site-v2" / "public" / "img" / "samples"
ORIGIN = "https://cleansight-test.netlify.app"
OTHER_ORIGIN = "https://evil.example.com"
os.environ["CLEANSIGHT_ALLOWED_ORIGINS"] = f"{ORIGIN},http://localhost:5180"

sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
import cv2  # noqa: E402
from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402

PASS = FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[OK]   {name} {detail}".rstrip())
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}".rstrip())


def jpeg_bytes(img: Image.Image, quality: int = 90, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, **kw)
    return buf.getvalue()


def fmt_bytes(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def decode_data_url(url: str):
    assert url.startswith("data:image/jpeg;base64,")
    arr = np.frombuffer(base64.b64decode(url.split(",", 1)[1]), dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


class WriteMonitor:
    """Ghi lại mọi lần mở file ở chế độ GHI, tạo file tạm và cv2.imwrite trong khối `with`."""

    def __init__(self):
        self.events: list[str] = []

    def __enter__(self):
        self._open, self._io_open = builtins.open, io.open
        self._imwrite = cv2.imwrite
        self._tmp = {n: getattr(tempfile, n) for n in ("SpooledTemporaryFile", "NamedTemporaryFile", "TemporaryFile", "mkstemp", "mkdtemp")}
        monitor = self

        def wrap_open(real):
            def _open(file, mode="r", *a, **k):
                if isinstance(mode, str) and any(c in mode for c in "wax+"):
                    monitor.events.append(f"open({file!r}, {mode!r})")
                return real(file, mode, *a, **k)
            return _open

        builtins.open = wrap_open(self._open)
        io.open = wrap_open(self._io_open)
        cv2.imwrite = lambda *a, **k: (monitor.events.append("cv2.imwrite"), self._imwrite(*a, **k))[1]
        for name, real in self._tmp.items():
            setattr(tempfile, name, (lambda real=real, name=name: lambda *a, **k: (monitor.events.append(f"tempfile.{name}"), real(*a, **k))[1])())
        return self

    def __exit__(self, *exc):
        builtins.open, io.open, cv2.imwrite = self._open, self._io_open, self._imwrite
        for name, real in self._tmp.items():
            setattr(tempfile, name, real)


def main() -> int:
    litter = Image.open(SAMPLES / "litter.jpg").convert("RGB")
    drain = Image.open(SAMPLES / "drain.jpg").convert("RGB")
    litter_bytes = (SAMPLES / "litter.jpg").read_bytes()

    generous = server.RateLimiter(10_000, 100_000, 100_000)
    server.limiter = generous

    with TestClient(server.app) as client:

        def post(body: bytes, ctype: str = "image/jpeg", headers: dict | None = None):
            h = {"Content-Type": ctype, "Origin": ORIGIN}
            h.update(headers or {})
            return client.post("/api/analyze", content=body, headers=h)

        # ---------------- health, cấu hình, CORS ----------------
        r = client.get("/api/health", headers={"Origin": ORIGIN})
        check("health: 200, status ok, ready", r.status_code == 200 and r.json() == {"status": "ok", "ready": True}, str(r.json()))
        check("health: CORS cho origin được phép", r.headers.get("access-control-allow-origin") == ORIGIN)
        r2 = client.get("/api/health", headers={"Origin": OTHER_ORIGIN})
        check("health: KHÔNG có CORS cho origin lạ", "access-control-allow-origin" not in r2.headers)
        pre = client.options("/api/analyze", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        check("preflight: origin được phép -> 200 + cho Content-Type", pre.status_code == 200 and pre.headers.get("access-control-allow-origin") == ORIGIN
              and "content-type" in pre.headers.get("access-control-allow-headers", "").lower(), str(dict(pre.headers)))
        pre2 = client.options("/api/analyze", headers={"Origin": OTHER_ORIGIN, "Access-Control-Request-Method": "POST"})
        check("preflight: origin lạ bị từ chối", pre2.status_code >= 400 and "access-control-allow-origin" not in pre2.headers, str(pre2.status_code))
        check("header: Cache-Control no-store + nosniff", r.headers.get("cache-control") == "no-store" and r.headers.get("x-content-type-options") == "nosniff")
        d = client.get("/docs")
        check("/docs và /openapi.json đã tắt (JSON lỗi, không lộ schema)", d.status_code == 404 and client.get("/openapi.json").status_code == 404 and "code" in d.json())
        m = client.get("/api/analyze")
        check("GET /api/analyze -> 405 dạng JSON", m.status_code == 405 and m.json().get("code") == "http_405", str(m.json()))

        # ---------------- ảnh hợp lệ (có theo dõi ghi đĩa + log) ----------------
        out_buf, err_buf = io.StringIO(), io.StringIO()
        with WriteMonitor() as mon, contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            t0 = time.time()
            r = post(litter_bytes, headers={"X-Forwarded-For": "203.0.113.77"})
            dt = time.time() - t0
            r_png = post(fmt_bytes(litter, "PNG"), "image/png", {"X-Forwarded-For": "203.0.113.77"})
            r_bad = post(b"not an image", headers={"X-Forwarded-For": "203.0.113.77"})
        j = r.json()
        check("JPEG hợp lệ: 200", r.status_code == 200, f"{dt:.2f}s")
        check("JPEG: đúng 4 khoá, KHÔNG có độ tin cậy", set(j) == {"waste_pct", "level_index", "drain_pct", "annotated_jpg"}, str(sorted(j)))
        check("JPEG: rác ~2,7% mức Low, không thấy cống", 1.5 <= j["waste_pct"] <= 4.0 and j["level_index"] == 0 and j["drain_pct"] is None, f"{j['waste_pct']} {j['level_index']} {j['drain_pct']}")
        ann = decode_data_url(j["annotated_jpg"])
        check("JPEG: ảnh khoanh giải mã được, đúng kích thước 1280x720", ann is not None and ann.shape[:2] == (720, 1280), str(None if ann is None else ann.shape))
        check("PNG hợp lệ: 200 và cùng khoá", r_png.status_code == 200 and set(r_png.json()) == set(j))
        check("ảnh hỏng: 400 invalid_image", r_bad.status_code == 400 and r_bad.json()["code"] == "invalid_image")
        check("KHÔNG ghi gì ra đĩa khi xử lý ảnh (open ghi, tempfile, imwrite)", mon.events == [], str(mon.events[:5]))
        logged = out_buf.getvalue() + err_buf.getvalue()
        check("không log IP hay nội dung ảnh", "203.0.113.77" not in logged and "testclient" not in logged and "base64" not in logged, repr(logged[:120]))

        # ---------------- ảnh cống: model không thấy ----------------
        rd = post((SAMPLES / "drain.jpg").read_bytes())
        jd = rd.json()
        check("ảnh có cống: 200, rác dưới ngưỡng, cống = null (không phải 0)", rd.status_code == 200 and jd["drain_pct"] is None and jd["level_index"] == -1, str({k: jd[k] for k in ("waste_pct", "level_index", "drain_pct")}))

        # ---------------- PNG có alpha, xoay EXIF, ảnh lớn ----------------
        rgba = Image.new("RGBA", (640, 360), (0, 0, 0, 0))
        rgba.paste(litter.resize((320, 180)), (100, 90))
        ra = post(fmt_bytes(rgba, "PNG"), "image/png")
        check("PNG có alpha: 200", ra.status_code == 200, str(ra.json().get("code", "")))

        exif = Image.Exif()
        exif[0x0112] = 6  # xoay 90° theo chiều kim đồng hồ khi hiển thị
        rr = post(jpeg_bytes(litter.resize((640, 360)), exif=exif))
        a2 = decode_data_url(rr.json()["annotated_jpg"]) if rr.status_code == 200 else None
        check("EXIF orientation=6: ảnh được xoay (360 rộng x 640 cao)", a2 is not None and a2.shape[:2] == (640, 360), str(None if a2 is None else a2.shape))

        big = litter.resize((3200, 1800), Image.LANCZOS)
        rb = post(jpeg_bytes(big))
        a3 = decode_data_url(rb.json()["annotated_jpg"]) if rb.status_code == 200 else None
        check("ảnh 3200x1800 được thu về cạnh dài 1600", a3 is not None and max(a3.shape[:2]) == 1600, str(None if a3 is None else a3.shape))

        # ---------------- ảnh/định dạng bị từ chối ----------------
        small = Image.new("RGB", (640, 360), (200, 200, 200))
        cases = [
            ("GIF", fmt_bytes(small, "GIF"), "image/jpeg", 415, "unsupported_type"),
            ("WebP", fmt_bytes(small, "WEBP"), "image/jpeg", 415, "unsupported_type"),
            ("BMP", fmt_bytes(small, "BMP"), "image/jpeg", 415, "unsupported_type"),
            ("văn bản đổi tên thành ảnh", b"hello world, definitely not a jpeg", "image/jpeg", 400, "invalid_image"),
            ("Content-Type sai (text/plain)", litter_bytes, "text/plain", 415, "unsupported_type"),
            ("thân rỗng", b"", "image/jpeg", 400, "invalid_image"),
            ("JPEG bị cắt cụt", litter_bytes[: len(litter_bytes) // 2], "image/jpeg", 400, "invalid_image"),
            ("ảnh quá nhỏ 10x10", jpeg_bytes(Image.new("RGB", (10, 10), (128, 128, 128))), "image/jpeg", 422, "too_small"),
            ("ảnh quá tối", jpeg_bytes(Image.fromarray(np.full((480, 640, 3), 4, dtype=np.uint8))), "image/jpeg", 422, "too_dark"),
        ]
        for name, body, ctype, status, code in cases:
            rr = post(body, ctype)
            ok = rr.status_code == status and rr.json().get("code") == code
            check(f"từ chối {name}: {status} {code}", ok, f"-> {rr.status_code} {rr.json().get('code')}")

        r413 = post(b"\xff\xd8" + os.urandom(server.MAX_BODY_BYTES + 10))
        check("thân > 8 MB: 413 too_big", r413.status_code == 413 and r413.json()["code"] == "too_big", str(r413.status_code))

        # ---------------- ảnh "bom" điểm ảnh: không được giải mã ----------------
        bomb = fmt_bytes(Image.new("1", (8000, 8000)), "PNG")  # 64 MP, nén rất nhỏ
        loads = []
        real_load = Image.Image.load
        Image.Image.load = lambda self, *a, **k: (loads.append(1), real_load(self, *a, **k))[1]
        try:
            t0 = time.time()
            rbomb = post(bomb, "image/png")
            dt = time.time() - t0
        finally:
            Image.Image.load = real_load
        check("PNG 64 MP: 422 too_large", rbomb.status_code == 422 and rbomb.json()["code"] == "too_large", f"{len(bomb)//1024} KB, {dt:.2f}s")
        check("PNG 64 MP: KHÔNG giải mã điểm ảnh (load() không được gọi)", loads == [], str(len(loads)))

        # ---------------- hàng chờ, sẵn sàng ----------------
        server._pending = server.MAX_WAITING + 1
        rbusy = post(litter_bytes)
        server._pending = 0
        check("quá tải hàng chờ: 503 busy + Retry-After", rbusy.status_code == 503 and rbusy.json()["code"] == "busy" and rbusy.headers.get("retry-after") == "5", str(rbusy.status_code))
        server._ready = False
        rnr = post(litter_bytes)
        server._ready = True
        check("model chưa sẵn sàng: 503 not_ready", rnr.status_code == 503 and rnr.json()["code"] == "not_ready")

        # ---------------- 5 yêu cầu song song ----------------
        server.MAX_WAITING = 10

        def one(_):
            with TestClient(server.app) as c:  # client riêng cho mỗi luồng
                return c.post("/api/analyze", content=litter_bytes, headers={"Content-Type": "image/jpeg", "Origin": ORIGIN}).status_code

        t0 = time.time()
        with ThreadPoolExecutor(5) as pool:
            codes = list(pool.map(one, range(5)))
        check("5 yêu cầu song song: đều 200, xếp hàng không sập", codes == [200] * 5 and server._pending == 0, f"{codes} {time.time()-t0:.1f}s")
        server.MAX_WAITING = 3

        # ---------------- giới hạn tần suất ----------------
        server.limiter = server.RateLimiter(2, 50, 100)
        codes = [post(b"x", headers={"X-Forwarded-For": "1.1.1.1"}).status_code for _ in range(3)]
        r429 = post(b"x", headers={"X-Forwarded-For": "1.1.1.1"})
        check("tần suất: 2 lượt/phút/IP, lượt 3 bị 429", codes == [400, 400, 429], str(codes))
        check("429: có Retry-After là số giây > 0 và mã rate_limited", r429.json()["code"] == "rate_limited" and int(r429.headers["retry-after"]) > 0, r429.headers.get("retry-after", ""))
        check("429: Retry-After được khai báo cho trình duyệt đọc (expose-headers)", "retry-after" in r429.headers.get("access-control-expose-headers", "").lower(), r429.headers.get("access-control-expose-headers", ""))
        check("IP khác vẫn được phép", post(b"x", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 400)
        server.limiter = server.RateLimiter(2, 50, 100)
        spoof = [post(b"x", headers={"X-Forwarded-For": f"{i}.{i}.{i}.{i}, 7.7.7.7"}).status_code for i in (1, 2, 3)]
        check("giả mạo phần đầu X-Forwarded-For không né được giới hạn", spoof == [400, 400, 429], str(spoof))
        server.limiter = server.RateLimiter(5, 50, 2)
        g = [post(b"x", headers={"X-Forwarded-For": f"9.9.9.{i}"}) for i in (1, 2, 3)]
        check("trần chung toàn dịch vụ: lượt thứ 3 (IP khác) bị 429 busy_global", [x.status_code for x in g] == [400, 400, 429] and g[2].json()["code"] == "busy_global")
        server.limiter = generous

    # ---------------- hàm thuần ----------------
    levels = [(0.0, -1), (0.99, -1), (1.0, 0), (4.99, 0), (5.0, 1), (9.99, 1), (10.0, 2), (19.99, 2), (20.0, 3), (100.0, 3)]
    check("level_index: đúng ngưỡng 1/5/10/20", all(server.level_index(p) == e for p, e in levels), str([(p, server.level_index(p)) for p, _ in levels]))

    # ---------------- khởi động thất bại khi cấu hình sai ----------------
    for label, env_value in (("thiếu CLEANSIGHT_ALLOWED_ORIGINS", None), ("có '*'", "*"), ("không phải URL", "netlify.app")):
        env = {k: v for k, v in os.environ.items() if k != "CLEANSIGHT_ALLOWED_ORIGINS"}
        if env_value is not None:
            env["CLEANSIGHT_ALLOWED_ORIGINS"] = env_value
        t0 = time.time()
        p = subprocess.run([sys.executable, "-B", "-c", "import server"], cwd=HERE, env=env, capture_output=True, text=True, timeout=90)
        check(f"khởi động thất bại: {label}", p.returncode != 0 and "CLEANSIGHT_ALLOWED_ORIGINS" in p.stderr, f"exit={p.returncode} {time.time()-t0:.1f}s")

    print(f"\nTổng: {PASS} đạt, {FAIL} hỏng")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
