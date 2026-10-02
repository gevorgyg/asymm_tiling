#ifndef MY_OPTIONS_H_
#define MY_OPTIONS_H_

#include "config.h"

struct MyOptions : public CLI::App {
    using super = CLI::App;
    enum oriantation { output, weight };

    // multiplication options
    oriantation mult_oriantation = weight;

    // matrix factory options
    uint32_t m;
    uint32_t k;
    uint32_t n;
    uint32_t small_percision;
    uint32_t ratio;
    bool aligned;

    // prnf fifo options
    size_t capacity;
    size_t generation_cost;
    size_t accsess_cost;
    uint32_t seed_size;

    // multi unit options
    size_t tile_h;
    size_t tile_w;
    BSource b_source;
    size_t reg_dim;
    size_t mulacc_cost;

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
    ReplPolicy policy;

    explicit MyOptions(std::string app_description = "",
                       std::string app_name        = "");

    void apply_config(const Config& config);

  private:
    std::array<int, 8> cache_options;

    // run by CLI11 at the end of parsing (see final_callback in the ctor)
    void post_parse();

    // throws CLI::ValidationError, reported by CLI11_PARSE like any bad flag
    void validate_cache() const;

    const std::map<std::string, oriantation> oriantation_map{
        {"output", output}, {"out", output}, {"o", output},
        {"C", output},      {"c", output},   {"weight", weight},
        {"w", weight},      {"B", weight},   {"b", weight},
    };

    const std::map<std::string, BSource> b_source_map{
        {"memory", BSource::memory}, {"mem", BSource::memory},
        {"m", BSource::memory},      {"fifo", BSource::fifo},
        {"f", BSource::fifo},
    };

    const std::map<std::string, ReplPolicy> policy_map{
        {"lru", ReplPolicy::lru},
        {"fifo", ReplPolicy::fifo},
        {"mru", ReplPolicy::mru},
        {"random", ReplPolicy::random},
    };
};

#endif
