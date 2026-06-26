#!/usr/bin/env python3
import os
import subprocess
import re
import json
import matplotlib.pyplot as plt
import numpy as np

EXECUTABLE = "./asymm"
TEMP_CONFIG = "prng_comp_sweep_temp.conf"
OUTPUT_DIR = "interesting_results/v5-results/prngfifo-vs-prnggen"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def compile_simulator():
    print("Compiling simulator...")
    subprocess.run(["make"], check=True)

def write_config(
    a_precision=8, b_precision=2,
    l1_size=8192, l1_line=4, l1_assoc=8, l1_policy="LRU", l1_write="WRITE_BACK",
    l2_size=32768, l2_line=4, l2_assoc=8, l2_policy="LRU", l2_write="WRITE_BACK",
    mem_cycles=180, reg_m=4, reg_n=4, reg_k=4, mat_dim=256,
    fifo_capacity=64, fifo_gen_cost=10, prng_gen_cost=8
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
        f.write(f"PRNG_GEN_COST_PER_LINE={prng_gen_cost}\n")
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
    # EXPERIMENT A: Tile Shape Sweep (Fixed Area)
    # ==========================================================================
    print("\nRunning Experiment A: Tile Shape Sweep...")
    shapes = [
        (4, 64),
        (8, 32),
        (16, 16),
        (32, 8),
        (64, 4)
    ]
    data_shape_fifo = []
    data_shape_gen = []
    
    # Fixed tile area = 256, k = 16. B precision = 2 bytes. L2 Cache = 32 KB.
    # Note: L1 line size = 64 bytes. For tile width n:
    # 4x64: n=64. 64*2 = 128 (divisible by 64).
    # 8x32: n=32. 32*2 = 64 (divisible by 64).
    # 16x16: n=16. 16*2 = 32 (NOT divisible by 64!).
    # Wait! If n=16, then (n*2) % 64 is 32, which is not 0!
    # So for 16x16, 32x8, and 64x4, Bgenerated and Bfifo modes might fail if L1_LINE_SIZE_BYTES=64!
    # Let's verify: can we use L1_LINE_SIZE_BYTES = 8 bytes for this experiment?
    # Yes! If L1_LINE_SIZE_BYTES = 8 bytes, then for any tile width n (which is a multiple of 4, since register tiles are 4x4x4):
    # (n * 2) % 8 == 0 is always true because 2*n is a multiple of 8 (since n is a multiple of 4).
    # Let's check: if we use L1_LINE_SIZE_BYTES=8, L2_LINE_SIZE_BYTES=8 for this experiment,
    # then all tile shapes are perfectly valid!
    # Let's write config with line size = 8 bytes.
    
    for m, n in shapes:
        ratio = n / m
        # 1. Run PRNG FIFO mode
        write_config(b_precision=2, l1_line=8, l2_line=8, l2_size=32768, mat_dim=256)
        res_fifo = run_sim(m, n, 16, flags=["--Bfifo"])
        data_shape_fifo.append(res_fifo)
        
        # 2. Run PRNG Generated mode
        res_gen = run_sim(m, n, 16, flags=["--Bgenerated"])
        data_shape_gen.append(res_gen)
        
        print(f"Shape: {m}x{n} (ratio={ratio:.4f}) -> FIFO Cycles: {res_fifo['cycles'] if res_fifo else 0:,} | Generated Cycles: {res_gen['cycles'] if res_gen else 0:,}")

    # Plot Experiment A
    plt.figure(figsize=(9, 5.5))
    x_ratios = [n/m for m, n in shapes]
    cycles_fifo = [d["cycles"] / 1e6 for d in data_shape_fifo]
    cycles_gen = [d["cycles"] / 1e6 for d in data_shape_gen]
    
    plt.plot(x_ratios, cycles_fifo, color='#1f77b4', marker='o', linewidth=2.5, label='PRNG FIFO (MMIO Streaming)')
    plt.plot(x_ratios, cycles_gen, color='#ff7f0e', marker='s', linewidth=2.5, label='PRNG Generated (Cache-Backed)')
    
    plt.xscale('log', base=2)
    plt.xticks(x_ratios, ["4x64\n(16)", "8x32\n(4)", "16x16\n(1)", "32x8\n(0.25)", "64x4\n(0.06)"])
    plt.xlabel('Tile Shape (Aspect Ratio TN / TM)', fontweight='bold')
    plt.ylabel('Execution Cycles (Millions)', fontweight='bold')
    plt.title("Exp A: Tile Shape Sweep vs. PRNG Method\n(Tile Area: 256 | L2 Cache: 32 KB | Matrix: 256x256x256)", fontsize=11, fontweight='bold')
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/exp_a_tile_shapes.png", dpi=200)
    plt.close()
    
    # Table Exp A
    t_a = """### Experiment A: Tile Shape Aspect Ratio Sweep
Fixed tile area ($T_M \\cdot T_N = 256$ elements) and constrained L2 Cache size (32 KB) compares how tile shape aspect ratio affects cache-backed generation vs. MMIO streaming.

| Tile Shape ($T_M \\times T_N$) | Ratio ($T_N/T_M$) | FIFO Cycles | Gen Cycles | L2 Hit Rate (Gen) | FIFO Stalls |
| :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for (m, n), df, dg in zip(shapes, data_shape_fifo, data_shape_gen):
        ratio = n / m
        t_a += f"| {m}x{n} | {ratio:.4f} | {df['cycles']:,} | {dg['cycles']:,} | {dg['l2_hit_rate']:.3f} | {df['fifo_stall_cycles']:,} |\n"
    report_segments.append(t_a)

    # ==========================================================================
    # EXPERIMENT B: Matrix B Precision Sweep
    # ==========================================================================
    print("\nRunning Experiment B: B Precision Sweep...")
    precisions = [1, 2, 4, 8]
    data_prec_fifo = []
    data_prec_gen = []
    
    # Use 32x64x32 tile dimensions to satisfy the alignment constraints for B across all precisions (n=64, line=64)
    m, n, k = 32, 64, 32
    
    for p in precisions:
        # 1. Run PRNG FIFO mode
        write_config(b_precision=p, mat_dim=256)
        res_fifo = run_sim(m, n, k, flags=["--Bfifo"])
        data_prec_fifo.append(res_fifo)
        
        # 2. Run PRNG Generated mode
        res_gen = run_sim(m, n, k, flags=["--Bgenerated"])
        data_prec_gen.append(res_gen)
        
        print(f"B Precision: {p}B -> FIFO Cycles: {res_fifo['cycles']:,} | Generated Cycles: {res_gen['cycles']:,}")

    # Plot Experiment B
    plt.figure(figsize=(9, 5.5))
    x = np.arange(len(precisions))
    width = 0.35
    
    cycles_fifo = [d["cycles"] / 1e6 for d in data_prec_fifo]
    cycles_gen = [d["cycles"] / 1e6 for d in data_prec_gen]
    
    plt.bar(x - width/2, cycles_fifo, width, label='PRNG FIFO (MMIO Streaming)', color='#1f77b4', edgecolor='black')
    plt.bar(x + width/2, cycles_gen, width, label='PRNG Generated (Cache-Backed)', color='#ff7f0e', edgecolor='black')
    
    plt.title("Exp B: B Precision Sweep (FIFO vs. Generated)\n(Matrix: 256x256x256 | Tile: 32x64x32)", fontsize=11, fontweight="bold")
    plt.xlabel("Matrix B Precision (Bytes per Element)", fontweight="bold")
    plt.ylabel("Execution Cycles (Millions)", fontweight="bold")
    plt.xticks(x, [f"{p}B" for p in precisions])
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/exp_b_precision.png", dpi=200)
    plt.close()
    
    # Table Exp B
    t_b = """### Experiment B: Matrix B Precision Sweep
This sweep compares the scaling of execution cycles as the element precision of Matrix B increases.

| B Precision | FIFO Cycles | Generated Cycles | L1 Hit Rate (Gen) | L2 Hit Rate (Gen) | FIFO Stalls | Speedup (FIFO vs. Gen) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for p, df, dg in zip(precisions, data_prec_fifo, data_prec_gen):
        speedup = dg["cycles"] / df["cycles"]
        t_b += f"| {p}B | {df['cycles']:,} | {dg['cycles']:,} | {dg['l1_hit_rate']:.3f} | {dg['l2_hit_rate']:.3f} | {df['fifo_stall_cycles']:,} | {speedup:.2f}x |\n"
    report_segments.append(t_b)

    # ==========================================================================
    # EXPERIMENT C: Generator Throughput/Latency Sensitivity Sweep
    # ==========================================================================
    print("\nRunning Experiment C: Generator Cost Sensitivity Sweep...")
    # Sweeping normalized cost per element: 0.5, 1, 2, 4, 8 cycles/element
    # For FIFO: cost = 1, 2, 4, 8 (or 10)
    # For Generated: line_cost = cost_per_element * (64 / B_precision).
    # Since B precision is 2 bytes, a 64-byte line has 32 elements.
    # Therefore, line_cost = cost_per_element * 32.
    # Swept cost per element: 0.5, 1.0, 2.0, 4.0, 8.0 cycles/element
    costs_per_element = [0.5, 1.0, 2.0, 4.0, 8.0]
    data_cost_fifo = []
    data_cost_gen = []
    
    m, n, k = 32, 64, 32
    
    for cost in costs_per_element:
        fifo_cost = int(max(1, cost)) # FIFO cycles per element must be integer >= 1
        line_cost = int(max(1, cost * 2))
        
        # 1. Run PRNG FIFO mode
        write_config(b_precision=2, fifo_gen_cost=fifo_cost, prng_gen_cost=line_cost, mat_dim=256)
        res_fifo = run_sim(m, n, k, flags=["--Bfifo"])
        data_cost_fifo.append(res_fifo)
        
        # 2. Run PRNG Generated mode
        res_gen = run_sim(m, n, k, flags=["--Bgenerated"])
        data_cost_gen.append(res_gen)
        
        print(f"Cost/elem: {cost} cyc -> FIFO Cycles (cost={fifo_cost}): {res_fifo['cycles']:,} | Generated Cycles (line_cost={line_cost}): {res_gen['cycles']:,}")

    # Plot Experiment C
    plt.figure(figsize=(9, 5.5))
    cycles_cost_fifo = [d["cycles"] / 1e6 for d in data_cost_fifo]
    cycles_cost_gen = [d["cycles"] / 1e6 for d in data_cost_gen]
    
    plt.plot(costs_per_element, cycles_cost_fifo, color='#1f77b4', marker='o', linewidth=2.5, label='PRNG FIFO (MMIO Streaming)')
    plt.plot(costs_per_element, cycles_cost_gen, color='#ff7f0e', marker='s', linewidth=2.5, label='PRNG Generated (Cache-Backed)')
    
    plt.title("Exp C: Performance vs. PRNG Latency (Normalized per Element)\n(Matrix: 256x256x256 | B Precision: 2B | Tile: 32x64x32)", fontsize=11, fontweight="bold")
    plt.xlabel("Normalized Generator Cost (Cycles per Element)", fontweight="bold")
    plt.ylabel("Execution Cycles (Millions)", fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/exp_c_latency_sensitivity.png", dpi=200)
    plt.close()
    
    # Table Experiment C
    t_c = """### Experiment C: Generator Cost Sensitivity Sweep
This experiment evaluates the sensitivity of both PRNG modes to generator throughput by sweeping the cost per element.

| Normalized Cost (cy/elem) | FIFO Cycles | FIFO Stall Cycles | Gen Cycles | L2 Hit Rate (Gen) | Ratio (FIFO / Gen) |
| :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for cost, df, dg in zip(costs_per_element, data_cost_fifo, data_cost_gen):
        ratio = df["cycles"] / dg["cycles"]
        t_c += f"| {cost:.1f} cycles | {df['cycles']:,} | {df['fifo_stall_cycles']:,} | {dg['cycles']:,} | {dg['l2_hit_rate']:.3f} | {ratio:.2f}x |\n"
    report_segments.append(t_c)

    # ==========================================================================
    # EXPERIMENT D: Loop Stationarity under PRNG FIFO vs. PRNG Generated
    # ==========================================================================
    print("\nRunning Experiment D: Loop Stationarity Sweep...")
    tile_shapes = [(32, 32, 32), (32, 64, 32), (32, 128, 32)]
    exp_d_results = []
    
    for t_m, t_n, t_k in tile_shapes:
        write_config(b_precision=2, mat_dim=256)
        
        # 1. C-Stationary + PRNG FIFO
        res_c_fifo = run_sim(t_m, t_n, t_k, flags=["--Bfifo"])
        
        # 2. B-Stationary + PRNG FIFO
        res_b_fifo = run_sim(t_m, t_n, t_k, flags=["--Bstationary", "--Bfifo"])
        
        # 3. C-Stationary + PRNG Generated
        res_c_gen = run_sim(t_m, t_n, t_k, flags=["--Bgenerated"])
        
        # 4. B-Stationary + PRNG Generated
        res_b_gen = run_sim(t_m, t_n, t_k, flags=["--Bstationary", "--Bgenerated"])
        
        exp_d_results.append({
            "tile": f"{t_m}x{t_n}x{t_k}",
            "c_fifo": res_c_fifo,
            "b_fifo": res_b_fifo,
            "c_gen": res_c_gen,
            "b_gen": res_b_gen
        })
        print(f"Tile {t_m}x{t_n}x{t_k} -> C-FIFO: {res_c_fifo['cycles']:,} | B-FIFO: {res_b_fifo['cycles']:,} | C-Gen: {res_c_gen['cycles']:,} | B-Gen: {res_b_gen['cycles']:,}")

    # Plot Experiment D
    plt.figure(figsize=(10, 6))
    x_labels = [r["tile"] for r in exp_d_results]
    x_indices = np.arange(len(x_labels))
    width = 0.2
    
    cycles_c_fifo = [r["c_fifo"]["cycles"] / 1e6 for r in exp_d_results]
    cycles_b_fifo = [r["b_fifo"]["cycles"] / 1e6 for r in exp_d_results]
    cycles_c_gen = [r["c_gen"]["cycles"] / 1e6 for r in exp_d_results]
    cycles_b_gen = [r["b_gen"]["cycles"] / 1e6 for r in exp_d_results]
    
    plt.bar(x_indices - 1.5*width, cycles_c_fifo, width, label='C-Stationary + FIFO', color='#1f77b4', edgecolor='black')
    plt.bar(x_indices - 0.5*width, cycles_b_fifo, width, label='B-Stationary + FIFO', color='#2ca02c', edgecolor='black')
    plt.bar(x_indices + 0.5*width, cycles_c_gen, width, label='C-Stationary + Generated', color='#ff7f0e', edgecolor='black')
    plt.bar(x_indices + 1.5*width, cycles_b_gen, width, label='B-Stationary + Generated', color='#d62728', edgecolor='black')
    
    plt.title("Exp D: Loop Stationarity under PRNG FIFO vs. Generated\n(Matrix: 256x256x256 | B Precision: 2B)", fontsize=11, fontweight="bold")
    plt.xlabel("Tile Size (M x N x K)", fontweight="bold")
    plt.ylabel("Execution Cycles (Millions)", fontweight="bold")
    plt.xticks(x_indices, x_labels)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/exp_d_stationarity.png", dpi=200)
    plt.close()
    
    # Table Experiment D
    t_d = """### Experiment D: Loop Stationarity & Access Policy
Comparing C-Stationary and B-Stationary policies under PRNG FIFO and PRNG Generated mode.

| Tile Size | Policy & Mode | Total Cycles | FIFO Stall / Gen Fills | L1 Hit Rate | L2 Hit Rate |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **32x32x32** | C-Stationary + FIFO | {c_fifo_32_cyc:,} | {c_fifo_32_stalls:,} stalls | {c_fifo_32_l1:.3f} | {c_fifo_32_l2:.3f} |
| | B-Stationary + FIFO | {b_fifo_32_cyc:,} | {b_fifo_32_stalls:,} stalls | {b_fifo_32_l1:.3f} | {b_fifo_32_l2:.3f} |
| | C-Stationary + Generated | {c_gen_32_cyc:,} | {c_gen_32_fills:,} fills | {c_gen_32_l1:.3f} | {c_gen_32_l2:.3f} |
| | B-Stationary + Generated | {b_gen_32_cyc:,} | {b_gen_32_fills:,} fills | {b_gen_32_l1:.3f} | {b_gen_32_l2:.3f} |
| --- | --- | --- | --- | --- | --- |
| **32x64x32** | C-Stationary + FIFO | {c_fifo_64_cyc:,} | {c_fifo_64_stalls:,} stalls | {c_fifo_64_l1:.3f} | {c_fifo_64_l2:.3f} |
| | B-Stationary + FIFO | {b_fifo_64_cyc:,} | {b_fifo_64_stalls:,} stalls | {b_fifo_64_l1:.3f} | {b_fifo_64_l2:.3f} |
| | C-Stationary + Generated | {c_gen_64_cyc:,} | {c_gen_64_fills:,} fills | {c_gen_64_l1:.3f} | {c_gen_64_l2:.3f} |
| | B-Stationary + Generated | {b_gen_64_cyc:,} | {b_gen_64_fills:,} fills | {b_gen_64_l1:.3f} | {b_gen_64_l2:.3f} |
| --- | --- | --- | --- | --- | --- |
| **32x128x32** | C-Stationary + FIFO | {c_fifo_128_cyc:,} | {c_fifo_128_stalls:,} stalls | {c_fifo_128_l1:.3f} | {c_fifo_128_l2:.3f} |
| | B-Stationary + FIFO | {b_fifo_128_cyc:,} | {b_fifo_128_stalls:,} stalls | {b_fifo_128_l1:.3f} | {b_fifo_128_l2:.3f} |
| | C-Stationary + Generated | {c_gen_128_cyc:,} | {c_gen_128_fills:,} fills | {c_gen_128_l1:.3f} | {c_gen_128_l2:.3f} |
| | B-Stationary + Generated | {b_gen_128_cyc:,} | {b_gen_128_fills:,} fills | {b_gen_128_l1:.3f} | {b_gen_128_l2:.3f} |
"""
    
    r32 = exp_d_results[0]
    r64 = exp_d_results[1]
    r128 = exp_d_results[2]
    
    t_d = t_d.format(
        c_fifo_32_cyc=r32["c_fifo"]["cycles"], c_fifo_32_stalls=r32["c_fifo"]["fifo_stall_cycles"], c_fifo_32_l1=r32["c_fifo"]["l1_hit_rate"], c_fifo_32_l2=r32["c_fifo"]["l2_hit_rate"],
        b_fifo_32_cyc=r32["b_fifo"]["cycles"], b_fifo_32_stalls=r32["b_fifo"]["fifo_stall_cycles"], b_fifo_32_l1=r32["b_fifo"]["l1_hit_rate"], b_fifo_32_l2=r32["b_fifo"]["l2_hit_rate"],
        c_gen_32_cyc=r32["c_gen"]["cycles"], c_gen_32_fills=r32["c_gen"]["l1_fills"], c_gen_32_l1=r32["c_gen"]["l1_hit_rate"], c_gen_32_l2=r32["c_gen"]["l2_hit_rate"],
        b_gen_32_cyc=r32["b_gen"]["cycles"], b_gen_32_fills=r32["b_gen"]["l1_fills"], b_gen_32_l1=r32["b_gen"]["l1_hit_rate"], b_gen_32_l2=r32["b_gen"]["l2_hit_rate"],
        
        c_fifo_64_cyc=r64["c_fifo"]["cycles"], c_fifo_64_stalls=r64["c_fifo"]["fifo_stall_cycles"], c_fifo_64_l1=r64["c_fifo"]["l1_hit_rate"], c_fifo_64_l2=r64["c_fifo"]["l2_hit_rate"],
        b_fifo_64_cyc=r64["b_fifo"]["cycles"], b_fifo_64_stalls=r64["b_fifo"]["fifo_stall_cycles"], b_fifo_64_l1=r64["b_fifo"]["l1_hit_rate"], b_fifo_64_l2=r64["b_fifo"]["l2_hit_rate"],
        c_gen_64_cyc=r64["c_gen"]["cycles"], c_gen_64_fills=r64["c_gen"]["l1_fills"], c_gen_64_l1=r64["c_gen"]["l1_hit_rate"], c_gen_64_l2=r64["c_gen"]["l2_hit_rate"],
        b_gen_64_cyc=r64["b_gen"]["cycles"], b_gen_64_fills=r64["b_gen"]["l1_fills"], b_gen_64_l1=r64["b_gen"]["l1_hit_rate"], b_gen_64_l2=r64["b_gen"]["l2_hit_rate"],
        
        c_fifo_128_cyc=r128["c_fifo"]["cycles"], c_fifo_128_stalls=r128["c_fifo"]["fifo_stall_cycles"], c_fifo_128_l1=r128["c_fifo"]["l1_hit_rate"], c_fifo_128_l2=r128["c_fifo"]["l2_hit_rate"],
        b_fifo_128_cyc=r128["b_fifo"]["cycles"], b_fifo_128_stalls=r128["b_fifo"]["fifo_stall_cycles"], b_fifo_128_l1=r128["b_fifo"]["l1_hit_rate"], b_fifo_128_l2=r128["b_fifo"]["l2_hit_rate"],
        c_gen_128_cyc=r128["c_gen"]["cycles"], c_gen_128_fills=r128["c_gen"]["l1_fills"], c_gen_128_l1=r128["c_gen"]["l1_hit_rate"], c_gen_128_l2=r128["c_gen"]["l2_hit_rate"],
        b_gen_128_cyc=r128["b_gen"]["cycles"], b_gen_128_fills=r128["b_gen"]["l1_fills"], b_gen_128_l1=r128["b_gen"]["l1_hit_rate"], b_gen_128_l2=r128["b_gen"]["l2_hit_rate"]
    )
    report_segments.append(t_d)

    # Clean up temp config
    if os.path.exists(TEMP_CONFIG):
        os.remove(TEMP_CONFIG)

    # Write unified report
    print("\nWriting final report...")
    with open(f"{OUTPUT_DIR}/README.md", "w") as f:
        f.write("# Advanced Sweeps: PRNG FIFO vs. Cache-Backed PRNG Generated Mode\n\n")
        f.write("This directory contains 4 advanced sweeps designed to evaluate the trade-offs between background MMIO PRNG FIFO streaming and standard Cache-Backed PRNG dynamic line generation.\n\n")
        f.write("## Table of Contents\n")
        f.write("1. [Experiment A: Tile Shape Sweep](#experiment-a-tile-shape-aspect-ratio-sweep)\n")
        f.write("2. [Experiment B: B Precision Sweep](#experiment-b-matrix-b-precision-sweep)\n")
        f.write("3. [Experiment C: Generator Cost Sensitivity Sweep](#experiment-c-generator-cost-sensitivity-sweep)\n")
        f.write("4. [Experiment D: Loop Stationarity Sweep](#experiment-d-loop-stationarity--access-policy)\n\n")
        
        f.write("--- \n\n")
        f.write("## 1. Experiment A: Tile Shape Aspect Ratio Sweep\n")
        f.write("![Exp A Tile Shapes](exp_a_tile_shapes.png)\n\n")
        f.write(report_segments[0] + "\n\n")
        
        f.write("--- \n\n")
        f.write("## 2. Experiment B: Matrix B Precision Sweep\n")
        f.write("![Exp B Precision](exp_b_precision.png)\n\n")
        f.write(report_segments[1] + "\n\n")
        
        f.write("--- \n\n")
        f.write("## 3. Experiment C: Generator Cost Sensitivity Sweep\n")
        f.write("![Exp C Latency Sensitivity](exp_c_latency_sensitivity.png)\n\n")
        f.write(report_segments[2] + "\n\n")
        
        f.write("--- \n\n")
        f.write("## 4. Experiment D: Loop Stationarity Sweep\n")
        f.write("![Exp D Stationarity](exp_d_stationarity.png)\n\n")
        f.write(report_segments[3] + "\n\n")

    print(f"Success! PRNG FIFO vs Cache-Backed PRNG sweep report and plots written to '{OUTPUT_DIR}'")

if __name__ == "__main__":
    main()
