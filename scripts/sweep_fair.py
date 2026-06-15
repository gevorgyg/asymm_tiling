import subprocess
import re
import os
import matplotlib.pyplot as plt
import numpy as np

EXECUTABLE = "./asymm"
TEMP_CONFIG = "sweep_fair_temp.conf"

A_HEIGHT = 500
A_WIDTH = 500
B_WIDTH = 500
K_TILE = 20

def write_temporary_config(l1_size=8192, l1_line=8, l2_size=32768, l2_line=8):
    """Generates the config file for the 500x500 matrix sweeps."""
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={A_HEIGHT}\n")
        f.write(f"A_WIDTH_DIM={A_WIDTH}\n")
        f.write("A_PRECISION_BYTES=8\n") 
        f.write(f"B_WIDTH_DIM={B_WIDTH}\n")
        f.write("B_PRECISION_BYTES=2\n") 
        
        # L1 Cache Configuration (8 KB)
        f.write(f"L1_SIZE_BYTES={l1_size}\n")
        f.write(f"L1_LINE_SIZE_BYTES={l1_line}\n")
        f.write("L1_ASSOC=4\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        
        # L2 Cache Configuration (32 KB)
        f.write(f"L2_SIZE_BYTES={l2_size}\n")
        f.write(f"L2_LINE_SIZE_BYTES={l2_line}\n")
        f.write("L2_ASSOC=8\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        
        f.write("L1_REPLACEMENT_POLICY=FIFO\n")
        f.write("L2_REPLACEMENT_POLICY=FIFO\n")
        f.write("L1_WRITE_POLICY=WRITE_THROUGH\n")
        f.write("L2_WRITE_POLICY=WRITE_THROUGH\n")
        
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\n")
        f.write("PRNG_GEN_COST_PER_LINE=64\n")

def run_simulation(m, n, k, prng=False):
    """Runs a single simulation and parses hit rates and cycles."""
    cmd = [EXECUTABLE, "--config", TEMP_CONFIG]
    if prng:
        cmd.append("--Bgenerated")
    cmd.extend([str(m), str(n), str(k)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = result.stdout
        
        l1_match = re.search(r"--- L1 ---\s+Hit rate:\s+([\d.]+)", stdout)
        l2_match = re.search(r"--- L2 ---\s+Hit rate:\s+([\d.]+)", stdout)
        cycles_match = re.search(r"Cycles:\s+(\d+)", stdout)
        
        l1_val = float(l1_match.group(1)) if l1_match else 0.0
        l2_val = float(l2_match.group(1)) if l2_match else 0.0
        cycles_val = int(cycles_match.group(1)) if cycles_match else 0
        
        return l1_val, l2_val, cycles_val
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Subprocess failed at shape {m}x{n}x{k} (PRNG={prng}): {e.stderr}")
        return 0.0, 0.0, 0

print("====================================================")
print("Starting Fair Tiling Shape Comparison (Capped Area)")
print("====================================================")

write_temporary_config()

# Define size classes: Area = m * n
# Format: size_class_name -> list of (m, n) tuples
size_classes = {
    "Area = 400 Elements": [(100, 4), (20, 20), (4, 100)],
    "Area = 2,000 Elements": [(100, 20), (20, 100), (4, 500)],
    "Area = 10,000 Elements": [(500, 20), (100, 100), (20, 500)]
}


results = {}

for class_name, shapes in size_classes.items():
    print(f"\n--- {class_name} ---")
    results[class_name] = []
    
    for m, n in shapes:
        # Normal
        n_l1, n_l2, n_cyc = run_simulation(m, n, K_TILE, prng=False)
        # PRNG
        p_l1, p_l2, p_cyc = run_simulation(m, n, K_TILE, prng=True)
        
        results[class_name].append({
            "shape": f"{m}x{n}",
            "normal_cycles": n_cyc,
            "prng_cycles": p_cyc,
            "normal_l1": n_l1,
            "prng_l1": p_l1
        })
        
        print(f"Shape {m}x{n} | Normal: {n_cyc/1e6:7.1f}M cyc (L1: {n_l1:.3f}) | PRNG: {p_cyc/1e6:7.1f}M cyc (L1: {p_l1:.3f})")

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("\nGenerating bar charts for fair comparison...")

# Set up the figure with 3 subplots (one for each size class)
fig, axs = plt.subplots(1, 3, figsize=(18, 6.5))

for idx, (class_name, class_results) in enumerate(results.items()):
    shapes = [r["shape"] for r in class_results]
    normal_cycles = [r["normal_cycles"] / 1e6 for r in class_results]
    prng_cycles = [r["prng_cycles"] / 1e6 for r in class_results]
    
    x = np.arange(len(shapes))
    width = 0.35
    
    rects1 = axs[idx].bar(x - width/2, normal_cycles, width, label='Normal Mode', color='#1f77b4')
    rects2 = axs[idx].bar(x + width/2, prng_cycles, width, label='PRNG Mode', color='#d62728')
    
    axs[idx].set_title(class_name, fontsize=12, fontweight='bold', pad=10)
    axs[idx].set_ylabel('Execution Cycles (Millions)', fontsize=11)
    axs[idx].set_xlabel('Tile Shape (M x N)', fontsize=11)
    axs[idx].set_xticks(x)
    axs[idx].set_xticklabels(shapes, fontsize=10)
    axs[idx].grid(True, linestyle='--', alpha=0.5, axis='y')
    axs[idx].legend(fontsize=9)

plt.suptitle("Fair Shape Comparison: Square vs. Rectangular Tiles (Capped Output Area)\n(Matrix A: 500x500 [8B] | Matrix B: 500x500 [2B] | Caches: 8KB L1, 32KB L2 | Reduction Depth k=20)", fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.93])

os.makedirs("plots", exist_ok=True)
output_filename = "plots/asymmetric_fair_comparison.png"
plt.savefig(output_filename, dpi=300, bbox_inches='tight')
print(f"Success! Fair comparison chart generated: '{output_filename}'")
