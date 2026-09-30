cmake_minimum_required(VERSION 3.16)
project(sim CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(spdlog REQUIRED)
find_package(fmt REQUIRED)
find_package(CLI11 REQUIRED)

# everything except main.cpp, so tests can link the simulator without its main
add_library(simcore STATIC)

target_sources(simcore PRIVATE src/cachesim.h
                               src/cachesim.cpp
                               src/my_utils.h
                               src/my_utils.cpp
                               src/matrix_factory.h
                               src/matrix_factory.cpp
                               src/multi_unit.h
                               src/multi_unit.cpp
                               src/prngfifo.h
                               src/prngfifo.cpp
                               src/registry.cpp
                               src/registry.h
                               src/my_options.cpp
                               src/my_options.h
                               src/config.cpp
                               src/config.h
)

target_include_directories(simcore PUBLIC src)

target_link_libraries(simcore PUBLIC
    spdlog::spdlog
    fmt::fmt
    CLI11::CLI11
)

target_precompile_headers(simcore PUBLIC
        <spdlog/spdlog.h>
        <fmt/format.h>
        <CLI/CLI.hpp>
        <toml++/toml.hpp>
)

add_executable(${PROJECT_NAME} src/main.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE simcore)

# trace-driven cache driver used by the python differential tests (tests/)
add_executable(cache_driver tests/cache_driver.cpp)
target_link_libraries(cache_driver PRIVATE simcore)
