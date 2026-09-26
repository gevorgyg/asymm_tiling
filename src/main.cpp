#include "matrix_factory.h"
#include "multi_unit.h"
#include "my_options.h"
#include "registry.h"

#include <CLI/CLI.hpp>
#include <fmt/format.h>
#include <spdlog/spdlog.h>

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
