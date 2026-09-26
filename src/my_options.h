#ifndef MY_OPTIONS_H_
#define MY_OPTIONS_H_

#include "multi_unit.h"

struct MyOptions : public CLI::App {
    using super   = CLI::App;
    using BSource = MultiUnit::BSource;
    enum oriantation { output, weight };

    // multiplication options
    oriantation mult_oriantation = weight;

    // matrix factory options
    uint32_t m               = 100;
    uint32_t k               = 100;
    uint32_t n               = 100;
    uint32_t small_percision = 1;
    uint32_t ratio           = 4;

    // prnf fifo options
    // PrngFifo(size_t capacity, size_t generation_cost, size_t accsess_cost,
    //          size_t seed_size);
    size_t capacity        = 14;
    size_t generation_cost = 10;
    size_t accsess_cost    = 2;
    uint32_t seed_size     = 1;

    // multi unit options
    size_t tile_h{m / 2};
    size_t tile_w{n / 2};
    BSource b_source = BSource::memory;

    // CacheUnit{6, 100, 14, 4, 3, 16, 20, 3, true};

    // cache unit options
    int block_size = 6;
    int mem_cycles = 100;
    int l1_size    = 14;
    int l1_cycles  = 4;
    int l1_assoc   = 3;
    int l2_size    = 16;
    int l2_cycles  = 20;
    int l2_assoc   = 3;

    bool write_alloc = false;

    explicit MyOptions(std::string app_description = "",
                       std::string app_name        = "");

  private:
    std::array<int, 8> cache_options;

    const std::map<std::string, oriantation> oriantation_map{
        {"output", output}, {"out", output}, {"o", output},
        {"C", output},      {"c", output},   {"weight", weight},
        {"w", weight},      {"B", weight},   {"b", weight},
    };

    const std::map<std::string, BSource> b_source_map{
        {"memory", MultiUnit::BSource::memory},
        {"mem", MultiUnit::BSource::memory},
        {"m", MultiUnit::BSource::memory},
        {"fifo", MultiUnit::BSource::fifo},
        {"f", MultiUnit::BSource::fifo},
    };
};

#endif
