#pragma once

#include "utils.h"

#include <string>


// Parsed `default.config` (or a user-supplied file). The single source of
// truth for hardware/workload parameters in this run. Built once in main()
// and passed by const-ref to every consumer; nothing else owns global state.

struct CacheConfig {
    uint        size_bytes;
    uint        line_size_bytes;
    uint        assoc;
    uint        access_cycles;
    std::string replacement_policy;   // "LRU" | "FIFO"
    std::string write_policy;         // "WRITE_THROUGH" | "WRITE_BACK"
};

struct Config {
    // Matrix
    uint a_height;
    uint a_width;
    uint b_width;
    uint a_precision;
    uint b_precision;

    // Cache tile dimensions (elements). With --3dreg, register tile below
    // further subdivides each cache tile.
    uint tile_m;
    uint tile_n;
    uint tile_k;

    // Memory hierarchy
    CacheConfig l1;
    CacheConfig l2;
    uint mem_access_cycles;

    // PRNG (on-demand line generator) -- used only with --Bsource prng_mem
    uint prng_access_cycles;
    uint prng_gen_cost_per_line;

    // PRNG FIFO (cycle-accurate MMIO generator) -- used only with --Bsource prng_fifo
    uint prng_fifo_capacity;
    uint prng_fifo_gen_cost;
    uint prng_fifo_seed_bytes;   // bytes of seed stored per B tile
    uint prng_fifo_num_prefill;  // parallel prefill buffers (pipelined only; 0 → default 1)

    // Hardware register tile -- used only with --3dreg.
    uint reg_m = 0;
    uint reg_n = 0;
    uint reg_k = 0;

    // Per-tmulac compute cost -- recorded by default, suppressed by --mulac_norecord.
    uint mulac_cycles = 0;
};

// Load Config from a file. If the file is missing, writes the default file
// to `path` first and then loads it. Missing required keys are hard errors.
Config loadConfig(const std::string& path);
