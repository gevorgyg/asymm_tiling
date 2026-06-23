#!/usr/bin/env python3
import os
import subprocess
import re
import json
import sys

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CONFIG_PATH = os.path.join(WORKSPACE_DIR, "tests", "configs", "sweep_temp.conf")
DATA_DIR = os.path.join(WORKSPACE_DIR, "presentation", "results-for-presentation")
REPORT_PATH = os.path.join(DATA_DIR, "cache_tiling_sweep_report.md")
PLOT_PATH = os.path.join(DATA_DIR, "cache_tiling_sweep.png")

# Config content (L2 Cache set to 32 KB to force capacity evictions)
CONFIG_CONTENT = """# Matrix dimensions (elements)
A_HEIGHT_DIM=256
A_WIDTH_DIM=256
B_WIDTH_DIM=256

# Element precisions (bytes)
A_PRECISION_BYTES=8
B_PRECISION_BYTES=2

# L1 Cache Parameters
L1_SIZE_BYTES=32768
L1_LINE_SIZE_BYTES=64
L1_ASSOC=8
L1_ACCESS_CYCLES=4
L1_REPLACEMENT_POLICY=LRU
L1_WRITE_POLICY=WRITE_BACK

# L2 Cache Parameters (Constrained: 32 KB)
L2_SIZE_BYTES=32768
L2_LINE_SIZE_BYTES=64
L2_ASSOC=8
L2_ACCESS_CYCLES=14
L2_REPLACEMENT_POLICY=LRU
L2_WRITE_POLICY=WRITE_BACK

# DRAM Latency (cycles)
MEM_ACCESS_CYCLES=180

# PRNG Device
PRNG_ACCESS_CYCLES=2
PRNG_GEN_COST_PER_LINE=64

# PRNG FIFO Device
PRNG_FIFO_CAPACITY=64
PRNG_FIFO_GEN_COST=10

# Hardware register tile
REG_M=4
REG_N=4
REG_K=4
MULAC_CYCLES=8

# Scratchpad memory (unused for this cache-only experiment)
SP_ACCESS_CYCLES=1
SP_BANKS=8
SP_WORD_SIZE_BYTES=8
"""

def create_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        f.write(CONFIG_CONTENT)

def remove_config():
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)

def run_simulation(m, n, k):
    cmd = [os.path.join(WORKSPACE_DIR, "asymm"), "--config", CONFIG_PATH, str(m), str(n), str(k)]
    result = subprocess.run(cmd, cwd=WORKSPACE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"Error running simulation for tile {m}x{n}x{k}:")
        print(result.stderr)
        return None
    return parse_output(result.stdout)

def parse_output(stdout):
    stats = {
        "cycles": 0,
        "l1_lookups": 0,
        "l1_fills": 0,
        "l1_evicts": 0,
        "l2_lookups": 0,
        "l2_fills": 0,
        "l2_evicts": 0
    }
    
    current_section = None
    for line in stdout.splitlines():
        if "--- L1 ---" in line:
            current_section = "L1"
        elif "--- L2 ---" in line:
            current_section = "L2"
        elif "--- System ---" in line:
            current_section = "System"
            
        if current_section == "L1":
            if "TagLookup:" in line:
                stats["l1_lookups"] = int(line.split()[-1])
            elif "LineFill:" in line:
                stats["l1_fills"] = int(line.split()[-1])
            elif "Evict:" in line:
                stats["l1_evicts"] = int(line.split()[-1])
        elif current_section == "L2":
            if "TagLookup:" in line:
                stats["l2_lookups"] = int(line.split()[-1])
            elif "LineFill:" in line:
                stats["l2_fills"] = int(line.split()[-1])
            elif "Evict:" in line:
                stats["l2_evicts"] = int(line.split()[-1])
        elif current_section == "System":
            if "Cycles:" in line:
                stats["cycles"] = int(line.split()[-1])
                
    # DRAM Traffic = (L2 LineFills + L2 Evictions) * 64 bytes
    stats["dram_traffic"] = (stats["l2_fills"] + stats["l2_evicts"]) * 64
    return stats

def main():
    print("=== Cache-Constrained Tile Shape Sweep ===")
    
    # 1. Compile simulator
    print("Compiling simulator...")
    subprocess.run(["make"], cwd=WORKSPACE_DIR, check=True)
    
    # 2. Create config
    create_config()
    
    # Sweep shapes with Area = 256, K = 16
    fixed_area = 256
    k_dim = 16
    shapes = [
        (4, 64),
        (8, 32),
        (16, 16),
        (32, 8),
        (64, 4)
    ]
    
    results = []
    
    for m, n in shapes:
        ratio = n / m
        print(f"Simulating shape: {m}x{n}x{k_dim} (ratio = {ratio:.4f})...")
        stats = run_simulation(m, n, k_dim)
        if stats:
            results.append({
                "m": m,
                "n": n,
                "ratio": ratio,
                "stats": stats
            })
            
    # Cleanup config
    remove_config()
    
    # 3. Save raw data
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "cache_tiling_sweep_data.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    # 4. Generate Markdown report
    print(f"Generating Markdown report in {REPORT_PATH}...")
    with open(REPORT_PATH, "w") as f:
        f.write("# Cache-Constrained Mixed-Precision Tiling Sweep\n\n")
        f.write("This experiment sweeps tile shapes for a fixed tile area $T_M \\cdot T_N = 256$ elements on $256 \\times 256 \\times 256$ matrix multiplication.\n")
        f.write("The L2 cache size is set to **32 KB** to force capacity misses for the 128 KB Matrix B and 512 KB Matrices A/C.\n\n")
        
        f.write("## Comparative Results Table\n\n")
        f.write("| Tile Shape ($T_M \\times T_N$) | Ratio ($T_N / T_M$) | L1 Misses (LineFills) | L2 Misses (LineFills) | DRAM Traffic (KB) | Total Cycles |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for r in results:
            s = r["stats"]
            f.write(f"| {r['m']}x{r['n']} | {r['ratio']:.4f} | {s['l1_fills']:,} | {s['l2_fills']:,} | {s['dram_traffic']/1024:.1f} KB | {s['cycles']:,} |\n")
            
        f.write("\n## Observations\n\n")
        
        best_cycles = min(results, key=lambda x: x["stats"]["cycles"])
        best_dram = min(results, key=lambda x: x["stats"]["dram_traffic"])
        
        f.write(f"*   **Optimal Cycles**: `{best_cycles['m']}x{best_cycles['n']}` ({best_cycles['stats']['cycles']:,} cycles, ratio = {best_cycles['ratio']})\n")
        f.write(f"*   **Optimal DRAM Traffic**: `{best_dram['m']}x{best_dram['n']}` ({best_dram['stats']['dram_traffic']/1024:.1f} KB, ratio = {best_dram['ratio']})\n\n")
        
        # Verify the theory
        if best_cycles["m"] == 8 and best_cycles["n"] == 32:
            f.write("✅ **SUCCESS**: The optimal tile shape for execution cycles is the $8 \\times 32$ tile (ratio = 4.0), matching the theoretical mixed-precision optimum!\n")
        else:
            f.write(f"❌ **FAIL**: Cycle minimum is at `{best_cycles['m']}x{best_cycles['n']}`.\n")
            
    # 5. Generate Matplotlib Plot
    print(f"Plotting results in {PLOT_PATH}...")
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        ratios = [r["ratio"] for r in results]
        cycles = [r["stats"]["cycles"] for r in results]
        dram = [r["stats"]["dram_traffic"] / 1024 for r in results] # KB
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot Cycles
        ax1.plot(ratios, cycles, marker='o', color='blue', label='Execution Cycles')
        ax1.set_xscale('log', base=2)
        ax1.set_xticks(ratios)
        ax1.get_xaxis().set_major_formatter(plt.FormatStrFormatter('%.4g'))
        ax1.set_xlabel('Tile Shape Ratio (TN / TM) - Log Scale')
        ax1.set_ylabel('Execution Cycles')
        ax1.set_title('Execution Cycles vs Tile Shape Ratio')
        ax1.grid(True, which="both", ls="--")
        ax1.axvline(x=4.0, color='red', linestyle=':', label='Theoretical Optimum (Ratio=4)')
        ax1.legend()
        
        # Plot DRAM Traffic
        ax2.plot(ratios, dram, marker='o', color='green', label='DRAM Traffic (KB)')
        ax2.set_xscale('log', base=2)
        ax2.set_xticks(ratios)
        ax2.get_xaxis().set_major_formatter(plt.FormatStrFormatter('%.4g'))
        ax2.set_xlabel('Tile Shape Ratio (TN / TM) - Log Scale')
        ax2.set_ylabel('DRAM Traffic (KB)')
        ax2.set_title('DRAM Traffic vs Tile Shape Ratio')
        ax2.grid(True, which="both", ls="--")
        ax2.axvline(x=4.0, color='red', linestyle=':')
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(PLOT_PATH, dpi=150)
        print("Successfully generated performance plot.")
    except Exception as e:
        print(f"Error generating plot: {e}")
        
    print("=== Sweep Completed Successfully! ===")

if __name__ == "__main__":
    main()
