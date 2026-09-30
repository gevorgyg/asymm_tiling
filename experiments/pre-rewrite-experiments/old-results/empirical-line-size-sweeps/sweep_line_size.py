#!/usr/bin/env python3
import os
import subprocess
import json
import re

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../.."))
CONFIG_PATH = os.path.join(WORKSPACE_DIR, "tests", "configs", "sweep_line_size_temp.conf")
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
L1_LINE_SIZE_BYTES={line_size}
L1_ASSOC=8
L1_ACCESS_CYCLES=4
L1_REPLACEMENT_POLICY=LRU
L1_WRITE_POLICY=WRITE_BACK

# L2 Cache Parameters
L2_SIZE_BYTES=65536
L2_LINE_SIZE_BYTES={line_size}
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

def write_config(a_prec, b_prec, line_size):
    with open(CONFIG_PATH, "w") as f:
        f.write(CONFIG_TEMPLATE.format(a_prec=a_prec, b_prec=b_prec, line_size=line_size))

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
    print("=== Running Cache Line Size Empirical Tiling Sweeps ===")
    
    # Compile
    subprocess.run(["make"], cwd=WORKSPACE_DIR, check=True)
    
    # Dimensions to sweep
    dims = [8, 12, 16, 24, 32, 48, 96]
    
    # Line sizes to sweep
    line_sizes = [16, 32, 64, 128]
    
    # 3 Precision Configurations
    precisions = [
        {"name": "Symmetric Double", "a_prec": 8, "b_prec": 8},
        {"name": "Asymmetric", "a_prec": 8, "b_prec": 2},
        {"name": "Symmetric Single", "a_prec": 4, "b_prec": 4}
    ]
    
    all_results = {}
    
    for ls in line_sizes:
        print(f"\n==========================================")
        print(f"Sweeping Line Size: {ls} Bytes")
        print(f"==========================================")
        ls_key = f"{ls}B"
        all_results[ls_key] = {}
        
        for prec in precisions:
            name = prec["name"]
            print(f"\nSweeping {name} (A={prec['a_prec']}B, B={prec['b_prec']}B) with Line Size = {ls}B...")
            write_config(prec["a_prec"], prec["b_prec"], ls)
            
            results = []
            for m in dims:
                for n in dims:
                    for k in dims:
                        stats = run_simulation(m, n, k)
                        if stats:
                            # calculate dram traffic based on current line size
                            stats["dram_traffic"] = (stats["l2_fills"] + stats["l2_evicts"]) * ls
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
            all_results[ls_key][name] = results
            print(f"Done! Best: {results[0]['m']}x{results[0]['n']}x{results[0]['k']} with {results[0]['stats']['cycles']:,} cycles.")

    # Cleanup config
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)
        
    # Save raw data
    with open(os.path.join(DATA_DIR, "results_line_size.json"), "w") as f:
        json.dump(all_results, f, indent=2)
        
    # Generate report
    generate_report(all_results)
    
    # Generate plots
    generate_plots(all_results)

def generate_report(all_results):
    print(f"Writing report to {REPORT_PATH}...")
    with open(REPORT_PATH, "w") as f:
        f.write("# Empirical Cache Line Size Tiling Sweeps\n\n")
        f.write("This directory contains the results of empirical tile sweeps for a **$96 \\times 96 \\times 96$ matrix** under **16 KB L1** and **64 KB L2** caches, sweeping cache line sizes $L \\in \\{16, 32, 64, 128\\}$ bytes and tile dimensions $T_M, T_N, T_K \\in \\{8, 12, 16, 24, 32, 48\\}$.\n\n")
        
        f.write("> [!NOTE]\n")
        f.write("> **Hardware Parameters:**\n")
        f.write("> * **Matrix Size:** $96 \\times 96 \\times 96$.\n")
        f.write("> * **L1 Cache:** 16 KB capacity, 8-way associativity, 4-cycle access, LRU replacement, Write-Back policy.\n")
        f.write("> * **L2 Cache:** 64 KB capacity, 8-way associativity, 14-cycle access, LRU replacement, Write-Back policy.\n")
        f.write("> * **DRAM Latency:** 180 cycles.\n")
        f.write("> * **Register Tile:** $4 \\times 4 \\times 4$ ($R_M \\times R_N \\times R_K$), 8-cycle compute (`tmulac`).\n\n")
        
        f.write("## 1. Summary of Optimal Tile Shapes by Cache Line Size\n\n")
        f.write("| Cache Line Size | Precision Config | Optimal Tile Shape ($T_M \\times T_N \\times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |\n")
        f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        
        for ls_key in sorted(all_results.keys(), key=lambda x: int(x[:-1])):
            for name in ["Symmetric Double", "Asymmetric", "Symmetric Single"]:
                best = all_results[ls_key][name][0]
                s = best["stats"]
                f.write(f"| {ls_key} | {name} | {best['m']}x{best['n']}x{best['k']} | {best['ratio']:.3f} | {best['footprint_kb']:.1f} KB | {s['l1_hit_rate']:.3f} | {s['l2_hit_rate']:.3f} | {s['dram_traffic']/1024:.1f} KB | {s['cycles']:,} |\n")
                
        f.write("\n---\n\n")
        
        for ls_key in sorted(all_results.keys(), key=lambda x: int(x[:-1])):
            f.write(f"## 2. Details for Line Size = {ls_key}\n\n")
            
            for name in ["Symmetric Double", "Asymmetric", "Symmetric Single"]:
                results = all_results[ls_key][name]
                f.write(f"### {name} ({ls_key})\n\n")
                f.write("#### Top 3 Optimal Tile Shapes\n\n")
                f.write("| Rank | Tile Shape ($T_M \\times T_N \\times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |\n")
                f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
                for rank, r in enumerate(results[:3], 1):
                    s = r["stats"]
                    f.write(f"| {rank} | {r['m']}x{r['n']}x{r['k']} | {r['ratio']:.3f} | {r['footprint_kb']:.1f} KB | {s['l1_hit_rate']:.3f} | {s['l2_hit_rate']:.3f} | {s['dram_traffic']/1024:.1f} KB | {s['cycles']:,} |\n")
                
                f.write("\n#### Bottom 3 Worst Tile Shapes\n\n")
                f.write("| Rank | Tile Shape ($T_M \\times T_N \\times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |\n")
                f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
                for rank, r in enumerate(results[-3:], len(results)-2):
                    s = r["stats"]
                    f.write(f"| {rank} | {r['m']}x{r['n']}x{r['k']} | {r['ratio']:.3f} | {r['footprint_kb']:.1f} KB | {s['l1_hit_rate']:.3f} | {s['l2_hit_rate']:.3f} | {s['dram_traffic']/1024:.1f} KB | {s['cycles']:,} |\n")
                f.write("\n")
            f.write("---\n\n")
            
        f.write("## 3. Aspect Ratio Sensitivity vs. Cache Line Size\n")
        f.write("The plot below details how the cache line size affects both execution cycles and the shape aspect ratio trend.\n\n")
        f.write("![Line Size Aspect Ratio Sweeps](line_size_empirical.png)\n")

def generate_plots(all_results):
    print("Generating Matplotlib plots...")
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        line_keys = sorted(all_results.keys(), key=lambda x: int(x[:-1]))
        
        fig, axs = plt.subplots(2, 2, figsize=(14, 10), dpi=150)
        axs = axs.ravel()
        
        colors = {
            "Symmetric Double": "#636EFA",
            "Asymmetric": "#EF553B",
            "Symmetric Single": "#00CC96"
        }
        
        for i, ls_key in enumerate(line_keys):
            ax = axs[i]
            ax.grid(True, which="both", ls="--", color="#E5E5E5", zorder=0)
            
            ls_results = all_results[ls_key]
            
            for name in ["Symmetric Double", "Asymmetric", "Symmetric Single"]:
                results = ls_results[name]
                ratios = [r["ratio"] for r in results]
                cycles = [r["stats"]["cycles"] for r in results]
                
                # Scatter points
                ax.scatter(ratios, cycles, color=colors[name], alpha=0.3, s=12, zorder=3)
                
                # Minimum cycles per ratio line
                unique_ratios = sorted(list(set(ratios)))
                min_cycles_per_ratio = []
                for ur in unique_ratios:
                    min_cycles_per_ratio.append(min([r["stats"]["cycles"] for r in results if r["ratio"] == ur]))
                    
                ax.plot(unique_ratios, min_cycles_per_ratio, color=colors[name], linewidth=2.0, marker="o", markersize=4, label=name, zorder=4)
                
                # Annotate absolute minimum
                best = results[0]
                ax.annotate(f"{best['m']}x{best['n']}x{best['k']}", 
                            (best['ratio'], best['stats']['cycles']),
                            textcoords="offset points", 
                            xytext=(0, 10 if "Double" in name else (-12 if "Single" in name else 10)),
                            ha='center', fontsize=7, fontweight='bold',
                            bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.6))
                
            ax.set_xscale('log', base=2)
            ax.set_title(f"Cache Line Size = {ls_key}", fontsize=11, fontweight='bold')
            ax.set_xlabel('Tile Aspect Ratio ($T_N / T_M$)', fontsize=9)
            ax.set_ylabel('Execution Latency (Cycles)', fontsize=9)
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
            if i == 0:
                ax.legend(frameon=True, facecolor="white", edgecolor="none", fontsize=8)
                
        plt.suptitle('Tiling Performance vs. Cache Line Size & Aspect Ratio (96x96x96 Matrix)', fontsize=14, fontweight='bold', y=0.98)
        plt.tight_layout()
        
        plot_path = os.path.join(DATA_DIR, "line_size_empirical.png")
        plt.savefig(plot_path, bbox_inches='tight')
        plt.close()
        
        # Copy to artifact
        subprocess.run(["cp", plot_path, os.path.join(ARTIFACT_DIR, "line_size_empirical.png")], check=True)
        print("Plot successfully saved and copied to artifact!")
    except Exception as e:
        print("Error generating plots:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
