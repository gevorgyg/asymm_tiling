import json, math
from pathlib import Path
import matplotlib.pyplot as plt

curves = json.loads(Path("curves.json").read_text())

colors = {"1.0": "#636EFA", "0.5": "#00CC96", "0.25": "#EF553B", "0.125": "#AB63FA"}

fig, ax = plt.subplots(figsize=(10, 6), dpi=140)
for rho_str, curve in curves.items():
    ratios = sorted(curve, key=float)
    log2r  = [math.log2(float(r)) for r in ratios]
    dram   = [curve[r]["dram_min"] / 1024 for r in ratios]
    c = colors.get(rho_str, "k")
    ax.plot(log2r, dram, marker="o", color=c, label=f"ρ = {rho_str}")
    ax.axvline(math.log2(1 / float(rho_str)), color=c, linestyle="--", alpha=0.4)

    # annotate the empirical minimum
    best_ratio = min(curve, key=lambda r: curve[r]["dram_min"])
    best = curve[best_ratio]
    ax.annotate(f"{best['pair'][0]}x{best['pair'][1]}",
                (math.log2(float(best_ratio)), best["dram_min"] / 1024),
                textcoords="offset points", xytext=(5, 5),
                fontsize=8, color=c)
ax.set_xlabel("log₂(T_N / T_M)")
ax.set_ylabel("DRAM (KB)")
ax.set_title("DRAM vs aspect ratio per ρ (dashed = predicted optimum 1/ρ)")
ax.grid(True, ls=":", alpha=0.5)
ax.legend()
plt.tight_layout()
plt.savefig("dram_vs_aspect_ratio.png")
plt.show()    # or remove this if you only want the file

