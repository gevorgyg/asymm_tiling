#ifndef MY_OPTIONS_H_
#define MY_OPTIONS_H_

#include "config.h"
#include "multi_unit.h"

struct MyOptions : public CLI::App {
    using super   = CLI::App;
    using BSource = MultiUnit::BSource;
    enum oriantation { output, weight };

    // multiplication options
    oriantation mult_oriantation = weight;

    // matrix factory options
    uint32_t m;
    uint32_t k;
    uint32_t n;
    uint32_t small_percision;
    uint32_t ratio;

    // prnf fifo options
    size_t capacity;
    size_t generation_cost;
    size_t accsess_cost;
    uint32_t seed_size;

    // multi unit options
    size_t tile_h;
    size_t tile_w;
    BSource b_source;

    // cache unit options
    int block_size;
    int mem_cycles;
    int l1_size;
    int l1_cycles;
    int l1_assoc;
    int l2_size;
    int l2_cycles;
    int l2_assoc;
    bool write_alloc;

    explicit MyOptions(std::string app_description = "",
                       std::string app_name        = "");

    void apply_config(const Config& config);

    void post_parse();

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
