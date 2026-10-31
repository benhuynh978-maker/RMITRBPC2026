"""Buoc 4 (GPU): mo phong camera co dinh, 20 khung / anh, canh tinh (GT khong doi).
-> outputs/per_frame.csv, outputs/perturbations.csv (chinh, JPEG cuoi q10..15).

`--variant C2` (bo sung): giong het (cung seed [SEED, image_idx, frame], cung moi nhieu), chi JPEG cuoi
q20..30 -> outputs/per_frame_C2.csv, outputs/perturbations_C2.csv (KHONG ghi de file chinh)."""
import argparse
import math

import cv2
import numpy as np

import config as C
import common as U

S = C.SIM
FRAME_FIELDS = ["split", "stem", "image_idx", "drain_idx", "frame", "gt", "gt_band", "m0", "m1",
                "shadow", "occluder", "occluder_on_drain"]
PERT_FIELDS = ["split", "stem", "image_idx", "frame", "contrast", "brightness", "gamma",
               "tx_px", "ty_px", "rot_deg", "shadow", "shadow_nv", "shadow_cx", "shadow_cy", "shadow_r",
               "shadow_area_frac", "occluder", "occ_drain_idx", "occ_target_frac", "occ_actual_frac",
               "occ_x0", "occ_y0", "occ_x1", "occ_y1", "occ_color", "noise_sigma", "jpeg_q", "infer_time_s"]


def _rect(cx, cy, s, aspect, h, w):
    hw = s * math.sqrt(aspect) / 2
    hh = s / math.sqrt(aspect) / 2
    x0, x1 = int(max(0, round(cx - hw))), int(min(w, round(cx + hw) + 1))
    y0, y1 = int(max(0, round(cy - hh))), int(min(h, round(cy + hh) + 1))
    return x0, y0, x1, y1


def place_occluder(roi, frac, aspect, rng):
    """Hinh chu nhat tam la 1 pixel ngau nhien trong ROI, co lon sao cho phu ~frac dien tich ROI."""
    h, w = roi.shape
    area = roi.sum()
    ys, xs = np.nonzero(roi)
    j = int(rng.integers(len(ys)))
    cy, cx = float(ys[j]), float(xs[j])
    lo, hi = 0.0, 2.0 * max(h, w)
    for _ in range(30):
        mid = (lo + hi) / 2
        x0, y0, x1, y1 = _rect(cx, cy, mid, aspect, h, w)
        if roi[y0:y1, x0:x1].sum() / area < frac:
            lo = mid
        else:
            hi = mid
    x0, y0, x1, y1 = _rect(cx, cy, hi, aspect, h, w)
    return (x0, y0, x1, y1), float(roi[y0:y1, x0:x1].sum() / area)


def make_frame(base, rois_native, rng, jpeg_range=S["jpeg_quality"]):
    h, w = base.shape[:2]
    p = {}
    x = base.astype(np.float32)

    # anh sang
    p["contrast"] = rng.uniform(*S["contrast_range"])
    p["brightness"] = rng.uniform(*S["brightness_range"])
    p["gamma"] = rng.uniform(*S["gamma_range"])
    mean = float(x.mean())
    x = ((x - mean) * p["contrast"] + mean) * p["brightness"]
    x = 255.0 * (np.clip(x, 0, 255) / 255.0) ** p["gamma"]

    # rung (ROI/GT giu co dinh)
    p["tx_px"] = rng.uniform(-S["translate_frac"], S["translate_frac"]) * w
    p["ty_px"] = rng.uniform(-S["translate_frac"], S["translate_frac"]) * h
    p["rot_deg"] = rng.uniform(-S["rotate_deg"], S["rotate_deg"])
    M = cv2.getRotationMatrix2D((w / 2, h / 2), p["rot_deg"], 1.0)
    M[:, 2] += (p["tx_px"], p["ty_px"])
    x = cv2.warpAffine(x, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # bong do mem
    p["shadow"] = bool(rng.random() < S["shadow_p"])
    if p["shadow"]:
        nv = int(rng.integers(*S["shadow_vertices"]))
        cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h
        r = rng.uniform(0.15, 0.4) * min(h, w)
        ang = np.sort(rng.uniform(0, 2 * np.pi, nv))
        rad = r * rng.uniform(0.6, 1.0, nv)
        pts = np.stack([cx + rad * np.cos(ang), cy + rad * np.sin(ang)], 1)
        sm = np.zeros((h, w), np.float32)
        cv2.fillPoly(sm, [np.round(pts).astype(np.int32).reshape(-1, 1, 2)], 1.0)
        sigma = S["shadow_blur_frac"] * min(h, w)
        sm = cv2.GaussianBlur(sm, (0, 0), sigmaX=sigma, sigmaY=sigma)
        x *= (1.0 - (1.0 - S["shadow_factor"]) * sm)[..., None]
        p.update(shadow_nv=nv, shadow_cx=cx, shadow_cy=cy, shadow_r=r, shadow_area_frac=float((sm > 0.5).mean()))

    # vat che tam thoi
    p["occluder"] = bool(rng.random() < S["occluder_p"])
    if p["occluder"]:
        d = int(rng.integers(len(rois_native)))
        frac = rng.uniform(*S["occluder_area_frac"])
        aspect = rng.uniform(*S["occluder_aspect"])
        (x0, y0, x1, y1), actual = place_occluder(rois_native[d], frac, aspect, rng)
        if rng.random() < 0.5:
            color = np.full(3, rng.integers(30, 226), dtype=np.float32)
        else:
            color = rng.integers(0, 256, 3).astype(np.float32)
        patch = np.broadcast_to(color, (y1 - y0, x1 - x0, 3)).astype(np.float32)
        patch = patch + rng.normal(0, S["occluder_noise_sigma"], patch.shape)
        x[y0:y1, x0:x1] = patch
        p.update(occ_drain_idx=d, occ_target_frac=frac, occ_actual_frac=actual,
                 occ_x0=x0, occ_y0=y0, occ_x1=x1, occ_y1=y1,
                 occ_color="-".join(str(int(c)) for c in color))

    # nhieu -> resize -> jpeg
    p["noise_sigma"] = rng.uniform(*S["noise_sigma"])
    x = x + rng.normal(0, p["noise_sigma"], x.shape)
    x = np.clip(x, 0, 255).astype(np.uint8)
    x = cv2.resize(x, (S["size"], S["size"]), interpolation=cv2.INTER_AREA)
    p["jpeg_q"] = int(rng.integers(jpeg_range[0], jpeg_range[1] + 1))  # buoc rng cuoi cung
    return U.jpeg_roundtrip(x, p["jpeg_q"]), p


VARIANTS = {
    "C1": {"jpeg_range": S["jpeg_quality"], "frame_csv": C.PER_FRAME_CSV, "pert_csv": C.PERTURB_CSV,
           "warmup_q": C.ESP32_JPEG_QUALITY},
    "C2": {"jpeg_range": C.SIM_C2_JPEG_QUALITY, "frame_csv": C.PER_FRAME_C2_CSV, "pert_csv": C.PERTURB_C2_CSV,
           "warmup_q": C.C2_JPEG_QUALITY},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="C1", choices=sorted(VARIANTS))
    variant = ap.parse_args().variant
    V = VARIANTS[variant]
    print(f"[bien the] {variant}: JPEG cuoi q{V['jpeg_range'][0]}..{V['jpeg_range'][1]} -> {V['frame_csv'].name}")
    items = U.list_all_drain_images()
    U.check_counts(items)
    device = U.get_device()
    model = U.load_model()
    size = S["size"]
    U.run_model(model, U.degrade_esp32(U.read_image(items[0]["image_path"]), quality=V["warmup_q"]), device)  # khoi dong

    frame_rows, pert_rows = [], []
    for gi, it in enumerate(items):
        base = U.read_image(it["image_path"])
        h, w = base.shape[:2]
        _, rois_native, _ = U.gt_for_image(it["polys"], h, w)
        trash640, rois640, _ = U.gt_for_image(it["polys"], size, size)
        gts = [U.blockage_roi(trash640, r) for r in rois640]
        for f in range(C.N_FRAMES):
            rng = np.random.default_rng([C.SEED, gi, f])
            frame, p = make_frame(base, rois_native, rng, V["jpeg_range"])
            out = U.run_model(model, frame, device)
            m0 = U.blockage_m0(out["trash_union"], out["drain_union"])
            pert_rows.append({"split": it["split"], "stem": it["stem"], "image_idx": gi, "frame": f,
                              **p, "infer_time_s": out["time_s"]})
            for d, roi in enumerate(rois640):
                frame_rows.append({
                    "split": it["split"], "stem": it["stem"], "image_idx": gi, "drain_idx": d, "frame": f,
                    "gt": gts[d], "gt_band": U.band(gts[d]), "m0": m0,
                    "m1": U.blockage_roi(out["trash_union"], roi),
                    "shadow": p["shadow"], "occluder": p["occluder"],
                    "occluder_on_drain": p["occluder"] and p.get("occ_drain_idx") == d,
                })
        print(f"[{gi + 1}/{len(items)}] {it['split']} {it['stem'][:50]}")

    U.write_csv(V["frame_csv"], frame_rows, FRAME_FIELDS)
    U.write_csv(V["pert_csv"], pert_rows, PERT_FIELDS)
    n_sh = sum(1 for r in pert_rows if r["shadow"])
    n_oc = sum(1 for r in pert_rows if r["occluder"])
    ts = np.array([r["infer_time_s"] for r in pert_rows])
    print(f"Khung: {len(pert_rows)}; bong do {n_sh}; vat che {n_oc}; infer median {np.median(ts) * 1000:.1f} ms")


if __name__ == "__main__":
    main()
