import subprocess
import re
import os
import numpy as np
import matplotlib.pyplot as plt

EXECUTABLE = "./asymm"
TEMP_CONFIG = "prng_plot_temp.conf"
OUTPUT_DIR = "interesting_results/prng_vs_mem_comparison"

os.makedirs(OUTPUT_DIR, exist_ok=True)

MAT_DIM = 96
L1_SIZE = 8192
L2_SIZE = 32768

def write_config(b_prec):
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={MAT_DIM}\n")
        f.write(f"A_WIDTH_DIM={MAT_DIM}\n")
        f.write("A_PRECISION_BYTES=8\n")
        f.write(f"B_WIDTH_DIM={MAT_DIM}\n")
        f.write(f"B_PRECISION_BYTES={b_prec}\n")
        
        f.write(f"L1_SIZE_BYTES={L1_SIZE}\n")
        f.write("L1_LINE_SIZE_BYTES=8\n")
        f.write("L1_ASSOC=4\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        f.write("L1_REPLACEMENT_POLICY=LRU\n")
        f.write("L1_WRITE_POLICY=WRITE_BACK\n")
        
        f.write(f"L2_SIZE_BYTES={L2_SIZE}\n")
        f.write("L2_LINE_SIZE_BYTES=8\n")
        f.write("L2_ASSOC=8\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        f.write("L2_REPLACEMENT_POLICY=LRU\n")
        f.write("L2_WRITE_POLICY=WRITE_BACK\n")
        
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\n")
        f.write("PRNG_GEN_COST_PER_LINE=64\n")

def run_sim(m, n, k, b_prec, prng):
    write_config(b_prec)
    cmd = [EXECUTABLE, "--config", TEMP_CONFIG]
    if prng:
        cmd.append("--Bgenerated")
    cmd.extend([str(m), str(n), str(k)])
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = res.stdout
        cycles = int(re.search(r"Cycles:\s+(\d+)", stdout).group(1))
        return cycles
    except Exception as e:
        return 0

precisions = [1, 2, 4, 8]
tiles = [
    {"name": "Standard (16x16x16)", "m": 16, "n": 16, "k": 16},
    {"name": "Best (16x48x16)", "m": 16, "n": 48, "k": 16},
    {"name": "Combined (24x48x16)", "m": 24, "n": 48, "k": 16}
]

# Collect data
data_cycles = {t["name"]: {"prng": [], "mem": []} for t in tiles}

print("Running comparison sweep for plotting...")
for t in tiles:
    for p in precisions:
        cyc_prng = run_sim(t['m'], t['n'], t['k'], p, True)
        cyc_mem = run_sim(t['m'], t['n'], t['k'], p, False)
        data_cycles[t["name"]]["prng"].append(cyc_prng / 1e6)
        data_cycles[t["name"]]["mem"].append(cyc_mem / 1e6)

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("Plotting results...")
fig, axs = plt.subplots(1, 3, figsize=(18, 6.5), sharey=True)

x = np.arange(len(precisions))
width = 0.35

for i, t in enumerate(tiles):
    name = t["name"]
    prng_c = data_cycles[name]["prng"]
    mem_c = data_cycles[name]["mem"]
    
    rects1 = axs[i].bar(x - width/2, prng_c, width, label='PRNG (On-Demand)', color='#1f77b4', edgecolor='black')
    rects2 = axs[i].bar(x + width/2, mem_c, width, label='Non-PRNG (Memory)', color='#d62728', edgecolor='black')
    
    axs[i].set_title(f"Tile Shape: {name}", fontsize=11, fontweight="bold")
    axs[i].set_xlabel("B Element Precision", fontsize=10)
    axs[i].set_xticks(x)
    axs[i].set_xticklabels([f"{p}B" for p in precisions], fontsize=9)
    axs[i].grid(True, linestyle="--", alpha=0.5)
    axs[i].legend(fontsize=9)
    
    # Add values on top of bars
    for rect in rects1:
        height = rect.get_height()
        axs[i].annotate(f'{height:.2f}M',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8)
    for rect in rects2:
        height = rect.get_height()
        axs[i].annotate(f'{height:.2f}M',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8)

axs[0].set_ylabel("Execution Cycles (Millions)", fontsize=11)
plt.suptitle("PRNG vs. Non-PRNG Execution Cycles Comparison (C-Stationary)\n(Matrix: 96x96 | A Precision: 8B | Cache: 8KB L1, 32KB L2 | Write-Back Policy)", fontsize=13, fontweight="bold")
plt.tight_layout(rect=[0, 0, 1, 0.94])
plt.savefig(f"{OUTPUT_DIR}/prng_vs_mem_comparison.png", dpi=300)
plt.close()

print(f"Success! Plot saved to '{OUTPUT_DIR}/prng_vs_mem_comparison.png'")
