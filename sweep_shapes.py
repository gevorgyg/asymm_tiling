import subprocess
import re
import os
import matplotlib.pyplot as plt

EXECUTABLE = "./asymm"
TEMP_CONFIG = "shape_sweep.conf"

# Matrix definition constraints (500x500 layout)
MATRIX_DIM = 100
PRECISION_A = 8  
PRECISION_B = 1  

# Valid matrix divisors to iterate over
sweep_steps = [5, 10, 20, 25, 50, 100]

def write_config():
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={MATRIX_DIM}\n")
        f.write(f"A_WIDTH_DIM={MATRIX_DIM}\n")
        f.write(f"A_PRECISION_BYTES={PRECISION_A}\n")
        f.write(f"B_WIDTH_DIM={MATRIX_DIM}\n")
        f.write(f"B_PRECISION_BYTES={PRECISION_B}\n")
        
        # L1 Setup (4 KB Layout)
        f.write("L1_SIZE_BYTES=4096\n")
        f.write("L1_LINE_SIZE_BYTES=64\n")
        f.write("L1_ASSOC=4\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        
        # New L2 Setup (16 KB Layout)
        f.write("L2_SIZE_BYTES=16384\n")
        f.write("L2_LINE_SIZE_BYTES=64\n")
        f.write("L2_ASSOC=8\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        
        f.write("MEM_ACCESS_CYCLES=180\n")

def run_sim(m, n, k):
    cmd = [EXECUTABLE, "--config", TEMP_CONFIG, "--Bgenerated", str(m), str(n), str(k)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        captured = res.stdout
        
        l1_match = re.search(r"--- L1 ---\s+Hit rate:\s+([\d.]+)", captured)
        l2_match = re.search(r"--- L2 ---\s+Hit rate:\s+([\d.]+)", captured)
        
        return (float(l1_match.group(1)) if l1_match else 0.0,
                float(l2_match.group(1)) if l2_match else 0.0)
    except Exception:
        return (0.0, 0.0)

write_config()

# Data structures separating L1 and L2 traces
l1_curves = {"Square (TxTxT)": [], "Wide in N (5xTx5)": [], "Wide in K (5x5xT)": [], "Tall in M (Tx5x5)": []}
l2_curves = {"Square (TxTxT)": [], "Wide in N (5xTx5)": [], "Wide in K (5x5xT)": [], "Tall in M (Tx5x5)": []}

print("Running memory hierarchy shape geometry sweeps over 500x500 matrix...")
for t in sweep_steps:
    sq_l1, sq_l2 = run_sim(t, t, t)
    wn_l1, wn_l2 = run_sim(5, t, 5)
    wk_l1, wk_l2 = run_sim(5, 5, t)
    tm_l1, tm_l2 = run_sim(t, 5, 5)
    
    l1_curves["Square (TxTxT)"].append(sq_l1)
    l2_curves["Square (TxTxT)"].append(sq_l2)
    
    l1_curves["Wide in N (5xTx5)"].append(wn_l1)
    l2_curves["Wide in N (5xTx5)"].append(wn_l2)
    
    l1_curves["Wide in K (5x5xT)"].append(wk_l1)
    l2_curves["Wide in K (5x5xT)"].append(wk_l2)
    
    l1_curves["Tall in M (Tx5x5)"].append(tm_l1)
    l2_curves["Tall in M (Tx5x5)"].append(tm_l2)
    
    print(f"Processed dimension configuration index vector step: {t}")

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

# Render side-by-side subplot panel tracking
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.5))
colors = ["#d62728", "#2ca02c", "#ff7f0e", "#1f77b4"]
markers = ["o", "s", "^", "D"]

# Left Panel: L1 Execution Trace
for (label, values), color, marker in zip(l1_curves.items(), colors, markers):
    ax1.plot(sweep_steps, values, label=label, color=color, marker=marker, linewidth=2, markersize=6)
ax1.set_title("L1 Cache Behavior (4 KB Capacity)", fontsize=11, fontweight='bold')
ax1.set_xlabel("Scaling Dimension Vector Value (T)", fontsize=10)
ax1.set_ylabel("L1 Cache Hit Rate", fontsize=10)
ax1.set_xticks(sweep_steps)
ax1.grid(True, linestyle='--', alpha=0.5)
ax1.set_ylim(-0.05, 1.05)
ax1.legend(fontsize=9, loc="lower left")

# Right Panel: L2 Execution Trace
for (label, values), color, marker in zip(l2_curves.items(), colors, markers):
    ax2.plot(sweep_steps, values, label=label, color=color, marker=marker, linewidth=2, markersize=6)
ax2.set_title("L2 Cache Behavior (16 KB Capacity Layer)", fontsize=11, fontweight='bold')
ax2.set_xlabel("Scaling Dimension Vector Value (T)", fontsize=10)
ax2.set_ylabel("L2 Cache Hit Rate", fontsize=10)
ax2.set_xticks(sweep_steps)
ax2.grid(True, linestyle='--', alpha=0.5)
ax2.set_ylim(-0.05, 1.05)
ax2.legend(fontsize=9, loc="lower left")

plt.suptitle("Asymmetric Tiling Structural Shape Analysis Across the Memory Hierarchy\n(Matrix A: 8-Byte Precision | Matrix B: 1-Byte Precision)", fontsize=13, fontweight='bold')
output_img = "plots/asymmetric_hierarchy_shape_comparison.png"
plt.savefig(output_img, dpi=300, bbox_inches='tight')
print(f"\nSuccess! Subplot chart generated and saved to: {output_img}")
