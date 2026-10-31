"""Buoc 2 (GPU): chay model 1 lan / anh / dieu kien (C0 goc, C1 ESP32-like q12, C2 ESP32-like q25) -> cache/*.npz.

Mac dinh chay C0 C1 (nhu ban dau). Chon dieu kien: `--conds C2` -> chi chay C2; cac dong cua dieu kien
khac trong cache/index.csv va outputs/inference_times.csv duoc GIU NGUYEN (khong tinh lai).
"""
import argparse

import numpy as np

import config as C
import common as U

DEFAULT_CONDITIONS = ("C0", "C1")


def cache_name(split, idx, cond):
    return f"{split}_{idx:03d}_{cond}.npz"


def merge_rows(old_rows, new_rows, conds, order_key):
    """Giu dong cu cua dieu kien khong chay lai, thay dong cua dieu kien da chay; sap theo (thu tu anh, dieu kien)."""
    keep = [r for r in old_rows if r["cond"] not in conds]
    merged = keep + new_rows
    return sorted(merged, key=order_key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", nargs="+", default=list(DEFAULT_CONDITIONS), choices=list(U.CONDITIONS))
    conds = tuple(c for c in U.CONDITIONS if c in ap.parse_args().conds)
    print(f"[dieu kien] {conds}")

    items = U.list_all_drain_images()
    U.check_counts(items)
    device = U.get_device()
    model = U.load_model()
    C.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # khoi dong (khong tinh thoi gian)
    U.run_model(model, U.read_image(items[0]["image_path"]), device)

    index_rows, timing_rows = [], []
    counters = {s: 0 for s in C.SPLITS}
    for n, it in enumerate(items, 1):
        idx = counters[it["split"]]
        counters[it["split"]] += 1
        img = U.read_image(it["image_path"])
        for cond in conds:
            x = U.prepare_condition(img, cond)
            out = U.run_model(model, x, device)
            fname = cache_name(it["split"], idx, cond)
            np.savez_compressed(
                C.CACHE_DIR / fname,
                trash_union=out["trash_union"], drain_union=out["drain_union"],
                inst_masks=out["inst_masks"], inst_cls=out["inst_cls"], inst_conf=out["inst_conf"],
                stem=np.array(it["stem"]), shape=np.array(x.shape[:2]), time_s=np.array(out["time_s"]),
            )
            n_tr = int((out["inst_cls"] == C.TRASH_CLASS).sum())
            n_dr = int((out["inst_cls"] == C.DRAIN_CLASS).sum())
            index_rows.append({"split": it["split"], "idx": idx, "stem": it["stem"], "cond": cond,
                               "file": fname, "h": x.shape[0], "w": x.shape[1],
                               "n_trash": n_tr, "n_drain": n_dr})
            timing_rows.append({"split": it["split"], "stem": it["stem"], "cond": cond,
                                "h": x.shape[0], "w": x.shape[1], "time_s": out["time_s"]})
        if n % 10 == 0 or n == len(items):
            print(f"[{n}/{len(items)}] {it['split']} {it['stem'][:50]}")

    # thu tu anh = thu tu items (valid roi test, theo stem); trong moi anh: C0, C1, C2
    pos = {(it["split"], it["stem"]): i for i, it in enumerate(items)}
    order = lambda r: (pos[(r["split"], r["stem"])], U.CONDITIONS.index(r["cond"]))  # noqa: E731
    if set(conds) != set(U.CONDITIONS):
        old_index = U.read_csv(C.CACHE_INDEX_CSV) if C.CACHE_INDEX_CSV.exists() else []
        old_timing = U.read_csv(C.TIMING_CSV) if C.TIMING_CSV.exists() else []
        index_rows = merge_rows(old_index, index_rows, conds, order)
        timing_rows = merge_rows(old_timing, timing_rows, conds, order)
    U.write_csv(C.CACHE_INDEX_CSV, index_rows, list(index_rows[0].keys()))
    U.write_csv(C.TIMING_CSV, timing_rows, list(timing_rows[0].keys()))
    for cond in conds:
        ts = np.array([float(r["time_s"]) for r in timing_rows if r["cond"] == cond])
        print(f"[thoi gian] {cond}: trung binh {ts.mean() * 1000:.1f} ms, median {np.median(ts) * 1000:.1f} ms, n={ts.size}")


if __name__ == "__main__":
    main()
