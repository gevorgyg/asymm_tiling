#include "matrix_factory.h"
#include "multi_unit.h"

#include <fmt/printf.h>
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
    MultiUnit m{CacheUnit{6, 100, 14, 4, 3, 16, 20, 3, true},
                mat_factory.create_memory_source(), 25, 25};

    // start simulation
    m.weight_stat_mul();

    fmt::printf("\n--- SIMULATION RESULTS ---\n");
    fmt::printf("L1 Miss Rate: %.4f%%\n",
                m.cache().calc_L1_miss_rate() * 100.0);
    fmt::printf("L2 Miss Rate: %.4f%%\n",
                m.cache().calc_L2_miss_rate() * 100.0);
    fmt::printf("Avg Access Time: %.2f cycles\n",
                m.cache().calc_avg_access_time());

    return 0;
}
