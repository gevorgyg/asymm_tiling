cmake_minimum_required(VERSION 3.16)
project(sim CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(spdlog REQUIRED)
find_package(fmt REQUIRED)
find_package(CLI11 REQUIRED)

add_executable(${PROJECT_NAME} src/main.cpp)

target_sources(${PROJECT_NAME} PRIVATE src/cachesim.h src/cachesim.cpp src/my_utils.h src/my_utils.cpp)

target_link_libraries(${PROJECT_NAME} spdlog::spdlog fmt::fmt CLI11::CLI11)

target_precompile_headers(${PROJECT_NAME} PRIVATE
        <spdlog/spdlog.h>
        <spdlog/async.h>
        <fmt/format.h>
)
