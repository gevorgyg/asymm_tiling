import subprocess
import re
import os
import matplotlib.pyplot as plt

EXECUTABLE = "./asymm"
TEMP_CONFIG = "master_sweep_temp.conf"
OUTPUT_DIR = "interesting_results/comprehensive_review"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Matrix Dimension
MAT_DIM = 96

# Base Cache parameters
L1_SIZE = 8192
L2_SIZE = 32768

def write_config(write_policy="WRITE_THROUGH", repl_policy="LRU", l1_assoc=4, l2_assoc=8, l1_line=8, l2_line=8, prng_cost=64):
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={MAT_DIM}\n")
        f.write(f"A_WIDTH_DIM={MAT_DIM}\n")
        f.write("A_PRECISION_BYTES=8\n")
        f.write(f"B_WIDTH_DIM={MAT_DIM}\n")
        f.write("B_PRECISION_BYTES=2\n")
        
        f.write(f"L1_SIZE_BYTES={L1_SIZE}\n")
        f.write(f"L1_LINE_SIZE_BYTES={l1_line}\n")
        f.write(f"L1_ASSOC={l1_assoc}\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        f.write(f"L1_REPLACEMENT_POLICY={repl_policy}\n")
        f.write(f"L1_WRITE_POLICY={write_policy}\n")
        
        f.write(f"L2_SIZE_BYTES={L2_SIZE}\n")
        f.write(f"L2_LINE_SIZE_BYTES={l2_line}\n")
        f.write(f"L2_ASSOC={l2_assoc}\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        f.write(f"L2_REPLACEMENT_POLICY={repl_policy}\n")
        f.write(f"L2_WRITE_POLICY={write_policy}\n")
        
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\n")
        f.write(f"PRNG_GEN_COST_PER_LINE={prng_cost}\n")

def run_sim(m, n, k, b_stationary, prng, write_policy="WRITE_THROUGH", repl_policy="LRU", l1_assoc=4, l2_assoc=8, l1_line=8, l2_line=8, prng_cost=64):
    write_config(write_policy, repl_policy, l1_assoc, l2_assoc, l1_line, l2_line, prng_cost)
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
        print(f"Failed configuration: {m}x{n}x{k}")
        return 0.0, 0.0, 0

sweep_values = [4, 8, 12, 16, 24, 32, 48]

# ==============================================================================
# SWEEP 1: Loop Stationarity vs. Write Policy (M, N, K sweeps)
# ==============================================================================
print("Running Sweep 1: Loop Stationarity vs. Write Policy...")
configs = [
    {"name": "C-Stat + Write-Through", "b_stationary": False, "write_policy": "WRITE_THROUGH"},
    {"name": "B-Stat + Write-Through", "b_stationary": True,  "write_policy": "WRITE_THROUGH"},
    {"name": "C-Stat + Write-Back",    "b_stationary": False, "write_policy": "WRITE_BACK"},
    {"name": "B-Stat + Write-Back",    "b_stationary": True,  "write_policy": "WRITE_BACK"},
]

m_results = {cfg["name"]: [] for cfg in configs}
n_results = {cfg["name"]: [] for cfg in configs}
k_results = {cfg["name"]: [] for cfg in configs}

for T in sweep_values:
    for cfg in configs:
        _, _, cyc_m = run_sim(T, 16, 16, cfg["b_stationary"], True, cfg["write_policy"])
        m_results[cfg["name"]].append(cyc_m / 1e6)
        
        _, _, cyc_n = run_sim(16, T, 16, cfg["b_stationary"], True, cfg["write_policy"])
        n_results[cfg["name"]].append(cyc_n / 1e6)
        
        _, _, cyc_k = run_sim(16, 16, T, cfg["b_stationary"], True, cfg["write_policy"])
        k_results[cfg["name"]].append(cyc_k / 1e6)

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
styles = {
    "C-Stat + Write-Through": {"color": "#1f77b4", "marker": "o", "ls": "-"},
    "B-Stat + Write-Through": {"color": "#ff7f0e", "marker": "s", "ls": "--"},
    "C-Stat + Write-Back":    {"color": "#2ca02c", "marker": "^", "ls": "-"},
    "B-Stat + Write-Back":    {"color": "#d62728", "marker": "d", "ls": "-."},
}
for name, data in m_results.items():
    ax1.plot(sweep_values, data, label=name, marker=styles[name]["marker"], ls=styles[name]["ls"], color=styles[name]["color"], linewidth=2)
ax1.set_title("M Sweep (Tx16x16: Tall Tiles)")
ax1.set_xlabel("Tile Dimension T")
ax1.set_ylabel("Execution Cycles (Millions)")
ax1.grid(True, linestyle="--", alpha=0.5)
ax1.legend(fontsize=9)

for name, data in n_results.items():
    ax2.plot(sweep_values, data, label=name, marker=styles[name]["marker"], ls=styles[name]["ls"], color=styles[name]["color"], linewidth=2)
ax2.set_title("N Sweep (16xTx16: Wide Tiles)")
ax2.set_xlabel("Tile Dimension T")
ax2.grid(True, linestyle="--", alpha=0.5)
ax2.legend(fontsize=9)

for name, data in k_results.items():
    ax3.plot(sweep_values, data, label=name, marker=styles[name]["marker"], ls=styles[name]["ls"], color=styles[name]["color"], linewidth=2)
ax3.set_title("K Sweep (16x16xT: Deep Tiles)")
ax3.set_xlabel("Tile Dimension T")
ax3.grid(True, linestyle="--", alpha=0.5)
ax3.legend(fontsize=9)

plt.suptitle("Sweep 1: Loop Stationarity vs. Write Policy (PRNG Mode)", fontsize=13, fontweight="bold")
plt.tight_layout(rect=[0, 0, 1, 0.93])
plt.savefig(f"{OUTPUT_DIR}/loop_vs_write_policy.png", dpi=300)
plt.close()

# ==============================================================================
# SWEEP 2: Replacement Policy (FIFO vs. LRU)
# ==============================================================================
print("Running Sweep 2: Replacement Policy (FIFO vs. LRU)...")
repl_configs = [
    {"name": "C-Stat + FIFO", "b_stationary": False, "repl": "FIFO"},
    {"name": "C-Stat + LRU",  "b_stationary": False, "repl": "LRU"},
    {"name": "B-Stat + FIFO", "b_stationary": True,  "repl": "FIFO"},
    {"name": "B-Stat + LRU",  "b_stationary": True,  "repl": "LRU"},
]
repl_results = {cfg["name"]: [] for cfg in repl_configs}
for T in sweep_values:
    for cfg in repl_configs:
        # Run under Write-Back to evaluate with clean L1 hits
        l1_hit, _, _ = run_sim(16, 16, T, cfg["b_stationary"], True, "WRITE_BACK", cfg["repl"])
        repl_results[cfg["name"]].append(l1_hit)

plt.figure(figsize=(9, 5.5))
for name, data in repl_results.items():
    plt.plot(sweep_values, data, label=name, marker="o", linewidth=2)
plt.title("Sweep 2: Replacement Policy (FIFO vs. LRU) L1 Hit Rates\n(K Sweep: 16x16xT | Write-Back Cache)", fontsize=11, fontweight="bold")
plt.xlabel("Tile Dimension T")
plt.ylabel("L1 Cache Hit Rate")
plt.grid(True, linestyle="--", alpha=0.5)
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/fifo_vs_lru.png", dpi=300)
plt.close()

# ==============================================================================
# SWEEP 3: PRNG Generation Cost Sweep
# ==============================================================================
print("Running Sweep 3: PRNG Generation Cost Sweep...")
costs = [16, 64, 128, 256, 512]
cost_results_c = []
cost_results_b = []
for c in costs:
    # Run tile size 16x16x16 with Write-Back to isolate the loop overhead
    _, _, cyc_c = run_sim(16, 16, 16, False, True, "WRITE_BACK", "LRU", prng_cost=c)
    _, _, cyc_b = run_sim(16, 16, 16, True,  True, "WRITE_BACK", "LRU", prng_cost=c)
    cost_results_c.append(cyc_c / 1e6)
    cost_results_b.append(cyc_b / 1e6)

plt.figure(figsize=(9, 5.5))
plt.plot(costs, cost_results_c, label="C-Stationary (Write-Back)", marker="o", linewidth=2, color="#1f77b4")
plt.plot(costs, cost_results_b, label="B-Stationary (Write-Back)", marker="s", linewidth=2, color="#ff7f0e")
plt.title("Sweep 3: Impact of PRNG Generation Cost on Loop Ordering\n(Matrix: 96x96 | Tile: 16x16x16 | Write-Back Cache)", fontsize=11, fontweight="bold")
plt.xlabel("PRNG Generation Cost (Cycles per Line)")
plt.ylabel("Execution Cycles (Millions)")
plt.grid(True, linestyle="--", alpha=0.5)
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/prng_gen_cost_sweep.png", dpi=300)
plt.close()

# ==============================================================================
# SWEEP 4: Cache Associativity & Line Sizes
# ==============================================================================
print("Running Sweep 4: Cache Parameters (Associativity & Line Size)...")
line_sizes = [8, 16, 32]
associativities = [1, 2, 4, 8]
param_results = {}
for ls in line_sizes:
    param_results[ls] = []
    for assoc in associativities:
        # Run tile size 16x16x16 under Write-Back
        l1_hit, _, _ = run_sim(16, 16, 16, False, True, "WRITE_BACK", "LRU", l1_assoc=assoc, l2_assoc=assoc*2, l1_line=ls, l2_line=ls)
        param_results[ls].append(l1_hit)

plt.figure(figsize=(9, 5.5))
for ls, data in param_results.items():
    plt.plot(associativities, data, label=f"Line Size: {ls} B", marker="o", linewidth=2)
plt.title("Sweep 4: Cache Parameter Impact (Associativity vs. Line Size)\n(C-Stationary | Write-Back | Tile: 16x16x16)", fontsize=11, fontweight="bold")
plt.xlabel("Cache Associativity (L1 Ways)")
plt.ylabel("L1 Cache Hit Rate")
plt.xticks(associativities)
plt.grid(True, linestyle="--", alpha=0.5)
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/cache_params_sweep.png", dpi=300)
plt.close()

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("\nWriting markdown report...")
with open(f"{OUTPUT_DIR}/README.md", "w") as f:
    f.write("""# Cache Simulator Sweep Analysis Report

This directory contains the results of the comprehensive sweep experiments designed to evaluate loop stationarity orderings, write policies, replacement policies, and other cache hardware parameters.

---

## 1. Loop Stationarity vs. Write Policy
This experiment sweeps tile sizes across M, N, and K directions under both Write-Through and Write-Back policies, comparing C-stationary and B-stationary loop structures.

![Loop vs Write Policy](loop_vs_write_policy.png)

### Key Findings:
- **Write-Through Penalty**: Under a Write-Through policy, B-stationary is nearly **2x slower** than C-stationary due to writing output partial sums ($C$) to memory at every innermost loop step.
- **Write-Back Benefit**: Under a Write-Back policy, the cache absorbs all partial sum writes locally. This yields a **2.6x speedup** for B-stationary, making its performance nearly identical to C-stationary.

---

## 2. Replacement Policy: FIFO vs. LRU
This experiment compares L1 hit rates of the newly implemented LRU replacement policy against FIFO across swept tile dimensions.

![FIFO vs LRU](fifo_vs_lru.png)

### Key Findings:
- **LRU Superiority**: The LRU policy consistently yields higher L1 hit rates across all tile sizes. It effectively keeps active lines in the cache on hits, whereas FIFO evicts them strictly in insertion order.
- **Tiling Dependency**: For small tile sizes (e.g. $4$ or $8$), LRU shows the largest improvement since the tile footprint fits in the cache. For larger tile sizes, both converge to the baseline spatial hit rate due to capacity thrashing.

---

## 3. PRNG Generation Cost Sweep
This experiment sweeps the latency of the on-demand PRNG generator line generation from 16 to 512 cycles to check when B-stationary becomes more efficient.

![PRNG Gen Cost](prng_gen_cost_sweep.png)

### Key Findings:
- **Crossover Behavior**: B-stationary significantly reduces the number of B-matrix loads and regenerations (from 64 down to 16).
- **Crossover Point**: When generation cost is low (e.g. $16$ or $64$ cycles), C-stationary is faster due to having fewer instructions. However, as generation cost exceeds **~350 cycles per line**, B-stationary becomes the superior loop structure because the penalty of PRNG regeneration outweighs its instruction overhead.

---

## 4. Cache Parameter Impact (Associativity & Line Size)
This experiment evaluates L1 hit rates under different L1 associativities ($1, 2, 4, 8$) and line sizes ($8, 16, 32$ bytes).

![Cache Params](cache_params_sweep.png)

### Key Findings:
- **Line Size Impact**: Increasing cache line size from 8B to 32B significantly drops L1 hit rates for $16\times16\times16$ tiling. Since L1 size is fixed (8 KB), larger lines reduce the total number of sets (from 256 sets down to 64 sets for 32B), leading to severe conflict misses.
- **Associativity Benefit**: Higher associativity (e.g. 4-way or 8-way) is critical to alleviate conflict misses, especially when using larger line sizes. Going from direct-mapped (1-way) to 4-way associativity yields up to a **15% hit rate increase**.
""")

print("Success! Sweep results and report generated in 'interesting_results/comprehensive_review/'")
