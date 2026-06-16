import subprocess
import re
import sys

EXECUTABLE = "./asymm"

def run_test_trace(config_file, trace_file, prng=False, fifo=False):
    cmd = [EXECUTABLE, "--config", config_file, "--trace_input", trace_file]
    if prng:
        cmd.append("--Bgenerated")
    if fifo:
        cmd.append("--Bfifo")
    # Add dummy dimensions (required by argv positional parsing)
    cmd.extend(["16", "16", "16"])
    
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    stdout = res.stdout
    
    # Parse stats
    stats = {}
    
    # L1 Stats
    l1_section = re.search(r"--- L1 ---\nHit rate:\s+([\d.]+)\nTagLookup:\s+(\d+)\nLineFill:\s+(\d+)\nEvict:\s+(\d+)", stdout)
    if l1_section:
        stats["l1_hit_rate"] = float(l1_section.group(1))
        stats["l1_tag_lookup"] = int(l1_section.group(2))
        stats["l1_line_fill"] = int(l1_section.group(3))
        stats["l1_evict"] = int(l1_section.group(4))
        
    # L2 Stats
    l2_section = re.search(r"--- L2 ---\nHit rate:\s+([\d.]+)\nTagLookup:\s+(\d+)\nLineFill:\s+(\d+)\nEvict:\s+(\d+)", stdout)
    if l2_section:
        stats["l2_hit_rate"] = float(l2_section.group(1))
        stats["l2_tag_lookup"] = int(l2_section.group(2))
        stats["l2_line_fill"] = int(l2_section.group(3))
        stats["l2_evict"] = int(l2_section.group(4))

    # PRNG FIFO Stats
    fifo_section = re.search(r"--- PRNG FIFO ---\nStarts:\s+(\d+)\nStops:\s+(\d+)\nReads:\s+(\d+)\nStalls:\s+(\d+)\nStallCycles:\s+(\d+)\nGenerates:\s+(\d+)", stdout)
    if fifo_section:
        stats["fifo_starts"] = int(fifo_section.group(1))
        stats["fifo_stops"] = int(fifo_section.group(2))
        stats["fifo_reads"] = int(fifo_section.group(3))
        stats["fifo_stalls"] = int(fifo_section.group(4))
        stats["fifo_stall_cycles"] = int(fifo_section.group(5))
        stats["fifo_generates"] = int(fifo_section.group(6))

    cycles_match = re.search(r"\nCycles:\s+(\d+)", stdout)
    if cycles_match:
        stats["cycles"] = int(cycles_match.group(1))
        
    return stats

# Test Cases
test_cases = [
    {
        "name": "Compulsory Read Misses & Hits (read_compulsory.trace)",
        "config": "tests/configs/test_base.conf",
        "trace": "tests/traces/read_compulsory.trace",
        "expected": {
            "l1_hit_rate": 0.500,
            "l1_tag_lookup": 8,
            "l1_line_fill": 4,
            "l1_evict": 0
        }
    },
    {
        "name": "Write-Through No-Allocate Policy (write_through.trace)",
        "config": "tests/configs/write_through.conf",
        "trace": "tests/traces/write_through.trace",
        "expected": {
            "l1_hit_rate": 0.500,
            "l1_tag_lookup": 4,
            "l1_line_fill": 1,
            "l1_evict": 0
        }
    },
    {
        "name": "Write-Back + Write-Allocate Policy (write_back.trace)",
        "config": "tests/configs/write_back.conf",
        "trace": "tests/traces/write_back.trace",
        "expected": {
            "l1_hit_rate": 0.667,
            "l1_tag_lookup": 3,
            "l1_line_fill": 1,
            "l1_evict": 0
        }
    },
    {
        "name": "Write-Back Capacity Eviction and Writebacks (capacity_evict.trace)",
        "config": "tests/configs/write_back.conf",
        "trace": "tests/traces/capacity_evict.trace",
        "expected": {
            "l1_hit_rate": 0.000,
            "l1_tag_lookup": 3,
            "l1_line_fill": 3,
            "l1_evict": 1,
            "l2_tag_lookup": 4
        }
    },
    {
        "name": "MMIO PRNG FIFO Device & Stall Latency (prng_fifo_stall.trace)",
        "config": "tests/configs/test_base.conf",
        "trace": "tests/traces/prng_fifo_stall.trace",
        "fifo": True,
        "expected": {
            "fifo_starts": 1,
            "fifo_stops": 1,
            "fifo_reads": 3,
            "fifo_stalls": 3,
            "fifo_stall_cycles": 24,
            "fifo_generates": 3,
            "cycles": 36
        }
    }
]

failed = False

print("==================================================")
print("Running Trace-Based Functional Integration Tests...")
print("==================================================")

for tc in test_cases:
    print(f"Running test: {tc['name']}...")
    try:
        stats = run_test_trace(tc["config"], tc["trace"], fifo=tc.get("fifo", False))
        
        # Verify stats
        mismatch = False
        for key, val in tc["expected"].items():
            if stats.get(key) != val:
                print(f"  FAILED: Mismatch in '{key}'. Expected {val}, got {stats.get(key)}")
                mismatch = True
                failed = True
        if not mismatch:
            print("  PASSED!")
    except Exception as e:
        print(f"  FAILED with exception: {e}")
        failed = True

print("\nRunning test: PRNG Equivalence Self-Consistency check...")
try:
    # Generate matmul.matv first using default.config
    subprocess.run([EXECUTABLE, "--config", "default.config", "4", "4", "4"], capture_output=True, check=True)

    # Run matmul 16x16x16 with PRNG enabled vs. disabled using default config
    stats_prng = run_test_trace("default.config", "matmul.matv", prng=True)
    stats_mem = run_test_trace("default.config", "matmul.matv", prng=False)
    
    # Assert L1 hit rates and tag lookups are identical
    mismatch = False
    for key in ["l1_hit_rate", "l1_tag_lookup"]:
        if stats_prng[key] != stats_mem[key]:
            print(f"  FAILED: PRNG vs memory-mapped mismatch in '{key}'. PRNG={stats_prng[key]}, Mem={stats_mem[key]}")
            mismatch = True
            failed = True
    if not mismatch:
        print("  PASSED! Address stream access metrics are identical between PRNG and memory-mapped B.")
except Exception as e:
    print(f"  FAILED with exception: {e}")
    failed = True

print("==================================================")
if failed:
    print("Some Trace Integration Tests FAILED!")
    print("==================================================")
    sys.exit(1)
else:
    print("All Trace Integration Tests PASSED Successfully!")
    print("==================================================")
    sys.exit(0)
