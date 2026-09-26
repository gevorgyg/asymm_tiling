#include "CLI/CLI.hpp"
#include "matrix_factory.h"
#include "multi_unit.h"
#include "registry.h"

#include <CLI/CLI.hpp>
#include <fmt/format.h>
#include <map>
#include <spdlog/spdlog.h>

using BSource = MultiUnit::BSource;

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
                       std::string app_name        = "")
        : App(app_description, app_name)
    {
        add_option("-o, --oriantation", mult_oriantation,
                   "choose between output stationary, or weight stationary")
            ->transform(
                CLI::CheckedTransformer(oriantation_map, CLI::ignore_case));

        add_option("-m, --matrix-height", m, "choose matrix height dimantion");
        add_option("-k, --inner-dimantion", k, "choose inner dimantion");
        add_option("-n, --matrix-width", n, "choose matrix width dimantion");

        add_option("-p, --small-percision", small_percision,
                   "choose percision of low percision matrix")
            ->check(CLI::IsMember({1, 2, 4, 8}));

        add_option(
            "-r, --ratio", ratio,
            "choose ratio between low and high percision elements (high / low)")
            ->check([this](const std::string& input) {
                int input_int = std::atoi(input.c_str());
                if (this->small_percision * input_int <= 8) {
                    return std::string("");
                }
                std::string ret =
                    "Ratio must keep the high percision matrix at "
                    "percision smaller than 8 bytes. Try: ";
                int sp = this->small_percision;
                int r  = 1;
                do {
                    sp *= r;
                    ret += std::to_string(r);
                    if (sp < 8) {
                        ret += " or";
                    }
                    ret += " ";
                    r += 1;
                } while (sp < 8);
                ret += "instead :)";
                return ret;
            });

        add_option("--fc, --fifo-capacity", capacity, "choose fifo capacity");

        add_option("--fg, --fifo-gencost", generation_cost,
                   "choose fifo generation cost");

        add_option("--fa, --fifo-access", accsess_cost,
                   "choose access cost for elements of the prng fifo");

        add_option("-s, --seed-size", seed_size,
                   "choose percision of the seeds")
            ->check(CLI::IsMember({1, 2, 4, 8}));

        add_option("--th, --tile-height", tile_h, "choose height of tiles")
            ->check([this](const std::string& input) {
                if (std::atoi(input.c_str()) <= this->m) {
                    return std::string("");
                }
                std::string ret =
                    "tile height must be smaller than matrix height: ";
                ret += std::to_string(this->m);
                return ret;
            });

        add_option("--tw, --tile-width", tile_w, "choose width of tiles")
            ->check([this](const std::string& input) {
                if (std::atoi(input.c_str()) <= this->n) {
                    return std::string("");
                }
                std::string ret =
                    "tile width must be smaller than matrix width: ";
                ret += std::to_string(this->n);
                return ret;
            });

        add_option("-B, --BSource", b_source,
                   "Choose B elemnt source between memory or prng fifo")
            ->transform(
                CLI::CheckedTransformer(b_source_map, CLI::ignore_case));

        add_option("-c, --cache", cache_options,
                   "set cache options in units of log2 [ block_size, "
                   "mem_cycles, l1_size, l1_cycles, "
                   "l1_assoc, l2_size, l2_cycles, l2_assoc ]");

        auto [block_size, mem_cycles, l1_size, l1_cycles, l1_assoc, l2_size,
              l2_cycles, l2_assoc] = cache_options;

        add_flag("-w, --write-allocate, --no-write-allocate{false}",
                 write_alloc, "set write allocate");
    }

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

int main(int argc, char* argv[])
{
    MyOptions options{"asymm tiling options", "asymm tiling"};
    CLI11_PARSE(options, argc, argv);

    spdlog::info("Asymm Matrix Multiplication Log Start");

    // create matrices
    MatrixFactory mat_factory{options.m, options.k, options.n,
                              options.small_percision, options.ratio};
    const size_t tile_w = 25, tile_h = 25;

    MultiUnit m{
        CacheUnit{options.block_size, options.mem_cycles, options.l1_size,
                  options.l1_cycles, options.l1_assoc, options.l2_size,
                  options.l2_cycles, options.l2_assoc, options.write_alloc},
        PrngFifo{options.capacity, options.generation_cost,
                 options.accsess_cost, options.seed_size},
        mat_factory.create_mats(),
        options.tile_w,
        options.tile_h,
        options.b_source,
    };

    // start simulation
    if (options.mult_oriantation) {
        m.output_stat_matmul();
    } else {
        m.weight_stat_matmul();
    }

    gRegistry().dump();

    return 0;
}
