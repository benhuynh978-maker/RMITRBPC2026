"""
Phân tích stress_test/results.csv -> in bảng markdown ra stdout, vẽ chart PNG + ảnh ví dụ vào
stress_test/charts/ và stress_test/examples/. Không ghi ra ngoài stress_test/.

Chạy: C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/analyze.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

STRESS_DIR = Path(__file__).resolve().parent
if str(STRESS_DIR) not in sys.path:
    sys.path.insert(0, str(STRESS_DIR))

import detect_variants as dv  # noqa: E402
import run_stress as rs  # noqa: E402
import scene  # noqa: E402

CHART_DIR = STRESS_DIR / "charts"
EX_DIR = STRESS_DIR / "examples"
COND_ORDER = ["q95", "q50", "q30", "q25", "q20", "q15", "q12", "q8",
              "q25+blur1.0", "q25+blur2.0", "q25+noise5", "q25+noise10"]
JPEG_ONLY = COND_ORDER[:8]
BIN_EDGES = [0, 8, 12, 16, 20, 25, 30, 35, 40, 45, 50, 60, 80, 1e9]
F_PX = float(scene.K[0, 0])
RECO_DISTANCES = [3, 5, 8]
VARIANT_LABEL = {"A_mac_dinh": "A (calibrate_aruco hiện tại)", "B_subpix": "B (SUBPIX)",
                 "C_subpix_ippe": "C (SUBPIX + IPPE_SQUARE)"}


def cell_stats(g: pd.DataFrame) -> pd.Series:
    det = g.detected.mean()
    dd = g[g.detected == 1]
    mr = dd.rot_err_deg.median() if len(dd) else np.nan
    mp = dd.pos_err_rel.median() if len(dd) else np.nan
    usable = bool(det >= 0.9 and mr <= 2.0 and mp <= 0.10)
    safe = bool(g.pass_strict.mean() >= 0.9)
    return pd.Series({"det_rate": det, "med_rot": mr, "p90_rot": dd.rot_err_deg.quantile(0.9) if len(dd) else np.nan,
                      "med_pos_rel": mp, "pass_rate": g.pass_strict.mean(), "usable": usable, "safe": safe,
                      "side_min": g.side_min_px.mean(), "side_mean": g.side_mean_px.mean(),
                      "reproj_med": dd.reproj_px.median() if len(dd) else np.nan, "n": len(g)})


def md_table(df: pd.DataFrame, fmt=lambda v: str(v), index_names=None) -> str:
    cols = list(df.columns)
    idx_names = index_names or [str(n) for n in (df.index.names if df.index.names[0] else ["" for _ in [0]])]
    lines = ["| " + " | ".join(idx_names + [str(c) for c in cols]) + " |",
             "|" + "---|" * (len(idx_names) + len(cols))]
    for idx, row in df.iterrows():
        idx_t = idx if isinstance(idx, tuple) else (idx,)
        lines.append("| " + " | ".join([str(i) for i in idx_t] + [fmt(v) for v in row.values]) + " |")
    return "\n".join(lines)


def symbol(r) -> str:
    return "AT" if r["safe"] else ("DĐ" if r["usable"] else "x")


def bin_rule(df: pd.DataFrame, variant: str):
    d = df[(df.variant == variant) & (df.esp32_like == 1)].copy()
    d["bin"] = pd.cut(d.side_min_px, BIN_EDGES, right=False)
    g = d.groupby("bin", observed=True).agg(n=("detected", "size"), det_rate=("detected", "mean"),
                                            pass_rate=("pass_strict", "mean"))
    ok = (g.pass_rate >= 0.9).values
    n_px = None
    for i in range(len(g)):
        if ok[i:].all():
            n_px = float(g.index[i].left)
            break
    return g, n_px


def k_factor(df: pd.DataFrame) -> dict:
    """side_min_px ≈ k(θ) · f · S / D  (ước lượng vùng xa, D ≥ 3 m, từ hình học đáp án; lấy phân vị 10% cho an toàn)."""
    d = df[(df.variant == "A_mac_dinh") & (df.cond == "q95") & (df.distance_m >= 3)].copy()
    d["k"] = d.side_min_px * d.distance_m / (F_PX * d.marker_mm / 1000.0)
    return {int(th): float(g.k.quantile(0.10)) for th, g in d.groupby("theta_deg")}


def recommend(n_px: float, kf: dict) -> pd.DataFrame:
    rows = {}
    for th, k in kf.items():
        rows[f"θ={th}°"] = {f"D={D} m": int(np.ceil(n_px * D / (F_PX * k) * 1000 / 50.0) * 50) for D in RECO_DISTANCES}
    return pd.DataFrame(rows).T


# ---------------- charts ----------------

def chart_heatmap(df: pd.DataFrame, variant: str, path: Path):
    d = df[df.variant == variant]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    for ax, th in zip(axes, rs.THETAS_DEG):
        p = d[d.theta_deg == th].pivot_table(index="distance_m", columns="cond", values="detected", aggfunc="mean")[JPEG_ONLY]
        im = ax.imshow(p.values, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
        ax.set_xticks(range(len(JPEG_ONLY)), JPEG_ONLY)
        ax.set_yticks(range(len(p.index)), [f"{v} m" for v in p.index])
        for i in range(p.shape[0]):
            for j in range(p.shape[1]):
                ax.text(j, i, f"{p.values[i, j]:.1f}", ha="center", va="center", fontsize=8)
        ax.axvspan(1.5, 4.5, fill=False, edgecolor="blue", lw=2)
        ax.set_title(f"θ = {th}° (khung xanh = q20–30 gần ESP32)")
        ax.set_xlabel("JPEG quality (thang OpenCV)")
    axes[0].set_ylabel("Khoảng cách camera → marker")
    fig.colorbar(im, ax=axes, shrink=0.8, label="Tỉ lệ nhận diện")
    fig.suptitle(f"Tỉ lệ nhận diện marker 200 mm — {VARIANT_LABEL[variant]}")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def chart_bins(tables: dict, path: Path):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for var, (g, n_px) in tables.items():
        x = [f"[{iv.left:g},{iv.right:g})" if iv.right < 1e8 else f"≥{iv.left:g}" for iv in g.index]
        ax.plot(x, g.pass_rate.values, marker="o", label=f"{VARIANT_LABEL[var]} — đạt 'an toàn' (N={n_px:g})")
        ax.plot(x, g.det_rate.values, ls="--", marker=".", alpha=0.6, label=f"{VARIANT_LABEL[var]} — chỉ nhận diện")
    ax.axhline(0.9, color="red", lw=1, ls=":")
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Cạnh ngắn nhất của marker trên ảnh (px)")
    ax.set_ylabel("Tỉ lệ")
    ax.set_title("JPEG q20/25/30 (gần ESP32): tỉ lệ đạt theo kích thước marker trên ảnh")
    plt.setp(ax.get_xticklabels(), rotation=30)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def chart_rot(stats: pd.DataFrame, path: Path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    for ax, th in zip(axes, rs.THETAS_DEG):
        for var, ls in [("A_mac_dinh", "-"), ("B_subpix", "--")]:
            for cond, c in [("q95", "tab:green"), ("q30", "tab:blue"), ("q20", "tab:orange"), ("q8", "tab:red")]:
                s = stats.loc[(var, th, slice(None), cond)]
                ax.plot(s.index.get_level_values("distance_m"), s.med_rot.values, ls=ls, color=c, marker="o",
                        label=f"{var[0]} {cond}")
        ax.axhline(2.0, color="k", lw=1, ls=":")
        ax.set_yscale("log")
        ax.set_title(f"θ = {th}°")
        ax.set_xlabel("Khoảng cách (m)")
        ax.grid(alpha=0.3, which="both")
    axes[0].set_ylabel("Trung vị sai số xoay (°, log)")
    axes[0].legend(fontsize=7, ncol=2)
    fig.suptitle("Sai số xoay theo khoảng cách (A = code hiện tại nét liền, B = SUBPIX nét đứt), ngưỡng 2°")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


# ---------------- ảnh ví dụ ----------------

def example_panel(D, th, seed, cond_name, title):
    conds = rs.conditions()
    ci = [c[0] for c in conds].index(cond_name)
    jb, img, R, t, C, sl, _ = rs.build_image(D, th, seed, ci, conds[ci])
    res = dv.detect_official(jb)
    gt = scene.gt_corners(R, t, 0.2)
    vis = img.copy()
    cv2.polylines(vis, [np.round(gt * 4).astype(np.int32)], True, (0, 0, 255), 1, cv2.LINE_AA, shift=2)
    loc = dv.detect_local(img, "A_local")
    txt = "KHONG detect"
    if res["ok"]:
        rot = scene.rotation_error_deg(R, res["R"])
        pos = float(np.linalg.norm(scene.camera_center(res["R"], res["t"]) - C))
        txt = f"rot {rot:.2f} deg, pos {pos:.2f} m ({pos / D * 100:.0f}%)"
        if loc["ok"]:
            cv2.polylines(vis, [np.round(loc["corners"] * 4).astype(np.int32)], True, (0, 255, 0), 1, cv2.LINE_AA, shift=2)
    # crop quanh marker, phóng to nearest để thấy rõ khối JPEG
    c = gt.mean(0)
    half = max(24, int(sl.max() * 1.3))
    x0, y0 = int(max(0, c[0] - half)), int(max(0, c[1] - half))
    x1, y1 = int(min(img.shape[1], c[0] + half)), int(min(img.shape[0], c[1] + half))
    crop = vis[y0:y1, x0:x1]
    crop = cv2.resize(crop, (320, int(320 * crop.shape[0] / crop.shape[1])), interpolation=cv2.INTER_NEAREST)
    full = cv2.resize(vis, (320, 240), interpolation=cv2.INTER_AREA)
    h = max(full.shape[0], crop.shape[0])
    panel = np.full((h + 50, 640 + 10, 3), 255, np.uint8)
    panel[:full.shape[0], :320] = full
    panel[:crop.shape[0], 330:330 + crop.shape[1]] = crop
    cv2.putText(panel, title, (5, h + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(panel, f"D={D}m th={th} {cond_name} seed{seed} canh_min={sl.min():.0f}px | {txt}", (5, h + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
    return panel


def main():
    CHART_DIR.mkdir(exist_ok=True)
    EX_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(STRESS_DIR / "results.csv")
    stats = df.groupby(["variant", "theta_deg", "distance_m", "cond"]).apply(cell_stats, include_groups=False)

    print("## Kích thước marker 200 mm trên ảnh (px, trung bình 10 seed)\n")
    sz = stats.loc["A_mac_dinh"].xs("q95", level="cond")[["side_mean", "side_min"]].unstack("theta_deg")
    sz.columns = [f"{'cạnh TB' if a == 'side_mean' else 'cạnh ngắn'} θ={b}°" for a, b in sz.columns]
    print(md_table(sz, lambda v: f"{v:.1f}", ["D (m)"]))

    for var in ["A_mac_dinh", "B_subpix"]:
        print(f"\n## Tỉ lệ nhận diện — {VARIANT_LABEL[var]}\n")
        for th in rs.THETAS_DEG:
            p = stats.loc[(var, th)].det_rate.unstack("cond")[COND_ORDER]
            print(f"\n**θ = {th}°**\n")
            print(md_table(p, lambda v: f"{v * 100:.0f}%", ["D (m)"]))

    for var in rs_variants():
        print(f"\n## Kết luận ô theo tiêu chí — {VARIANT_LABEL[var]} (AT = an toàn, DĐ = dùng được, x = không đạt)\n")
        for th in rs.THETAS_DEG:
            s = stats.loc[(var, th)]
            p = s.apply(symbol, axis=1).unstack("cond")[COND_ORDER]
            print(f"\n**θ = {th}°**\n")
            print(md_table(p, str, ["D (m)"]))

    for var in ["A_mac_dinh", "B_subpix"]:
        for col, name, fmt in [("med_rot", "Trung vị sai số xoay (°)", lambda v: "—" if np.isnan(v) else f"{v:.2f}"),
                               ("med_pos_rel", "Trung vị sai số vị trí (% D)", lambda v: "—" if np.isnan(v) else f"{v * 100:.1f}")]:
            print(f"\n## {name} — {VARIANT_LABEL[var]}\n")
            for th in rs.THETAS_DEG:
                p = stats.loc[(var, th)][col].unstack("cond")[COND_ORDER]
                print(f"\n**θ = {th}°**\n")
                print(md_table(p, fmt, ["D (m)"]))

    print("\n## Điểm gãy (D lớn nhất còn đạt; ô đầu tiên trượt) — chỉ JPEG\n")
    rows = []
    for var in ["A_mac_dinh", "B_subpix", "C_subpix_ippe"]:
        for th in rs.THETAS_DEG:
            for cond in JPEG_ONLY:
                s = stats.loc[(var, th, slice(None), cond)]
                ds = s.index.get_level_values("distance_m").tolist()
                for key in ["usable", "safe"]:
                    okv = s[key].values
                    last_ok = None
                    for i in range(len(ds)):
                        if okv[: i + 1].all():
                            last_ok = ds[i]
                    rows.append({"variant": var, "theta": th, "cond": cond, "tieu_chi": key, "D_max_dat": last_ok})
    bp = pd.DataFrame(rows)
    for key, nm in [("usable", "dùng được (chính)"), ("safe", "an toàn")]:
        t = bp[bp.tieu_chi == key].pivot_table(index=["variant", "theta"], columns="cond", values="D_max_dat",
                                              aggfunc="first")[JPEG_ONLY]
        print(f"\n**D lớn nhất (m) mà mọi D ≤ nó đều đạt '{nm}'** (— = trượt ngay từ 1 m)\n")
        print(md_table(t, lambda v: "—" if pd.isna(v) else f"{v:g}", ["biến thể", "θ"]))

    tables = {}
    kf = k_factor(df)
    summary = {"k_factor_p10": kf, "f_px": F_PX}
    for var in ["A_mac_dinh", "B_subpix", "C_subpix_ippe"]:
        g, n_px = bin_rule(df, var)
        tables[var] = (g, n_px)
        print(f"\n## Quy tắc N px — {VARIANT_LABEL[var]} (mẫu q20/25/30, mọi D, θ)\n")
        gg = g.copy()
        gg.index = [f"[{iv.left:g}, {iv.right:g})" if iv.right < 1e8 else f"≥ {iv.left:g}" for iv in g.index]
        print(md_table(gg, lambda v: f"{v:.0f}" if v > 1.5 else f"{v * 100:.0f}%", ["cạnh ngắn (px)"]))
        print(f"\n=> N = {n_px}")
        rec = recommend(n_px, kf) if n_px is not None else None
        summary[var] = {"N_px": n_px, "reco_mm": rec.to_dict() if rec is not None else None}
        if rec is not None:
            print(f"\nKích thước marker khuyến nghị (mm, làm tròn lên bội 50) với N={n_px:g}, k(θ)={kf}:\n")
            print(md_table(rec, lambda v: f"{v}", ["góc nhìn"]))

    print("\n## Tỉ lệ 'ngược hướng' (sai số xoay > 10°) trong các mẫu detect được\n")
    d = df[df.detected == 1]
    print(d.assign(flip=d.rot_err_deg > 10).groupby("variant").flip.mean().round(3).to_string())
    print("\n## Detect nhầm id\n")
    print(df[df.fail_msg.fillna("").str.contains("id=")][["variant", "distance_m", "theta_deg", "seed", "cond", "fail_msg"]].to_string())
    print("\n## Dung lượng JPEG trung vị (KB) theo điều kiện\n")
    print(df[df.variant == "A_mac_dinh"].groupby("cond").jpeg_kb.median()[COND_ORDER].to_string())
    print("\n## Reprojection RMS trung vị (px) — A, theo θ/D ở q25\n")
    print(stats.loc["A_mac_dinh"].xs("q25", level="cond").reproj_med.unstack("theta_deg").round(3).to_string())

    chart_heatmap(df, "A_mac_dinh", CHART_DIR / "01_ti_le_nhan_dien_A.png")
    chart_bins(tables, CHART_DIR / "02_ti_le_dat_theo_px.png")
    chart_rot(stats, CHART_DIR / "03_sai_so_xoay_theo_khoang_cach.png")
    (STRESS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                                             encoding="utf-8")
    return stats


def rs_variants():
    return ["A_mac_dinh", "B_subpix", "C_subpix_ippe"]


if __name__ == "__main__":
    main()
