import subprocess
import re
import os
import matplotlib.pyplot as plt

EXECUTABLE = "./asymm"
TEMP_CONFIG = "b_prec_sweep_temp.conf"
OUTPUT_DIR = "interesting_results/b_precision_sweep"

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

def run_sim(m, n, k, b_prec):
    write_config(b_prec)
    cmd = [EXECUTABLE, "--config", TEMP_CONFIG, "--Bgenerated"]
    cmd.extend([str(m), str(n), str(k)])
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = res.stdout
        l1_hit = float(re.search(r"--- L1 ---\s+Hit rate:\s+([\d.]+)", stdout).group(1))
        cycles = int(re.search(r"Cycles:\s+(\d+)", stdout).group(1))
        return l1_hit, cycles
    except Exception as e:
        print(f"Failed configuration: {m}x{n}x{k}, b_prec={b_prec}")
        return 0.0, 0

sweep_values = [8, 16, 24, 32, 48]
precisions = [1, 2, 4, 8]

# Results structures
m_hits = {p: [] for p in precisions}
m_cycles = {p: [] for p in precisions}

n_hits = {p: [] for p in precisions}
n_cycles = {p: [] for p in precisions}

k_hits = {p: [] for p in precisions}
k_cycles = {p: [] for p in precisions}

print("Running B precision sweeps...")

for T in sweep_values:
    print(f"Running sweep index T={T}...")
    for p in precisions:
        # 1. M Sweep (Tx16x16)
        hit_m, cyc_m = run_sim(T, 16, 16, p)
        m_hits[p].append(hit_m)
        m_cycles[p].append(cyc_m / 1e6)
        
        # 2. N Sweep (16xTx16)
        hit_n, cyc_n = run_sim(16, T, 16, p)
        n_hits[p].append(hit_n)
        n_cycles[p].append(cyc_n / 1e6)
        
        # 3. K Sweep (16x16xT)
        hit_k, cyc_k = run_sim(16, 16, T, p)
        k_hits[p].append(hit_k)
        k_cycles[p].append(cyc_k / 1e6)

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("\nGenerating B precision plot...")

# 2x3 Subplot Grid
fig, axs = plt.subplots(2, 3, figsize=(18, 11))
styles = {
    1: {"color": "#2ca02c", "marker": "o", "label": "B: 1 Byte (8-bit)"},
    2: {"color": "#1f77b4", "marker": "s", "label": "B: 2 Bytes (16-bit)"},
    4: {"color": "#ff7f0e", "marker": "^", "label": "B: 4 Bytes (32-bit)"},
    8: {"color": "#d62728", "marker": "d", "label": "B: 8 Bytes (64-bit)"},
}

# Row 0: L1 Cache Hit Rates
for p in precisions:
    axs[0, 0].plot(sweep_values, m_hits[p], label=styles[p]["label"], marker=styles[p]["marker"], color=styles[p]["color"], linewidth=2)
axs[0, 0].set_title("M Sweep (Tx16x16): L1 Hit Rate", fontsize=11, fontweight="bold")
axs[0, 0].set_xlabel("Tile Dimension T", fontsize=9)
axs[0, 0].set_ylabel("L1 Hit Rate", fontsize=10)
axs[0, 0].set_ylim(0.0, 1.0)
axs[0, 0].grid(True, linestyle="--", alpha=0.5)
axs[0, 0].legend()

for p in precisions:
    axs[0, 1].plot(sweep_values, n_hits[p], label=styles[p]["label"], marker=styles[p]["marker"], color=styles[p]["color"], linewidth=2)
axs[0, 1].set_title("N Sweep (16xTx16): L1 Hit Rate", fontsize=11, fontweight="bold")
axs[0, 1].set_xlabel("Tile Dimension T", fontsize=9)
axs[0, 1].set_ylim(0.0, 1.0)
axs[0, 1].grid(True, linestyle="--", alpha=0.5)
axs[0, 1].legend()

for p in precisions:
    axs[0, 2].plot(sweep_values, k_hits[p], label=styles[p]["label"], marker=styles[p]["marker"], color=styles[p]["color"], linewidth=2)
axs[0, 2].set_title("K Sweep (16x16xT: L1 Hit Rate", fontsize=11, fontweight="bold")
axs[0, 2].set_xlabel("Tile Dimension T", fontsize=9)
axs[0, 2].set_ylim(0.0, 1.0)
axs[0, 2].grid(True, linestyle="--", alpha=0.5)
axs[0, 2].legend()

# Row 1: Execution Cycles
for p in precisions:
    axs[1, 0].plot(sweep_values, m_cycles[p], label=styles[p]["label"], marker=styles[p]["marker"], color=styles[p]["color"], linewidth=2)
axs[1, 0].set_title("M Sweep (Tx16x16): Execution Cycles", fontsize=11, fontweight="bold")
axs[1, 0].set_xlabel("Tile Dimension T", fontsize=9)
axs[1, 0].set_ylabel("Execution Cycles (Millions)", fontsize=10)
axs[1, 0].grid(True, linestyle="--", alpha=0.5)
axs[1, 0].legend()

for p in precisions:
    axs[1, 1].plot(sweep_values, n_cycles[p], label=styles[p]["label"], marker=styles[p]["marker"], color=styles[p]["color"], linewidth=2)
axs[1, 1].set_title("N Sweep (16xTx16): Execution Cycles", fontsize=11, fontweight="bold")
axs[1, 1].set_xlabel("Tile Dimension T", fontsize=9)
axs[1, 1].grid(True, linestyle="--", alpha=0.5)
axs[1, 1].legend()

for p in precisions:
    axs[1, 2].plot(sweep_values, k_cycles[p], label=styles[p]["label"], marker=styles[p]["marker"], color=styles[p]["color"], linewidth=2)
axs[1, 2].set_title("K Sweep (16x16xT): Execution Cycles", fontsize=11, fontweight="bold")
axs[1, 2].set_xlabel("Tile Dimension T", fontsize=9)
axs[1, 2].grid(True, linestyle="--", alpha=0.5)
axs[1, 2].legend()

plt.suptitle("Impact of Matrix B Precision on L1 Hit Rates & Execution Cycles (C-Stationary)\n(Matrix: 96x96 | A Precision: 8B | Cache: 8KB L1, 32KB L2 | Write-Back Policy)", fontsize=13, fontweight="bold")
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(f"{OUTPUT_DIR}/b_precision_sweep.png", dpi=300)
plt.close()

print(f"Success! Sweep plot saved to '{OUTPUT_DIR}/b_precision_sweep.png'")
