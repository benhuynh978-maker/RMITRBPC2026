"""Buoc 5 (CPU): chi so, tieu chi dang ky truoc, bieu do, vi du, summary.json, REPORT.md."""
import json
import math

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import config as C
import common as U

COL = {"M0": "#2a78d6", "M1": "#eb6834", "C0": "#2a78d6", "C1": "#eb6834",
       "green": "#0ca30c", "yellow": "#fab219", "red": "#d03b3b",
       "ink": "#0b0b0b", "muted": "#898781", "grid": "#e1e0d9", "surface": "#fcfcfb"}
BAND_VI = {"green": "xanh", "yellow": "vàng", "red": "đỏ", "missing": "thiếu"}
SUBSETS = ("pooled", "test", "valid")
SUBSET_VI = {"pooled": "gộp valid+test", "test": "chỉ test", "valid": "chỉ valid"}
M2 = U.m2_names()
M2_S05 = [f"m2_s05_{d}" for d in C.M2_DIRECTIONS]
M2_S10 = [f"m2_s10_{d}" for d in C.M2_DIRECTIONS]

plt.rcParams.update({"figure.facecolor": COL["surface"], "axes.facecolor": COL["surface"],
                     "axes.edgecolor": COL["muted"], "axes.labelcolor": COL["ink"],
                     "xtick.color": COL["muted"], "ytick.color": COL["muted"],
                     "axes.grid": True, "grid.color": COL["grid"], "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 9})


# ---------------------------------------------------------------- tien ich

def nanmean(xs):
    xs = [x for x in xs if not U.is_missing(x)]
    return float(np.mean(xs)) if xs else math.nan


def f2(v, nd=2):
    return "—" if U.is_missing(v) else f"{v:.{nd}f}"


def ci_str(d):
    return f"{f2(d['mean'])} [{f2(d['ci'][0])}; {f2(d['ci'][1])}]"


def mae_ci(errs):
    errs = [e for e in errs if not U.is_missing(e)]
    return {"mean": nanmean(errs), "ci": U.bootstrap_ci(errs), "n": len(errs)}


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


# ---------------------------------------------------------------- doc du lieu

def load_drains():
    rows = U.read_csv(C.PER_DRAIN_CSV)
    num = ["gt", "gt_native", "m0", "m1", "old_conf", "new_cert"] + M2
    for r in rows:
        for k in num:
            r[k] = U.to_float(r[k])
        for k in ("drain_idx", "n_drains_in_image", "gt_area_px_1024", "roi_area_px", "h", "w"):
            r[k] = int(r[k])
        r["old_flag"] = r["old_flag"] == "1"
        r["new_flag"] = r["new_flag"] == "1"
    return rows


def select(rows, cond, subset, filt="all"):
    out = [r for r in rows if r["condition"] == cond and (subset == "pooled" or r["split"] == subset)]
    if filt == "single":
        out = [r for r in out if r["n_drains_in_image"] == 1]
    elif filt == "large":
        out = [r for r in out if r["gt_area_px_1024"] >= C.SMALL_DRAIN_MIN_AREA_PX_1024]
    return out


# ---------------------------------------------------------------- chi so per-drain

def confusion(rows, key, cols):
    m = {g: {p: 0 for p in cols} for g in U.BANDS}
    for r in rows:
        if r[key] not in cols:
            raise ValueError(f"Muc du doan khong mong doi '{r[key]}' cho {key}")
        m[r["gt_band"]][r[key]] += 1
    return m


def critical_misses(rows, key):
    return sum(1 for r in rows if r["gt_band"] == "red" and r[key] in ("green", "missing"))


def false_alarms(rows, key):
    return sum(1 for r in rows if r["gt_band"] == "green" and r[key] == "red")


def drain_block(rows):
    ok = [r for r in rows if not U.is_missing(r["m0"])]
    red = [r for r in rows if r["gt_band"] == "red"]
    b = {
        "n": len(rows), "n_m0_ok": len(ok), "n_gt_red": len(red),
        "gt_bands": {g: sum(1 for r in rows if r["gt_band"] == g) for g in U.BANDS},
        "m0_missing": len(rows) - len(ok),
        "m0_missing_rate": (len(rows) - len(ok)) / len(rows) if rows else math.nan,
        "m0_missing_red": sum(1 for r in red if U.is_missing(r["m0"])),
        "m1_missing_red": sum(1 for r in red if U.is_missing(r["m1"])),
        "mae_m0": mae_ci([abs(r["m0"] - r["gt"]) for r in ok]),
        "mae_m1_same": mae_ci([abs(r["m1"] - r["gt"]) for r in ok]),
        "diff_m1_minus_m0": mae_ci([abs(r["m1"] - r["gt"]) - abs(r["m0"] - r["gt"]) for r in ok]),
        "mae_m1_all": mae_ci([abs(r["m1"] - r["gt"]) for r in rows]),
        "m2": {k: mae_ci([abs(r[k] - r["gt"]) for r in rows]) for k in M2},
        "crit_m0": critical_misses(rows, "m0_band"), "crit_m1": critical_misses(rows, "m1_band"),
        "fa_m0": false_alarms(rows, "m0_band"), "fa_m1": false_alarms(rows, "m1_band"),
        "conf_m0": confusion(rows, "m0_band", list(U.BANDS) + ["missing"]),
        "conf_m1": confusion(rows, "m1_band", list(U.BANDS)),
    }
    b["m2_s05_mean4"] = nanmean([b["m2"][k]["mean"] for k in M2_S05])
    b["m2_s10_mean4"] = nanmean([b["m2"][k]["mean"] for k in M2_S10])
    return b


def conf_block(rows):
    out = {"n": len(rows)}
    for which in ("old", "new"):
        fl = [r for r in rows if r[f"{which}_flag"]]
        nf = [r for r in rows if not r[f"{which}_flag"]]
        out[which] = {
            "frac_flagged": len(fl) / len(rows) if rows else math.nan,
            "n_flagged": len(fl),
            "mae_m1_flagged": nanmean([abs(r["m1"] - r["gt"]) for r in fl]),
            "mae_m1_not_flagged": nanmean([abs(r["m1"] - r["gt"]) for r in nf]),
        }
    out["new"]["n_nan"] = sum(1 for r in rows if U.is_missing(r["new_cert"]))
    return out


# ---------------------------------------------------------------- lam muot

def load_series(path=C.PER_FRAME_CSV):
    rows = U.read_csv(path)
    series = {}
    for r in rows:
        key = (int(r["image_idx"]), int(r["drain_idx"]))
        s = series.setdefault(key, {"split": r["split"], "stem": r["stem"], "gt": float(r["gt"]),
                                    "gt_band": r["gt_band"], "frames": {}})
        s["frames"][int(r["frame"])] = (U.to_float(r["m0"]), float(r["m1"]), r["occluder_on_drain"] == "1")
    for key, s in series.items():
        if sorted(s["frames"]) != list(range(C.N_FRAMES)):
            raise ValueError(f"Chuoi {key} thieu khung")
        fr = [s["frames"][f] for f in range(C.N_FRAMES)]
        s["m0"] = [None if U.is_missing(a) else a for a, _, _ in fr]
        s["m1"] = [b for _, b, _ in fr]
        s["occ"] = [c for _, _, c in fr]
    return dict(sorted(series.items()))


def analyze_series(vals, gt, gtb, occ):
    ev = list(range(C.WARMUP_FRAMES, C.N_FRAMES))
    s1 = U.rolling_median(vals)
    s0_states = [U.band(vals[t]) for t in ev]
    s1_states = [U.band(s1[t]) for t in ev]
    s2_states = U.hysteresis_run([s1[t] for t in ev])
    known = [t for t in ev if not U.is_missing(vals[t])]
    raw_all = [v for v in vals if not U.is_missing(v)]
    return {
        "s1": s1, "s2_states": s2_states, "s0_states": s0_states,
        "n_eval": len(ev),
        "flips0": U.count_flips(s0_states), "flips1": U.count_flips(s1_states),
        "flips2": U.count_flips(s2_states),
        "acc0": sum(1 for s in s0_states if s == gtb), "acc1": sum(1 for s in s1_states if s == gtb),
        "acc2": sum(1 for s in s2_states if s == gtb),
        "err0": [abs(vals[t] - gt) for t in known], "err1": [abs(s1[t] - gt) for t in known],
        "err0_occ": [abs(vals[t] - gt) for t in known if occ[t]],
        "err1_occ": [abs(s1[t] - gt) for t in known if occ[t]],
        "bias": (float(np.mean(raw_all)) - gt) if raw_all else math.nan,
        "noise": float(np.std(raw_all)) if raw_all else math.nan,
        "n_known_eval": len(known),
    }


def smooth_block(analyses):
    a = analyses
    n_eval = sum(x["n_eval"] for x in a)
    err0 = [e for x in a for e in x["err0"]]
    err1 = [e for x in a for e in x["err1"]]
    dpd = [np.mean(x["err1"]) - np.mean(x["err0"]) for x in a if x["err0"]]
    dec = [x for x in a if not U.is_missing(x["bias"])]
    b2 = sum(x["bias"] ** 2 for x in dec)
    var = sum(x["noise"] ** 2 for x in dec)
    f0 = [x["flips0"] for x in a]
    f2_ = [x["flips2"] for x in a]
    return {
        "n_drains": len(a), "n_eval_frames": n_eval, "n_err_frames": len(err0),
        "mae_s0": nanmean(err0), "mae_s1": nanmean(err1),
        "diff_s1_minus_s0_per_drain": {"mean": nanmean(dpd), "ci": U.bootstrap_ci(dpd)},
        "mae_s0_occluded": nanmean([e for x in a for e in x["err0_occ"]]),
        "mae_s1_occluded": nanmean([e for x in a for e in x["err1_occ"]]),
        "n_occluded_frames": sum(len(x["err0_occ"]) for x in a),
        "flips_s0": int(sum(f0)), "flips_s1": int(sum(x["flips1"] for x in a)), "flips_s2": int(sum(f2_)),
        "flips_s0_per_drain_mean": nanmean(f0), "flips_s2_per_drain_mean": nanmean(f2_),
        "flips_s0_max": int(max(f0)) if f0 else 0, "flips_s2_max": int(max(f2_)) if f2_ else 0,
        "drains_zero_flips_s0": sum(1 for v in f0 if v == 0), "drains_zero_flips_s2": sum(1 for v in f2_ if v == 0),
        "acc_s0": 100 * sum(x["acc0"] for x in a) / n_eval if n_eval else math.nan,
        "acc_s1": 100 * sum(x["acc1"] for x in a) / n_eval if n_eval else math.nan,
        "acc_s2": 100 * sum(x["acc2"] for x in a) / n_eval if n_eval else math.nan,
        "mean_abs_bias": nanmean([abs(x["bias"]) for x in dec]),
        "mean_noise": nanmean([x["noise"] for x in dec]),
        "mse_share_bias": b2 / (b2 + var) if (b2 + var) > 0 else math.nan,
        "mse_share_var": var / (b2 + var) if (b2 + var) > 0 else math.nan,
    }


def step_delay_test():
    vals = [10.0] * 10 + [70.0] * 10
    states = U.hysteresis_run(U.rolling_median(vals))
    first_red = next((i for i, s in enumerate(states) if s == "red"), None)
    delay = None if first_red is None else first_red - 10 + 1
    return {"delay_frames": delay, "expected": 3, "pass": delay == 3}


# ---------------------------------------------------------------- tieu chi

def roi_criteria(b):
    return [
        {"id": "1", "desc": "M1 không thiếu ở cống GT đỏ",
         "value": f"M1 thiếu={b['m1_missing_red']} / {b['n_gt_red']} đỏ (M0 thiếu={b['m0_missing_red']})",
         "pass": b["m1_missing_red"] == 0},
        {"id": "2", "desc": "MAE(M1) ≤ MAE(M0) trên tập M0 không thiếu",
         "value": f"M1={f2(b['mae_m1_same']['mean'])} vs M0={f2(b['mae_m0']['mean'])} (n={b['n_m0_ok']})",
         "pass": bool(b["mae_m1_same"]["mean"] <= b["mae_m0"]["mean"])},
        {"id": "3", "desc": "Bỏ sót nghiêm trọng M1 < M0",
         "value": f"M1={b['crit_m1']} vs M0={b['crit_m0']}",
         "pass": b["crit_m1"] < b["crit_m0"]},
        {"id": "4", "desc": f"MAE(M2 dịch 10%, TB 4 hướng) − MAE(M1) ≤ {C.CALIB_TOLERANCE_PTS:g}",
         "value": f"{f2(b['m2_s10_mean4'])} − {f2(b['mae_m1_all']['mean'])} = "
                  f"{f2(b['m2_s10_mean4'] - b['mae_m1_all']['mean'])}",
         "pass": bool(b["m2_s10_mean4"] - b["mae_m1_all"]["mean"] <= C.CALIB_TOLERANCE_PTS)},
    ]


def smooth_criteria(s, step):
    return [
        {"id": "a", "desc": f"Tổng lần đổi trạng thái S2 ≤ {C.FLIP_RATIO_MAX:.0%} S0",
         "value": f"S2={s['flips_s2']} vs S0={s['flips_s0']} (ngưỡng {C.FLIP_RATIO_MAX * s['flips_s0']:.1f})",
         "pass": s["flips_s2"] <= C.FLIP_RATIO_MAX * s["flips_s0"]},
        {"id": "b", "desc": "MAE(S1) ≤ MAE(S0)",
         "value": f"S1={f2(s['mae_s1'])} vs S0={f2(s['mae_s0'])}",
         "pass": bool(s["mae_s1"] <= s["mae_s0"])},
        {"id": "c", "desc": "Độ chính xác trạng thái S2 ≥ S0",
         "value": f"S2={f2(s['acc_s2'], 1)}% vs S0={f2(s['acc_s0'], 1)}%",
         "pass": bool(s["acc_s2"] >= s["acc_s0"])},
        {"id": "d", "desc": "Kiểm tra trễ bậc (đỏ ở khung 70 thứ 3)",
         "value": f"trễ={step['delay_frames']} khung (kỳ vọng {step['expected']})",
         "pass": bool(step["pass"])},
    ]


def verdict(pooled, test):
    disagree = [p["id"] for p, t in zip(pooled, test) if p["pass"] != t["pass"]]
    if disagree:
        return "KHÔNG KẾT LUẬN", (f"tiêu chí {', '.join(disagree)} cho kết quả khác nhau giữa "
                                  f"gộp valid+test và chỉ test")
    if all(p["pass"] for p in pooled):
        return "ĐẠT", "mọi tiêu chí đạt trên cả gộp và chỉ test"
    failed = [p["id"] for p in pooled if not p["pass"]]
    return "KHÔNG ĐẠT", f"tiêu chí {', '.join(failed)} không đạt (nhất quán gộp và test)"


def print_criteria(title, pooled, test, v):
    print(f"\n=== {title} ===")
    for p, t in zip(pooled, test):
        print(f"({p['id']}) {p['desc']}\n    gop : {p['value']} -> {'PASS' if p['pass'] else 'FAIL'}"
              f"\n    test: {t['value']} -> {'PASS' if t['pass'] else 'FAIL'}")
    print(f"==> {v[0]}: {v[1]}")


# ---------------------------------------------------------------- bieu do

def chart_scatter(rows, cond):
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.4), sharey=True)
    for ax, m in zip(axes, ("M0", "M1")):
        key = m.lower()
        ok = [r for r in rows if not U.is_missing(r[key])]
        miss = [r for r in rows if U.is_missing(r[key])]
        ax.plot([0, 100], [0, 100], color=COL["muted"], lw=1, ls="--", zorder=1)
        for t in (C.YELLOW_THRESHOLD, C.RED_THRESHOLD):
            ax.axhline(t, color=COL["grid"], lw=1, zorder=0)
            ax.axvline(t, color=COL["grid"], lw=1, zorder=0)
        ax.scatter([r["gt"] for r in ok], [r[key] for r in ok], s=28, color=COL[m],
                   edgecolor=COL["surface"], linewidth=1, zorder=3, label=f"{m} (n={len(ok)})")
        if miss:
            ax.scatter([r["gt"] for r in miss], [-6] * len(miss), marker="x", s=30, color=COL["ink"],
                       zorder=3, label=f"thiếu (n={len(miss)}), vẽ ở y=−6")
        ax.set_xlim(-8, 102)
        ax.set_ylim(-10, 102)
        ax.set_xlabel("GT che cống (%)")
        ax.set_title(f"{m} — {cond}", color=COL["ink"])
        ax.legend(loc="upper left", frameon=False, fontsize=8)
    axes[0].set_ylabel("Dự đoán (%)")
    fig.tight_layout()
    fig.savefig(C.CHART_DIR / f"scatter_{cond}.png", dpi=130)
    plt.close(fig)


def chart_confusion(b, cond):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), gridspec_kw={"width_ratios": [4, 3]})
    for ax, (name, cm) in zip(axes, (("M0", b["conf_m0"]), ("M1", b["conf_m1"]))):
        cols = list(next(iter(cm.values())).keys())
        mat = np.array([[cm[g][p] for p in cols] for g in U.BANDS])
        ax.imshow(mat, cmap="Blues", vmin=0, vmax=max(1, mat.max()))
        ax.grid(False)
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                ax.text(j, i, str(mat[i, j]), ha="center", va="center",
                        color="white" if mat[i, j] > mat.max() * 0.6 else COL["ink"])
        ax.set_xticks(range(len(cols)), [BAND_VI[c] for c in cols])
        ax.set_yticks(range(3), [BAND_VI[g] for g in U.BANDS])
        ax.set_xlabel("Dự đoán")
        ax.set_ylabel("GT")
        ax.set_title(f"{name} — {cond}", color=COL["ink"])
    fig.tight_layout()
    fig.savefig(C.CHART_DIR / f"confusion_{cond}.png", dpi=130)
    plt.close(fig)


def chart_m2(blocks):
    names = ["m1"] + M2
    labels = ["M1"] + [n.replace("m2_", "") for n in M2]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(10, 3.8))
    wbar = 0.38
    for k, cond in enumerate(("C0", "C1")):
        b = blocks[cond]
        vals = [b["mae_m1_all"]["mean"]] + [b["m2"][n]["mean"] for n in M2]
        ax.bar(x + (k - 0.5) * wbar, vals, width=wbar - 0.04, color=COL[cond], label=cond, zorder=2)
        ax.axhline(b["mae_m1_all"]["mean"], color=COL[cond], lw=1, ls=":", zorder=1)
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("MAE (điểm %)")
    ax.set_title("Độ nhạy ROI (M2) — gộp valid+test", color=COL["ink"])
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(C.CHART_DIR / "m2_sensitivity.png", dpi=130)
    plt.close(fig)


def chart_decomp(sm):
    cats = ["|bias| TB", "nhiễu (std) TB"]
    x = np.arange(len(cats))
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    wbar = 0.38
    for k, m in enumerate(("M1", "M0")):
        s = sm[m]["pooled"]
        ax.bar(x + (k - 0.5) * wbar, [s["mean_abs_bias"], s["mean_noise"]], width=wbar - 0.04,
               color=COL[m], label=f"{m} (bias² chiếm {f2(100 * s['mse_share_bias'], 0)}% MSE)", zorder=2)
    ax.set_xticks(x, cats)
    ax.set_ylabel("điểm %")
    ax.set_title("Phân rã sai số theo cống (chuỗi mô phỏng)", color=COL["ink"])
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(C.CHART_DIR / "error_decomposition.png", dpi=130)
    plt.close(fig)


def short_stem(stem, n=24):
    return stem if len(stem) <= n else stem[:n] + "…"


def chart_timeline(key, s, an, title, fname, split_idx):
    t = np.arange(C.N_FRAMES)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for i, st in enumerate(an["s2_states"]):
        f = C.WARMUP_FRAMES + i
        ax.axvspan(f - 0.5, f + 0.5, color=COL.get(st, COL["muted"]), alpha=0.18, lw=0, zorder=0)
    ax.axvspan(-0.5, C.WARMUP_FRAMES - 0.5, color=COL["grid"], alpha=0.5, lw=0, zorder=0)
    for th in (C.YELLOW_THRESHOLD, C.RED_THRESHOLD):
        ax.axhline(th, color=COL["muted"], lw=0.8, ls=":", zorder=1)
    ax.axhline(s["gt"], color=COL["ink"], lw=1.5, ls="--", label=f"GT {s['gt']:.1f}%", zorder=2)
    ax.plot(t, s["m1"], color=COL["M0"], lw=1.2, marker="o", ms=4, label="thô (S0, M1)", zorder=3)
    s1 = [np.nan if v is None else v for v in an["s1"]]
    ax.plot(t, s1, color=COL["M1"], lw=2, label="median 5 (S1)", zorder=4)
    occ = [f for f in t if s["occ"][f]]
    if occ:
        ax.scatter(occ, [s["m1"][f] for f in occ], marker="s", s=40, facecolor="none",
                   edgecolor=COL["ink"], zorder=5, label="khung có vật che")
    ax.set_xlim(-0.5, C.N_FRAMES - 0.5)
    ax.set_xticks(range(0, C.N_FRAMES, 2))
    ax.set_ylim(-3, 103)
    ax.set_xlabel("khung (0–3 khởi động; nền màu = trạng thái S2)")
    ax.set_ylabel("che cống (%)")
    # chi so theo split (khop ten tep overlay {split}_{idx:03d}), khong dung chi so toan cuc
    ax.set_title(f"{title}: {s['split']} #{split_idx:03d} ({short_stem(s['stem'])}) cống {key[1]}\n"
                 f"S0 đổi {an['flips0']} lần, S2 đổi {an['flips2']} lần", color=COL["ink"], fontsize=9)
    # chu thich nam duoi truc (khong che duong GT)
    ax.legend(frameon=False, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4)
    fig.tight_layout()
    fig.savefig(C.CHART_DIR / fname, dpi=130, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- vi du overlay (C1)

def make_examples(rows):
    index = {(r["split"], r["stem"], r["cond"]): r for r in U.read_csv(C.CACHE_INDEX_CSV)}
    items = {(it["split"], it["stem"]): it for it in U.list_all_drain_images()}
    c1 = select(rows, "C1", "pooled")
    key0 = lambda r: (r["split"], r["stem"], r["drain_idx"])
    g1 = sorted([r for r in c1 if r["gt_band"] == "red" and U.is_missing(r["m0"])], key=key0)
    rest = [r for r in c1 if r not in g1]

    def err(r):
        e1 = abs(r["m1"] - r["gt"])
        return max(e1, abs(r["m0"] - r["gt"])) if not U.is_missing(r["m0"]) else e1
    rest.sort(key=lambda r: (-err(r), key0(r)))
    picks = (g1 + rest)[:10]
    C.EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for rank, r in enumerate(picks, 1):
        ix = index[(r["split"], r["stem"], "C1")]
        z = np.load(C.CACHE_DIR / ix["file"])
        img = U.degrade_esp32(U.read_image(items[(r["split"], r["stem"])]["image_path"]))
        h, w = img.shape[:2]
        trash, drain = z["trash_union"], z["drain_union"]
        vis = img.astype(np.float32)
        red = np.array([40, 40, 230], np.float32)
        vis[trash] = vis[trash] * 0.55 + red * 0.45
        vis = vis.astype(np.uint8)
        cnts, _ = cv2.findContours(drain.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(vis, cnts, -1, (255, 80, 0), 2)
        _, _, drains_px = U.gt_for_image(items[(r["split"], r["stem"])]["polys"], h, w)
        pts = np.round(drains_px[r["drain_idx"]]).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(vis, [pts], True, (0, 220, 0), 2)
        m0s = "missing" if U.is_missing(r["m0"]) else f"{r['m0']:.1f}%"
        lines = [f"GT {r['gt']:.1f}% ({r['gt_band']})  M0 {m0s}  M1 {r['m1']:.1f}%",
                 f"{r['split']} #{ix['idx']} drain {r['drain_idx']}  ROI green / pred trash red / pred drain blue"]
        cv2.rectangle(vis, (0, 0), (w, 44), (0, 0, 0), -1)
        for i, ln in enumerate(lines):
            cv2.putText(vis, ln, (6, 18 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5 if i == 0 else 0.4,
                        (255, 255, 255), 1, cv2.LINE_AA)
        fname = f"{rank:02d}_{r['split']}_{int(ix['idx']):03d}_d{r['drain_idx']}.jpg"
        cv2.imwrite(str(C.EXAMPLE_DIR / fname), vis, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        out.append({"file": fname, "split": r["split"], "stem": r["stem"], "drain_idx": r["drain_idx"],
                    "gt": r["gt"], "m0": r["m0"], "m1": r["m1"]})
    print(f"[vi du] {len(out)} anh -> {C.EXAMPLE_DIR}")
    return out


# ---------------------------------------------------------------- REPORT.md

def md_table(header, rows):
    s = "| " + " | ".join(header) + " |\n|" + "|".join("---" for _ in header) + "|\n"
    return s + "".join("| " + " | ".join(str(c) for c in r) + " |\n" for r in rows)


def mae_rows(blocks_by, filt, conds=("C0", "C1")):
    out = []
    for cond in conds:
        for sub in SUBSETS:
            b = blocks_by[(cond, sub, filt)]
            out.append([cond, SUBSET_VI[sub], b["n"], b["n_m0_ok"], ci_str(b["mae_m0"]), ci_str(b["mae_m1_same"]),
                        ci_str(b["diff_m1_minus_m0"]), ci_str(b["mae_m1_all"]),
                        f"{b['m0_missing_red']}/{b['n_gt_red']}", f"{b['crit_m0']} / {b['crit_m1']}",
                        f"{b['fa_m0']} / {b['fa_m1']}"])
    return out


MAE_HEADER = ["Điều kiện", "Tập", "n cống", "n M0 có giá trị", "MAE M0 [95% CI]", "MAE M1 cùng tập",
              "M1−M0 (cặp)", "MAE M1 tất cả", "M0 thiếu / GT đỏ", "Bỏ sót nghiêm trọng M0 / M1",
              "Báo động giả M0 / M1"]


def crit_table(pooled, test, cond="C1"):
    return md_table(["Tiêu chí", f"Gộp valid+test ({cond})", f"Chỉ test ({cond})"],
                    [[f"({p['id']}) {p['desc']}", f"{p['value']} → **{'ĐẠT' if p['pass'] else 'KHÔNG ĐẠT'}**",
                      f"{t['value']} → **{'ĐẠT' if t['pass'] else 'KHÔNG ĐẠT'}**"] for p, t in zip(pooled, test)])


def compare_rows(blocks, sm_by_cond):
    """Bang so sanh gon C0 / C1 / C2 (gop va chi test)."""
    out = []
    for cond in [c for c in U.CONDITIONS if (c, "pooled", "all") in blocks]:
        for sub in ("pooled", "test"):
            b = blocks[(cond, sub, "all")]
            s = sm_by_cond.get(cond)
            if s is None:
                fl, bias = "— (không có chuỗi)", "—"
            else:
                fl = f"{s['M1'][sub]['flips_s0']} / {s['M1'][sub]['flips_s2']}"
                bias = f"{f2(100 * s['M1'][sub]['mse_share_bias'], 1)}%"
            out.append([cond, SUBSET_VI[sub], f"{b['m0_missing_red']}/{b['n_gt_red']}",
                        f"{b['crit_m0']} / {b['crit_m1']}", b["n_m0_ok"], ci_str(b["mae_m0"]),
                        ci_str(b["mae_m1_same"]), ci_str(b["diff_m1_minus_m0"]), ci_str(b["mae_m1_all"]), fl, bias])
    return out


COMPARE_HEADER = ["Điều kiện", "Tập", "M0 thiếu / GT đỏ", "Bỏ sót nghiêm trọng M0 / M1", "n M0 có giá trị",
                  "MAE M0 [95% CI]", "MAE M1 cùng tập [95% CI]", "M1−M0 (cặp)", "MAE M1 tất cả [95% CI]",
                  "Đổi trạng thái S0 / S2 (M1, chuỗi)", "Tỷ phần MSE do bias² (M1, chuỗi)"]


def smooth_rows(sm):
    rows = []
    for m in ("M1", "M0"):
        for sub in SUBSETS:
            s = sm[m][sub]
            rows.append([m, SUBSET_VI[sub], f2(s["mae_s0"]), f2(s["mae_s1"]), ci_str(s["diff_s1_minus_s0_per_drain"]),
                         f"{s['flips_s0']} / {s['flips_s1']} / {s['flips_s2']}",
                         f"{f2(s['flips_s0_per_drain_mean'])} / {f2(s['flips_s2_per_drain_mean'])}",
                         f"{s['drains_zero_flips_s0']} / {s['drains_zero_flips_s2']} (của {s['n_drains']})",
                         f"{f2(s['acc_s0'], 1)} / {f2(s['acc_s1'], 1)} / {f2(s['acc_s2'], 1)}",
                         f"{f2(s['mae_s0_occluded'])} / {f2(s['mae_s1_occluded'])} (n={s['n_occluded_frames']})"])
    return rows


SMOOTH_HEADER = ["Phương pháp", "Tập", "MAE S0", "MAE S1", "S1−S0 theo cống [CI]", "Đổi trạng thái S0 / S1 / S2",
                 "TB đổi/cống S0 / S2", "Cống 0 lần đổi S0 / S2", "Đúng trạng thái S0 / S1 / S2 (%)",
                 "MAE khung bị che S0 / S1"]


def decomp_rows(sm):
    return [[m, SUBSET_VI[sub], f2(sm[m][sub]["mean_abs_bias"]), f2(sm[m][sub]["mean_noise"]),
             f"{f2(100 * sm[m][sub]['mse_share_bias'], 1)}%", f"{f2(100 * sm[m][sub]['mse_share_var'], 1)}%"]
            for m in ("M1", "M0") for sub in SUBSETS]


DECOMP_HEADER = ["Phương pháp", "Tập", "|bias| TB", "Nhiễu TB", "Tỷ phần MSE do bias²", "Tỷ phần do phương sai"]


def conf_rows(cb):
    return [[w, f"{f2(100 * cb[w]['frac_flagged'], 1)}% ({cb[w]['n_flagged']}/{cb['n']})",
             f2(cb[w]["mae_m1_flagged"]), f2(cb[w]["mae_m1_not_flagged"])] for w in ("old", "new")]


CONF_HEADER = ["Quy tắc", "Tỷ lệ gắn cờ", "MAE M1 có cờ", "MAE M1 không cờ"]


def jpeg_sizes_kb():
    """Kich thuoc JPEG (KB) khi ma hoa anh 640x640 o q C1 va C2 - chi de mo ta, khong anh huong chi so."""
    out = {}
    imgs = [cv2.resize(U.read_image(it["image_path"]), (C.ESP32_SIZE, C.ESP32_SIZE), interpolation=cv2.INTER_AREA)
            for it in U.list_all_drain_images()]
    for cond, q in U.CONDITION_QUALITY.items():
        kb = np.array([len(cv2.imencode(".jpg", im, [int(cv2.IMWRITE_JPEG_QUALITY), q])[1]) / 1024 for im in imgs])
        out[cond] = {"quality": q, "mean_kb": float(kb.mean()), "median_kb": float(np.median(kb)),
                     "min_kb": float(kb.min()), "max_kb": float(kb.max()), "n": int(kb.size)}
    return out


def conf_md(cm, cols):
    return md_table(["GT \\ dự đoán"] + [BAND_VI[c] for c in cols],
                    [[BAND_VI[g]] + [cm[g][c] for c in cols] for g in U.BANDS])


def supp_section(supp, blocks):
    """Muc 'Phan tich bo sung C2' - THAM KHAO, khong phai ket luan."""
    L = []
    js = supp["jpeg_size_kb"]
    L.append("\n## Phân tích bổ sung C2 — sát ảnh ESP32 thật\n")
    L.append("> **Tham khảo bổ sung — không phải kết luận.** Kết luận chính ở đầu báo cáo vẫn tính trên C1 và không đổi.\n")
    L.append(
        "**Lý do (quyết định trước khi có bất kỳ kết quả C2 nào):** firmware dùng esp32-camera `jpeg_quality = 12`, "
        "nhưng thang của esp32-camera ngược với OpenCV (esp32-camera: số **nhỏ** = chất lượng **cao**). Ảnh ESP32 VGA "
        "thật khoảng 12–15 KB; OpenCV quality 20–30 ở 640×480 cho 13,1–16,4 KB trên ảnh tphcm của Try1. Vì vậy C1 "
        "(OpenCV q12) có lẽ khắc nghiệt hơn thực tế.\n")
    L.append(
        f"**Định nghĩa C2:** resize {C.ESP32_SIZE}×{C.ESP32_SIZE} INTER_AREA → JPEG OpenCV q{C.C2_JPEG_QUALITY} → giải mã; "
        "GT/ROI rasterize ở 640×640 (giống C1, chỉ khác quality). Chuỗi mô phỏng C2: giống hệt chuỗi chính (cùng seed "
        f"theo ảnh × khung, cùng mọi nhiễu), chỉ JPEG cuối lấy ngẫu nhiên q{C.SIM_C2_JPEG_QUALITY[0]}..{C.SIM_C2_JPEG_QUALITY[1]} "
        f"thay vì q{C.SIM['jpeg_quality'][0]}..{C.SIM['jpeg_quality'][1]}.\n")
    L.append(
        f"Kích thước JPEG ở 640×640 ({js['C1']['n']} ảnh, chỉ mô tả): C1 q{js['C1']['quality']} TB {f2(js['C1']['mean_kb'], 1)} KB "
        f"(median {f2(js['C1']['median_kb'], 1)}); C2 q{js['C2']['quality']} TB {f2(js['C2']['mean_kb'], 1)} KB "
        f"(median {f2(js['C2']['median_kb'], 1)}). 640×640 nhiều hơn 640×480 khoảng 33% pixel nên KB lớn hơn mốc VGA.\n")

    L.append("### So sánh gọn C0 / C1 / C2\n")
    L.append("C0 không có chuỗi mô phỏng. C1 = chuỗi chính (JPEG q10..15); C2 = chuỗi bổ sung (JPEG q20..30). "
             "CI bootstrap 95% (n=2000, theo cống).\n")
    L.append(md_table(COMPARE_HEADER, supp["comparison_rows"]))

    L.append("\n### Tiêu chí trên C2 (tham khảo bổ sung)\n")
    L.append("Cùng tiêu chí và ngưỡng đã đăng ký, áp dụng nguyên vẹn cho C2. Kết quả dưới đây **không thay thế** "
             "kết luận chính.\n")
    L.append("#### Phương pháp ROI — C2\n")
    L.append(crit_table(supp["criteria_roi"]["pooled"], supp["criteria_roi"]["test"], "C2"))
    r = supp["reference_result_roi"]
    L.append(f"\nKết quả tham khảo ROI trên C2: {r[0]} ({r[1]}).\n")
    L.append("#### Làm mượt — chuỗi C2\n")
    L.append(crit_table(supp["criteria_smoothing"]["pooled"], supp["criteria_smoothing"]["test"], "chuỗi C2"))
    r = supp["reference_result_smoothing"]
    L.append(f"\nKết quả tham khảo làm mượt trên chuỗi C2: {r[0]} ({r[1]}).\n")

    L.append("### MAE theo cống — C2 (điểm %)\n")
    L.append(md_table(MAE_HEADER, mae_rows(blocks, "all", ("C2",))))
    L.append("\nPhụ — ảnh có đúng 1 cống:\n\n" + md_table(MAE_HEADER, mae_rows(blocks, "single", ("C2",))))
    L.append(f"\nPhụ — bỏ cống < {C.SMALL_DRAIN_MIN_AREA_PX_1024} px²:\n\n"
             + md_table(MAE_HEADER, mae_rows(blocks, "large", ("C2",))))
    b = blocks[("C2", "pooled", "all")]
    L.append("\n### Ma trận nhầm lẫn — C2 (gộp)\n")
    L.append("**C2 — M0**\n\n" + conf_md(b["conf_m0"], list(U.BANDS) + ["missing"]))
    L.append("\n**C2 — M1**\n\n" + conf_md(b["conf_m1"], list(U.BANDS)) + "\n")
    L.append(f"Độ nhạy ROI C2 (gộp): MAE M1 = {ci_str(b['mae_m1_all'])}; dịch 5% TB 4 hướng = {f2(b['m2_s05_mean4'])}; "
             f"dịch 10% TB 4 hướng = {f2(b['m2_s10_mean4'])}.\n")
    cb = supp["confidence"]
    L.append(f"\n### Độ tin cậy — C2 (gộp)\n\nĐộ tin cậy mới là NaN ở {cb['new']['n_nan']} cống.\n")
    L.append(md_table(CONF_HEADER, conf_rows(cb)))
    L.append(f"\n### Làm mượt — chuỗi C2\n\n{supp['smoothing']['M1']['pooled']['n_drains']} cống × {C.N_FRAMES} khung, "
             "đánh giá như chuỗi chính.\n")
    L.append(md_table(SMOOTH_HEADER, smooth_rows(supp["smoothing"])))
    L.append("\nPhân rã sai số (chuỗi C2):\n\n" + md_table(DECOMP_HEADER, decomp_rows(supp["smoothing"])))
    return L


def write_report(S, blocks, sm, timeline_info, examples, timing, supp=None):
    rv, sv = S["verdict_roi"], S["verdict_smoothing"]
    b1 = blocks[("C1", "pooled", "all")]
    s1 = sm["M1"]["pooled"]
    L = []
    L.append("# Báo cáo exp01 — Chỉ số che cống: ROI cố định & làm mượt theo thời gian\n")
    L.append("*Tệp này do `05_report.py` sinh tự động; không sửa tay.*\n")
    L.append("## Kết luận\n")
    L.append(
        f"**Phương pháp ROI cố định (M1): {rv[0]}** — {rv[1]}. Trên điều kiện ESP32 (C1), gộp valid+test "
        f"({b1['n']} cống): M0 (công thức hiện tại) thiếu giá trị ở {b1['m0_missing']} cống "
        f"({f2(100 * b1['m0_missing_rate'], 1)}%), trong đó {b1['m0_missing_red']}/{b1['n_gt_red']} cống GT đỏ; "
        f"M1 không bao giờ thiếu. Trên tập M0 có giá trị (n={b1['n_m0_ok']}), MAE M0 = {f2(b1['mae_m0']['mean'])} "
        f"điểm, MAE M1 = {f2(b1['mae_m1_same']['mean'])} điểm (chênh lệch cặp M1−M0 = {ci_str(b1['diff_m1_minus_m0'])}). "
        f"Bỏ sót nghiêm trọng (GT đỏ → xanh/thiếu): M0 = {b1['crit_m0']}, M1 = {b1['crit_m1']}. "
        f"Dịch ROI 10% làm MAE tăng trung bình {f2(b1['m2_s10_mean4'] - b1['mae_m1_all']['mean'])} điểm.\n")
    L.append(
        f"**Làm mượt (median 5 + hysteresis): {sv[0]}** — {sv[1]}. Trên chuỗi mô phỏng (M1, gộp): "
        f"số lần đổi trạng thái S0 = {s1['flips_s0']} → S2 = {s1['flips_s2']}; MAE S0 = {f2(s1['mae_s0'])} → "
        f"S1 = {f2(s1['mae_s1'])}; độ chính xác trạng thái S0 = {f2(s1['acc_s0'], 1)}% → S2 = {f2(s1['acc_s2'], 1)}%. "
        f"Trễ khi nhảy bậc 10%→70%: {S['step_delay']['delay_frames']} khung.\n")
    L.append("Tiêu chí được đăng ký trước khi có kết quả; ngưỡng không được chỉnh sau khi chạy.\n")
    if supp:
        L.append("*Hai kết luận trên (tính trên C1) là kết luận chính và không đổi. Xem thêm mục "
                 "\"Phân tích bổ sung C2 — sát ảnh ESP32 thật\" (JPEG OpenCV q25) — chỉ để tham khảo.*\n")

    L.append("## Tiêu chí đăng ký trước\n")
    L.append("### Phương pháp ROI\n")
    L.append(crit_table(S["criteria_roi"]["pooled"], S["criteria_roi"]["test"]))
    L.append(f"\n**Kết luận ROI: {rv[0]}** ({rv[1]}).\n")
    L.append("### Làm mượt\n")
    L.append(crit_table(S["criteria_smoothing"]["pooled"], S["criteria_smoothing"]["test"]))
    L.append(f"\n**Kết luận làm mượt: {sv[0]}** ({sv[1]}).\n")

    L.append("## MAE theo cống (điểm %)\n")
    L.append("C0 = ảnh gốc (GT ở kích thước gốc); C1 = giống ESP32 (640×640, JPEG q12; GT/ROI rasterize ở 640). "
             "CI bootstrap 95% (n=2000, lấy mẫu lại theo cống).\n")
    L.append(md_table(MAE_HEADER, mae_rows(blocks, "all")))
    n_single_img = S["counts"]["single_drain_images"]
    L.append(f"\n### Phân tích phụ: ảnh có đúng 1 cống ({n_single_img} ảnh)\n")
    L.append("M0 tính trên hợp mọi cống dự đoán của cả ảnh nên mọi cống trong ảnh nhiều cống nhận cùng một giá trị. "
             "Tập con này so sánh M0 và M1 công bằng ở mức từng cống.\n")
    L.append(md_table(MAE_HEADER, mae_rows(blocks, "single")))
    L.append(f"\n### Phân tích phụ: bỏ cống rất nhỏ (< {C.SMALL_DRAIN_MIN_AREA_PX_1024} px²)\n")
    L.append(f"Chỉ giữ cống có diện tích polygon GT ≥ {C.SMALL_DRAIN_MIN_AREA_PX_1024} px² đo ở 1024×1024 "
             f"(bỏ {S['counts']['small_drains']} cống: {S['counts']['small_drain_areas']} px²). "
             "Phân tích này **không** ảnh hưởng tiêu chí chính.\n")
    L.append(md_table(MAE_HEADER, mae_rows(blocks, "large")))

    L.append("\n## Ma trận nhầm lẫn (gộp valid+test)\n")
    for cond in ("C0", "C1"):
        b = blocks[(cond, "pooled", "all")]
        L.append(f"**{cond} — M0**\n\n" + conf_md(b["conf_m0"], list(U.BANDS) + ["missing"]))
        L.append(f"\n**{cond} — M1**\n\n" + conf_md(b["conf_m1"], list(U.BANDS)) + "\n")

    L.append("## Độ nhạy ROI (M2, MAE điểm %, gộp)\n")
    L.append(md_table(["Biến thể", "C0", "C1"],
                      [["M1 (ROI đúng)", ci_str(blocks[("C0", "pooled", "all")]["mae_m1_all"]),
                        ci_str(blocks[("C1", "pooled", "all")]["mae_m1_all"])]]
                      + [[n.replace("m2_", ""), ci_str(blocks[("C0", "pooled", "all")]["m2"][n]),
                          ci_str(blocks[("C1", "pooled", "all")]["m2"][n])] for n in M2]
                      + [["dịch 5% — TB 4 hướng", f2(blocks[("C0", "pooled", "all")]["m2_s05_mean4"]),
                          f2(blocks[("C1", "pooled", "all")]["m2_s05_mean4"])],
                         ["dịch 10% — TB 4 hướng", f2(blocks[("C0", "pooled", "all")]["m2_s10_mean4"]),
                          f2(blocks[("C1", "pooled", "all")]["m2_s10_mean4"])]]))

    L.append("\n## Độ tin cậy (C1, gộp)\n")
    cb = S["confidence"]["C1"]
    L.append(f"Cũ = min confidence của mọi object trong ảnh (mặc định {C.DEFAULT_CONFIDENCE}); mới = trung bình có trọng "
             f"số (pixel trong ROI) của confidence các instance Trash; cờ = giá trị < {C.FLAG_THRESHOLD}. "
             f"Độ tin cậy mới là NaN (không gắn cờ) ở {cb['new']['n_nan']} cống.\n")
    L.append(md_table(CONF_HEADER, conf_rows(cb)))

    L.append("\n## Làm mượt theo thời gian (chuỗi mô phỏng)\n")
    L.append(f"{S['counts']['sequence_drains']} cống × {C.N_FRAMES} khung, đánh giá khung {C.WARMUP_FRAMES + 1}..{C.N_FRAMES} "
             "(4 khung đầu khởi động). S0 = giá trị thô + ngưỡng thường; S1 = median 5 khung; S2 = hysteresis trên S1. "
             "Với M0: khung thiếu tính là trạng thái 'thiếu' (sai), S1 bỏ khung thiếu trong cửa sổ, S2 giữ trạng thái cũ.\n")
    L.append(md_table(SMOOTH_HEADER, smooth_rows(sm)))
    L.append("\n### Phân rã sai số (khung thô, 20 khung/cống)\n")
    L.append("bias = TB(thô) − GT; nhiễu = độ lệch chuẩn (ddof=0) theo cống; MSE = bias² + phương sai.\n")
    L.append(md_table(DECOMP_HEADER, decomp_rows(sm)))
    L.append("\nGiảm nhiễu bằng làm mượt chỉ xử lý được phần phương sai; phần bias (sai lệch hệ thống của model) không đổi.\n")

    L.append("## Thời gian suy luận (02_predict.py)\n")
    L.append(md_table(["Điều kiện", "TB (ms)", "Median (ms)", "n"],
                      [[c, f2(timing[c]["mean_ms"], 1), f2(timing[c]["median_ms"], 1), timing[c]["n"]] for c in timing]))
    if supp:
        L.append("\nDòng C2 được đo trong phiên chạy riêng (sau C0/C1), nên chênh lệch thời gian với C0/C1 có thể "
                 "do trạng thái GPU/nhiệt, không chỉ do điều kiện ảnh.\n")

    L.append("\n## Biểu đồ và ví dụ\n")
    L.append("- `outputs/charts/scatter_C0.png`, `scatter_C1.png` — GT vs dự đoán (M0, M1), đường y=x.\n"
             "- `outputs/charts/confusion_C0.png`, `confusion_C1.png` — ma trận nhầm lẫn.\n"
             "- `outputs/charts/m2_sensitivity.png` — độ nhạy ROI.\n"
             "- `outputs/charts/error_decomposition.png` — bias vs nhiễu.\n")
    if supp:
        L.append("- `outputs/charts/scatter_C2.png`, `confusion_C2.png` — như trên cho C2 (phân tích bổ sung).\n")
    for t in timeline_info:
        L.append(f"- `outputs/charts/{t['file']}` — {t['title']} ({t['split']} #{t['split_idx']:03d} "
                 f"`{t['stem']}` cống {t['drain_idx']}, GT {f2(t['gt'], 1)}%).\n")
    L.append(f"- `outputs/examples/` — {len(examples)} ảnh overlay C1 (ROI xanh lá, rác dự đoán đỏ, cống dự đoán xanh dương); "
             "ưu tiên cống GT đỏ mà M0 thiếu, sau đó theo sai số lớn nhất.\n")
    L.append("\n| Tệp | GT | M0 | M1 |\n|---|---|---|---|\n"
             + "".join(f"| {e['file']} | {f2(e['gt'], 1)} | {f2(e['m0'], 1)} | {f2(e['m1'], 1)} |\n" for e in examples))

    if supp:
        L.extend(supp_section(supp, blocks))

    L.append("\n## Hạn chế\n")
    L.append(
        f"- Mẫu nhỏ: {b1['n']} cống, chỉ khoảng {b1['gt_bands']['yellow']} cống vàng (C1) — CI rộng, ma trận nhầm lẫn kém ổn định.\n"
        "- Tập valid đã được dùng để chọn `best.pt`, nên số trên valid có thể lạc quan; vì vậy tiêu chí yêu cầu "
        "kết quả trên chỉ test cùng chiều với tập gộp.\n"
        "- Nhiễu mô phỏng độc lập giữa các khung; nhiễu thực tế (mưa, bóng đổ kéo dài, rác thay đổi) tương quan theo thời gian, "
        "nên lợi ích thật của làm mượt có thể nhỏ hơn.\n"
        "- Vật che hình học (hình chữ nhật) không giống người/xe thật.\n"
        "- Không có ảnh tham chiếu sạch của từng camera, nên phương án ROI do AI đề xuất chưa được kiểm tra.\n"
        "- ROI lấy từ polygon GT là **cận trên** của độ chính xác M1; ROI vẽ tay thực tế sẽ lệch — xem M2 để ước lượng mức suy giảm.\n"
        "- C1 chỉ xấp xỉ ESP32 (resize + JPEG chất lượng thấp), không mô phỏng cảm biến, nhiễu màu hay ánh sáng yếu thật.\n"
        "- Thang `jpeg_quality` của esp32-camera ngược với OpenCV (esp32-camera: số nhỏ = chất lượng cao), nên C1 "
        "(OpenCV q12) có lẽ khắc nghiệt hơn ảnh ESP32 thật; C2 (OpenCV q25) gần thực tế hơn nhưng chỉ là phân tích bổ sung.\n")
    C.REPORT_PATH.write_text("\n".join(L), encoding="utf-8")
    print(f"[ghi] {C.REPORT_PATH}")


# ---------------------------------------------------------------- main

def main():
    C.CHART_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_drains()
    conds = [c for c in U.CONDITIONS if any(r["condition"] == c for r in rows)]
    has_c2 = "C2" in conds and C.PER_FRAME_C2_CSV.exists()
    if "C2" in conds and not has_c2:
        print("CANH BAO: co C2 trong per_drain nhung thieu per_frame_C2.csv -> bo qua phan tich bo sung C2")
    for cond in conds:
        n = len(select(rows, cond, "pooled"))
        if n != C.EXPECTED_DRAIN_POLYGONS:
            print(f"!!!! CANH BAO: {cond} co {n} cong (ky vong {C.EXPECTED_DRAIN_POLYGONS})")

    blocks = {}
    for cond in conds:
        for sub in SUBSETS:
            for filt in ("all", "single", "large"):
                blocks[(cond, sub, filt)] = drain_block(select(rows, cond, sub, filt))

    c0_pooled = select(rows, "C0", "pooled")
    n_single_img = len({(r["split"], r["stem"]) for r in c0_pooled if r["n_drains_in_image"] == 1})
    small = sorted(r["gt_area_px_1024"] for r in c0_pooled if r["gt_area_px_1024"] < C.SMALL_DRAIN_MIN_AREA_PX_1024)
    print(f"Anh co dung 1 cong: {n_single_img}; cong rat nho: {len(small)} {small}")

    conf = {cond: conf_block(select(rows, cond, "pooled")) for cond in conds}

    series = load_series()
    def smooth_all(ser):
        sm_, an_ = {}, {}
        for m in ("M1", "M0"):
            an_[m] = {k: analyze_series(s[m.lower()], s["gt"], s["gt_band"], s["occ"]) for k, s in ser.items()}
            sm_[m] = {sub: smooth_block([a for k, a in an_[m].items()
                                         if sub == "pooled" or ser[k]["split"] == sub]) for sub in SUBSETS}
        return sm_, an_
    sm, analyses = smooth_all(series)
    step = step_delay_test()

    crit_roi = {sub: roi_criteria(blocks[("C1", sub, "all")]) for sub in ("pooled", "test")}
    crit_sm = {sub: smooth_criteria(sm["M1"][sub], step) for sub in ("pooled", "test")}
    v_roi = verdict(crit_roi["pooled"], crit_roi["test"])
    v_sm = verdict(crit_sm["pooled"], crit_sm["test"])
    print_criteria("Phuong phap ROI (C1)", crit_roi["pooled"], crit_roi["test"], v_roi)
    print_criteria("Lam muot (M1, chuoi mo phong)", crit_sm["pooled"], crit_sm["test"], v_sm)

    # ---- PHAN TICH BO SUNG C2 (tham khao; KHONG thay doi ket luan chinh tren C1)
    supp = None
    if has_c2:
        series_c2 = load_series(C.PER_FRAME_C2_CSV)
        if set(series_c2) != set(series):
            raise ValueError("Chuoi C2 khong cung tap (anh, cong) voi chuoi chinh")
        sm_c2, _ = smooth_all(series_c2)
        crit_roi_c2 = {sub: roi_criteria(blocks[("C2", sub, "all")]) for sub in ("pooled", "test")}
        crit_sm_c2 = {sub: smooth_criteria(sm_c2["M1"][sub], step) for sub in ("pooled", "test")}
        ref_roi_c2 = verdict(crit_roi_c2["pooled"], crit_roi_c2["test"])
        ref_sm_c2 = verdict(crit_sm_c2["pooled"], crit_sm_c2["test"])
        print_criteria("[BO SUNG - tham khao] Phuong phap ROI (C2)", crit_roi_c2["pooled"], crit_roi_c2["test"], ref_roi_c2)
        print_criteria("[BO SUNG - tham khao] Lam muot (M1, chuoi C2)", crit_sm_c2["pooled"], crit_sm_c2["test"], ref_sm_c2)
        supp = {
            "note": "Phan tich bo sung, tham khao - KHONG phai ket luan; ket luan chinh tinh tren C1.",
            "definition": {"size": C.ESP32_SIZE, "jpeg_quality": C.C2_JPEG_QUALITY,
                           "sim_jpeg_quality": list(C.SIM_C2_JPEG_QUALITY)},
            "criteria_roi": crit_roi_c2, "criteria_smoothing": crit_sm_c2,
            "reference_result_roi": ref_roi_c2, "reference_result_smoothing": ref_sm_c2,
            "confidence": conf["C2"], "smoothing": sm_c2, "sequence_drains": len(series_c2),
            "jpeg_size_kb": jpeg_sizes_kb(),
            "comparison_rows": compare_rows(blocks, {"C1": sm, "C2": sm_c2}),
            "comparison_header": COMPARE_HEADER,
        }

    # bieu do
    for cond in conds:
        chart_scatter(select(rows, cond, "pooled"), cond)
        chart_confusion(blocks[(cond, "pooled", "all")], cond)
    chart_m2({c: blocks[(c, "pooled", "all")] for c in ("C0", "C1")})
    chart_decomp(sm)

    a1 = analyses["M1"]
    keys = sorted(a1, key=lambda k: (-a1[k]["flips0"], k))
    picks = [("Nhiều lần đổi S0 nhất", keys[0])]
    for title, gb in (("Một cống GT đỏ", "red"), ("Một cống GT xanh", "green")):
        cand = [k for k in keys if series[k]["gt_band"] == gb and k not in [p[1] for p in picks]]
        if cand:
            picks.append((title, cand[0]))
        else:
            print(f"CANH BAO: khong co cong GT {gb} cho bieu do timeline")
    split_idx = {(r["split"], r["stem"]): int(r["idx"]) for r in U.read_csv(C.CACHE_INDEX_CSV)}
    timeline_info = []
    for i, (title, k) in enumerate(picks, 1):
        fname = f"timeline_{i}.png"
        si = split_idx[(series[k]["split"], series[k]["stem"])]
        chart_timeline(k, series[k], a1[k], title, fname, si)
        timeline_info.append({"file": fname, "title": title, "image_idx": k[0], "drain_idx": k[1],
                              "split": series[k]["split"], "stem": series[k]["stem"], "gt": series[k]["gt"],
                              "split_idx": si})

    examples = make_examples(rows)

    timing = {}
    if C.TIMING_CSV.exists():
        trows = U.read_csv(C.TIMING_CSV)
        for cond in [c for c in U.CONDITIONS if any(r["cond"] == c for r in trows)]:
            ts = np.array([float(r["time_s"]) for r in trows if r["cond"] == cond])
            timing[cond] = {"mean_ms": float(ts.mean() * 1000), "median_ms": float(np.median(ts) * 1000), "n": int(ts.size)}
    if C.PERTURB_CSV.exists():
        ts = np.array([float(r["infer_time_s"]) for r in U.read_csv(C.PERTURB_CSV)])
        timing["mô phỏng (640)"] = {"mean_ms": float(ts.mean() * 1000), "median_ms": float(np.median(ts) * 1000),
                                    "n": int(ts.size)}
    if has_c2 and C.PERTURB_C2_CSV.exists():
        ts = np.array([float(r["infer_time_s"]) for r in U.read_csv(C.PERTURB_C2_CSV)])
        timing["mô phỏng C2 (640)"] = {"mean_ms": float(ts.mean() * 1000), "median_ms": float(np.median(ts) * 1000),
                                       "n": int(ts.size)}

    S = {
        "verdict_roi": v_roi, "verdict_smoothing": v_sm,
        "criteria_roi": crit_roi, "criteria_smoothing": crit_sm, "step_delay": step,
        "counts": {"drains": len(c0_pooled), "images": len({(r["split"], r["stem"]) for r in c0_pooled}),
                   "single_drain_images": n_single_img, "small_drains": len(small), "small_drain_areas": small,
                   "sequence_drains": len(series)},
        "per_drain": {f"{c}|{s}|{f}": b for (c, s, f), b in blocks.items()},
        "confidence": conf, "smoothing": sm, "timelines": timeline_info, "examples": examples, "timing": timing,
        "config": {"seed": C.SEED, "bootstrap_n": C.BOOTSTRAP_N, "thresholds": [C.YELLOW_THRESHOLD, C.RED_THRESHOLD],
                   "hysteresis": {"red_enter": C.HYST_RED_ENTER, "red_exit": C.HYST_RED_EXIT,
                                  "yellow_enter": C.HYST_YELLOW_ENTER, "yellow_exit": C.HYST_YELLOW_EXIT},
                   "small_drain_min_area_px_1024": C.SMALL_DRAIN_MIN_AREA_PX_1024},
    }
    if supp:
        S["supplementary_C2"] = supp
    with open(C.SUMMARY_JSON, "w", encoding="utf-8") as fh:
        json.dump(jsonable(S), fh, ensure_ascii=False, indent=2)
    print(f"[ghi] {C.SUMMARY_JSON}")
    write_report(S, blocks, sm, timeline_info, examples, timing, supp)
    print(f"\nKET LUAN (chinh, C1): ROI = {v_roi[0]} | Lam muot = {v_sm[0]}")
    if supp:
        print(f"[BO SUNG C2 - tham khao] ROI = {supp['reference_result_roi'][0]} | "
              f"Lam muot = {supp['reference_result_smoothing'][0]}")


if __name__ == "__main__":
    main()
