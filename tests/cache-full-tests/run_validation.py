#!/usr/bin/env python3
import os
import re
import struct
import subprocess
import sys

# Paths
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHAMPSIM_DIR = os.path.join(WORKSPACE_DIR, "tests", "cache-full-tests", "ChampSim")
CONFIG_JSON = os.path.join(WORKSPACE_DIR, "tests", "cache-full-tests", "champsim_config.json")
RAW_TRACE_PATH = os.path.join(WORKSPACE_DIR, "raw.trace")
BINARY_TRACE_PATH = os.path.join(WORKSPACE_DIR, "tmp.champsimtrace")

def run_cmd(cmd, cwd=WORKSPACE_DIR, check=True):
    print(f"Running: {' '.join(cmd)} in {cwd}")
    result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and result.returncode != 0:
        print(f"Error executing command: {' '.join(cmd)}")
        print("STDOUT:")
        print(result.stdout)
        print("STDERR:")
        print(result.stderr)
        sys.exit(result.returncode)
    return result

def patch_champsim():
    print("=== Checking and patching ChampSim ===")
    
    # 1. Patch ooo_cpu.cc to disable store-to-load forwarding
    ooo_cpu_path = os.path.join(CHAMPSIM_DIR, "src", "ooo_cpu.cc")
    if os.path.exists(ooo_cpu_path):
        with open(ooo_cpu_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if "/* Disable store forwarding" not in content:
            print("Patching ooo_cpu.cc to disable store forwarding...")
            import re
            pattern = re.compile(
                r"(\s*)// Check for forwarding(\s+auto sq_it = std::max_element.*?\n\s*\}\n\s*\})" ,
                re.DOTALL
            )
            match = pattern.search(content)
            if match:
                indent = match.group(1)
                body = match.group(2)
                replacement = f"{indent}/* Disable store forwarding to match simple trace-driven cache simulation{body}\n{indent}*/"
                content = content[:match.start()] + replacement + content[match.end():]
                with open(ooo_cpu_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print("Successfully patched ooo_cpu.cc")
            else:
                print("Warning: Could not find forwarding block in ooo_cpu.cc")
        else:
            print("ooo_cpu.cc is already patched")
            
    # 2. Patch lru.cc to update LRU on writeback hits
    lru_path = os.path.join(CHAMPSIM_DIR, "replacement", "lru", "lru.cc")
    if os.path.exists(lru_path):
        with open(lru_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        target = "if (hit && access_type{type} != access_type::WRITE) // Skip this for writeback hits"
        replacement = "if (hit)"
        if target in content:
            print("Patching lru.cc to update LRU on writeback hits...")
            content = content.replace(target, replacement)
            with open(lru_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("Successfully patched lru.cc")
        elif "if (hit)" in content:
            print("lru.cc is already patched")
        else:
            print("Warning: Could not find LRU update condition in lru.cc")

def compile_our_simulator():
    print("=== Compiling our simulator ===")
    run_cmd(["make", "clean"])
    run_cmd(["make"])

def generate_our_trace(m, n, k):
    print(f"=== Generating simulator trace for matrix size {m}x{n}x{k} ===")
    # Run without PRNG / FIFO to ensure it is standard cache-able accesses
    cmd = ["./asymm", "--trace_file", "raw.trace", "--trace_level", "1", str(m), str(n), str(k)]
    result = run_cmd(cmd)
    
    # Parse our simulator's output stats
    l1_stats = {"accesses": 0, "misses": 0, "hits": 0}
    l2_stats = {"accesses": 0, "misses": 0, "hits": 0}
    
    current_cache = None
    for line in result.stdout.splitlines():
        if "--- L1 ---" in line:
            current_cache = "L1"
        elif "--- L2 ---" in line:
            current_cache = "L2"
        elif "---" in line:
            current_cache = None
            
        if current_cache == "L1":
            if "TagLookup:" in line:
                l1_stats["accesses"] = int(line.split()[-1])
            elif "LineFill:" in line:
                l1_stats["misses"] = int(line.split()[-1])
        elif current_cache == "L2":
            if "TagLookup:" in line:
                l2_stats["accesses"] = int(line.split()[-1])
            elif "LineFill:" in line:
                l2_stats["misses"] = int(line.split()[-1])
                
    l1_stats["hits"] = l1_stats["accesses"] - l1_stats["misses"]
    l2_stats["hits"] = l2_stats["accesses"] - l2_stats["misses"]
    
    return l1_stats, l2_stats

def convert_trace():
    print("=== Converting text trace to ChampSim binary trace ===")
    # ChampSim struct input_instr layout:
    #   unsigned long long ip;                      (Q)
    #   unsigned char is_branch;                    (B)
    #   unsigned char branch_taken;                 (B)
    #   unsigned char destination_registers[2];     (2B)
    #   unsigned char source_registers[4];          (4B)
    #   unsigned long long destination_memory[2];   (2Q)
    #   unsigned long long source_memory[4];        (4Q)
    # Layout format string: '<QBB2B4B2Q4Q'
    
    trace_re = re.compile(r"^\s*(read|write)\s+@0x([0-9a-fA-F]+)")
    
    dummy_ip = 0x1000
    is_branch = 0
    branch_taken = 0
    dest_regs = (0, 0)
    src_regs = (0, 0, 0, 0)
    
    num_accesses = 0
    num_filtered = 0
    
    with open(RAW_TRACE_PATH, "r") as infile, open(BINARY_TRACE_PATH, "wb") as outfile:
        for line in infile:
            m = trace_re.match(line)
            if not m:
                continue
                
            op, addr_hex = m.groups()
            addr = int(addr_hex, 16)
            is_write = (op == "write")
            
            # Filter out scratchpad and FIFO MMIO addresses
            # Scratchpad: 0x20000000 to 0x4FFFFFFF
            # FIFO MMIO: 0xFF000000 to 0xFF100008
            if (0x20000000 <= addr < 0x50000000) or (0xFF000000 <= addr < 0xFF100008):
                num_filtered += 1
                continue
                
            num_accesses += 1
            
            # Offset the address by 0x1000 (one page size) to avoid address 0x0,
            # which ChampSim's trace reader treats as "no access".
            # Adding a page-aligned offset preserves page-boundaries, DTLB mapping, 
            # and cache set indexing.
            offset_addr = addr + 0x1000
            
            if is_write:
                dest_mem = (offset_addr, 0)
                src_mem = (0, 0, 0, 0)
            else:
                dest_mem = (0, 0)
                src_mem = (offset_addr, 0, 0, 0)
                
            record = struct.pack('<QBB2B4B2Q4Q', 
                                 dummy_ip, is_branch, branch_taken,
                                 *dest_regs, *src_regs,
                                 *dest_mem, *src_mem)
            outfile.write(record)
            
        # Append 5000 dummy instructions (no memory accesses) to drain the pipeline before EOF is hit
        for _ in range(5000):
            record = struct.pack('<QBB2B4B2Q4Q', 
                                 dummy_ip, is_branch, branch_taken,
                                 *dest_regs, *src_regs,
                                 0, 0,
                                 0, 0, 0, 0)
            outfile.write(record)
            
    print(f"Conversion complete. Wrote {num_accesses} cache accesses + 5000 dummy instructions. Filtered out {num_filtered} scratchpad/MMIO accesses.")
    return num_accesses

def compile_champsim():
    print("=== Compiling ChampSim ===")
    run_cmd(["./config.sh", CONFIG_JSON], cwd=CHAMPSIM_DIR)
    run_cmd(["make"], cwd=CHAMPSIM_DIR)

def run_champsim(num_accesses):
    print("=== Running ChampSim ===")
    # Run with 0 warmup instructions and simulate the actual accesses + 200 dummy instructions to drain queues
    cmd = ["bin/champsim", "--warmup-instructions", "0", "--simulation-instructions", str(num_accesses + 200), BINARY_TRACE_PATH]
    result = run_cmd(cmd, cwd=CHAMPSIM_DIR)
    print("--- CHAMPSIM STDOUT ---")
    print(result.stdout)
    print("-----------------------")
    
    champsim_l1_stats = {"accesses": 0, "misses": 0, "hits": 0}
    champsim_l2_stats = {"accesses": 0, "misses": 0, "hits": 0}
    
    for line in result.stdout.splitlines():
        if "cpu0_L1D" in line and "TOTAL" in line:
            # Format: "cpu0->cpu0_L1D TOTAL ACCESS:   1234 HIT:    900 MISS:    334 MISS_MERGE:      0"
            parts = line.split()
            champsim_l1_stats["accesses"] = int(parts[3])
            champsim_l1_stats["hits"] = int(parts[5])
            champsim_l1_stats["misses"] = int(parts[7])
        elif "cpu0_L2C" in line and "TOTAL" in line:
            parts = line.split()
            champsim_l2_stats["accesses"] = int(parts[3])
            champsim_l2_stats["hits"] = int(parts[5])
            champsim_l2_stats["misses"] = int(parts[7])
            
    return champsim_l1_stats, champsim_l2_stats

def print_comparison_table(our_l1, cs_l1, our_l2, cs_l2):
    print("\n=== VALIDATION COMPARISON ===")
    print(f"{'Metric':<25} | {'Our Simulator':<15} | {'ChampSim':<15} | {'Match?':<10}")
    print("-" * 75)
    
    def check_match(val1, val2):
        return "PASS" if val1 == val2 else "FAIL"
        
    print(f"{'L1D Total Accesses':<25} | {our_l1['accesses']:<15} | {cs_l1['accesses']:<15} | {check_match(our_l1['accesses'], cs_l1['accesses'])}")
    print(f"{'L1D Hits':<25} | {our_l1['hits']:<15} | {cs_l1['hits']:<15} | {check_match(our_l1['hits'], cs_l1['hits'])}")
    print(f"{'L1D Misses':<25} | {our_l1['misses']:<15} | {cs_l1['misses']:<15} | {check_match(our_l1['misses'], cs_l1['misses'])}")
    print("-" * 75)
    print(f"{'L2C Total Accesses':<25} | {our_l2['accesses']:<15} | {cs_l2['accesses']:<15} | {check_match(our_l2['accesses'], cs_l2['accesses'])}")
    print(f"{'L2C Hits':<25} | {our_l2['hits']:<15} | {cs_l2['hits']:<15} | {check_match(our_l2['hits'], cs_l2['hits'])}")
    print(f"{'L2C Misses':<25} | {our_l2['misses']:<15} | {cs_l2['misses']:<15} | {check_match(our_l2['misses'], cs_l2['misses'])}")
    print("-" * 75)
    
    success = (
        our_l1['accesses'] == cs_l1['accesses'] and
        our_l1['hits'] == cs_l1['hits'] and
        our_l1['misses'] == cs_l1['misses'] and
        our_l2['accesses'] == cs_l2['accesses'] and
        our_l2['hits'] == cs_l2['hits'] and
        our_l2['misses'] == cs_l2['misses']
    )
    
    if success:
        print("\n🎉 SUCCESS: All cache statistics match exactly! 🎉\n")
        return True
    else:
        print("\n❌ FAILURE: Cache statistics mismatch detected! ❌\n")
        return False

def main():
    patch_champsim()
    compile_our_simulator()
    
    # Run with a 4x4x4 matrix multiplication sweep
    our_l1, our_l2 = generate_our_trace(4, 4, 4)
    
    num_accesses = convert_trace()
    compile_champsim()
    cs_l1, cs_l2 = run_champsim(num_accesses)
    
    matched = print_comparison_table(our_l1, cs_l1, our_l2, cs_l2)
    
    # Clean up temporary trace files on success
    if matched:
        print("Cleaning up temporary trace files...")
        if os.path.exists(RAW_TRACE_PATH):
            os.remove(RAW_TRACE_PATH)
        if os.path.exists(BINARY_TRACE_PATH):
            os.remove(BINARY_TRACE_PATH)

    sys.exit(0 if matched else 1)

if __name__ == "__main__":
    main()
