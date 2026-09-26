#include "config.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string_view>
#include <toml++/toml.hpp>

Config::Config()
{
    namespace fs = std::filesystem;
    fs::path p{fs::current_path() / "config.toml"};
    if (!fs::exists(p)) {
        const char* env_p;
        if ((env_p = std::getenv("XDG_CONFIG_HOME")) != nullptr) {
            p = fs::path{env_p} / "asym" / "config.toml";
            if (!fs::exists(p)) {
                p = fs::path{env_p} / "asym.toml";
            }
        } else if ((env_p = std::getenv("HOME")) != nullptr) {
            p = fs::path{env_p} / ".config" / "asym" / "config.toml";
            if (!fs::exists(p)) {
                p = fs::path{env_p} / ".config" / "asym.toml";
            }
        }
    }

    if (fs::exists(p)) {
        std::ifstream file{p};

        toml::table tbl = toml::parse(file, p);

        m = tbl["matrix"]["m"].value_or<uint32_t>(250);
        k = tbl["matrix"]["k"].value_or<uint32_t>(250);
        n = tbl["matrix"]["n"].value_or<uint32_t>(250);
        small_percision =
            tbl["matrix"]["small_percision"].value_or<uint32_t>(1);
        ratio = tbl["matrix"]["ratio"].value_or<uint32_t>(4);

        capacity        = tbl["fifo"]["capacity"].value_or<size_t>(14);
        generation_cost = tbl["fifo"]["generation_cost"].value_or<size_t>(10);
        accsess_cost    = tbl["fifo"]["accsess_cost"].value_or<size_t>(2);
        seed_size       = tbl["fifo"]["seed_size"].value_or<uint32_t>(1);

        tile_h = tbl["multiplication"]["tile_h"].value_or<size_t>(m / 2);
        tile_w = tbl["multiplication"]["tile_w"].value_or<size_t>(n / 2);

        std::string_view b_source_str =
            tbl["multiplication"]["b_source"].value_or<std::string_view>(
                "memory");
        if (b_source_str == "memory") {
            b_source = BSource::memory;
        } else if (b_source_str == "fifo") {
            b_source = BSource::fifo;
        }

        block_size = tbl["cache"]["block_size"].value_or<int>(6);
        mem_cycles = tbl["cache"]["mem_cycles"].value_or<int>(100);
        l1_size    = tbl["cache"]["l1_size"].value_or<int>(14);
        l1_cycles  = tbl["cache"]["l1_cycles"].value_or<int>(4);
        l1_assoc   = tbl["cache"]["l1_assoc"].value_or<int>(3);
        l2_size    = tbl["cache"]["l2_size"].value_or<int>(16);
        l2_cycles  = tbl["cache"]["l2_cycles"].value_or<int>(20);
        l2_assoc   = tbl["cache"]["l2_assoc"].value_or<int>(3);

        write_alloc = tbl["cache"]["write_alloc"].value_or<bool>(false);

        config_found = true;
    }
}
Config& gConfig()
{
    static Config config{};
    return config;
}

bool Config::is_found() const
{
    return config_found;
}
