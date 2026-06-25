#!/usr/bin/env python3
import os
import subprocess
import json

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../.."))
CONFIG_PATH = os.path.join(WORKSPACE_DIR, "tests", "configs", "sweep_l2_temp.conf")
DATA_DIR = SCRIPT_DIR
PLOT_PATH = os.path.join(DATA_DIR, "l2_size_shift.png")
ARTIFACT_DIR = "/home/aregmk/.gemini/antigravity/brain/2da43f73-946b-424d-9271-e7366e35cbd1"

# Config template
CONFIG_TEMPLATE = """# Matrix dimensions (elements)
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

# L2 Cache Parameters
L2_SIZE_BYTES={l2_size}
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

def write_config(l2_size):
    with open(CONFIG_PATH, "w") as f:
        f.write(CONFIG_TEMPLATE.format(l2_size=l2_size))

def run_simulation(m, n, k):
    cmd = [os.path.join(WORKSPACE_DIR, "asymm"), "--config", CONFIG_PATH, str(m), str(n), str(k)]
    result = subprocess.run(cmd, cwd=WORKSPACE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"Error running simulation for tile {m}x{n}x{k}:")
        return None
    
    cycles = 0
    for line in result.stdout.splitlines():
        if "Cycles:" in line:
            cycles = int(line.split()[-1])
    return cycles

def main():
    print("=== L2 Cache Size Shift Sweep ===")
    
    # Compile
    subprocess.run(["make"], cwd=WORKSPACE_DIR, check=True)
    
    l2_sizes = [32768, 65536, 131072, 262144, 524288] # 32 KB, 64 KB, 128 KB, 256 KB, 512 KB
    shapes = [
        (4, 64),
        (8, 32),
        (16, 16),
        (32, 8),
        (64, 4)
    ]
    
    results = {}
    
    for l2 in l2_sizes:
        l2_kb = l2 // 1024
        print(f"Sweeping shapes for L2 Cache = {l2_kb} KB...")
        write_config(l2)
        
        results[l2_kb] = []
        for tm, tn in shapes:
            ratio = tn / tm
            cycles = run_simulation(tm, tn, 16)
            results[l2_kb].append({
                "tm": tm,
                "tn": tn,
                "ratio": ratio,
                "cycles": cycles
            })
            
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)
        
    # Save raw data
    with open(os.path.join(DATA_DIR, "l2_shift_data.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    # Plot results
    print("Generating plot...")
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(10, 6), dpi=150)
        plt.grid(True, which="both", ls="--", color="#E5E5E5", zorder=0)
        
        # Color palette for curves (gradient from dark blue to purple/teal)
        colors = {
            32: "#EF553B",  # Orange-red (hot/constrained)
            64: "#AB63FA",  # Purple
            128: "#636EFA", # Blue
            256: "#19D3F3", # Cyan
            512: "#00CC96"  # Emerald green (cold/fully-cached)
        }
        
        for l2_kb, data in results.items():
            ratios = [d["ratio"] for d in data]
            cycles = [d["cycles"] for d in data]
            plt.plot(ratios, cycles, color=colors[l2_kb], marker='o', linewidth=2.5, 
                     label=f"L2 = {l2_kb} KB", zorder=3)
            
        plt.xscale('log')
        plt.xlabel('Tile Shape Ratio ($T_N / T_M$)', fontsize=12, fontweight='bold')
        plt.ylabel('Execution Latency (Cycles)', fontsize=12, fontweight='bold')
        
        # Custom ticks
        ratios = [d["ratio"] for d in results[32]]
        plt.xticks(ratios)
        plt.gca().get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        
        # Annotate tile shapes at the bottom
        labels = [f"{d['tm']}x{d['tn']}" for d in results[32]]
        for i, ratio in enumerate(ratios):
            plt.text(ratio, plt.ylim()[0] * 1.02, labels[i], ha='center', fontsize=8, fontweight='semibold')
            
        # Draw theoretical indicators
        plt.axvline(x=4.0, color="#EF553B", linestyle=":", linewidth=1.5, alpha=0.7)
        plt.axvline(x=1.0, color="#00CC96", linestyle=":", linewidth=1.5, alpha=0.7)
        
        plt.text(4.0, plt.ylim()[1] * 0.9, "Asymmetric Opt (4.0)", color="#EF553B", ha='center', fontsize=9, fontweight='semibold', rotation=90)
        plt.text(1.0, plt.ylim()[1] * 0.9, "Symmetric Opt (1.0)", color="#00CC96", ha='center', fontsize=9, fontweight='semibold', rotation=90)

        plt.title('Optimal Tile Aspect Ratio Shift vs. L2 Cache Capacity', fontsize=14, fontweight='bold', pad=20)
        plt.legend(loc='upper right', frameon=True, facecolor='#F8F9FA')
        plt.tight_layout()
        
        plt.savefig(PLOT_PATH, bbox_inches='tight')
        print(f"Plot saved in {PLOT_PATH}")
        
        # Copy to artifact folder
        artifact_plot_path = os.path.join(ARTIFACT_DIR, "l2_size_shift.png")
        subprocess.run(["cp", PLOT_PATH, artifact_plot_path], check=True)
        print(f"Plot copied to artifact path: {artifact_plot_path}")
        
    except Exception as e:
        print("Error plotting:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
