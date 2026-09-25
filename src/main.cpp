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
    using super = CLI::App;

    using BSource = MultiUnit::BSource;

    BSource b_source = BSource::memory;

    const std::map<std::string, BSource> b_source_map{
        {"memory", MultiUnit::BSource::memory},
        {"mem", MultiUnit::BSource::memory},
        {"m", MultiUnit::BSource::memory},
        {"fifo", MultiUnit::BSource::fifo},
        {"f", MultiUnit::BSource::fifo},
    };

    explicit MyOptions(std::string app_description = "",
                       std::string app_name        = "")
        : App(app_description, app_name)
    {
        add_option("-B, --BSource", b_source,
                   "Choose B elemnt source between memory or prng fifo")
            ->transform(
                CLI::CheckedTransformer(b_source_map, CLI::ignore_case));
    }
};

int main(int argc, char* argv[])
{
    spdlog::info("Initialized Logger");

    // create matrices
    MatrixFactory mat_factory{1000, 1000, 1000, 1, 4};
    const size_t tile_w = 25, tile_h = 25;

    MultiUnit m{
        std::move(CacheUnit{6, 100, 14, 4, 3, 16, 20, 3, true}),
        std::move(PrngFifo{14, 10, 2, 8}),
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
