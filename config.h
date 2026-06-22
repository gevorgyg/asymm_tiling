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

    // Memory hierarchy
    CacheConfig l1;
    CacheConfig l2;
    uint mem_access_cycles;

    // PRNG (on-demand line generator)
    uint prng_access_cycles;
    uint prng_gen_cost_per_line;

    // PRNG FIFO (cycle-accurate MMIO generator)
    uint prng_fifo_capacity;
    uint prng_fifo_gen_cost;

    // Hardware register tile. Zero in any dimension disables register
    // tiling (interpreter falls back to scalar element-by-element loads).
    uint reg_m = 0;
    uint reg_n = 0;
    uint reg_k = 0;

    // Per-tmulac compute cost. Zero means "don't charge anything".
    uint mulac_cycles = 0;

    // Scratchpad settings (optional)
    uint sp_banks = 8;
    uint sp_word_size_bytes = 8;
};

// Load Config from a file. If the file is missing, writes the default file
// to `path` first and then loads it. Missing required keys are hard errors.
Config loadConfig(const std::string& path);
