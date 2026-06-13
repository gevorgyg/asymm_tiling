import subprocess
import re
import os
import matplotlib.pyplot as plt

# Configuration Settings
EXECUTABLE = "./asymm"
TEMP_CONFIG = "sweep_200_temp.conf"

# Fixed matrix dimensions for the experiment
A_HEIGHT = 200
A_WIDTH = 200
B_WIDTH = 200

# Divisors of 200 that are multiples of 4 (required for PRNG line alignment)
tile_sizes = [4, 8, 20, 40, 100, 200]

def write_temporary_config(l1_size=8192, l1_line=8, l2_size=32768, l2_line=8):
    """Generates a config file for the 200x200 matrix sweeps."""
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

def run_simulation(tile, prng=False):
    """Runs a single simulation and parses hit rates and cycles."""
    cmd = [EXECUTABLE, "--config", TEMP_CONFIG]
    if prng:
        cmd.append("--Bgenerated")
    cmd.extend([str(tile), str(tile), str(tile)])
    
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
        print(f"[ERROR] Subprocess failed at tile size {tile} (PRNG={prng}): {e.stderr}")
        return 0.0, 0.0, 0

print("====================================================")
print("Starting 200x200 Asymmetric Tiling Sweep")
print("====================================================")

write_temporary_config()

normal_l1_hits = []
normal_l2_hits = []
normal_cycles = []

prng_l1_hits = []
prng_l2_hits = []
prng_cycles = []

for tile in tile_sizes:
    # Run Normal Mode
    n_l1, n_l2, n_cyc = run_simulation(tile, prng=False)
    normal_l1_hits.append(n_l1)
    normal_l2_hits.append(n_l2)
    normal_cycles.append(n_cyc)
    
    # Run PRNG Mode
    p_l1, p_l2, p_cyc = run_simulation(tile, prng=True)
    prng_l1_hits.append(p_l1)
    prng_l2_hits.append(p_l2)
    prng_cycles.append(p_cyc)
    
    print(f"Tile {tile:3d}x{tile:3d}x{tile:3d} | "
          f"Normal Cyc: {n_cyc:11d} (L1 Hit: {n_l1:.3f}) | "
          f"PRNG Cyc: {p_cyc:11d} (L1 Hit: {p_l1:.3f})")

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("\nGenerating performance plots for 200x200 matrix...")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7.5))

# Plot Cache Hit Rates (with slight offset for PRNG to see overlapping curves)
prng_l1_hits_offset = [h + 0.005 for h in prng_l1_hits]
prng_l2_hits_offset = [h + 0.005 for h in prng_l2_hits]

ax1.plot(tile_sizes, normal_l1_hits, marker='o', markersize=8, linestyle='-', color='#1f77b4', linewidth=3, label='Normal L1 (8 KB)')
ax1.plot(tile_sizes, normal_l2_hits, marker='s', markersize=8, linestyle='--', color='#ff7f0e', linewidth=3, label='Normal L2 (32 KB)')
ax1.plot(tile_sizes, prng_l1_hits_offset, marker='^', markersize=5, linestyle=':', color='#2ca02c', linewidth=1.5, label='PRNG L1 (8 KB, offset +0.005)')
ax1.plot(tile_sizes, prng_l2_hits_offset, marker='d', markersize=5, linestyle=':', color='#d62728', linewidth=1.5, label='PRNG L2 (32 KB, offset +0.005)')

ax1.set_title("Cache Hit Rates Comparison", fontsize=12, fontweight='bold', pad=10)
ax1.set_xlabel("Tile Block Size Parameters (M = N = K)", fontsize=11)
ax1.set_ylabel("Cache Hit Rate", fontsize=11)
ax1.grid(True, linestyle='--', alpha=0.5)
ax1.set_ylim(-0.05, 1.05)
ax1.set_xscale('log')
ax1.set_xticks(tile_sizes)
ax1.get_xaxis().set_major_formatter(plt.ScalarFormatter())
ax1.legend(fontsize=10, loc="best")

# Plot Execution Cycles (convert to Millions for readability)
normal_cycles_m = [c / 1e6 for c in normal_cycles]
prng_cycles_m = [c / 1e6 for c in prng_cycles]

ax2.plot(tile_sizes, normal_cycles_m, marker='o', linestyle='-', color='#1f77b4', linewidth=2.5, label='Normal MM (Read Matrix B)')
ax2.plot(tile_sizes, prng_cycles_m, marker='x', linestyle='-', color='#d62728', linewidth=2.5, label='PRNG MM (On-the-Fly Gen)')

ax2.set_title("Simulated Performance (Clock Cycles)", fontsize=12, fontweight='bold', pad=10)
ax2.set_xlabel("Tile Block Size Parameters (M = N = K)", fontsize=11)
ax2.set_ylabel("Execution Cycles (Millions)", fontsize=11)
ax2.grid(True, linestyle='--', alpha=0.5)
ax2.set_xscale('log')
ax2.set_xticks(tile_sizes)
ax2.get_xaxis().set_major_formatter(plt.ScalarFormatter())
ax2.legend(fontsize=10, loc="best")

plt.suptitle("200x200 Matrix Tiling Sweep (PRNG vs Normal Memory)\n(Caches: 8KB L1 [4 cy], 32KB L2 [15 cy] | Memory: 180 cy | PRNG: 2 cy + 64 cy/line)", fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.95])

os.makedirs("plots", exist_ok=True)
output_filename = "plots/asymmetric_200x200_sweep.png"
plt.savefig(output_filename, dpi=300, bbox_inches='tight')
print(f"Success! Performance chart generated: '{output_filename}'")
