"""
Sinh dữ liệu demo cho CHẾ ĐỘ "Demo simulation" của dashboard thật (ssc-v2/ssc-road-alerts), đúng dạng API của hệ thống.

Quy trình (tất cả MÔ PHỎNG, xem README.md):
  1. make_demo_data.py mô phỏng 100 camera (cùng bộ mô phỏng đã dùng cho trang website): số đo từng phút, vùng rác, vùng cống.
  2. Script này gom camera gần nhau thành tuyến (~25 tuyến), tên giả định ("Road R-01 (sample)", "Drain inlet 001").
  3. build_dashboard_state.mjs chạy MÃ THẬT của backend (computeDrainState, publicCamera, aggregateRoad, validateDataset) để ra đúng
     những gì /api/cameras và /api/road-alerts trả về; vùng rác (trash_regions) là trường tùy chọn mới, chỉ dữ liệu demo có.
  4. Kết quả: ssc-v2/ssc-road-alerts/src/mocks/city.json (dashboard nạp qua chính các hàm chuẩn hoá của nó).

Chạy:  python make_dashboard_data.py [--out ../../ssc-v2/ssc-road-alerts/src/mocks/city.json] [--seed 2026]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_demo_data as mk  # noqa: E402

DEFAULT_OUT = HERE.parents[1] / "ssc-v2" / "ssc-road-alerts" / "src" / "mocks" / "city.json"
BUILDER = HERE / "build_dashboard_state.mjs"
SPACING_M = 1100.0          # hai camera nối tiếp trong một tuyến cách nhau tối đa
MAX_ROAD_M = 2000.0         # tổng độ dài một tuyến tối đa (tránh đường nối quá dài cắt ngang cả khu)
SINGLE_HALF_LEN_M = 45.0    # camera lẻ: tuyến ngắn dọc trục đường đã dò, mỗi phía 45 m


def haversine_m(a, b) -> float:
    r = 6371008.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def group_roads(cams: list[dict], sites: dict, seed: int) -> list[list[dict]]:
    """Gom camera cùng khu thành tuyến 3-5 camera: bắt đầu từ camera ở cực Bắc còn lại, nối dần camera gần nhất. Camera lẻ lập tuyến ngắn."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 3]))
    chains: list[list[dict]] = []
    for zone in sorted({c["zone"] for c in cams}):
        rest = sorted((c for c in cams if c["zone"] == zone), key=lambda c: (-c["pos"][0], c["pos"][1]))
        while rest:
            chain = [rest.pop(0)]
            target = int(rng.integers(3, 6))
            length = 0.0
            while len(chain) < target and rest:
                nearest = min(rest, key=lambda c: haversine_m(chain[-1]["pos"], c["pos"]))
                step = haversine_m(chain[-1]["pos"], nearest["pos"])
                if step > SPACING_M or length + step > MAX_ROAD_M:
                    break
                rest.remove(nearest)
                chain.append(nearest)
                length += step
            chains.append(chain)
    # camera lẻ ghép vào đầu/cuối tuyến gần nhất nếu đủ gần (tuyến tối đa 6 camera)
    merged = True
    while merged:
        merged = False
        for single in [c for c in chains if len(c) == 1]:
            best = None
            for other in chains:
                if other is single or len(other) >= 6 or other[0]["zone"] != single[0]["zone"]:
                    continue
                other_len = sum(haversine_m(other[i]["pos"], other[i + 1]["pos"]) for i in range(len(other) - 1))
                for end, pos in ((0, other[0]["pos"]), (-1, other[-1]["pos"])):
                    d = haversine_m(single[0]["pos"], pos)
                    if d <= SPACING_M and other_len + d <= MAX_ROAD_M and (best is None or d < best[0]):
                        best = (d, other, end)
            if best:
                _d, other, end = best
                (other.insert(0, single[0]) if end == 0 else other.append(single[0]))
                chains.remove(single)
                merged = True
                break
    return chains


def build_input(seed: int) -> dict:
    doc, extras = mk._build(seed)
    sites = {s["id"]: s for s in json.loads(mk.SITES.read_text(encoding="utf-8"))["cameras"]}
    cams = [c for c in doc["cameras"] if c["id"] in extras]
    chains = group_roads(cams, sites, seed)
    roads, cameras, counter = [], [], 0
    for ri, chain in enumerate(chains, 1):
        road_id, road_name = f"DEMO-R{ri:02d}", f"Road R-{ri:02d} (sample)"
        if len(chain) >= 2:
            coords = [[c["pos"][1], c["pos"][0]] for c in chain]
        else:                                   # một camera: đoạn ngắn dọc trục đường
            site = sites[chain[0]["id"]]
            axis = math.radians(site["road_axis_bearing_deg"])
            lat0, lon0 = chain[0]["pos"]
            dn, de = SINGLE_HALF_LEN_M * math.cos(axis), SINGLE_HALF_LEN_M * math.sin(axis)
            a = mk.pm.meters_to_latlon(lat0, lon0, -de, -dn)
            b = mk.pm.meters_to_latlon(lat0, lon0, de, dn)
            coords = [[round(a[1], 7), round(a[0], 7)], [round(b[1], 7), round(b[0], 7)]]
        roads.append({"road_id": road_id, "road_name": road_name, "coordinates": coords})
        for c in chain:
            counter += 1
            ex = extras[c["id"]]
            cameras.append({
                "camera_id": f"DEMO-C{counter:03d}", "name": f"Drain inlet {counter:03d}", "road_id": road_id,
                "coordinates": [c["pos"][1], c["pos"][0]],
                "roi_polygon": ex["roi_norm"], "calibrated_at": ex["calibrated_at"],
                "readings": ex["run"], "latest_waste_pct": ex["latest_waste_pct"],
                "trash_regions": [{"kind": r["kind"], "area_m2": r["area_m2"], "ring": [[lon, lat] for lat, lon in r["ring"]]} for r in c["regions"]],
                "source_id": c["id"],
            })
    return {"as_of": doc["as_of"], "roads": roads, "cameras": cameras}


def run_builder(payload: dict) -> dict:
    r = subprocess.run(["node", str(BUILDER)], input=json.dumps(payload), capture_output=True, text=True, timeout=300, cwd=str(HERE))
    if r.returncode != 0:
        raise RuntimeError("build_dashboard_state.mjs lỗi: " + r.stderr[-800:])
    return json.loads(r.stdout)


def build(seed: int) -> dict:
    payload = build_input(seed)
    api = run_builder(payload)
    return {
        "simulated": True,
        "note": "SIMULATED data for illustration: camera positions, readings and litter outlines are generated, not measured. "
                "Shaped like the backend API output (roads from /api/road-alerts, cameras from /api/cameras) plus optional trash_regions.",
        "generator": "research/cleansight_customer_demo/make_dashboard_data.py",
        "seed": seed,
        "as_of": payload["as_of"],
        "roads": api["roads"],
        "cameras": api["cameras"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    data = build(args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    counts: dict[str, int] = {}
    for c in data["cameras"]:
        key = c["drain_state"]["state"] + ("/offline" if c["status"] == "offline" else "")
        counts[key] = counts.get(key, 0) + 1
    sev: dict[str, int] = {}
    for r in data["roads"]:
        sev[r["severity"]] = sev.get(r["severity"], 0) + 1
    print(f"Đã ghi {out} ({len(text) / 1024:.0f} KB): {len(data['roads'])} tuyến {sev}, {len(data['cameras'])} camera {counts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
