#include "config.h"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>


namespace {

void writeDefaultConfig(const std::string& path)
{
    std::ofstream outfile(path);
    if (!outfile.is_open()) {
        std::cerr << "error: could not create default config file at: " << path
                  << std::endl;
        exit(1);
    }
    outfile
        << "# Matrix dimensions (elements)\n"
        << "A_HEIGHT_DIM=12\n"
        << "A_WIDTH_DIM=12\n"
        << "B_WIDTH_DIM=24\n\n"
        << "# Element widths (bytes)\n"
        << "A_PRECISION_BYTES=8\n"
        << "B_PRECISION_BYTES=2\n\n"
        << "# L1 cache\n"
        << "L1_SIZE_BYTES=256\n"
        << "L1_LINE_SIZE_BYTES=8\n"
        << "L1_ASSOC=4\n"
        << "L1_ACCESS_CYCLES=4\n"
        << "L1_REPLACEMENT_POLICY=LRU\n"
        << "L1_WRITE_POLICY=WRITE_BACK\n\n"
        << "# L2 cache\n"
        << "L2_SIZE_BYTES=1024\n"
        << "L2_LINE_SIZE_BYTES=8\n"
        << "L2_ASSOC=8\n"
        << "L2_ACCESS_CYCLES=15\n"
        << "L2_REPLACEMENT_POLICY=LRU\n"
        << "L2_WRITE_POLICY=WRITE_BACK\n\n"
        << "# Main memory\n"
        << "MEM_ACCESS_CYCLES=180\n\n"
        << "# PRNG device (generates B's cache lines on demand)\n"
        << "PRNG_ACCESS_CYCLES=2\n"
        << "PRNG_GEN_COST_PER_LINE=64\n\n"
        << "# PRNG FIFO device\n"
        << "PRNG_FIFO_CAPACITY=64\n"
        << "PRNG_FIFO_GEN_COST=10\n\n"
        << "# Hardware register tile dimensions (for multi-level tiling)\n"
        << "REG_M=4\n"
        << "REG_N=4\n"
        << "REG_K=4\n\n"
        << "# tmulac computation cycles per register tile multiply-accumulate\n"
        << "MULAC_CYCLES=8\n";
    std::cout << "Config file not found. Created a default configuration at: "
              << path << std::endl;
}

// Parse the file into two parallel maps (uint values + string values, since
// some keys -- POLICY strings -- aren't numeric). Used internally; the
// public surface is the typed Config struct.
struct RawConfig {
    std::map<std::string, uint>        nums;
    std::map<std::string, std::string> strs;
};

RawConfig parseFile(const std::string& path)
{
    std::ifstream infile(path);
    if (!infile.is_open()) {
        writeDefaultConfig(path);
        infile.open(path);
        if (!infile.is_open()) {
            std::cerr << "error: could not open config file after creation: "
                      << path << std::endl;
            exit(1);
        }
    }

    RawConfig out;
    std::string line;
    while (std::getline(infile, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#')      continue;

        const std::size_t sep = line.find('=');
        if (sep == std::string::npos) continue;

        std::string key = line.substr(0, sep);
        std::string val = line.substr(sep + 1);

        const auto trim = [](std::string& s) {
            const size_t b = s.find_first_not_of(" \t");
            const size_t e = s.find_last_not_of(" \t");
            if (b == std::string::npos) { s.clear(); return; }
            s = s.substr(b, e - b + 1);
        };
        trim(key);
        trim(val);

        out.strs[key] = val;

        std::stringstream ss(val);
        uint n;
        if (ss >> n) out.nums[key] = n;
    }
    return out;
}

uint requireUint(const RawConfig& c, const char* key)
{
    auto it = c.nums.find(key);
    if (it == c.nums.end()) {
        std::cerr << "error: missing required config key: " << key << std::endl;
        exit(1);
    }
    return it->second;
}

uint optionalUint(const RawConfig& c, const char* key)
{
    auto it = c.nums.find(key);
    return it == c.nums.end() ? 0u : it->second;
}

std::string requireStr(const RawConfig& c, const char* key)
{
    auto it = c.strs.find(key);
    if (it == c.strs.end()) {
        std::cerr << "error: missing required config key: " << key << std::endl;
        exit(1);
    }
    return it->second;
}

CacheConfig loadCache(const RawConfig& c, const char* prefix)
{
    const auto k = [&](const char* suffix) {
        return std::string(prefix) + suffix;
    };
    return CacheConfig{
        .size_bytes        = requireUint(c, k("_SIZE_BYTES").c_str()),
        .line_size_bytes   = requireUint(c, k("_LINE_SIZE_BYTES").c_str()),
        .assoc             = requireUint(c, k("_ASSOC").c_str()),
        .access_cycles     = requireUint(c, k("_ACCESS_CYCLES").c_str()),
        .replacement_policy= requireStr(c, k("_REPLACEMENT_POLICY").c_str()),
        .write_policy      = requireStr(c, k("_WRITE_POLICY").c_str()),
    };
}

}  // namespace


Config loadConfig(const std::string& path)
{
    const RawConfig raw = parseFile(path);

    return Config{
        .a_height    = requireUint(raw, "A_HEIGHT_DIM"),
        .a_width     = requireUint(raw, "A_WIDTH_DIM"),
        .b_width     = requireUint(raw, "B_WIDTH_DIM"),
        .a_precision = requireUint(raw, "A_PRECISION_BYTES"),
        .b_precision = requireUint(raw, "B_PRECISION_BYTES"),

        .l1                = loadCache(raw, "L1"),
        .l2                = loadCache(raw, "L2"),
        .mem_access_cycles = requireUint(raw, "MEM_ACCESS_CYCLES"),

        .prng_access_cycles     = requireUint(raw, "PRNG_ACCESS_CYCLES"),
        .prng_gen_cost_per_line = requireUint(raw, "PRNG_GEN_COST_PER_LINE"),

        .prng_fifo_capacity = optionalUint(raw, "PRNG_FIFO_CAPACITY") == 0 ? 64 : optionalUint(raw, "PRNG_FIFO_CAPACITY"),
        .prng_fifo_gen_cost = optionalUint(raw, "PRNG_FIFO_GEN_COST") == 0 ? 10 : optionalUint(raw, "PRNG_FIFO_GEN_COST"),

        .reg_m = optionalUint(raw, "REG_M"),
        .reg_n = optionalUint(raw, "REG_N"),
        .reg_k = optionalUint(raw, "REG_K"),

        .mulac_cycles = optionalUint(raw, "MULAC_CYCLES"),

        .sp_banks = optionalUint(raw, "SP_BANKS") == 0 ? 8 : optionalUint(raw, "SP_BANKS"),
        .sp_word_size_bytes = optionalUint(raw, "SP_WORD_SIZE_BYTES") == 0 ? 8 : optionalUint(raw, "SP_WORD_SIZE_BYTES"),
    };
}
