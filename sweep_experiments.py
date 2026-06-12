import subprocess
import re
import os
import matplotlib.pyplot as plt

# Configuration Settings
EXECUTABLE = "./asymm"  
TEMP_CONFIG = "sweep_temp.conf"

# Fixed global matrix dimensions for the experiment
A_HEIGHT = 128
A_WIDTH = 128
B_WIDTH = 128

# The parameter we want to sweep: Tile Size (M = N = K)
tile_sizes = [4, 8, 16, 32, 64]
l1_hit_rates = []
l2_hit_rates = []

def write_temporary_config(l1_size=8192, l1_line=16, l2_size=32768, l2_line=16):
    """Generates a transient configuration file including both L1 and L2 parameters."""
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={A_HEIGHT}\n")
        f.write(f"A_WIDTH_DIM={A_WIDTH}\n")
        f.write("A_PRECISION_BYTES=8\n") 
        f.write(f"B_WIDTH_DIM={B_WIDTH}\n")
        f.write("B_PRECISION_BYTES=2\n") 
        
        # L1 Cache Configuration
        f.write(f"L1_SIZE_BYTES={l1_size}\n")
        f.write(f"L1_LINE_SIZE_BYTES={l1_line}\n")
        f.write("L1_ASSOC=4\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        
        # New L2 Cache Configuration
        f.write(f"L2_SIZE_BYTES={l2_size}\n")
        f.write(f"L2_LINE_SIZE_BYTES={l2_line}\n")
        f.write("L2_ASSOC=8\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        
        f.write("L1_REPLACEMENT_POLICY=FIFO\n")
        f.write("L2_REPLACEMENT_POLICY=FIFO\n")
        
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\n")
        f.write("PRNG_GEN_COST_PER_LINE=64\n")
        
print("====================================================")
print("Starting Asymmetric Tiling Hierarchy Sweep Execution")
print("====================================================")

# Establish architecture characteristics
write_temporary_config(l1_size=8192, l1_line=8, l2_size=32768, l2_line=8)

for tile in tile_sizes:
    cmd = [
        EXECUTABLE, 
        "--config", TEMP_CONFIG, 
        "--Bgenerated", 
        str(tile), str(tile), str(tile)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        captured_stdout = result.stdout
        
        # Parse isolated L1 and L2 hit rates via localized regex anchors
        l1_match = re.search(r"--- L1 ---\s+Hit rate:\s+([\d.]+)", captured_stdout)
        l2_match = re.search(r"--- L2 ---\s+Hit rate:\s+([\d.]+)", captured_stdout)
        
        l1_val = float(l1_match.group(1)) if l1_match else 0.0
        l2_val = float(l2_match.group(1)) if l2_match else 0.0
        
        l1_hit_rates.append(l1_val)
        l2_hit_rates.append(l2_val)
        
        print(f"[SUCCESS] Tile {tile}x{tile}x{tile} -> L1 Hit Rate: {l1_val:.3f} | L2 Hit Rate: {l2_val:.3f}")
            
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Subprocess failed at tile size {tile}: {e.stderr}")
        l1_hit_rates.append(0.0)
        l2_hit_rates.append(0.0)

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("\nProcessing multi-level analytical performance plots...")

# Render both curves
plt.figure(figsize=(10, 6))
plt.plot(tile_sizes, l1_hit_rates, marker='o', linestyle='-', color='#1f77b4', linewidth=2.5, label='L1 Cache (8 KB)')
plt.plot(tile_sizes, l2_hit_rates, marker='s', linestyle='--', color='#ff7f0e', linewidth=2.5, label='L2 Cache (32 KB)')

plt.title("Multi-Level Cache Footprint Analysis on Swept Tiling Layouts\n(Asymmetric Mixed-Precision Stream Matrix Multiplication)", fontsize=12, fontweight='bold', pad=12)
plt.xlabel("Tile Block Size Parameters (M = N = K)", fontsize=11)
plt.ylabel("Simulated Cache Hit Rate Percentiles", fontsize=11)
plt.grid(True, linestyle='--', alpha=0.5)
plt.xlim(min(tile_sizes) - 2, max(tile_sizes) + 2)
plt.ylim(-0.05, 1.05)
plt.legend(fontsize=11, loc="best")

os.makedirs("plots", exist_ok=True)
graph_output_name = "plots/asymmetric_hierarchy_sweep_results.png"
plt.savefig(graph_output_name, dpi=300, bbox_inches='tight')
print(f"Execution finished. Chart successfully generated: '{graph_output_name}'")
