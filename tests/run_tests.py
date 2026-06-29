import subprocess
import sys

# Reuse the harness's markdown parser so the integration tests track the
# same output schema the production runner sees.
sys.path.insert(0, ".")
from experiments.harness.parse import parse_stdout

EXECUTABLE = "./asymm"


def run_test_trace(config_file, trace_file, prng=False, fifo=False, three_d_reg=False):
    cmd = [EXECUTABLE, "--config", config_file, "--assembler_input", trace_file]
    if prng:
        cmd += ["--Bsource", "prng_mem"]
    elif fifo:
        cmd += ["--Bsource", "prng_fifo"]
    if three_d_reg:
        cmd += ["--3dregisters"]

    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    m = parse_stdout(res.stdout)

    stats = {
        "l1_hit_rate":   m.l1.hit_rate,
        "l1_tag_lookup": m.l1.tag_lookups,
        "l1_line_fill":  m.l1.line_fills,
        "l1_evict":      m.l1.evicts,
        "l2_hit_rate":   m.l2.hit_rate,
        "l2_tag_lookup": m.l2.tag_lookups,
        "l2_line_fill":  m.l2.line_fills,
        "l2_evict":      m.l2.evicts,
        "cycles":        m.cycles,
    }
    if m.prng_fifo is not None:
        stats.update({
            "fifo_starts":       m.prng_fifo.starts,
            "fifo_stops":        m.prng_fifo.stops,
            "fifo_reads":        m.prng_fifo.reads,
            "fifo_stalls":       m.prng_fifo.stalls,
            "fifo_stall_cycles": m.prng_fifo.stall_cycles,
            "fifo_generates":    m.prng_fifo.generates,
        })
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
    },
    {
        "name": "Multi-Level Tiling Prefetch & Reg Constraints (multitile_test.trace)",
        "config": "tests/configs/multitile_test.conf",
        "trace": "tests/traces/multitile_test.trace",
        "three_d_reg": True,
        "expected": {
            "l1_hit_rate": 0.948,
            "l1_tag_lookup": 96,
            "l2_tag_lookup": 5,
            "l2_hit_rate": 0.000
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
        stats = run_test_trace(tc["config"], tc["trace"],
                                fifo=tc.get("fifo", False),
                                three_d_reg=tc.get("three_d_reg", False))
        
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
    # Generate matmul.matv first using default.config (tile dims come from config)
    subprocess.run([EXECUTABLE, "--config", "default.config"], capture_output=True, check=True)

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

print("\nRunning test: Register Size Constraints validation...")
try:
    res = subprocess.run([EXECUTABLE, "--config", "tests/configs/multitile_test.conf",
                          "--assembler_input", "tests/traces/multitile_invalid.trace",
                          "--3dregisters"], capture_output=True)
    if res.returncode != 0 and b"register %ra" in res.stderr:
        print("  PASSED! Invalid register dimension detected and rejected successfully.")
    else:
        print(f"  FAILED: Expected non-zero exit code and error message. Got code {res.returncode}, stderr: {res.stderr}")
        failed = True
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
