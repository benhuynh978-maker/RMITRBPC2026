"""
Phân tích validation.csv + sweep.csv (phần bổ sung) -> in bảng markdown, vẽ chart 04 vào charts/.
Dùng ĐÚNG tiêu chí đã chốt (analyze.cell_stats). Chỉ ghi trong stress_test/.

Chạy: C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/analyze_supplementary.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

STRESS_DIR = Path(__file__).resolve().parent
if str(STRESS_DIR) not in sys.path:
    sys.path.insert(0, str(STRESS_DIR))

import analyze as an  # noqa: E402

COND3 = ["q30", "q25", "q20"]


def main():
    val = pd.read_csv(STRESS_DIR / "validation.csv")
    sw = pd.read_csv(STRESS_DIR / "sweep.csv")

    print("## Kiểm chứng kích thước khuyến nghị (seed mới 100–109)\n")
    st = val.groupby(["variant", "distance_m", "theta_deg", "marker_mm", "cond"]).apply(an.cell_stats, include_groups=False)
    out = st.reset_index()
    out["kq"] = out.apply(an.symbol, axis=1)
    out["txt"] = out.apply(lambda r: f"{r.kq}: det {r.det_rate * 100:.0f}% / đạt {r.pass_rate * 100:.0f}% / xoay {r.med_rot:.2f}°", axis=1)
    p = out.pivot_table(index=["variant", "distance_m", "theta_deg", "marker_mm"], columns="cond", values="txt",
                        aggfunc="first")[COND3]
    print(an.md_table(p, str, ["biến thể", "D (m)", "θ", "marker (mm)"]))

    print("\n## Quét kích thước marker: tỉ lệ đạt 'an toàn' (gộp q20/25/30, 30 mẫu/ô)\n")
    g = sw.groupby(["variant", "theta_deg", "distance_m", "marker_mm"]).agg(
        side_min=("side_min_px", "mean"), side_mean=("side_mean_px", "mean"),
        det=("detected", "mean"), pass_rate=("pass_strict", "mean")).reset_index()
    # trạng thái ô theo tiêu chí chính/an toàn cho từng điều kiện q, rồi "mọi q20/25/30 đều an toàn"
    cs = sw.groupby(["variant", "theta_deg", "distance_m", "marker_mm", "cond"]).apply(an.cell_stats, include_groups=False)
    allsafe = cs.groupby(level=[0, 1, 2, 3]).safe.all().rename("all_safe")
    allusable = cs.groupby(level=[0, 1, 2, 3]).usable.all().rename("all_usable")
    g = g.merge(allsafe.reset_index(), on=["variant", "theta_deg", "distance_m", "marker_mm"]).merge(
        allusable.reset_index(), on=["variant", "theta_deg", "distance_m", "marker_mm"])
    for var in ["A_mac_dinh", "B_subpix"]:
        print(f"\n**{an.VARIANT_LABEL[var]}** — mỗi ô: cạnh ngắn px / tỉ lệ đạt / (AT = mọi q an toàn, DĐ = mọi q dùng được)\n")
        x = g[g.variant == var].copy()
        x["txt"] = x.apply(lambda r: f"{r.side_min:.0f}px/{r.pass_rate * 100:.0f}%{' AT' if r.all_safe else (' DĐ' if r.all_usable else '')}", axis=1)
        p = x.pivot_table(index="marker_mm", columns=["distance_m", "theta_deg"], values="txt", aggfunc="first")
        p.columns = [f"D={a} θ={b}°" for a, b in p.columns]
        print(an.md_table(p, lambda v: "" if pd.isna(v) else str(v), ["marker (mm)"]))

    print("\n## Ngưỡng px theo từng θ (phân tích phụ): cạnh ngắn nhỏ nhất mà từ đó trở lên mọi kích thước đều AT\n")
    rows = []
    for (var, th, D), x in g.groupby(["variant", "theta_deg", "distance_m"]):
        x = x.sort_values("marker_mm")
        ok = x.all_safe.values
        first = None
        for i in range(len(x)):
            if ok[i:].all():
                first = i
                break
        rows.append({"variant": var, "theta": th, "D": D,
                     "S_min_mm": None if first is None else int(x.marker_mm.values[first]),
                     "side_min_px": None if first is None else round(float(x.side_min.values[first]), 1),
                     "side_mean_px": None if first is None else round(float(x.side_mean.values[first]), 1)})
    thr = pd.DataFrame(rows).set_index(["variant", "theta", "D"])
    print(an.md_table(thr, lambda v: "—" if pd.isna(v) else f"{v:g}", ["biến thể", "θ", "D (m)"]))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
    for ax, var in zip(axes, ["A_mac_dinh", "B_subpix"]):
        for th, c in zip([20, 45, 65], ["tab:blue", "tab:orange", "tab:green"]):
            for D, ls in [(5, "-"), (8, "--")]:
                x = g[(g.variant == var) & (g.theta_deg == th) & (g.distance_m == D)].sort_values("side_min")
                ax.plot(x.side_min, x.pass_rate, ls=ls, color=c, marker="o", ms=4, label=f"θ={th}°, D={D} m")
        ax.axhline(0.9, color="red", lw=1, ls=":")
        ax.set_xscale("log")
        ax.set_xticks([10, 20, 30, 40, 60, 80, 120, 160], ["10", "20", "30", "40", "60", "80", "120", "160"])
        ax.set_xlabel("Cạnh ngắn nhất marker trên ảnh (px)")
        ax.set_title(an.VARIANT_LABEL[var])
        ax.grid(alpha=0.3, which="both")
    axes[0].set_ylabel("Tỉ lệ đạt 'an toàn' (q20/25/30)")
    axes[0].legend(fontsize=8)
    fig.suptitle("Quét kích thước marker (seed 100–109): đạt theo px, tách theo góc nhìn")
    fig.savefig(an.CHART_DIR / "04_quet_kich_thuoc_theo_goc.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
