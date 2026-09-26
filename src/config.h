#ifndef CONFIG_H_
#define CONFIG_H_

#include "multi_unit.h"

class Config
{
    friend Config& gConfig();
    using BSource = MultiUnit::BSource;

  public:
    // matrix factory options
    uint32_t m               = 250;
    uint32_t k               = 250;
    uint32_t n               = 250;
    uint32_t small_percision = 1;
    uint32_t ratio           = 4;

    // prnf fifo options
    size_t capacity        = 14;
    size_t generation_cost = 10;
    size_t accsess_cost    = 2;
    uint32_t seed_size     = 1;

    // multi unit options
    size_t tile_h{m / 2};
    size_t tile_w{n / 2};
    BSource b_source = BSource::memory;

    // cache unit options
    int block_size   = 6;
    int mem_cycles   = 100;
    int l1_size      = 14;
    int l1_cycles    = 4;
    int l1_assoc     = 3;
    int l2_size      = 16;
    int l2_cycles    = 20;
    int l2_assoc     = 3;
    bool write_alloc = false;

    bool is_found() const;

  private:
    bool config_found = false;

    Config();
};

Config& gConfig();

#endif
