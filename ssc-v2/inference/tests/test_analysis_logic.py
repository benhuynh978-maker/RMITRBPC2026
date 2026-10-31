"""
Test logic thuan cua analysis.py / ai_worker.py / calibrate_roi.py - KHONG can GPU,
KHONG chay model, KHONG goi mang.

Chay (tu ssc-v2\\inference):
    ..\\..\\.venv\\Scripts\\python.exe -B tests\\test_analysis_logic.py
Thoat ma != 0 neu co test that bai.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import ai_worker  # noqa: E402
import analysis  # noqa: E402
import calibrate_roi  # noqa: E402

SQUARE = [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]


def raises(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except ValueError:
        return True
    return False


# ---------------------------------------------------------------- roi_mask

def test_roi_mask_square_pixel_count():
    mask = analysis.roi_mask(SQUARE, 100, 100)
    assert mask.shape == (100, 100) and mask.dtype == bool
    # fillPoly tinh ca pixel bien: x,y tu 25..75 -> 51 x 51
    assert int(mask.sum()) == 51 * 51, int(mask.sum())
    assert mask[25, 25] and mask[75, 75] and not mask[24, 50] and not mask[76, 50]


def test_roi_mask_non_square_image_uses_w_h():
    mask = analysis.roi_mask([[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]], 40, 200)
    ys, xs = np.nonzero(mask)
    assert xs.max() == 100 and ys.max() == 39 and xs.min() == 0, (xs.max(), ys.max())


def test_roi_mask_matches_exp01_rasterization():
    # Tai hien dung common.rasterize_norm cua exp01 (khong import de giu research read-only)
    poly = np.array([[0.1, 0.2], [0.83, 0.31], [0.66, 0.9], [0.05, 0.77]])
    h, w = 333, 517
    ref = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(ref, [np.round(poly * np.array([w, h])).astype(np.int32).reshape(-1, 1, 2)], 1)
    assert np.array_equal(analysis.roi_mask(poly.tolist(), h, w), ref.astype(bool))


# ---------------------------------------------------------------- blockage_in_roi

def test_blockage_in_roi_cases():
    roi = np.zeros((10, 10), dtype=bool)
    roi[0:10, 0:4] = True  # 40 px
    trash = np.zeros_like(roi)
    assert analysis.blockage_in_roi(trash, roi) == (0.0, 0)
    trash[:, 0:2] = True  # 20 px trong ROI
    assert analysis.blockage_in_roi(trash, roi) == (50.0, 20)
    trash[:, :] = True  # phu het (ca ngoai ROI)
    assert analysis.blockage_in_roi(trash, roi) == (100.0, 40)
    outside = np.zeros_like(roi)
    outside[:, 5:] = True  # rac chi nam ngoai ROI -> bo qua
    assert analysis.blockage_in_roi(outside, roi) == (0.0, 0)
    one_third = np.zeros((3, 1), dtype=bool)
    one_third[0, 0] = True
    assert analysis.blockage_in_roi(one_third, np.ones((3, 1), dtype=bool))[0] == 33.33


def test_blockage_in_roi_empty_roi_rejected():
    assert raises(analysis.blockage_in_roi, np.ones((4, 4), bool), np.zeros((4, 4), bool))


# ---------------------------------------------------------------- weighted_certainty

def test_weighted_certainty():
    roi = np.zeros((10, 10), dtype=bool)
    roi[:, :5] = True
    a = np.zeros_like(roi)
    a[0, 0:3] = True  # 3 px trong ROI
    b = np.zeros_like(roi)
    b[1, 3:8] = True  # 2 px trong ROI (3,4), 3 px ngoai
    drain = np.ones_like(roi)  # lop Drain -> bo qua
    far = np.zeros_like(roi)
    far[5, 6:10] = True  # Trash ngoai ROI -> trong so 0
    inst = [(a, 0, 0.9), (b, 0, 0.4), (drain, 1, 0.1), (far, 0, 0.01)]
    got = analysis.weighted_certainty(inst, roi)
    assert abs(got - (3 * 0.9 + 2 * 0.4) / 5) < 1e-12, got
    assert analysis.weighted_certainty([(far, 0, 0.5), (drain, 1, 0.9)], roi) is None
    assert analysis.weighted_certainty([], roi) is None


# ---------------------------------------------------------------- brightness

def test_brightness_gate():
    black = np.zeros((50, 60, 3), dtype=np.uint8)
    ok, value = analysis.brightness_ok(black)
    assert ok is False and value == 0.0
    normal = np.full((50, 60, 3), 128, dtype=np.uint8)
    ok, value = analysis.brightness_ok(normal)
    assert ok is True and abs(value - 128) < 1e-9
    edge = np.full((5, 5, 3), 40, dtype=np.uint8)
    assert analysis.brightness_ok(edge, threshold=40)[0] is True
    assert analysis.brightness_ok(edge, threshold=40.5)[0] is False


def test_analyze_dark_image_skips_model():
    original_predict = analysis.predict

    def boom(_image):
        raise AssertionError("Model khong duoc chay voi anh toi")

    analysis.predict = boom
    try:
        ok, buf = cv2.imencode(".jpg", np.full((64, 80, 3), 5, dtype=np.uint8))
        assert ok
        result = analysis.analyze(buf.tobytes(), roi=SQUARE, quality_gate=True)
    finally:
        analysis.predict = original_predict
    assert result["usable"] is False and result["quality_reason"] == "thieu_sang"
    assert result["confidence"] == 0.575
    assert "waste_coverage_pct" not in result and "drain_blockage_pct" not in result
    decoded = cv2.imdecode(np.frombuffer(result["analyzed_bytes"], np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (64, 80, 3)


def test_analyze_degenerate_roi_rejected_before_model():
    ok, buf = cv2.imencode(".jpg", np.full((32, 32, 3), 128, dtype=np.uint8))
    assert raises(analysis.analyze, buf.tobytes(), roi=[[0.1, 0.1], [0.1, 0.1], [0.1, 0.1]])
    assert raises(analysis.analyze, buf.tobytes(), roi=[[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]])


# ---------------------------------------------------------------- polygon validation

def test_polygon_validation():
    assert analysis.validate_roi_polygon(SQUARE) == SQUARE
    assert analysis.validate_roi_polygon([[0, 0], [1, 0], [1, 1]]) == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]
    bad = [
        None, "abc", {}, [], [[0, 0], [1, 1]],
        [[0, 0], [1, 0], [1]], [[0, 0], [1, 0], [1, 1, 1]],
        [[0, 0], [1, 0], ["1", 1]], [[0, 0], [1, 0], [True, 1]],
        [[0, 0], [1.2, 0], [1, 1]], [[0, 0], [-0.1, 0], [1, 1]],
        [[0, 0], [float("nan"), 0], [1, 1]], [[0, 0], [float("inf"), 0], [1, 1]],
        [[0.2, 0.2], [0.2, 0.2], [0.2, 0.2]], [[0, 0], [0.5, 0.5], [1, 1]],
        [0.1, 0.2, 0.3],
    ]
    for polygon in bad:
        assert raises(analysis.validate_roi_polygon, polygon), polygon


def test_parse_drain_roi():
    assert ai_worker.parse_drain_roi({}) == (None, None)
    assert ai_worker.parse_drain_roi({"drain_roi": None}) == (None, None)
    poly, version = ai_worker.parse_drain_roi({"drain_roi": {"polygon": SQUARE, "version": "v3"}})
    assert poly == SQUARE and version == "v3"
    for drain_roi in (
        [SQUARE], "x", {"polygon": SQUARE}, {"polygon": SQUARE, "version": 3},
        {"polygon": SQUARE, "version": ""}, {"version": "v1"},
        {"polygon": [[0, 0], [2, 0], [1, 1]], "version": "v1"},
    ):
        assert raises(ai_worker.parse_drain_roi, {"drain_roi": drain_roi}), drain_roi


def test_parse_polygon_cli_arg():
    assert calibrate_roi.parse_polygon_arg("0.1,0.2 0.5,0.2  0.3,0.9") == [[0.1, 0.2], [0.5, 0.2], [0.3, 0.9]]
    for text in ("0.1,0.2 0.5", "a,b 0.5,0.2 0.3,0.9", "0.1,0.2 0.5,0.2", "0.1,0.2,0.3 0.5,0.2 0.3,0.9"):
        assert raises(calibrate_roi.parse_polygon_arg, text), text


def test_contour_to_polygon():
    mask = np.zeros((200, 300), dtype=np.uint8)
    cv2.rectangle(mask, (60, 50), (239, 149), 1, thickness=-1)
    poly = calibrate_roi.contour_to_polygon(mask.astype(bool))
    assert poly is not None and 3 <= len(poly) <= 64
    roi = analysis.roi_mask(poly, 200, 300)
    iou = np.logical_and(roi, mask > 0).sum() / np.logical_or(roi, mask > 0).sum()
    assert iou > 0.97, iou
    circle = np.zeros((400, 400), dtype=np.uint8)
    cv2.circle(circle, (200, 200), 150, 1, thickness=-1)
    poly = calibrate_roi.contour_to_polygon(circle.astype(bool), max_points=8)
    assert poly is not None and len(poly) <= 8
    assert calibrate_roi.contour_to_polygon(np.zeros((10, 10), bool)) is None


# ---------------------------------------------------------------- payload builder

ALLOWED_KEYS = {
    "camera_id", "observation_id", "waste_coverage_pct", "drain_blockage_pct", "confidence",
    "analyzed_url", "usable", "quality_reason", "certainty", "no_trash_in_roi",
    "blockage_method", "roi_version",
}


def check_contract(payload: dict) -> None:
    assert set(payload) <= ALLOWED_KEYS, set(payload) - ALLOWED_KEYS
    assert isinstance(payload["usable"], bool)
    assert isinstance(payload["confidence"], float)
    if payload["usable"]:
        assert "quality_reason" not in payload
        assert payload["blockage_method"] in ("roi", "legacy")
        assert payload["certainty"] is None or 0.0 <= payload["certainty"] <= 1.0
    else:
        assert isinstance(payload["quality_reason"], str) and payload["quality_reason"]
        assert "waste_coverage_pct" not in payload and "drain_blockage_pct" not in payload
    json.dumps(payload)  # phai serialize duoc


def test_payload_roi_case():
    result = {
        "usable": True, "waste_coverage_pct": 12.5, "drain_blockage_pct": 40.0, "confidence": 0.31,
        "certainty": 0.7123, "no_trash_in_roi": False, "blockage_method": "roi", "analyzed_bytes": b"x",
    }
    payload = ai_worker.build_result_payload("C1", "O1", result, "/api/images/a.jpg", "v2")
    assert payload == {
        "camera_id": "C1", "observation_id": "O1", "waste_coverage_pct": 12.5, "drain_blockage_pct": 40.0,
        "confidence": 0.31, "usable": True, "certainty": 0.7123, "no_trash_in_roi": False,
        "blockage_method": "roi", "roi_version": "v2", "analyzed_url": "/api/images/a.jpg",
    }, payload
    check_contract(payload)
    # tat dinh: goi lai ra y het (ca thu tu khoa -> JSON giong tung byte)
    again = ai_worker.build_result_payload("C1", "O1", dict(result), "/api/images/a.jpg", "v2")
    assert json.dumps(again) == json.dumps(payload)


def test_payload_roi_clean_drain():
    result = {
        "usable": True, "waste_coverage_pct": 3.0, "drain_blockage_pct": 0.0, "confidence": 0.5,
        "certainty": None, "no_trash_in_roi": True, "blockage_method": "roi", "analyzed_bytes": b"x",
    }
    payload = ai_worker.build_result_payload("C1", "O1", result, None, "v1")
    assert payload["drain_blockage_pct"] == 0.0 and payload["certainty"] is None
    assert payload["no_trash_in_roi"] is True and "analyzed_url" not in payload
    check_contract(payload)


def test_payload_legacy_no_drain():
    result = {
        "usable": True, "waste_coverage_pct": 1.25, "confidence": 0.575, "certainty": None,
        "blockage_method": "legacy", "analyzed_bytes": b"x",
    }
    payload = ai_worker.build_result_payload("C1", "O1", result, "/api/images/b.jpg", None)
    assert payload == {
        "camera_id": "C1", "observation_id": "O1", "waste_coverage_pct": 1.25, "confidence": 0.575,
        "usable": True, "certainty": None, "blockage_method": "legacy", "roi_version": None,
        "analyzed_url": "/api/images/b.jpg",
    }, payload
    check_contract(payload)


def test_payload_legacy_with_drain():
    result = {
        "usable": True, "waste_coverage_pct": 9.0, "drain_blockage_pct": 22.22, "confidence": 0.4,
        "certainty": 0.6, "no_trash_in_roi": False, "blockage_method": "legacy", "analyzed_bytes": b"x",
    }
    payload = ai_worker.build_result_payload("C1", "O1", result, None, None)
    assert payload["drain_blockage_pct"] == 22.22 and payload["blockage_method"] == "legacy"
    assert payload["no_trash_in_roi"] is False and payload["roi_version"] is None
    check_contract(payload)


def test_payload_unusable():
    result = {
        "usable": False, "quality_reason": "thieu_sang", "brightness": 12.0, "confidence": 0.575,
        "analyzed_bytes": b"x",
    }
    payload = ai_worker.build_result_payload("C1", "O1", result, "/api/images/c.jpg", "v4")
    assert payload == {
        "camera_id": "C1", "observation_id": "O1", "confidence": 0.575, "usable": False,
        "quality_reason": "thieu_sang", "roi_version": "v4", "analyzed_url": "/api/images/c.jpg",
    }, payload
    check_contract(payload)
    no_conf = {k: v for k, v in result.items() if k != "confidence"}
    assert ai_worker.build_result_payload("C1", "O1", no_conf, None, None)["confidence"] == 0.575


def test_worker_bad_roi_reports_fail_without_download():
    calls = {"fail": [], "get": 0}
    original_fail, original_get = ai_worker._fail, ai_worker.requests.get
    ai_worker._fail = lambda cam, obs, msg: calls["fail"].append(msg)

    def fake_get(*_a, **_k):
        calls["get"] += 1
        raise AssertionError("khong duoc tai anh khi ROI hong")

    ai_worker.requests.get = fake_get
    try:
        ai_worker._process_job({
            "camera_id": "C1", "observation_id": "O1",
            "image_url": "/api/images/0123abcd-0000-0000-0000-000000000000.jpg",
            "drain_roi": {"polygon": [[0, 0], [1, 1]], "version": "v1"},
        })
    finally:
        ai_worker._fail, ai_worker.requests.get = original_fail, original_get
    assert calls["get"] == 0 and len(calls["fail"]) == 1 and "ROI" in calls["fail"][0], calls


def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} test dat")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
