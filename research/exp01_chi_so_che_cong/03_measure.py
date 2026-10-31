"""Buoc 3 (CPU): doc cache -> outputs/per_drain.csv (M0, M1, M2, confidence cu/moi).
Tinh cho moi dieu kien co trong cache/index.csv (C0, C1 va C2 neu da chay 02 --conds C2); tat dinh."""
import numpy as np

import config as C
import common as U

BASE_FIELDS = ["split", "stem", "drain_idx", "n_drains_in_image", "gt_area_px_1024", "condition",
               "h", "w", "roi_area_px", "gt", "gt_band", "gt_native",
               "m0", "m0_band", "m1", "m1_band"]
TAIL_FIELDS = ["old_conf", "old_flag", "new_cert", "new_flag", "n_pred_trash", "n_pred_drain"]


def main():
    gt_rows = U.read_csv(C.GT_CSV)
    gt_map = {(r["split"], r["stem"], int(r["drain_idx"])): r for r in gt_rows}
    index = U.read_csv(C.CACHE_INDEX_CSV)
    items = {(it["split"], it["stem"]): it for it in U.list_all_drain_images()}
    U.check_counts(list(items.values()))
    m2 = U.m2_names()

    rows = []
    for k, ix in enumerate(index, 1):
        key = (ix["split"], ix["stem"])
        if key not in items:
            raise KeyError(f"Cache co anh khong thuoc danh sach: {key}")
        z = np.load(C.CACHE_DIR / ix["file"])
        if str(z["stem"]) != ix["stem"]:
            raise ValueError(f"Cache sai stem: {ix['file']}")
        h, w = (int(v) for v in z["shape"])
        trash_p, drain_p = z["trash_union"], z["drain_union"]
        inst_masks, inst_cls, inst_conf = z["inst_masks"], z["inst_cls"], z["inst_conf"]
        if trash_p.shape != (h, w):
            raise ValueError(f"Kich thuoc mask khong khop: {ix['file']}")

        trash_gt, drain_masks, drains_px = U.gt_for_image(items[key]["polys"], h, w)
        m0 = U.blockage_m0(trash_p, drain_p)
        old_conf = U.old_confidence(inst_cls, inst_conf)
        for d, (roi, px) in enumerate(zip(drain_masks, drains_px)):
            g = gt_map[(ix["split"], ix["stem"], d)]
            gt = U.blockage_roi(trash_gt, roi)
            m1 = U.blockage_roi(trash_p, roi)
            row = {
                "split": ix["split"], "stem": ix["stem"], "drain_idx": d,
                "n_drains_in_image": len(drain_masks), "gt_area_px_1024": int(g["gt_area_px_1024"]),
                "condition": ix["cond"], "h": h, "w": w, "roi_area_px": int(roi.sum()),
                "gt": gt, "gt_band": U.band(gt), "gt_native": float(g["gt_blockage_pct"]),
                "m0": m0, "m0_band": U.band(m0), "m1": m1, "m1_band": U.band(m1),
            }
            for name, ppx in U.m2_variants(px).items():
                row[name] = U.blockage_roi(trash_p, U.rasterize_px([ppx], h, w))
            nc = U.new_certainty(inst_masks, inst_cls, inst_conf, roi)
            row.update({"old_conf": old_conf, "old_flag": U.flag(old_conf),
                        "new_cert": nc, "new_flag": U.flag(nc),
                        "n_pred_trash": int((inst_cls == C.TRASH_CLASS).sum()),
                        "n_pred_drain": int((inst_cls == C.DRAIN_CLASS).sum())})
            rows.append(row)
        if k % 20 == 0 or k == len(index):
            print(f"[{k}/{len(index)}]")

    U.write_csv(C.PER_DRAIN_CSV, rows, BASE_FIELDS + m2 + TAIL_FIELDS)
    for cond in [c for c in U.CONDITIONS if any(r["condition"] == c for r in rows)]:
        sub = [r for r in rows if r["condition"] == cond]
        miss = sum(1 for r in sub if r["m0"] is None)
        mae1 = np.mean([abs(r["m1"] - r["gt"]) for r in sub])
        print(f"[{cond}] n={len(sub)} M0 missing={miss} MAE(M1, tat ca)={mae1:.2f}")


if __name__ == "__main__":
    main()
