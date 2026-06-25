#!/usr/bin/env python3
import os
import subprocess
import re
import json
import matplotlib.pyplot as plt
import numpy as np

EXECUTABLE = "./asymm"
TEMP_CONFIG = "prngfifo_sweep_temp.conf"
OUTPUT_DIR = "interesting_results/v5-results/prngfifo-vs-normal"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def compile_simulator():
    print("Compiling simulator...")
    subprocess.run(["make"], check=True)

def write_config(
    a_precision=8, b_precision=2,
    l1_size=2**13, l1_line=32, l1_assoc=6, l1_policy="LRU", l1_write="WRITE_BACK",
    l2_size=2**15, l2_line=64, l2_assoc=8, l2_policy="LRU", l2_write="WRITE_BACK",
    mem_cycles=180, reg_m=4, reg_n=4, reg_k=4, mat_dim=256,
    fifo_capacity=64, fifo_gen_cost=10
):
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={mat_dim}\n")
        f.write(f"A_WIDTH_DIM={mat_dim}\n")
        f.write(f"A_PRECISION_BYTES={a_precision}\n")
        f.write(f"B_WIDTH_DIM={mat_dim}\n")
        f.write(f"B_PRECISION_BYTES={b_precision}\n")
        
        f.write(f"L1_SIZE_BYTES={l1_size}\n")
        f.write(f"L1_LINE_SIZE_BYTES={l1_line}\n")
        f.write(f"L1_ASSOC={l1_assoc}\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        f.write(f"L1_REPLACEMENT_POLICY={l1_policy}\n")
        f.write(f"L1_WRITE_POLICY={l1_write}\n")
        
        f.write(f"L2_SIZE_BYTES={l2_size}\n")
        f.write(f"L2_LINE_SIZE_BYTES={l2_line}\n")
        f.write(f"L2_ASSOC={l2_assoc}\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        f.write(f"L2_REPLACEMENT_POLICY={l2_policy}\n")
        f.write(f"L2_WRITE_POLICY={l2_write}\n")
        
        f.write(f"MEM_ACCESS_CYCLES={mem_cycles}\n")
        f.write("PRNG_ACCESS_CYCLES=2\n")
        f.write("PRNG_GEN_COST_PER_LINE=64\n")
        f.write(f"PRNG_FIFO_CAPACITY={fifo_capacity}\n")
        f.write(f"PRNG_FIFO_GEN_COST={fifo_gen_cost}\n")
        
        f.write(f"REG_M={reg_m}\n")
        f.write(f"REG_N={reg_n}\n")
        f.write(f"REG_K={reg_k}\n")
        f.write("MULAC_CYCLES=8\n")
        
        f.write("SP_ACCESS_CYCLES=1\n")
        f.write("SP_BANKS=8\n")
        f.write("SP_WORD_SIZE_BYTES=8\n")

def run_sim(m, n, k, flags=None):
    cmd = [EXECUTABLE, "--config", TEMP_CONFIG]
    if flags:
        cmd.extend(flags)
    cmd.extend([str(m), str(n), str(k)])
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return parse_output(res.stdout)
    except Exception as e:
        print(f"Simulation failed for tile {m}x{n}x{k} with error: {e}")
        return None

def parse_output(stdout):
    sections = {}
    current_section = None
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("--- ") and line.endswith(" ---"):
            current_section = line.strip("- ")
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)
            
    stats = {}
    
    # Parse L1
    if "L1" in sections:
        l1_lines = "\n".join(sections["L1"])
        m_hit = re.search(r"Hit rate:\s+([\d.]+)", l1_lines)
        m_lookup = re.search(r"TagLookup:\s+(\d+)", l1_lines)
        m_fill = re.search(r"LineFill:\s+(\d+)", l1_lines)
        m_evict = re.search(r"Evict:\s+(\d+)", l1_lines)
        stats["l1_hit_rate"] = float(m_hit.group(1)) if m_hit else 0.0
        stats["l1_lookups"] = int(m_lookup.group(1)) if m_lookup else 0
        stats["l1_fills"] = int(m_fill.group(1)) if m_fill else 0
        stats["l1_evicts"] = int(m_evict.group(1)) if m_evict else 0
    else:
        stats["l1_hit_rate"], stats["l1_lookups"], stats["l1_fills"], stats["l1_evicts"] = 0.0, 0, 0, 0
        
    # Parse L2
    if "L2" in sections:
        l2_lines = "\n".join(sections["L2"])
        m_hit = re.search(r"Hit rate:\s+([\d.]+)", l2_lines)
        m_lookup = re.search(r"TagLookup:\s+(\d+)", l2_lines)
        m_fill = re.search(r"LineFill:\s+(\d+)", l2_lines)
        m_evict = re.search(r"Evict:\s+(\d+)", l2_lines)
        stats["l2_hit_rate"] = float(m_hit.group(1)) if m_hit else 0.0
        stats["l2_lookups"] = int(m_lookup.group(1)) if m_lookup else 0
        stats["l2_fills"] = int(m_fill.group(1)) if m_fill else 0
        stats["l2_evicts"] = int(m_evict.group(1)) if m_evict else 0
    else:
        stats["l2_hit_rate"], stats["l2_lookups"], stats["l2_fills"], stats["l2_evicts"] = 0.0, 0, 0, 0

    # Parse System
    if "System" in sections:
        sys_lines = "\n".join(sections["System"])
        m_cycles = re.search(r"Cycles:\s+(\d+)", sys_lines)
        stats["cycles"] = int(m_cycles.group(1)) if m_cycles else 0
    else:
        stats["cycles"] = 0
        
    # Parse PRNG FIFO if present
    if "PRNG FIFO" in sections:
        fifo_lines = "\n".join(sections["PRNG FIFO"])
        m_stalls = re.search(r"Stalls:\s+(\d+)", fifo_lines)
        m_stall_cycles = re.search(r"StallCycles:\s+(\d+)", fifo_lines)
        stats["fifo_stalls"] = int(m_stalls.group(1)) if m_stalls else 0
        stats["fifo_stall_cycles"] = int(m_stall_cycles.group(1)) if m_stall_cycles else 0
    else:
        stats["fifo_stalls"], stats["fifo_stall_cycles"] = 0, 0
        
    return stats

def main():
    compile_simulator()
    
    report_segments = []
    
    # ==========================================================================
    # SWEEP A: Matrix B Precision Sweep (Normal DRAM vs. PRNG FIFO)
    # ==========================================================================
    print("\nRunning Sweep A: B Precision Sweep...")
    precisions = [1, 2, 4, 8]
    data_normal = []
    data_fifo = []
    
    # Use 32x64x32 tile dimensions to satisfy the alignment constraints:
    # (n * B_PRECISION_BYTES) % 64 == 0 (for n=64, it's 64, 128, 256, 512, all divisible)
    m, n, k = 32, 64, 32
    
    for p in precisions:
        # 1. Run Normal DRAM mode
        write_config(b_precision=p, mat_dim=256)
        res_normal = run_sim(m, n, k)
        data_normal.append(res_normal)
        
        # 2. Run PRNG FIFO mode (gen cost = 10, capacity = 64)
        res_fifo = run_sim(m, n, k, flags=["--Bfifo"])
        data_fifo.append(res_fifo)
        
        print(f"B Precision: {p}B -> Normal Cycles: {res_normal['cycles']:,} | FIFO Cycles: {res_fifo['cycles']:,}")

    # Plot Sweep A
    plt.figure(figsize=(9, 5.5))
    x = np.arange(len(precisions))
    width = 0.35
    
    cycles_normal = [d["cycles"] / 1e6 for d in data_normal]
    cycles_fifo = [d["cycles"] / 1e6 for d in data_fifo]
    
    plt.bar(x - width/2, cycles_normal, width, label='Normal DRAM-Backed B', color='#d62728', edgecolor='black')
    plt.bar(x + width/2, cycles_fifo, width, label='PRNG FIFO Streaming', color='#1f77b4', edgecolor='black')
    
    plt.title("Sweep A: PRNG FIFO vs. Normal DRAM across B Precisions\n(Matrix: 256x256x256 | Tile: 32x64x32)", fontsize=11, fontweight="bold")
    plt.xlabel("Matrix B Precision (Bytes per Element)", fontweight="bold")
    plt.ylabel("Execution Cycles (Millions)", fontweight="bold")
    plt.xticks(x, [f"{p}B" for p in precisions])
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/sweep_a_precision.png", dpi=200)
    plt.close()
    
    # Table Sweep A
    t_a = """### Sweep A: Matrix B Precision Sweep
This sweep compares the cycles and hit rates of Normal DRAM-backed mode against MMIO PRNG FIFO mode across different precision levels of matrix B.

| B Precision | Normal Cycles | FIFO Cycles | FIFO Stall Cycles | L1 Hit Rate (Normal) | L2 Hit Rate (Normal) | Speedup |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for p, dn, df in zip(precisions, data_normal, data_fifo):
        speedup = dn["cycles"] / df["cycles"]
        t_a += f"| {p}B | {dn['cycles']:,} | {df['cycles']:,} | {df['fifo_stall_cycles']:,} | {dn['l1_hit_rate']:.3f} | {dn['l2_hit_rate']:.3f} | {speedup:.2f}x |\n"
    report_segments.append(t_a)

    # ==========================================================================
    # SWEEP B: FIFO Generation Cost Sweep
    # ==========================================================================
    print("\nRunning Sweep B: FIFO Generation Cost Sweep...")
    gen_costs = [2, 5, 10, 15, 20, 25, 30, 40, 50]
    data_cost = []
    
    # Use B precision = 4 bytes, Matrix 256x256x256, Tile 32x64x32
    # Normal DRAM run is constant for a given B precision
    write_config(b_precision=4, mat_dim=256)
    res_normal_const = run_sim(m, n, k)
    normal_const_cycles = res_normal_const["cycles"]
    
    for cost in gen_costs:
        write_config(b_precision=4, mat_dim=256, fifo_gen_cost=cost)
        res_fifo = run_sim(m, n, k, flags=["--Bfifo"])
        data_cost.append(res_fifo)
        print(f"Gen Cost: {cost} cyc/elem -> FIFO Cycles: {res_fifo['cycles']:,} | Stalls: {res_fifo['fifo_stall_cycles']:,}")

    # Plot Sweep B
    plt.figure(figsize=(9, 5.5))
    fifo_cycles = [d["cycles"] / 1e6 for d in data_cost]
    
    plt.plot(gen_costs, fifo_cycles, color='#1f77b4', marker='o', linewidth=2.5, label='PRNG FIFO Mode')
    plt.axhline(y=normal_const_cycles / 1e6, color='#d62728', linestyle='--', linewidth=2.0, label='Normal DRAM Mode (Constant)')
    
    plt.title("Sweep B: Performance vs. PRNG FIFO Generation Cost\n(Matrix: 256x256x256 | B Precision: 4B | Tile: 32x64x32)", fontsize=11, fontweight="bold")
    plt.xlabel("FIFO Generator Cost (Cycles per Element)", fontweight="bold")
    plt.ylabel("Execution Cycles (Millions)", fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/sweep_b_gen_cost.png", dpi=200)
    plt.close()
    
    # Table Sweep B
    t_b = f"""### Sweep B: FIFO Generator Cost Sweep
This experiment sweeps the FIFO generation cost to identify the "crossover point" where the generator's cost makes it slower than loading from DRAM.

*   **Normal DRAM Cycles (Constant)**: {normal_const_cycles:,}

| Gen Cost (cy/elem) | FIFO Cycles | FIFO Stall Cycles | Stall % | FIFO vs. Normal Ratio |
| :---: | :---: | :---: | :---: | :---: |
"""
    for cost, df in zip(gen_costs, data_cost):
        ratio = df["cycles"] / normal_const_cycles
        stall_pct = df["fifo_stall_cycles"] / df["cycles"] * 100
        t_b += f"| {cost} cycles | {df['cycles']:,} | {df['fifo_stall_cycles']:,} | {stall_pct:.2f}% | {ratio:.2f}x |\n"
    report_segments.append(t_b)

    # ==========================================================================
    # SWEEP C: Loop Stationarity in PRNG FIFO vs. DRAM
    # ==========================================================================
    print("\nRunning Sweep C: Loop Stationarity Sweep...")
    # Tile sizes swept (all multiple of 32 to satisfy line alignment):
    tile_shapes = [(32, 32, 32), (32, 64, 32), (32, 128, 32)]
    exp_c_results = []
    
    for t_m, t_n, t_k in tile_shapes:
        write_config(b_precision=2, mat_dim=256)
        
        # 1. C-Stationary + Normal DRAM
        res_c_norm = run_sim(t_m, t_n, t_k)
        
        # 2. B-Stationary + Normal DRAM
        res_b_norm = run_sim(t_m, t_n, t_k, flags=["--Bstationary"])
        
        # 3. C-Stationary + PRNG FIFO
        res_c_fifo = run_sim(t_m, t_n, t_k, flags=["--Bfifo"])
        
        # 4. B-Stationary + PRNG FIFO
        res_b_fifo = run_sim(t_m, t_n, t_k, flags=["--Bstationary", "--Bfifo"])
        
        exp_c_results.append({
            "tile": f"{t_m}x{t_n}x{t_k}",
            "c_norm": res_c_norm,
            "b_norm": res_b_norm,
            "c_fifo": res_c_fifo,
            "b_fifo": res_b_fifo
        })
        print(f"Tile {t_m}x{t_n}x{t_k} -> C-Norm: {res_c_norm['cycles']:,} | B-Norm: {res_b_norm['cycles']:,} | C-FIFO: {res_c_fifo['cycles']:,} | B-FIFO: {res_b_fifo['cycles']:,}")

    # Plot Sweep C
    plt.figure(figsize=(10, 6))
    x_labels = [r["tile"] for r in exp_c_results]
    x_indices = np.arange(len(x_labels))
    width = 0.2
    
    cycles_c_norm = [r["c_norm"]["cycles"] / 1e6 for r in exp_c_results]
    cycles_b_norm = [r["b_norm"]["cycles"] / 1e6 for r in exp_c_results]
    cycles_c_fifo = [r["c_fifo"]["cycles"] / 1e6 for r in exp_c_results]
    cycles_b_fifo = [r["b_fifo"]["cycles"] / 1e6 for r in exp_c_results]
    
    plt.bar(x_indices - 1.5*width, cycles_c_norm, width, label='C-Stationary + DRAM', color='#d62728', edgecolor='black')
    plt.bar(x_indices - 0.5*width, cycles_b_norm, width, label='B-Stationary + DRAM', color='#ff7f0e', edgecolor='black')
    plt.bar(x_indices + 0.5*width, cycles_c_fifo, width, label='C-Stationary + FIFO', color='#1f77b4', edgecolor='black')
    plt.bar(x_indices + 1.5*width, cycles_b_fifo, width, label='B-Stationary + FIFO', color='#2ca02c', edgecolor='black')
    
    plt.title("Sweep C: Loop Stationarity under Normal DRAM vs. PRNG FIFO\n(Matrix: 256x256x256 | B Precision: 2B)", fontsize=11, fontweight="bold")
    plt.xlabel("Tile Size (M x N x K)", fontweight="bold")
    plt.ylabel("Execution Cycles (Millions)", fontweight="bold")
    plt.xticks(x_indices, x_labels)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/sweep_c_stationarity.png", dpi=200)
    plt.close()
    
    # Table Sweep C
    t_c = """### Sweep C: Loop Stationarity & Memory Access Method
Comparing C-Stationary and B-Stationary policies under Normal DRAM vs. PRNG FIFO.

| Tile Size | Policy & Mode | Total Cycles | FIFO Stall Cycles | L1 Hit Rate | L2 Hit Rate |
| :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for r in exp_c_results:
        tile = r["tile"]
        cn, bn, cf, bf = r["c_norm"], r["b_norm"], r["c_fifo"], r["b_fifo"]
        t_c += f"| {tile} | C-Stationary + DRAM | {cn['cycles']:,} | N/A | {cn['l1_hit_rate']:.3f} | {cn['l2_hit_rate']:.3f} |\n"
        t_c += f"| {tile} | B-Stationary + DRAM | {bn['cycles']:,} | N/A | {bn['l1_hit_rate']:.3f} | {bn['l2_hit_rate']:.3f} |\n"
        t_c += f"| {tile} | C-Stationary + FIFO | {cf['cycles']:,} | {cf['fifo_stall_cycles']:,} | {cf['l1_hit_rate']:.3f} | {cf['l2_hit_rate']:.3f} |\n"
        t_c += f"| {tile} | B-Stationary + FIFO | {bf['cycles']:,} | {bf['fifo_stall_cycles']:,} | {bf['l1_hit_rate']:.3f} | {bf['l2_hit_rate']:.3f} |\n"
        t_c += "| --- | --- | --- | --- | --- | --- |\n"
    report_segments.append(t_c)

    # ==========================================================================
    # SWEEP D: FIFO Capacity Sweep under C-Stationary vs. B-Stationary
    # ==========================================================================
    print("\nRunning Sweep D: FIFO Capacity Sweep...")
    capacities = [4, 8, 16, 32, 64, 128, 256]
    data_cap_c = []
    data_cap_b = []
    
    for cap in capacities:
        # C-stationary
        write_config(b_precision=2, mat_dim=256, fifo_capacity=cap, fifo_gen_cost=10)
        res_c = run_sim(32, 64, 32, flags=["--Bfifo"])
        data_cap_c.append(res_c)
        
        # B-stationary
        res_b = run_sim(32, 64, 32, flags=["--Bfifo", "--Bstationary"])
        data_cap_b.append(res_b)
        
        print(f"FIFO Cap: {cap} -> C-Stat Stalls: {res_c['fifo_stall_cycles']:,} | B-Stat Stalls: {res_b['fifo_stall_cycles']:,}")

    # Plot Sweep D
    plt.figure(figsize=(9, 5.5))
    stalls_c = [d["fifo_stall_cycles"] / 1e6 for d in data_cap_c]
    stalls_b = [d["fifo_stall_cycles"] / 1e6 for d in data_cap_b]
    
    plt.plot(capacities, stalls_c, color='#1f77b4', marker='o', linewidth=2.5, label='C-Stationary')
    plt.plot(capacities, stalls_b, color='#ff7f0e', marker='s', linewidth=2.5, label='B-Stationary')
    
    plt.xscale('log', base=2)
    plt.xticks(capacities, [str(c) for c in capacities])
    plt.xlabel("FIFO Queue Capacity", fontweight="bold")
    plt.ylabel("FIFO Stall Cycles (Millions)", fontweight="bold")
    plt.title("Sweep D: FIFO Capacity vs. Stall Cycles (C- vs. B-Stationary)\n(Matrix: 256x256x256 | B Precision: 2B | Tile: 32x64x32)", fontsize=11, fontweight="bold")
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/sweep_d_fifo_capacity.png", dpi=200)
    plt.close()
    
    # Table Sweep D
    t_d = """### Sweep D: FIFO Capacity Sweep
This sweep evaluates the stall cycles for different FIFO capacities under both C-Stationary and B-Stationary dataflow models.

| FIFO Capacity | C-Stationary Cycles | C-Stationary Stalls | B-Stationary Cycles | B-Stationary Stalls |
| :---: | :---: | :---: | :---: | :---: |
"""
    for cap, dc, db in zip(capacities, data_cap_c, data_cap_b):
        t_d += f"| {cap} entries | {dc['cycles']:,} | {dc['fifo_stall_cycles']:,} | {db['cycles']:,} | {db['fifo_stall_cycles']:,} |\n"
    report_segments.append(t_d)

    # Clean up temp config
    if os.path.exists(TEMP_CONFIG):
        os.remove(TEMP_CONFIG)

    # Write unified report
    print("\nWriting final report...")
    with open(f"{OUTPUT_DIR}/README.md", "w") as f:
        f.write("# Advanced Sweeps: PRNG FIFO vs. Normal DRAM-Backed Mode\n\n")
        f.write("This directory contains 4 advanced sweeps designed to evaluate the trade-offs between background MMIO PRNG FIFO streaming and standard DRAM cache lines fetching.\n\n")
        f.write("## Table of Contents\n")
        f.write("1. [Sweep A: B Precision Sweep](#sweep-a-matrix-b-precision-sweep)\n")
        f.write("2. [Sweep B: FIFO Generator Cost Sweep](#sweep-b-fifo-generator-cost-sweep)\n")
        f.write("3. [Sweep C: Loop Stationarity Sweep](#sweep-c-loop-stationarity-memory-access-method)\n")
        f.write("4. [Sweep D: FIFO Capacity Sweep](#sweep-d-fifo-capacity-sweep)\n\n")
        
        f.write("--- \n\n")
        f.write("## 1. Sweep A: Matrix B Precision Sweep\n")
        f.write("![Sweep A Precision](sweep_a_precision.png)\n\n")
        f.write(report_segments[0] + "\n\n")
        
        f.write("--- \n\n")
        f.write("## 2. Sweep B: FIFO Generator Cost Sweep\n")
        f.write("![Sweep B Cost](sweep_b_gen_cost.png)\n\n")
        f.write(report_segments[1] + "\n\n")
        
        f.write("--- \n\n")
        f.write("## 3. Sweep C: Loop Stationarity Sweep\n")
        f.write("![Sweep C Stationarity](sweep_c_stationarity.png)\n\n")
        f.write(report_segments[2] + "\n\n")
        
        f.write("--- \n\n")
        f.write("## 4. Sweep D: FIFO Capacity Sweep\n")
        f.write("![Sweep D Capacity](sweep_d_fifo_capacity.png)\n\n")
        f.write(report_segments[3] + "\n\n")

    print(f"Success! PRNG FIFO vs Normal DRAM sweep report and plots written to '{OUTPUT_DIR}'")

if __name__ == "__main__":
    main()
