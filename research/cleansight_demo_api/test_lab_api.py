"""
Test phòng thử hiệu chỉnh (lab.py) bằng fastapi TestClient, có chạy model THẬT trên các ảnh mẫu trong lab_samples/.

Chạy (từ thư mục này; không cần pytest):
  python -B test_lab_api.py

Kiểm: luồng đầy đủ (dò bảng -> xem vùng -> lưu -> gửi ảnh rác -> vẽ vùng), hai phiên KHÔNG lẫn nhau, hết hạn / đầy phiên,
bảng quá nhỏ bị từ chối, vị trí cục giấy ~0,5 m phía trước bảng, vùng cống (ROI) trên rác và trên nền trống,
giới hạn tần suất, hàng chờ, CORS cho header phiên, KHÔNG ghi gì ra đĩa, lỗi trả đúng dạng.
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import test_demo_api as base  # noqa: E402  (đặt CLEANSIGHT_ALLOWED_ORIGINS trước khi nạp server)
from fastapi.testclient import TestClient  # noqa: E402

import lab  # noqa: E402
import server  # noqa: E402

ORIGIN = base.ORIGIN
PASS = FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[OK]   {name} {detail}".rstrip())
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}".rstrip())


def main() -> int:
    sid_a, sid_b = "A" * 24, "B" * 24
    HA = {"X-Lab-Session": sid_a, "Origin": ORIGIN}
    HB = {"X-Lab-Session": sid_b, "Origin": ORIGIN}
    generous = (server.RateLimiter(100000, 1000000, 1000000), server.RateLimiter(100000, 1000000, 1000000))
    lab.LIGHT, lab.HEAVY = generous

    with TestClient(server.app) as c:

        def detect(H, sample="board-near", size=250, **kw):
            return c.post("/api/lab/board/detect", headers=H, json={"sample_id": sample, "marker_size_mm": size, **kw})

        # ---------------- danh sách mẫu, phiên ----------------
        r = c.get("/api/lab/board/samples", headers=HA)
        j = r.json()
        check("samples: 200, 2 ảnh hiệu chỉnh + 1 ảnh rác + vị trí mặc định", r.status_code == 200 and [s["id"] for s in j["calibration"]] == ["board-near", "board-far"]
              and [s["id"] for s in j["trash"]] == ["board-trash"] and abs(j["defaults"]["lat"] - 10.7769) < 1e-9, str([s["image_size"] for s in j["calibration"]]))
        r = c.get("/api/lab/board/samples", headers={"Origin": ORIGIN})
        check("thiếu header phiên: 400 invalid_session, đúng dạng {ok:false,error,code}", r.status_code == 400 and r.json() == {
            "ok": False, "error": "Missing or invalid lab session id.", "code": "invalid_session"}, str(r.json()))
        for bad in ("short", "x" * 100, "has space in it_____", "../../etc/passwd___"):
            check(f"phiên không hợp lệ bị từ chối ({bad[:12]!r})", c.get("/api/lab/board/samples", headers={"X-Lab-Session": bad, "Origin": ORIGIN}).status_code == 400)

        # ---------------- dò bảng ----------------
        far = detect(HA, "board-far")
        fj = far.json()
        check("bảng quá nhỏ (ảnh xa mô phỏng): 422 board_too_small, ~43 px, có ảnh overlay", far.status_code == 422 and fj["code"] == "board_too_small"
              and 40 <= fj["side_px_min"] < 50 and bool(fj["overlay_jpg_b64"]), f"{fj.get('side_px_min')}")
        r = detect(HA)
        d = r.json()
        check("dò bảng ảnh mẫu: 200, cạnh ~146 px (>= 50), có calibration_id và overlay", r.status_code == 200 and d["side_px_min"] > 140 and bool(d["overlay_jpg_b64"]) and len(d["calibration_id"]) == 16, f"{d.get('side_px_min'):.1f} px")
        check("không có EXIF -> dùng góc mở mặc định 66° và có cảnh báo", d["fov_source"] == "default" and d["fov_deg"] == 66.0 and any("default field of view" in w for w in d["warnings"]))
        h250 = d["camera_height_m_est"]
        h150 = detect(HA, size=150).json()["camera_height_m_est"]
        check("đổi cạnh bảng 250 -> 150 mm: độ cao camera tỉ lệ 0,6 (đúng vật lý)", abs(h150 / h250 - 0.6) < 0.01, f"{h250:.3f} m vs {h150:.3f} m")
        check("góc mở nhập tay được ghi nhận (fov_source=input)", detect(HA, fov_deg=75).json()["fov_source"] == "input")
        for body, code in (({"sample_id": "nope"}, 404), ({"sample_id": "board-trash"}, 404), ({"sample_id": "board-near", "marker_size_mm": 5}, 422),
                           ({"sample_id": "board-near", "marker_size_mm": "abc"}, 422), ({"sample_id": "board-near", "fov_deg": 200}, 422), ({}, 404)):
            rr = c.post("/api/lab/board/detect", headers=HA, json=body)
            check(f"dò bảng với dữ liệu sai {body}: {code}", rr.status_code == code and rr.json().get("ok") is False, str(rr.json().get("code")))
        rr = c.post("/api/lab/board/detect", headers=HA, content=b"{not json", )
        check("JSON hỏng: 422 dạng {ok:false,code:invalid_request} (không lộ chi tiết)", rr.status_code == 422 and rr.json()["code"] == "invalid_request", str(rr.json()))

        cid = d["calibration_id"]
        # ---------------- vùng mặt đất camera thấy ----------------
        r = c.get("/api/lab/board/footprint", headers=HA, params={"calibration_id": cid, "lat": 10.7769, "lon": 106.7009, "azimuth_deg": 0})
        kinds = [f["properties"]["kind"] for f in r.json().get("features", [])]
        check("footprint chưa lưu: 200, có vùng + điểm bảng + điểm camera", r.status_code == 200 and kinds == ["footprint", "marker", "camera"], str(kinds))
        check("footprint thiếu lat/lon: 422", c.get("/api/lab/board/footprint", headers=HA, params={"calibration_id": cid}).status_code == 422)
        check("footprint calibration_id lạ: 404", c.get("/api/lab/board/footprint", headers=HA, params={"calibration_id": "0" * 16, "lat": 1, "lon": 1}).status_code == 404)
        check("footprint với lat ngoài khoảng: 422", c.get("/api/lab/board/footprint", headers=HA, params={"calibration_id": cid, "lat": 95, "lon": 1}).status_code == 422)
        check("footprint đã lưu khi chưa lưu: 404", c.get("/api/lab/board/footprint", headers=HA).status_code == 404)

        # ---------------- trước khi lưu: không gửi ảnh rác được ----------------
        r = c.post("/api/lab/board/observe", headers=HA, json={"sample_id": "board-trash"})
        check("gửi ảnh rác khi chưa hiệu chỉnh: 409 not_calibrated", r.status_code == 409 and r.json()["code"] == "not_calibrated")
        check("đọc hiệu chỉnh khi chưa lưu: ok=false", c.get("/api/lab/board/calibration", headers=HA).json().get("ok") is False)

        # ---------------- lưu, rồi vẽ vùng rác ----------------
        save = c.post("/api/lab/board/calibration/save", headers=HA, json={"calibration_id": cid, "lat": 10.7769, "lon": 106.7009, "azimuth_deg": 0})
        check("lưu hiệu chỉnh: 200", save.status_code == 200 and save.json()["ok"] is True)
        check("lưu với calibration_id lạ: 404", c.post("/api/lab/board/calibration/save", headers=HA, json={"calibration_id": "f" * 16, "lat": 1, "lon": 1, "azimuth_deg": 0}).status_code == 404)
        check("lưu thiếu azimuth: 422", c.post("/api/lab/board/calibration/save", headers=HA, json={"calibration_id": cid, "lat": 1, "lon": 1}).status_code == 422)
        cal = c.get("/api/lab/board/calibration", headers=HA).json()["calibration"]
        check("đọc lại hiệu chỉnh đã lưu đúng giá trị", abs(cal["marker_latlon"][0] - 10.7769) < 1e-9 and cal["azimuth_deg"] == 0 and cal["image_size"] == [2000, 1125])
        check("footprint đã lưu: 200 (không cần calibration_id)", c.get("/api/lab/board/footprint", headers=HA).status_code == 200)

        with base.WriteMonitor() as mon:
            t0 = time.time()
            obs = c.post("/api/lab/board/observe", headers=HA, json={"sample_id": "board-trash"})
            dt = time.time() - t0
        o = obs.json()
        check("gửi ảnh rác: 200, có vùng + ảnh khoanh + thời gian", obs.status_code == 200 and o["n_regions"] >= 2 and bool(o["annotated_jpg_b64"]) and o["inference_ms"] > 0, f"{dt:.1f}s, {o.get('n_regions')} vùng")
        ball = [f["properties"] for f in o["regions"]["features"] if f["properties"]["area_m2"] < 0.02]
        board = [f["properties"] for f in o["regions"]["features"] if f["properties"]["area_m2"] > 0.05]
        check("cục giấy: ~0,5 m phía trước bảng (Y 0,47-0,53), lệch ngang < 6 cm, diện tích 3-12 cm²·100", len(ball) == 1 and 0.47 <= ball[0]["y_m"] <= 0.53 and abs(ball[0]["x_m"]) < 0.06 and 0.003 < ball[0]["area_m2"] < 0.012, str(ball))
        check("tờ bảng bị khoanh thành vùng rác lớn ở gần tâm (đúng như web test gốc)", len(board) == 1 and abs(board[0]["y_m"]) < 0.15 and abs(board[0]["x_m"]) < 0.15, str(board))
        check("gửi ảnh rác KHÔNG ghi gì ra đĩa", mon.events == [], str(mon.events[:3]))
        check("lịch sử phiên A có 1 lần gửi", len(c.get("/api/lab/board/observations", headers=HA).json()["observations"]) == 1)

        # đổi vị trí và lưu lại: vùng rác dịch đúng theo
        cid2 = detect(HA).json()["calibration_id"]
        c.post("/api/lab/board/calibration/save", headers=HA, json={"calibration_id": cid2, "lat": 10.7779, "lon": 106.7019, "azimuth_deg": 0})
        o2 = c.post("/api/lab/board/observe", headers=HA, json={"sample_id": "board-trash"}).json()

        def centre(feat):
            ring = feat["geometry"]["coordinates"][0]
            return sum(p[1] for p in ring) / len(ring), sum(p[0] for p in ring) / len(ring)
        la1, lo1 = centre([f for f in o["regions"]["features"] if f["properties"]["area_m2"] < 0.02][0])
        la2, lo2 = centre([f for f in o2["regions"]["features"] if f["properties"]["area_m2"] < 0.02][0])
        check("đặt bảng ở nơi khác (+0,001° vĩ, +0,001° kinh): vùng rác dịch đúng bấy nhiêu", abs((la2 - la1) - 0.001) < 2e-6 and abs((lo2 - lo1) - 0.001) < 2e-6, f"{la2-la1:.7f}, {lo2-lo1:.7f}")
        cid3 = detect(HA).json()["calibration_id"]
        c.post("/api/lab/board/calibration/save", headers=HA, json={"calibration_id": cid3, "lat": 10.7769, "lon": 106.7009, "azimuth_deg": 90})
        o3 = c.post("/api/lab/board/observe", headers=HA, json={"sample_id": "board-trash"}).json()
        check("xoay hướng bảng 90° làm đổi toạ độ nhưng KHÔNG đổi diện tích tổng", abs(o3["total_area_m2"] - o["total_area_m2"]) < 1e-6, f"{o3['total_area_m2']:.6f} vs {o['total_area_m2']:.6f}")

        # ---------------- hai phiên không lẫn nhau ----------------
        r = c.post("/api/lab/board/observe", headers=HB, json={"sample_id": "board-trash"})
        check("phiên B (chưa hiệu chỉnh) không dùng được hiệu chỉnh của phiên A: 409", r.status_code == 409)
        check("phiên B không thấy lịch sử của A", c.get("/api/lab/board/observations", headers=HB).json()["observations"] == [])
        check("phiên B không đọc được hiệu chỉnh của A", c.get("/api/lab/board/calibration", headers=HB).json().get("ok") is False)
        check("phiên B không dùng được calibration_id của A: 404", c.get("/api/lab/board/footprint", headers=HB, params={"calibration_id": cid, "lat": 1, "lon": 1}).status_code == 404)
        cb = detect(HB).json()["calibration_id"]
        c.post("/api/lab/board/calibration/save", headers=HB, json={"calibration_id": cb, "lat": 21.0, "lon": 105.8, "azimuth_deg": 180})
        ob = c.post("/api/lab/board/observe", headers=HB, json={"sample_id": "board-trash"}).json()
        a_hist = c.get("/api/lab/board/observations", headers=HA).json()["observations"]
        check("B lưu hiệu chỉnh khác (Hà Nội, hướng 180°): hiệu chỉnh của A KHÔNG đổi", c.get("/api/lab/board/calibration", headers=HA).json()["calibration"]["azimuth_deg"] == 90
              and abs(c.get("/api/lab/board/calibration", headers=HA).json()["calibration"]["marker_latlon"][0] - 10.7769) < 1e-9)
        check("lịch sử của A giữ nguyên 3 lần, của B có 1 lần", len(a_hist) == 3 and len(c.get("/api/lab/board/observations", headers=HB).json()["observations"]) == 1 and ob["n_regions"] >= 2)
        check("xoá lịch sử của B không ảnh hưởng A", c.delete("/api/lab/board/observations", headers=HB).json()["ok"] is True
              and len(c.get("/api/lab/board/observations", headers=HB).json()["observations"]) == 0 and len(c.get("/api/lab/board/observations", headers=HA).json()["observations"]) == 3)

        # ---------------- hết hạn / đầy phiên ----------------
        old_ttl = lab.SESSION_TTL_S
        lab.SESSION_TTL_S = 0.05
        time.sleep(0.2)
        check("phiên hết hạn: hiệu chỉnh cũ bị xoá", c.get("/api/lab/board/calibration", headers=HA).json().get("ok") is False)
        lab.SESSION_TTL_S = old_ttl
        old_max = lab.MAX_SESSIONS
        lab.MAX_SESSIONS = 3
        for k in "123":
            c.get("/api/lab/board/samples", headers={"X-Lab-Session": k * 24, "Origin": ORIGIN})
        check("đầy phiên (tối đa 3): số phiên không vượt trần, phiên CŨ NHẤT (A) bị bỏ, phiên mới nhất còn", len(lab._SESSIONS) == 3 and sid_a not in lab._SESSIONS and ("3" * 24) in lab._SESSIONS, str(list(k[:2] for k in lab._SESSIONS)))
        lab.MAX_SESSIONS = old_max

        # ---------------- vùng cống (ROI) ----------------
        pl = [[0.40, 0.25], [0.95, 0.25], [0.95, 0.80], [0.40, 0.80]]       # bao quanh đống rác và miệng cống
        asphalt = [[0.05, 0.05], [0.35, 0.05], [0.35, 0.25], [0.05, 0.25]]  # mặt đường trống, góc trên trái
        with base.WriteMonitor() as mon:
            r1 = c.post("/api/lab/drain/measure", headers=HA, json={"sample_id": "drain-litter", "polygon": pl})
            r2 = c.post("/api/lab/drain/measure", headers=HA, json={"sample_id": "drain-litter", "polygon": asphalt})
        a, b = r1.json(), r2.json()
        check("vùng cống bao quanh rác: 200, tỉ lệ che > 10%, phương pháp roi, có ảnh", r1.status_code == 200 and a["drain_blockage_pct"] > 10 and a["blockage_method"] == "roi" and a["annotated_jpg"].startswith("data:image/jpeg;base64,"), f"{a.get('drain_blockage_pct')}%")
        check("vùng trên mặt đường trống: ~0% và no_trash_in_roi", r2.status_code == 200 and b["drain_blockage_pct"] < 2 and b["no_trash_in_roi"] is True, f"{b.get('drain_blockage_pct')}%")
        check("đo vùng cống KHÔNG ghi gì ra đĩa", mon.events == [], str(mon.events[:3]))
        direct = server.analysis.analyze((HERE / "lab_samples" / "drain-litter.jpg").read_bytes(), roi=pl)["drain_blockage_pct"]
        check("kết quả khớp trực tiếp analysis.analyze(roi=...)", abs(direct - a["drain_blockage_pct"]) < 1e-9, f"{direct}")
        bad_polys = {"2 điểm": [[0.1, 0.1], [0.2, 0.2]], "65 điểm": [[0.5 + 0.1 * (i % 2), 0.1 + i * 0.01] for i in range(65)],
                     "ngoài [0,1]": [[0.1, 0.1], [1.5, 0.2], [0.5, 0.9]],
                     "không phải danh sách": "abc", "thiếu": None, "thẳng hàng (diện tích 0)": [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]]}
        for name, poly in bad_polys.items():
            rr = c.post("/api/lab/drain/measure", headers=HA, json={"sample_id": "drain-litter", "polygon": poly}) if poly is not None else c.post("/api/lab/drain/measure", headers=HA, json={"sample_id": "drain-litter"})
            check(f"vùng cống không hợp lệ ({name}): 422 invalid_polygon", rr.status_code == 422 and rr.json().get("code") == "invalid_polygon", str(rr.json().get("code")))
        rr = c.post("/api/lab/drain/measure", headers={**HA, "Content-Type": "application/json"},
                    content='{"sample_id": "drain-litter", "polygon": [[0.1, 0.1], [NaN, 0.2], [0.5, 0.9]]}')
        check("vùng cống có NaN: 422 invalid_polygon", rr.status_code == 422 and rr.json().get("code") == "invalid_polygon", str(rr.json().get("code")))
        check("ảnh cống lạ: 404", c.post("/api/lab/drain/measure", headers=HA, json={"sample_id": "board-near", "polygon": pl}).status_code == 404)
        check("danh sách ảnh cống: 1 ảnh 730x487", c.get("/api/lab/drain/samples", headers=HA).json()["samples"][0]["image_size"] == [730, 487])

        # ---------------- hàng chờ, sẵn sàng ----------------
        server._pending = server.MAX_WAITING + 1
        rr = c.post("/api/lab/drain/measure", headers=HA, json={"sample_id": "drain-litter", "polygon": pl})
        server._pending = 0
        check("hàng chờ model đầy: 503 busy, dạng lab, có Retry-After", rr.status_code == 503 and rr.json()["code"] == "busy" and rr.json()["ok"] is False and rr.headers.get("retry-after") == "5", str(rr.json()))
        check("sau khi trả lỗi, số chỗ giữ về 0", server._pending == 0)
        server._ready = False
        rr = c.post("/api/lab/board/observe", headers=HA, json={"sample_id": "board-trash"})
        server._ready = True
        check("model chưa sẵn sàng: 503 not_ready (observe/dò bảng nhẹ vẫn chạy)", rr.status_code in (503, 409) and (rr.status_code == 409 or rr.json()["code"] == "not_ready"))

        # ---------------- song song, hai phiên cùng lúc ----------------
        server.MAX_WAITING = 10
        sessions = [("P" + str(i)) * 12 for i in range(4)]

        def flow(sid):
            with TestClient(server.app) as cc:
                H = {"X-Lab-Session": sid, "Origin": ORIGIN}
                dd = cc.post("/api/lab/board/detect", headers=H, json={"sample_id": "board-near", "marker_size_mm": 250}).json()
                cc.post("/api/lab/board/calibration/save", headers=H, json={"calibration_id": dd["calibration_id"], "lat": 10.0 + len(sid) * 0 + int(sid[1]) * 0.01, "lon": 106.0, "azimuth_deg": 0})
                ob = cc.post("/api/lab/board/observe", headers=H, json={"sample_id": "board-trash"})
                return sid, ob.status_code, [round(f["geometry"]["coordinates"][0][0][1], 3) for f in ob.json()["regions"]["features"]]
        with ThreadPoolExecutor(4) as pool:
            res = list(pool.map(flow, sessions))
        check("4 giám khảo (4 phiên) cùng lúc: đều 200, mỗi người nhận vùng ở đúng vĩ độ của riêng mình", all(s == 200 for _, s, _ in res)
              and len({tuple(lat) for _, _, lat in res}) == 4 and server._pending == 0, str([(sid[:2], lat[:1]) for sid, _, lat in res]))
        server.MAX_WAITING = 3

        # ---------------- CORS ----------------
        pre = c.options("/api/lab/board/detect", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,x-lab-session"})
        check("preflight cho header X-Lab-Session: được phép", pre.status_code == 200 and "x-lab-session" in pre.headers.get("access-control-allow-headers", "").lower(), pre.headers.get("access-control-allow-headers", ""))
        pre = c.options("/api/lab/board/observations", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "DELETE", "Access-Control-Request-Headers": "x-lab-session"})
        check("preflight cho phương thức DELETE: được phép", pre.status_code == 200 and "DELETE" in pre.headers.get("access-control-allow-methods", ""))
        pre = c.options("/api/lab/board/detect", headers={"Origin": base.OTHER_ORIGIN, "Access-Control-Request-Method": "POST"})
        check("preflight từ origin lạ: bị từ chối", pre.status_code >= 400 and "access-control-allow-origin" not in pre.headers)
        check("phản hồi lab có Cache-Control no-store", c.get("/api/lab/board/samples", headers=HA).headers.get("cache-control") == "no-store")

        # ---------------- giới hạn tần suất ----------------
        lab.LIGHT = server.RateLimiter(3, 100, 100)
        codes = [c.get("/api/lab/board/observations", headers={"X-Lab-Session": "R" * 24, "Origin": ORIGIN, "X-Forwarded-For": "5.5.5.5"}).status_code for _ in range(4)]
        rr = c.get("/api/lab/board/observations", headers={"X-Lab-Session": "R" * 24, "Origin": ORIGIN, "X-Forwarded-For": "5.5.5.5"})
        check("giới hạn nhẹ: lượt thứ 4 bị 429 rate_limited, có Retry-After và dạng lab", codes == [200, 200, 200, 429] and rr.json()["code"] == "rate_limited" and int(rr.headers["retry-after"]) > 0 and rr.json()["ok"] is False)
        check("IP khác vẫn được phép", c.get("/api/lab/board/observations", headers={"X-Lab-Session": "R" * 24, "Origin": ORIGIN, "X-Forwarded-For": "6.6.6.6"}).status_code == 200)
        lab.LIGHT = generous[0]
        lab.HEAVY = server.RateLimiter(2, 100, 100)
        codes = [c.post("/api/lab/drain/measure", headers=HA, json={"sample_id": "drain-litter", "polygon": pl}).status_code for _ in range(3)]
        check("giới hạn nặng (chạy model): 2 lượt rồi 429", codes == [200, 200, 429], str(codes))
        lab.HEAVY = generous[1]

    print(f"\nTổng: {PASS} đạt, {FAIL} hỏng")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
