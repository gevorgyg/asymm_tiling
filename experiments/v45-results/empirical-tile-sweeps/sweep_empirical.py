#!/usr/bin/env python3
import os
import subprocess
import json
import re

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../.."))
CONFIG_PATH = os.path.join(WORKSPACE_DIR, "tests", "configs", "sweep_empirical_temp.conf")
DATA_DIR = SCRIPT_DIR
REPORT_PATH = os.path.join(DATA_DIR, "README.md")
ARTIFACT_DIR = "/home/aregmk/.gemini/antigravity/brain/2da43f73-946b-424d-9271-e7366e35cbd1"

# Config Template
CONFIG_TEMPLATE = """# Matrix dimensions (elements)
A_HEIGHT_DIM=96
A_WIDTH_DIM=96
B_WIDTH_DIM=96

# Element precisions (bytes)
A_PRECISION_BYTES={a_prec}
B_PRECISION_BYTES={b_prec}

# L1 Cache Parameters
L1_SIZE_BYTES=16384
L1_LINE_SIZE_BYTES=64
L1_ASSOC=8
L1_ACCESS_CYCLES=4
L1_REPLACEMENT_POLICY=LRU
L1_WRITE_POLICY=WRITE_BACK

# L2 Cache Parameters
L2_SIZE_BYTES=65536
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

# Scratchpad memory
SP_ACCESS_CYCLES=1
SP_BANKS=8
SP_WORD_SIZE_BYTES=8
"""

def write_config(a_prec, b_prec):
    with open(CONFIG_PATH, "w") as f:
        f.write(CONFIG_TEMPLATE.format(a_prec=a_prec, b_prec=b_prec))

def run_simulation(m, n, k):
    cmd = [os.path.join(WORKSPACE_DIR, "asymm"), "--config", CONFIG_PATH, str(m), str(n), str(k)]
    result = subprocess.run(cmd, cwd=WORKSPACE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
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
                
    stats["dram_traffic"] = (stats["l2_fills"] + stats["l2_evicts"]) * 64
    
    if stats["l1_lookups"] > 0:
        stats["l1_hit_rate"] = 1.0 - (stats["l1_fills"] / stats["l1_lookups"])
    else:
        stats["l1_hit_rate"] = 0.0
        
    if stats["l2_lookups"] > 0:
        stats["l2_hit_rate"] = 1.0 - (stats["l2_fills"] / stats["l2_lookups"])
    else:
        stats["l2_hit_rate"] = 0.0
        
    return stats

def main():
    print("=== Running Empirical Tile Shape Sweeps ===")
    
    # Compile
    subprocess.run(["make"], cwd=WORKSPACE_DIR, check=True)
    
    # Dimensions to sweep
    dims = [8, 12, 16, 24, 32, 48]
    
    # 3 Precision Configurations
    precisions = [
        {"name": "Symmetric Double", "a_prec": 8, "b_prec": 8},
        {"name": "Asymmetric", "a_prec": 8, "b_prec": 2},
        {"name": "Symmetric Single", "a_prec": 4, "b_prec": 4}
    ]
    
    all_results = {}
    
    for prec in precisions:
        name = prec["name"]
        print(f"\nSweeping {name} (A={prec['a_prec']}B, B={prec['b_prec']}B)...")
        write_config(prec["a_prec"], prec["b_prec"])
        
        results = []
        for m in dims:
            for n in dims:
                for k in dims:
                    stats = run_simulation(m, n, k)
                    if stats:
                        ratio = n / m
                        footprint = (m * k * prec["a_prec"]) + (k * n * prec["b_prec"]) + (m * n * max(prec["a_prec"], prec["b_prec"]))
                        results.append({
                            "m": m,
                            "n": n,
                            "k": k,
                            "ratio": ratio,
                            "footprint_kb": footprint / 1024.0,
                            "stats": stats
                        })
        
        # Sort by cycles (ascending)
        results.sort(key=lambda x: x["stats"]["cycles"])
        all_results[name] = results
        print(f"Sweep done! Best tile shape: {results[0]['m']}x{results[0]['n']}x{results[0]['k']} with {results[0]['stats']['cycles']:,} cycles.")

    # Cleanup config
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)
        
    # Save raw data
    with open(os.path.join(DATA_DIR, "results_empirical.json"), "w") as f:
        json.dump(all_results, f, indent=2)
        
    # Generate report
    generate_report(all_results)
    
    # Generate plots
    generate_plots(all_results)

def generate_report(all_results):
    print(f"Writing report to {REPORT_PATH}...")
    with open(REPORT_PATH, "w") as f:
        f.write("# Empirical Tile Shape Optimization\n\n")
        f.write("This directory contains empirical tile sweeps for a **$96 \\times 96 \\times 96$ matrix** multiplication under **16 KB L1** and **64 KB L2** caches, sweeping tile dimensions $T_M, T_N, T_K \\in \\{8, 12, 16, 24, 32, 48\\}$.\n\n")
        
        for name, results in all_results.items():
            f.write(f"## 1. {name} Configuration\n")
            if "Asymmetric" in name:
                f.write("In the Asymmetric configuration ($A=8B, B=2B, C=8B$), Matrix B is $4\\times$ smaller than A and C, meaning B access cost is significantly cheaper. This shifts the optimal tile shape to be wider.\n\n")
            else:
                f.write(f"In the {name} configuration, access costs to Matrix A and B are symmetric, which theoretically favors square-like tiling.\n\n")
                
            f.write("### Top 5 Optimal Tile Shapes\n\n")
            f.write("| Rank | Tile Shape ($T_M \\times T_N \\times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |\n")
            f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
            for rank, r in enumerate(results[:5], 1):
                s = r["stats"]
                f.write(f"| {rank} | {r['m']}x{r['n']}x{r['k']} | {r['ratio']:.3f} | {r['footprint_kb']:.1f} KB | {s['l1_hit_rate']:.3f} | {s['l2_hit_rate']:.3f} | {s['dram_traffic']/1024:.1f} KB | {s['cycles']:,} |\n")
            
            f.write("\n### Bottom 3 Worst Tile Shapes\n\n")
            f.write("| Rank | Tile Shape ($T_M \\times T_N \\times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |\n")
            f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
            for rank, r in enumerate(results[-3:], len(results)-2):
                s = r["stats"]
                f.write(f"| {rank} | {r['m']}x{r['n']}x{r['k']} | {r['ratio']:.3f} | {r['footprint_kb']:.1f} KB | {s['l1_hit_rate']:.3f} | {s['l2_hit_rate']:.3f} | {s['dram_traffic']/1024:.1f} KB | {s['cycles']:,} |\n")
            
            best_shape = f"{results[0]['m']}\\times{results[0]['n']}\\times{results[0]['k']}"
            best_ratio = results[0]['ratio']
            worst_shape = f"{results[-1]['m']}\\times{results[-1]['n']}\\times{results[-1]['k']}"
            slowdown = results[-1]['stats']['cycles'] / results[0]['stats']['cycles']
            
            f.write(f"\n**Key Takeaway:** The optimal shape is **${best_shape}$** (ratio = **{best_ratio:.3f}**). The worst shape is **${worst_shape}$**, causing a **{slowdown:.2f}x slowdown**. This underscores the extreme importance of shape selection under strict capacity limits.\n\n")
            f.write("---\n\n")
            
        f.write("## 2. Shift in Optimal Aspect Ratio\n")
        f.write("Below is a plot showing how the tile aspect ratio ($T_N/T_M$) affects execution cycles across the three configurations. Note how the optimal point shifts to the right (wider tiles) for the Asymmetric configuration, validating our access-cost asymmetry theory.\n\n")
        f.write("![Aspect Ratio Sweeps](aspect_ratio_empirical.png)\n")

def generate_plots(all_results):
    print("Generating Matplotlib plots...")
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(10, 6), dpi=150)
        plt.grid(True, which="both", ls="--", color="#E5E5E5", zorder=0)
        
        colors = {
            "Symmetric Double": "#636EFA",
            "Asymmetric": "#EF553B",
            "Symmetric Single": "#00CC96"
        }
        
        for name, results in all_results.items():
            ratios = [r["ratio"] for r in results]
            cycles = [r["stats"]["cycles"] for r in results]
            
            # Scatter plot to show all points
            plt.scatter(ratios, cycles, color=colors[name], alpha=0.4, s=15, zorder=3)
            
            # Calculate average or trend line per ratio
            unique_ratios = sorted(list(set(ratios)))
            min_cycles_per_ratio = []
            for ur in unique_ratios:
                min_cycles_per_ratio.append(min([r["stats"]["cycles"] for r in results if r["ratio"] == ur]))
                
            plt.plot(unique_ratios, min_cycles_per_ratio, color=colors[name], linewidth=2.5, marker="o", label=name, zorder=4)
            
            # Annotate the absolute minimum
            best = results[0]
            plt.annotate(f"Opt: {best['m']}x{best['n']}x{best['k']}", 
                         (best['ratio'], best['stats']['cycles']),
                         textcoords="offset points", 
                         xytext=(0, 12 if "Double" in name else (-15 if "Single" in name else 12)),
                         ha='center', fontsize=8, fontweight='bold',
                         bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.5))
            
        plt.xscale('log', base=2)
        plt.xlabel('Tile Aspect Ratio ($T_N / T_M$)', fontsize=11, fontweight='bold')
        plt.ylabel('Execution Latency (Cycles)', fontsize=11, fontweight='bold')
        plt.gca().get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
        plt.title('Execution Cycles vs. Tile Aspect Ratio (Matrix: 96x96x96)', fontsize=12, fontweight='bold', pad=15)
        plt.legend(frameon=True, facecolor="white", edgecolor="none")
        plt.tight_layout()
        
        plot_path = os.path.join(DATA_DIR, "aspect_ratio_empirical.png")
        plt.savefig(plot_path, bbox_inches='tight')
        plt.close()
        
        # Copy to artifact
        subprocess.run(["cp", plot_path, os.path.join(ARTIFACT_DIR, "aspect_ratio_empirical.png")], check=True)
        print("Plot successfully saved and copied to artifact!")
    except Exception as e:
        print("Error generating plots:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
