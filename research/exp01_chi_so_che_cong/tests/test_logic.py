"""Kiem tra logic truoc khi chay (khong GPU, khong model). Exit code != 0 neu loi."""
import math
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

import config as C  # noqa: E402
import common as U  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        def run():
            try:
                msg = fn()
                RESULTS.append((name, True, msg or ""))
            except Exception as exc:  # noqa: BLE001
                RESULTS.append((name, False, f"{exc}\n{traceback.format_exc()}"))
        run.__name__ = fn.__name__
        TESTS.append(run)
        return run
    return deco


TESTS = []


@check("GT trash lam du doan -> M1 == GT (76 cong, sai so 0)")
def test_gt_reproduction():
    items = U.list_all_drain_images()
    U.check_counts(items)
    n, max_err = 0, 0.0
    for it in items:
        for h, w in ((C.EXPECTED_NATIVE_SIZE, C.EXPECTED_NATIVE_SIZE), (C.ESP32_SIZE, C.ESP32_SIZE)):
            trash, drains, _ = U.gt_for_image(it["polys"], h, w)
            # du doan gia = GT trash
            pred_trash = trash.copy()
            for roi in drains:
                gt = U.blockage_roi(trash, roi)
                m1 = U.blockage_roi(pred_trash, roi)
                assert not math.isnan(gt), f"ROI rong: {it['stem']}"
                max_err = max(max_err, abs(m1 - gt))
                if h == C.EXPECTED_NATIVE_SIZE:
                    n += 1
    assert n == C.EXPECTED_DRAIN_POLYGONS, f"so cong {n} != {C.EXPECTED_DRAIN_POLYGONS}"
    assert max_err == 0.0, f"sai so lon nhat {max_err}"
    if C.GT_CSV.exists():
        rows = U.read_csv(C.GT_CSV)
        gt_map = {(r["split"], r["stem"], int(r["drain_idx"])): r for r in rows}
        for it in items:
            r0 = gt_map[(it["split"], it["stem"], 0)]
            trash, drains, _ = U.gt_for_image(it["polys"], int(r0["img_h"]), int(r0["img_w"]))
            for k, roi in enumerate(drains):
                v = float(gt_map[(it["split"], it["stem"], k)]["gt_blockage_pct"])
                assert abs(U.blockage_roi(trash, roi) - v) < 1e-3, f"lech ground_truth.csv: {it['stem']} {k}"
        return f"{n} cong, max err {max_err}; khop ground_truth.csv ({len(rows)} dong)"
    return f"{n} cong, max err {max_err} (chua co ground_truth.csv de doi chieu)"


@check("Hysteresis: chuyen trang thai")
def test_hysteresis():
    st = U.hysteresis_run([45, 55, 45, 55, 45, 55, 45, 55], init_state="red")
    assert all(s == "red" for s in st), st
    st = U.hysteresis_run([60, 60, 60], init_state="green")
    assert st[0] == "red" and all(s == "red" for s in st), st
    assert U.hysteresis_step("red", 40) == "red"
    assert U.hysteresis_step("red", 30) == "yellow"
    assert U.hysteresis_step("red", 10) == "green"
    assert U.hysteresis_step("green", 20) == "yellow"
    assert U.hysteresis_step("yellow", 12) == "yellow"
    assert U.hysteresis_step("yellow", 11.99) == "green"
    assert U.hysteresis_step("yellow", 50) == "red"
    # khoi tao bang nguong thuong
    assert U.hysteresis_run([45, 30])[0] == "yellow"
    assert U.hysteresis_run([None, 55, 40]) == ["missing", "red", "red"]


@check("Median 5 >= T <=> it nhat 3/5 gia tri >= T")
def test_median_property():
    rng = np.random.default_rng(C.SEED)
    n = 0
    for _ in range(20000):
        if rng.random() < 0.5:
            win = rng.uniform(0, 100, 5)
        else:
            win = rng.integers(0, 6, 5).astype(float) * 10  # nhieu gia tri bang nhau
        T = float(rng.choice([rng.uniform(0, 100), *win]))
        med = U.rolling_median(list(win))[-1]
        assert (med >= T) == (int((win >= T).sum()) >= 3), (win, T, med)
        n += 1
    return f"{n} truong hop"


@check("Tre buoc nhay: 10%x10 roi 70% -> do o khung 70 thu 3")
def test_step_delay():
    vals = [10.0] * 10 + [70.0] * 10
    states = U.hysteresis_run(U.rolling_median(vals))
    first_red = next(i for i, s in enumerate(states) if s == "red")
    delay = first_red - 10 + 1
    assert delay == 3, f"tre = {delay}, states={states}"
    assert all(s == "green" for s in states[:first_red]), states
    return f"tre {delay} khung"


@check("degrade_esp32 / prepare_condition (C1 q12, C2 q25) -> 640x640x3 uint8")
def test_degrade():
    rng = np.random.default_rng(1)
    for shape in ((1024, 1024, 3), (720, 1280, 3)):
        img = rng.integers(0, 256, shape, dtype=np.uint8)
        out = U.degrade_esp32(img)
        assert out.shape == (640, 640, 3) and out.dtype == np.uint8, (out.shape, out.dtype)
        assert np.array_equal(U.prepare_condition(img, "C1"), out), "C1 phai giong degrade_esp32 mac dinh (q12)"
        c2 = U.prepare_condition(img, "C2")
        assert c2.shape == (640, 640, 3) and c2.dtype == np.uint8
        assert np.array_equal(c2, U.degrade_esp32(img, quality=C.C2_JPEG_QUALITY))
        assert U.prepare_condition(img, "C0") is img
    assert C.ESP32_JPEG_QUALITY == 12 and C.C2_JPEG_QUALITY == 25 and tuple(C.SIM_C2_JPEG_QUALITY) == (20, 30)
    assert tuple(C.SIM["jpeg_quality"]) == (10, 15), "chuoi chinh khong duoc doi"
    assert C.PER_FRAME_C2_CSV != C.PER_FRAME_CSV and C.PERTURB_C2_CSV != C.PERTURB_CSV


@check("band() bien")
def test_band():
    assert U.band(19.99) == "green"
    assert U.band(20) == "yellow"
    assert U.band(49.99) == "yellow"
    assert U.band(50) == "red"
    assert U.band(None) == "missing" and U.band(math.nan) == "missing"


@check("M0 production + confidence + M2 hinh hoc")
def test_formulas():
    h = w = 100
    trash = np.zeros((h, w), bool)
    drain = np.zeros((h, w), bool)
    assert U.blockage_m0(trash, drain) is None
    drain[0:10, 0:10] = True
    trash[0:5, 0:10] = True
    assert U.blockage_m0(trash, drain) == 50.0
    assert U.blockage_roi(trash, drain) == 50.0
    assert U.old_confidence(np.array([]), np.array([])) == C.DEFAULT_CONFIDENCE
    assert U.old_confidence(np.array([0, 1]), np.array([0.9, 0.3])) == 0.3
    m_a = np.zeros((h, w), bool); m_a[0:5, 0:10] = True   # 50 px trong ROI
    m_b = np.zeros((h, w), bool); m_b[50:60, 50:60] = True  # ngoai ROI
    m_c = np.zeros((h, w), bool); m_c[0:10, 0:10] = True   # Drain -> bo qua
    cert = U.new_certainty(np.stack([m_a, m_b, m_c]), np.array([0, 0, 1]), np.array([0.8, 0.1, 0.2]), drain)
    assert abs(cert - 0.8) < 1e-12, cert
    assert math.isnan(U.new_certainty(np.stack([m_b]), np.array([0]), np.array([0.9]), drain))
    sq = np.array([[10, 10], [30, 10], [30, 50], [10, 50]], float)  # bw=20, bh=40
    v = U.m2_variants(sq)
    assert np.allclose(v["m2_s10_right"] - sq, [2, 0]) and np.allclose(v["m2_s05_up"] - sq, [0, -2])
    assert np.allclose(v["m2_sc110"].mean(0), sq.mean(0))
    assert np.isclose(np.ptp(v["m2_sc090"][:, 0]), 18)
    assert len(U.m2_names()) == 10 and set(U.m2_names()) == set(v)
    # rasterize: 2 polygon chong lan -> hop, khong even-odd
    a = np.array([[0, 0], [20, 0], [20, 20], [0, 20]], float)
    b = a + 10
    mask = U.rasterize_px([a, b], 40, 40)
    assert mask[15, 15], "vung chong lan bi khoet (even-odd)"
    assert U.count_flips(["green", "green", "red", "yellow", "yellow"]) == 2


@check("bootstrap_ci tat dinh va chua trung binh")
def test_bootstrap():
    x = np.random.default_rng(3).normal(10, 2, 76)
    lo, hi = U.bootstrap_ci(x)
    assert (lo, hi) == U.bootstrap_ci(x)
    assert lo < x.mean() < hi
    assert all(math.isnan(v) for v in U.bootstrap_ci([]))


def main():
    for t in TESTS:
        t()
    ok = True
    for name, passed, msg in RESULTS:
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" -- {msg}" if msg else ""))
    print(f"\n{sum(p for _, p, _ in RESULTS)}/{len(RESULTS)} PASS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
