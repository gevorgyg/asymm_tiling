import subprocess
import re
import os
import matplotlib.pyplot as plt

EXECUTABLE = "./asymm"
TEMP_CONFIG = "comp_sweep_temp.conf"

# Matrix sizes (96 has many clean divisors: 4, 6, 8, 12, 16, 24, 32, 48)
MAT_DIM = 96

# Cache config parameters (Large cache to see write-back benefits clearly)
L1_SIZE = 8192
L2_SIZE = 32768

def write_config(write_policy, repl_policy):
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={MAT_DIM}\n")
        f.write(f"A_WIDTH_DIM={MAT_DIM}\n")
        f.write("A_PRECISION_BYTES=8\n")
        f.write(f"B_WIDTH_DIM={MAT_DIM}\n")
        f.write("B_PRECISION_BYTES=2\n")
        
        f.write(f"L1_SIZE_BYTES={L1_SIZE}\n")
        f.write("L1_LINE_SIZE_BYTES=8\n")
        f.write("L1_ASSOC=4\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        f.write(f"L1_REPLACEMENT_POLICY={repl_policy}\n")
        f.write(f"L1_WRITE_POLICY={write_policy}\n")
        
        f.write(f"L2_SIZE_BYTES={L2_SIZE}\n")
        f.write("L2_LINE_SIZE_BYTES=8\n")
        f.write("L2_ASSOC=8\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        f.write(f"L2_REPLACEMENT_POLICY={repl_policy}\n")
        f.write(f"L2_WRITE_POLICY={write_policy}\n")
        
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\n")
        f.write("PRNG_GEN_COST_PER_LINE=64\n")

def run_sim(m, n, k, b_stationary, prng, write_policy, repl_policy):
    write_config(write_policy, repl_policy)
    cmd = [EXECUTABLE, "--config", TEMP_CONFIG]
    if prng:
        cmd.append("--Bgenerated")
    if b_stationary:
        cmd.append("--Bstationary")
    cmd.extend([str(m), str(n), str(k)])
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = res.stdout
        
        l1_hit = float(re.search(r"--- L1 ---\s+Hit rate:\s+([\d.]+)", stdout).group(1))
        l2_hit = float(re.search(r"--- L2 ---\s+Hit rate:\s+([\d.]+)", stdout).group(1))
        cycles = int(re.search(r"Cycles:\s+(\d+)", stdout).group(1))
        
        return l1_hit, l2_hit, cycles
    except Exception as e:
        print(f"Failed configuration: {m}x{n}x{k}, stat={b_stationary}, prng={prng}, wp={write_policy}, repl={repl_policy}")
        return 0.0, 0.0, 0

# Sweep values
sweep_values = [4, 8, 12, 16, 24, 32, 48]

# Configurations to test:
# Loop Mode: 'C-Stationary' (b_stationary=False) vs 'B-Stationary' (b_stationary=True)
# Write Policy: 'WRITE_THROUGH' vs 'WRITE_BACK'
# (We will keep replacement policy fixed to LRU and cache mode to PRNG to isolate the loop and write policy tradeoffs)
configs = [
    {"name": "C-Stat + Write-Through", "b_stationary": False, "write_policy": "WRITE_THROUGH"},
    {"name": "B-Stat + Write-Through", "b_stationary": True,  "write_policy": "WRITE_THROUGH"},
    {"name": "C-Stat + Write-Back",    "b_stationary": False, "write_policy": "WRITE_BACK"},
    {"name": "B-Stat + Write-Back",    "b_stationary": True,  "write_policy": "WRITE_BACK"},
]

print("Starting comprehensive loop ordering and write policy sweep...")

# 1. Sweep M (Tall Tiles): M = T, N = 16, K = 16
m_results = {cfg["name"]: [] for cfg in configs}
# 2. Sweep N (Wide Tiles): M = 16, N = T, K = 16
n_results = {cfg["name"]: [] for cfg in configs}
# 3. Sweep K (Deep Tiles): M = 16, N = 16, K = T
k_results = {cfg["name"]: [] for cfg in configs}

for T in sweep_values:
    print(f"Running sweep index T={T}...")
    for cfg in configs:
        # Tall Sweep (T x 16 x 16)
        l1_hit_m, _, _ = run_sim(T, 16, 16, cfg["b_stationary"], True, cfg["write_policy"], "LRU")
        m_results[cfg["name"]].append(l1_hit_m)
        
        # Wide Sweep (16 x T x 16)
        l1_hit_n, _, _ = run_sim(16, T, 16, cfg["b_stationary"], True, cfg["write_policy"], "LRU")
        n_results[cfg["name"]].append(l1_hit_n)
        
        # Deep Sweep (16 x 16 x T)
        l1_hit_k, _, _ = run_sim(16, 16, T, cfg["b_stationary"], True, cfg["write_policy"], "LRU")
        k_results[cfg["name"]].append(l1_hit_k)

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("\nGenerating multi-plot sweep comparison...")

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(20, 6.5))

styles = {
    "C-Stat + Write-Through": {"color": "#1f77b4", "marker": "o", "ls": "-"},
    "B-Stat + Write-Through": {"color": "#ff7f0e", "marker": "s", "ls": "--"},
    "C-Stat + Write-Back":    {"color": "#2ca02c", "marker": "^", "ls": "-"},
    "B-Stat + Write-Back":    {"color": "#d62728", "marker": "d", "ls": "-."},
}

# Plot M Sweep
for name, data in m_results.items():
    ax1.plot(sweep_values, data, label=name, marker=styles[name]["marker"], 
             linestyle=styles[name]["ls"], color=styles[name]["color"], linewidth=2)
ax1.set_title("M Sweep (Tx16x16: Tall Tiles)", fontsize=11, fontweight="bold")
ax1.set_xlabel("Tile Dimension T", fontsize=10)
ax1.set_ylabel("L1 Cache Hit Rate", fontsize=10)
ax1.set_ylim(0.0, 1.0)
ax1.grid(True, linestyle="--", alpha=0.5)
ax1.legend(fontsize=9)

# Plot N Sweep
for name, data in n_results.items():
    ax2.plot(sweep_values, data, label=name, marker=styles[name]["marker"], 
             linestyle=styles[name]["ls"], color=styles[name]["color"], linewidth=2)
ax2.set_title("N Sweep (16xTx16: Wide Tiles)", fontsize=11, fontweight="bold")
ax2.set_xlabel("Tile Dimension T", fontsize=10)
ax2.set_ylabel("L1 Cache Hit Rate", fontsize=10)
ax2.set_ylim(0.0, 1.0)
ax2.grid(True, linestyle="--", alpha=0.5)
ax2.legend(fontsize=9)

# Plot K Sweep
for name, data in k_results.items():
    ax3.plot(sweep_values, data, label=name, marker=styles[name]["marker"], 
             linestyle=styles[name]["ls"], color=styles[name]["color"], linewidth=2)
ax3.set_title("K Sweep (16x16xT: Deep Tiles)", fontsize=11, fontweight="bold")
ax3.set_xlabel("Tile Dimension T", fontsize=10)
ax3.set_ylabel("L1 Cache Hit Rate", fontsize=10)
ax3.set_ylim(0.0, 1.0)
ax3.grid(True, linestyle="--", alpha=0.5)
ax3.legend(fontsize=9)

plt.suptitle("Asymmetric Matrix Multiplication Sweep: Loop Stationarity vs. Write Policy\n(Matrix: 96x96 | Cache: 8KB L1, 32KB L2 | PRNG Mode)", fontsize=13, fontweight="bold")
plt.tight_layout(rect=[0, 0, 1, 0.93])

os.makedirs("plots", exist_ok=True)
plt.savefig("plots/comprehensive_sweep_comparison.png", dpi=300, bbox_inches="tight")
print("Success! Comprehensive comparison plots generated: 'plots/comprehensive_sweep_comparison.png'")
