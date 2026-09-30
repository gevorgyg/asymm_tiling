#include "multi_unit.h"
#include "my_options.h"
#include "registry.h"

#include <CLI/CLI.hpp>
#include <fmt/format.h>
#include <gtest/gtest.h>
#include <spdlog/spdlog.h>

int main(int argc, char* argv[])
{
    MyOptions options{"asymm tiling options", "asymm tiling"};

    // apply config from file
    options.apply_config(gConfig());

    // overwrite things given from CLI
    CLI11_PARSE(options, argc, argv);
    options.post_parse();

    spdlog::info("Asymm Matrix Multiplication Log Start");

    MultiUnit m{options};

    // start simulation
    m.run();

    gRegistry().dump();

    return 0;
}
