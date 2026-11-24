"""
Kiểm bộ dữ liệu demo mô phỏng (make_demo_data.py + camera_sites.json). Chạy:  python -B test_demo_data.py

Quan trọng nhất: (1) luật trạng thái cống bản Python giống HỆT bản thật của backend (chạy mã Node thật, từng bước, 60 chuỗi ngẫu nhiên);
(2) ngưỡng chính sách giống config.js; (3) hình học: mọi vùng rác nằm trong vùng camera thấy, diện tích m² đúng, độ che cống khớp số đo;
(4) dữ liệu sinh ra lặp lại được (cùng hạt giống -> cùng từng byte); (5) mọi nhãn "mô phỏng".
"""
from __future__ import annotations

import json
import math
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_demo_data as mk  # noqa: E402

PASS = FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[OK]   {name} {detail}".rstrip())
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}".rstrip())


def node(args: list[str], stdin: str | None = None) -> str:
    r = subprocess.run(["node", str(HERE / "check_policy.mjs"), *args], input=stdin, capture_output=True, text=True, timeout=120, cwd=str(HERE))
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])
    return r.stdout


def to_m(ring, lat0, lon0):
    """[[lat, lon], ...] -> mét Đông-Bắc quanh (lat0, lon0)."""
    k_lat = 111320.0
    k_lon = 111320.0 * math.cos(math.radians(lat0))
    return np.array([[(lon - lon0) * k_lon, (lat - lat0) * k_lat] for lat, lon in ring])


def main() -> int:
    # ---------------- luật thật của backend ----------------
    try:
        real = json.loads(node(["--policy"]))
        have_node = True
    except Exception as exc:  # noqa: BLE001
        print(f"[BỎ QUA] không chạy được Node ({exc}); các kiểm tra so với backend thật không chạy")
        have_node = False
    if have_node:
        p = mk.POLICY
        check("ngưỡng rác giống server/config.js", real["waste"] == p["waste"], str(real["waste"]))
        check("ngưỡng che cống giống server/config.js", real["blockage"] == p["blockage"])
        ds = real["drainState"]
        check("tham số trạng thái cống giống server/config.js (cửa sổ 5, tối thiểu 3, vào/ra 50/35 và 20/12)",
              ds["windowSize"] == p["drain_state"]["window_size"] and ds["minReadings"] == p["drain_state"]["min_readings"]
              and ds["clean"] == p["drain_state"]["clean"] and ds["watch"] == p["drain_state"]["watch"], str(ds))
        check("tuổi tối đa của một lần đo giống (15 phút)", real["readingMaxAgeMs"] == p["reading_max_age_min"] * 60000)

        rng = random.Random(7)
        cases = []
        for _ in range(60):
            minute, level, series = 0, rng.uniform(0, 80), []
            for _ in range(250):
                minute += rng.choice([1, 1, 1, 1, 2, 3, 20, 400]) if rng.random() < 0.3 else 1
                level = min(100.0, max(0.0, level + rng.gauss(0, 4)))
                v = level + (rng.uniform(15, 35) if rng.random() < 0.02 else 0)
                series.append((minute, round(min(100.0, max(0.0, v)), 1)))
            cases.append(series)
        real_out = json.loads(node([], json.dumps(cases)))
        mismatches, steps, states_seen = 0, 0, set()
        T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
        for series, expected in zip(cases, real_out):
            tr = mk.DrainTracker()
            for (minute, v), (state, smoothed, reason, wcount, since_ms) in zip(series, expected):
                tr.add(minute, v)
                steps += 1
                states_seen.add(state)
                since_min = (since_ms - int(T0.timestamp() * 1000)) // 60000
                if not (tr.state == state and tr.reason == reason and tr.window_count == wcount and tr.since == since_min
                        and ((tr.smoothed is None and smoothed is None) or (tr.smoothed is not None and smoothed is not None and abs(tr.smoothed - smoothed) < 1e-9))):
                    mismatches += 1
        check("trạng thái cống (Python) == backend thật, từng bước (state, lý do, số lần đo, mốc 'since', giá trị trung vị)", mismatches == 0,
              f"{steps} bước, {len(cases)} chuỗi, {mismatches} lệch; gặp các trạng thái {sorted(states_seen)}")

    # ---------------- vị trí camera ----------------
    sites = json.loads(mk.SITES.read_text(encoding="utf-8"))["cameras"]
    ids = [s["id"] for s in sites]
    check("camera_sites.json: 100 camera, mã duy nhất", len(sites) == 100 and len(set(ids)) == 100, f"{len(sites)}")
    check("camera_sites.json: nằm trong khung TP.HCM và có đủ 6 khu", all(10.6 < s["camera"][0] < 10.95 and 106.5 < s["camera"][1] < 106.9 for s in sites)
          and {s["zone"] for s in sites} == {"Z1", "Z2", "Z3", "Z4", "Z5", "Z6"})

    def hav(a, b):
        r = 6371008.8
        p1, p2 = math.radians(a[0]), math.radians(b[0])
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
        return 2 * r * math.asin(math.sqrt(h))
    dmin = min(hav(a["drain"], b["drain"]) for i, a in enumerate(sites) for b in sites[i + 1:])
    check("hai camera bất kỳ cách nhau >= 100 m", dmin >= 100.0, f"gần nhất {dmin:.0f} m")
    dcam = [hav(s["camera"], s["drain"]) for s in sites]
    check("camera cách miệng cống 3.0-4.6 m (đặt trên vỉa hè nhìn vào mép đường)", all(3.0 <= d <= 4.6 for d in dcam), f"{min(dcam):.1f}-{max(dcam):.1f} m")
    check("bề rộng lòng đường hợp lý (5-22 m)", all(5.0 <= s["road_width_m"] <= 22.0 for s in sites))

    # ---------------- sinh dữ liệu, lặp lại được ----------------
    import time
    t0 = time.time()
    a = mk.build(2026)
    took = time.time() - t0
    b = mk.build(2026)
    ta, tb = json.dumps(a, allow_nan=False, separators=(",", ":")), json.dumps(b, allow_nan=False, separators=(",", ":"))
    check("cùng hạt giống -> dữ liệu giống từng byte (và không có NaN/Infinity)", ta == tb, f"{len(ta) / 1024:.0f} KB, sinh trong {took:.0f} s")
    c = mk.build(7)
    check("hạt giống khác -> dữ liệu khác", json.dumps(c, separators=(",", ":")) != ta)
    check("kích thước vừa phải (< 1,5 MB, trước khi nén)", len(ta) < 1_500_000)
    check("gắn nhãn mô phỏng trong chính dữ liệu", a["simulated"] is True and "SIMULATED" in a["note"] and a["version"] == 1)
    check("100 camera, 6 khu, mã khớp camera_sites.json", len(a["cameras"]) == 100 and [x["id"] for x in a["cameras"]] == ids and len(a["zones"]) == 6)

    # ---------------- phân bố trạng thái ----------------
    cams = a["cameras"]
    by = {}
    for x in cams:
        k = "offline" if x["status"] == "offline" else x["state"]
        by[k] = by.get(k, 0) + 1
    check("có đủ các tình huống: sạch / theo dõi / cần dọn / đang thu thập / mất kết nối", all(by.get(k, 0) >= 3 for k in ("clear", "watch", "clean", "unknown", "offline")), str(by))
    check("phần lớn camera bình thường (sạch >= 40%), cần dọn không quá 25%", by.get("clear", 0) >= 40 and by.get("clean", 0) <= 25, str(by))
    off = [x for x in cams if x["status"] == "offline"]
    check("camera mất kết nối: trạng thái 'chưa rõ / stale', không có số che cống đã làm mượt", len(off) == mk.N_OFFLINE_LONG + mk.N_OFFLINE_RECENT
          and all(x["state"] == "unknown" and x["reason"] == "stale" and x["blockage_pct"] is None for x in off), f"{len(off)} camera")
    new = [x for x in cams if x["reason"] == "collecting"]
    check("camera mới lắp: đang thu thập (< 3 lần đo), chưa có số đã làm mượt", len(new) == mk.N_NEW and all(x["window"] < 3 and x["blockage_pct"] is None for x in new), f"{len(new)} camera")
    ok_cams = [x for x in cams if x["status"] == "online" and x["reason"] == "ok"]
    check("camera hoạt động bình thường: có trung vị, số lần đo 3-5, có mốc since", all(x["blockage_pct"] is not None and 3 <= x["window"] <= 5 and x["since"] for x in ok_cams), f"{len(ok_cams)} camera")
    check("trạng thái khớp ngưỡng (cần dọn >= 35, theo dõi >= 12, sạch < 35 nhờ trễ)", all(
        (x["state"] == "clean" and x["blockage_pct"] >= 35) or (x["state"] == "watch" and 12 <= x["blockage_pct"] < 50) or (x["state"] == "clear" and x["blockage_pct"] < 20)
        for x in ok_cams))

    # ---------------- hình học ----------------
    bad_in, bad_area, bad_sum, bad_cov, bad_roi, bad_foot, n_reg = [], [], [], [], [], [], 0
    for x in cams:
        lat0, lon0 = x["pos"]
        foot = to_m(x["footprint"], lat0, lon0)
        fa = mk.shoelace(foot)
        if not (8.0 <= fa <= 80.0) or float(np.max(np.hypot(foot[:, 0], foot[:, 1]))) > 12.6:
            bad_foot.append(x["id"])
        roi = to_m(x["roi"], lat0, lon0)
        if not mk.inside(foot, roi, 0.0):
            bad_roi.append(x["id"])
        if not x.get("latest"):
            continue
        tot = 0.0
        for r in x["regions"]:
            n_reg += 1
            ring = to_m(r["ring"], lat0, lon0)
            if not mk.inside(foot, ring, 0.0):
                bad_in.append((x["id"], r["kind"]))
            area = mk.shoelace(ring)
            tot += r["area_m2"]
            if abs(area - r["area_m2"]) > max(0.01, 0.03 * r["area_m2"]):
                bad_area.append((x["id"], round(area, 3), r["area_m2"]))
        la = x["latest"]
        if abs(tot - la["total_area_m2"]) > 0.02 or abs(la["waste_pct"] - tot / la["footprint_area_m2"] * 100.0) > 0.5:
            bad_sum.append((x["id"], round(tot, 3), la["total_area_m2"], la["waste_pct"]))
        if abs(la["blockage_measured_pct"] - la["blockage_pct"]) > 1.5:
            bad_cov.append((x["id"], la["blockage_measured_pct"], la["blockage_pct"]))
    check("vùng nhìn thấy của camera hợp lý (8-80 m², trong bán kính 12 m)", not bad_foot, str(bad_foot[:3]))
    check("ROI cống nằm trong vùng camera thấy", not bad_roi, str(bad_roi[:3]))
    check("mọi vùng rác nằm trong vùng camera thấy", not bad_in, f"{n_reg} vùng; ngoài: {bad_in[:3]}")
    check("diện tích m² của từng vùng khớp tính lại từ toạ độ (sai số <= 3%)", not bad_area, str(bad_area[:3]))
    check("tổng diện tích và mức rác (%) khớp các vùng (sai số <= 0,5 điểm %)", not bad_sum, str(bad_sum[:3]))
    check("độ che cống đo lại từ hình vẽ khớp số báo (lệch <= 1,5 điểm %)", not bad_cov, str(bad_cov[:3]))
    levels = {x["latest"]["waste_level"] for x in cams if x.get("latest")}
    check("có nhiều mức rác khác nhau trong dữ liệu (không đơn điệu)", len(levels) >= 3, str(sorted(levels)))
    sev = {x["latest"]["severity"] for x in cams if x.get("latest")}
    check("mức cảnh báo (severity) theo luật thật có từ 3 mức trở lên", len(sev) >= 3, str(sorted(sev)))

    # ---------------- dữ liệu cho dashboard thật (mã backend thật chạy trong Node) ----------------
    if have_node:
        import make_dashboard_data as md
        payload = md.build_input(2026)
        api = md.run_builder(payload)
        by_src = {c["id"]: c for c in a["cameras"]}
        diff = []
        for src, out in zip(payload["cameras"], api["cameras"]):
            ref = by_src[src["source_id"]]
            ds = out["drain_state"]
            same_state = ds["state"] == ref["state"] and ds["reason"] == ref["reason"] and (ref["status"] == "offline" or ds["window_count"] == ref["window"])  # camera mất kết nối: backend thật giữ số lần đo cũ, chỉ đổi state/reason
            same_pct = (ds.get("smoothed_blockage_pct") is None and ref["blockage_pct"] is None) or abs(ds["smoothed_blockage_pct"] - ref["blockage_pct"]) < 1e-9
            same_status = out["status"] == ref["status"]
            if not (same_state and same_pct and same_status):
                diff.append((src["camera_id"], ds["state"], ref["state"]))
        check("dashboard: trạng thái cống do MÃ BACKEND THẬT (Node) tính == bộ theo dõi Python, cả 100 camera (trạng thái, lý do, số lần đo của camera đang online, % làm mượt, online/offline)", not diff, str(diff[:3]))
        roads = {r["road_id"]: r for r in api["roads"]}
        check("dashboard: mọi camera thuộc một tuyến có thật, mỗi tuyến có ít nhất một camera", all(c["road_id"] in roads for c in api["cameras"])
              and all(any(c["road_id"] == rid for c in api["cameras"]) for rid in roads), f"{len(roads)} tuyến, {len(api['cameras'])} camera")
        ok_sum = all(sum(r["drain_summary"][k] for k in ("clear", "watch", "clean", "unknown")) == r["camera_count"] for r in roads.values())
        check("dashboard: tổng hợp theo tuyến của backend thật nhất quán (drain_summary cộng lại = số camera của tuyến)", ok_sum)
        check("dashboard: tên giả định, không tên phố thật hay tên cuộc thi", all(r["road_name"].startswith("Road R-") and r["road_name"].endswith("(sample)") for r in roads.values())
              and all(c["name"].startswith("Drain inlet ") for c in api["cameras"]) and not __import__("re").search(r"SSC|Sustainable|Challenge|RMIT|RBPC", json.dumps(api), __import__("re").I))
        check("dashboard: mô tả tuyến do backend ghi rõ dữ liệu mô phỏng", all(r["description"].startswith("[Simulated data via the test API]") for r in roads.values() if r["data_quality"] != "unknown"))
        check("dashboard: vùng cống quy về ảnh nằm trong khung [0,1] và có 4 đỉnh", all(len(c["drain_roi"]["polygon"]) == 4 and all(0 <= v <= 1 for p in c["drain_roi"]["polygon"] for v in p) for c in api["cameras"]))
        again = md.run_builder(md.build_input(2026))
        check("dashboard: sinh lại cho đúng từng byte (cùng hạt giống)", json.dumps(api, sort_keys=True) == json.dumps(again, sort_keys=True))

    print(f"\nTổng: {PASS} đạt, {FAIL} hỏng")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
