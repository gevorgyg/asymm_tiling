# ChampSim Cache Validation Framework

This directory contains the automated validation framework used to verify the correctness of our cache simulator's standard hierarchy (L1D and L2C caches) against the trusted **ChampSim** simulator.

Both simulators are configured with matching cache parameters and run on identical memory traces, achieving a **100% exact match** on all access, hit, and miss statistics.

## Directory Structure

*   **`ChampSim/`**: The ChampSim simulator git submodule.
*   **`champsim_config.json`**: ChampSim's JSON configuration mapping our default simulator cache parameters.
*   **`run_validation.py`**: Automated python script that compiles both simulators, runs a matrix multiplication test trace, handles address filtering and page offsets, translates the trace to ChampSim binary format, executes ChampSim, compares the L1D/L2C stats, and cleans up.
*   **`README.md`**: This documentation.

## Running the Validation

To execute the validation workflow, run the driver script:
```bash
python3 tests/cache-full-tests/run_validation.py
```
This script will:
1. Compile our simulator (`make`).
2. Run our simulator with standard configurations to produce `raw.trace`.
3. Translate and filter out scratchpad/MMIO operations, offsetting memory addresses by `0x1000` into `tmp.champsimtrace`.
4. Compile ChampSim with our JSON configuration.
5. Run ChampSim on the binary trace.
6. Display a comparative validation table and assert that all metrics match exactly.
7. Clean up the temporary trace files on success.

## Alignment Changes Made to ChampSim

To perform a fair comparison against a simple trace-driven cache simulation model, we aligned ChampSim's CPU and replacement behaviors as follows:

### 1. Commented Out Store-to-Load Forwarding
*   **File**: [ooo_cpu.cc](file:///home/aregmk/Shortcuts/semester6/project/asymm_tiling/tests/cache-full-tests/ChampSim/src/ooo_cpu.cc#L498-L516)
*   **Reason**: ChampSim's Out-of-Order CPU model forwards store data directly to dependent loads within the pipeline (avoiding a cache access). In our simple simulator, all loads read from the cache hierarchy. Disabling store forwarding ensures every memory instruction in the trace performs an explicit cache lookup.

### 2. Addressed Address `0x0` Ignoring
*   **File**: Handled in [run_validation.py](file:///home/aregmk/Shortcuts/semester6/project/asymm_tiling/tests/cache-full-tests/run_validation.py#L106-L121)
*   **Reason**: ChampSim's trace reader uses `0` to denote empty padding slots in its fixed-width binary trace structure. As a result, memory operations to address `0x0` are discarded.
*   **Fix**: The driver script `run_validation.py` offsets all memory addresses in the binary trace by `0x1000` (one page size). This shifts all accesses off `0x0` while preserving page alignment, DTLB mapping, and set/tag indexing properties.

### 3. Enabled LRU Replacement State Updates on Writeback Hits
*   **File**: [lru.cc](file:///home/aregmk/Shortcuts/semester6/project/asymm_tiling/tests/cache-full-tests/ChampSim/replacement/lru/lru.cc#L30-L37)
*   **Reason**: ChampSim's default LRU replacement policy skips updating replacement states for writebacks (`access_type::WRITE`), as writebacks are eviction traffic rather than CPU references. Our simulator updates LRU positions on writeback hits in L2. 
*   **Fix**: Modified `lru::update_replacement_state` to always update the last used cycle on a hit (removing the `type != WRITE` filter), ensuring identical eviction candidates under both simulators.
