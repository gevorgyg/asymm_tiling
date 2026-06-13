import subprocess
import re
import os
import matplotlib.pyplot as plt

EXECUTABLE = "./asymm"
TEMP_CONFIG = "sweep_500_temp.conf"

A_HEIGHT = 500
A_WIDTH = 500
B_WIDTH = 500

# Constants for shape sweeps
CONST_DIM = 20

# Valid tile sizes for each category
square_sizes = [4, 20, 100, 500]
wide_n_sizes = [4, 20, 100, 500]      # n=T, must be multiple of 4
tall_m_sizes = [4, 10, 20, 50, 100, 250, 500]
wide_k_sizes = [4, 10, 20, 50, 100, 250, 500]

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
print("Starting 500x500 Asymmetric Tiling Shape Sweeps")
print("====================================================")

write_temporary_config()

# Data structures: category -> { 'normal': { 'cycles': [], 'l1': [] }, 'prng': { 'cycles': [], 'l1': [] } }
curves = {
    "Square (TxTxT)": {
        "sizes": square_sizes,
        "normal": {"cycles": [], "l1": []},
        "prng": {"cycles": [], "l1": []},
        "shape_func": lambda t: (t, t, t)
    },
    "Wide in N (20xTx20)": {
        "sizes": wide_n_sizes,
        "normal": {"cycles": [], "l1": []},
        "prng": {"cycles": [], "l1": []},
        "shape_func": lambda t: (CONST_DIM, t, CONST_DIM)
    },
    "Tall in M (Tx20x20)": {
        "sizes": tall_m_sizes,
        "normal": {"cycles": [], "l1": []},
        "prng": {"cycles": [], "l1": []},
        "shape_func": lambda t: (t, CONST_DIM, CONST_DIM)
    },
    "Wide in K (20x20xT)": {
        "sizes": wide_k_sizes,
        "normal": {"cycles": [], "l1": []},
        "prng": {"cycles": [], "l1": []},
        "shape_func": lambda t: (CONST_DIM, CONST_DIM, t)
    }
}

for name, info in curves.items():
    print(f"\nSweeping shape category: {name}")
    for t in info["sizes"]:
        m, n, k = info["shape_func"](t)
        
        # Normal
        n_l1, n_l2, n_cyc = run_simulation(m, n, k, prng=False)
        info["normal"]["cycles"].append(n_cyc)
        info["normal"]["l1"].append(n_l1)
        
        # PRNG
        p_l1, p_l2, p_cyc = run_simulation(m, n, k, prng=True)
        info["prng"]["cycles"].append(p_cyc)
        info["prng"]["l1"].append(p_l1)
        
        print(f"  T={t:3d} ({m}x{n}x{k}) | Normal: {n_cyc/1e6:7.1f}M cyc (L1: {n_l1:.3f}) | PRNG: {p_cyc/1e6:7.1f}M cyc (L1: {p_l1:.3f})")

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)

print("\nGenerating dashboard plots for 500x500 matrix...")

fig, axs = plt.subplots(2, 2, figsize=(16, 12))
colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
markers = ["o", "s", "^", "D"]

# Top-Left: Standard Mode Cycles
for (name, info), color, marker in zip(curves.items(), colors, markers):
    cycles_m = [c / 1e6 for c in info["normal"]["cycles"]]
    axs[0, 0].plot(info["sizes"], cycles_m, marker=marker, linestyle='-', color=color, linewidth=2.5, label=name)
axs[0, 0].set_title("Standard Mode: Execution Cycles", fontsize=12, fontweight='bold', pad=10)
axs[0, 0].set_xlabel("Sweep Parameter T", fontsize=10)
axs[0, 0].set_ylabel("Execution Cycles (Millions)", fontsize=10)
axs[0, 0].set_xscale('log')
axs[0, 0].grid(True, linestyle='--', alpha=0.5)
axs[0, 0].legend(fontsize=9, loc="best")

# Top-Right: PRNG Mode Cycles
for (name, info), color, marker in zip(curves.items(), colors, markers):
    cycles_m = [c / 1e6 for c in info["prng"]["cycles"]]
    axs[0, 1].plot(info["sizes"], cycles_m, marker=marker, linestyle='-', color=color, linewidth=2.5, label=name)
axs[0, 1].set_title("PRNG Mode: Execution Cycles", fontsize=12, fontweight='bold', pad=10)
axs[0, 1].set_xlabel("Sweep Parameter T", fontsize=10)
axs[0, 1].set_ylabel("Execution Cycles (Millions)", fontsize=10)
axs[0, 1].set_xscale('log')
axs[0, 1].grid(True, linestyle='--', alpha=0.5)
axs[0, 1].legend(fontsize=9, loc="best")

# Bottom-Left: Standard L1 Hit Rates
for (name, info), color, marker in zip(curves.items(), colors, markers):
    axs[1, 0].plot(info["sizes"], info["normal"]["l1"], marker=marker, linestyle='-', color=color, linewidth=2, label=name)
axs[1, 0].set_title("Standard Mode: L1 Hit Rates", fontsize=12, fontweight='bold', pad=10)
axs[1, 0].set_xlabel("Sweep Parameter T", fontsize=10)
axs[1, 0].set_ylabel("L1 Cache Hit Rate", fontsize=10)
axs[1, 0].set_xscale('log')
axs[1, 0].set_ylim(-0.05, 1.05)
axs[1, 0].grid(True, linestyle='--', alpha=0.5)
axs[1, 0].legend(fontsize=9, loc="best")

# Bottom-Right: PRNG L1 Hit Rates
for (name, info), color, marker in zip(curves.items(), colors, markers):
    # Offset PRNG slightly to avoid complete overlay hiding curves
    l1_offset = [h + 0.005 for h in info["prng"]["l1"]]
    axs[1, 1].plot(info["sizes"], l1_offset, marker=marker, linestyle=':', color=color, linewidth=2, label=name)
axs[1, 1].set_title("PRNG Mode: L1 Hit Rates (offset +0.005)", fontsize=12, fontweight='bold', pad=10)
axs[1, 1].set_xlabel("Sweep Parameter T", fontsize=10)
axs[1, 1].set_ylabel("L1 Cache Hit Rate", fontsize=10)
axs[1, 1].set_xscale('log')
axs[1, 1].set_ylim(-0.05, 1.05)
axs[1, 1].grid(True, linestyle='--', alpha=0.5)
axs[1, 1].legend(fontsize=9, loc="best")

# Formatting log ticks for x-axis
for ax in axs.flat:
    ax.set_xticks([4, 10, 20, 50, 100, 250, 500])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())

plt.suptitle("500x500 Matrix Shape Tiling Sweep (Square vs. Tall M vs. Wide N vs. Wide K)\n(Caches: 8KB L1, 32KB L2 | Constants: m,n,k = 20 where not swept)", fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.95])

os.makedirs("plots", exist_ok=True)
output_filename = "plots/asymmetric_500x500_sweep.png"
plt.savefig(output_filename, dpi=300, bbox_inches='tight')
print(f"Success! Performance dashboard generated: '{output_filename}'")
