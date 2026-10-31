"""Buoc 1 (CPU): tinh muc che cong GT cho tung polygon Drain -> outputs/ground_truth.csv."""
import config as C
import common as U

FIELDS = ["split", "stem", "drain_idx", "n_drains_in_image", "img_h", "img_w",
          "gt_area_px_native", "gt_area_px_1024", "gt_area_poly_px_1024", "gt_blockage_pct", "gt_band",
          "gt_blockage_pct_640", "gt_band_640"]


def main():
    items = U.list_all_drain_images()
    U.check_counts(items)
    rows = []
    for it in items:
        img = U.read_image(it["image_path"])
        h, w = img.shape[:2]
        if (h, w) != (C.EXPECTED_NATIVE_SIZE, C.EXPECTED_NATIVE_SIZE):
            print(f"CANH BAO: {it['stem']} kich thuoc {w}x{h} (ky vong {C.EXPECTED_NATIVE_SIZE}) - dung kich thuoc that")
        trash, drains, _ = U.gt_for_image(it["polys"], h, w)
        _, drains_1024, _ = U.gt_for_image(it["polys"], C.EXPECTED_NATIVE_SIZE, C.EXPECTED_NATIVE_SIZE)
        s = C.ESP32_SIZE
        trash640, drains640, _ = U.gt_for_image(it["polys"], s, s)
        _, _, px1024 = U.gt_for_image(it["polys"], C.EXPECTED_NATIVE_SIZE, C.EXPECTED_NATIVE_SIZE)
        for k, dm in enumerate(drains):
            gt = U.blockage_roi(trash, dm)
            gt640 = U.blockage_roi(trash640, drains640[k])
            rows.append({
                "split": it["split"], "stem": it["stem"], "drain_idx": k,
                "n_drains_in_image": len(drains), "img_h": h, "img_w": w,
                "gt_area_px_native": int(dm.sum()), "gt_area_px_1024": int(drains_1024[k].sum()),
                "gt_area_poly_px_1024": U.polygon_area(px1024[k]),
                "gt_blockage_pct": gt, "gt_band": U.band(gt),
                "gt_blockage_pct_640": gt640, "gt_band_640": U.band(gt640),
            })
    C.OUT_DIR.mkdir(parents=True, exist_ok=True)
    U.write_csv(C.GT_CSV, rows, FIELDS)

    for split in ("valid", "test", "pooled"):
        sub = [r for r in rows if split == "pooled" or r["split"] == split]
        cnt = {b: sum(1 for r in sub if r["gt_band"] == b) for b in U.BANDS}
        cnt640 = {b: sum(1 for r in sub if r["gt_band_640"] == b) for b in U.BANDS}
        print(f"[{split}] {len(sub)} cong; band native {cnt}; band 640 {cnt640}")
    changed = [r for r in rows if r["gt_band"] != r["gt_band_640"]]
    if changed:
        print(f"Luu y: {len(changed)} cong doi band GT khi rasterize o 640")
    small = [r for r in rows if r["gt_area_px_1024"] < C.SMALL_DRAIN_MIN_AREA_PX_1024]
    print(f"Cong rat nho (< {C.SMALL_DRAIN_MIN_AREA_PX_1024} px2 @1024): {len(small)} "
          f"-> {[r['gt_area_px_1024'] for r in small]}")
    n_single = len({(r["split"], r["stem"]) for r in rows if r["n_drains_in_image"] == 1})
    print(f"Anh co dung 1 cong: {n_single}")


if __name__ == "__main__":
    main()
