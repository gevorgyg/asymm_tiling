import subprocess
import re
import os
import matplotlib.pyplot as plt

# Configuration Settings
EXECUTABLE = "./asymm"  
TEMP_CONFIG = "size_sweep_temp.conf"

# Matrix sizes and tile sizes to sweep
matrix_sizes = [64, 128, 256]
tile_sizes = [4, 8, 16, 32, 64]

def write_temporary_config(mat_dim, l1_size=512, l1_line=8, l2_size=2048, l2_line=8):
    """Generates a transient configuration file for the current matrix dimensions."""
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={mat_dim}\n")
        f.write(f"A_WIDTH_DIM={mat_dim}\n")
        f.write("A_PRECISION_BYTES=8\n") 
        f.write(f"B_WIDTH_DIM={mat_dim}\n")
        f.write("B_PRECISION_BYTES=2\n") 
        
        # L1 Cache Configuration
        f.write(f"L1_SIZE_BYTES={l1_size}\n")
        f.write(f"L1_LINE_SIZE_BYTES={l1_line}\n")
        f.write("L1_ASSOC=4\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        
        # L2 Cache Configuration
        f.write(f"L2_SIZE_BYTES={l2_size}\n")
        f.write(f"L2_LINE_SIZE_BYTES={l2_line}\n")
        f.write("L2_ASSOC=8\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        
        f.write("L1_REPLACEMENT_POLICY=FIFO\n")
        f.write("L2_REPLACEMENT_POLICY=FIFO\n")
        
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\n")
        f.write("PRNG_GEN_COST_PER_LINE=64\n")

def run_simulation(tile):
    """Runs a single simulation and parses L1 hit rate and CPU cycles."""
    cmd = [EXECUTABLE, "--config", TEMP_CONFIG, "--Bgenerated", str(tile), str(tile), str(tile)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = result.stdout
        
        # Parse L1 hit rate and cycles
        l1_match = re.search(r"--- L1 ---\s+Hit rate:\s+([\d.]+)", stdout)
        cycles_match = re.search(r"Cycles:\s+(\d+)", stdout)
        
        l1_val = float(l1_match.group(1)) if l1_match else 0.0
        cycles_val = int(cycles_match.group(1)) if cycles_match else 0
        
        return l1_val, cycles_val
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Subprocess failed at tile size {tile}: {e.stderr}")
        return 0.0, 0

print("====================================================")
print("Starting Asymmetric Tiling Matrix Size Sweep (PRNG)")
print("====================================================")

# Dictionary to hold results: matrix_size -> { 'l1_hits': [], 'cycles': [] }
results = {}

for size in matrix_sizes:
    print(f"\n--- Sweeping Matrix Size: {size}x{size} ---")
    write_temporary_config(size)
    
    results[size] = {'l1_hits': [], 'cycles': []}
    
    for tile in tile_sizes:
        l1_hit, cycles = run_simulation(tile)
        results[size]['l1_hits'].append(l1_hit)
        results[size]['cycles'].append(cycles)
        print(f"  Tile {tile:2d}x{tile:2d}x{tile:2d} -> L1 Hit: {l1_hit:.3f} | Cycles: {cycles:11d}")

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("\nGenerating matrix size comparison plots...")

# Create side-by-side plots
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7.5))

colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
markers = ["o", "s", "^"]

# Plot 1: L1 Cache Hit Rates
for idx, size in enumerate(matrix_sizes):
    ax1.plot(tile_sizes, results[size]['l1_hits'], marker=markers[idx], linestyle='-', 
             color=colors[idx], linewidth=2, label=f'{size}x{size} Matrix')

ax1.set_title("L1 Cache Hit Rates across Matrix Sizes", fontsize=12, fontweight='bold', pad=10)
ax1.set_xlabel("Tile Block Size Parameters (M = N = K)", fontsize=11)
ax1.set_ylabel("L1 Cache Hit Rate", fontsize=11)
ax1.grid(True, linestyle='--', alpha=0.5)
ax1.set_ylim(-0.05, 1.05)
ax1.legend(fontsize=10, loc="best")

# Plot 2: Simulated Clock Cycles
for idx, size in enumerate(matrix_sizes):
    cycles_m = [c / 1e6 for c in results[size]['cycles']]
    ax2.plot(tile_sizes, cycles_m, marker=markers[idx], linestyle='-', 
             color=colors[idx], linewidth=2.5, label=f'{size}x{size} Matrix')

ax2.set_title("Simulated Clock Cycles", fontsize=12, fontweight='bold', pad=10)
ax2.set_xlabel("Tile Block Size Parameters (M = N = K)", fontsize=11)
ax2.set_ylabel("Execution Cycles (Log Scale)", fontsize=11)
ax2.set_yscale('log')
ax2.grid(True, linestyle='--', alpha=0.5)
ax2.legend(fontsize=10, loc="best")

plt.suptitle("Matrix Size Tiling Sweep comparison (PRNG Mode)\n(Caches: 512B L1 [4 cy], 2KB L2 [15 cy] | Memory: 180 cy)", fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.95])

os.makedirs("plots", exist_ok=True)
output_filename = "plots/asymmetric_prng_matrix_size_sweep.png"
plt.savefig(output_filename, dpi=300, bbox_inches='tight')
print(f"Success! Performance chart generated: '{output_filename}'")
