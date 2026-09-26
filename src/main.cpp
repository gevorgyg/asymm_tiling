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

    explicit MyOptions(std::string app_description = "",
                       std::string app_name        = "")
        : App(app_description, app_name)
    {

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
    }

  private:
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
    MyOptions parser{"asymm tiling options", "asymm tiling"};
    parser.parse(argc, argv);

    spdlog::info("Initialized Logger");

    // create matrices
    MatrixFactory mat_factory{100, 100, 100, 1, 4};
    const size_t tile_w = 25, tile_h = 25;

    MultiUnit m{
        CacheUnit{6, 100, 14, 4, 3, 16, 20, 3, true},
        PrngFifo{14, 10, 2, 8},
        mat_factory.create_mats(),
        tile_w,
        tile_h,
        MultiUnit::fifo,
    };

    // start simulation
    m.weight_stat_matmul();

    gRegistry().dump();

    return 0;
}
