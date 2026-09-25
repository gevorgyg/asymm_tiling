#include "matrix_factory.h"
#include "multi_unit.h"
#include "registry.h"

#include <fmt/format.h>
#include <spdlog/async.h>
#include <spdlog/sinks/ansicolor_sink.h>
#include <spdlog/spdlog.h>

int main(int argc, char* argv[])
{
    // init logger
    spdlog::init_thread_pool(8192, 1);
    std::shared_ptr<spdlog::logger> bg_console_logger =
        spdlog::create_async<spdlog::sinks::ansicolor_stdout_sink_mt>(
            "b_console_logger");
    spdlog::set_default_logger(bg_console_logger);
    spdlog::info("Initialized Async Logger");

    // create matrices
    MatrixFactory mat_factory{100, 100, 100, 1, 4};
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
