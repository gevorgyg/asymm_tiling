#include "instruction-stream-generator/instgen.h"
#include "interpreter/interpeter.h"
#include "memory-system/cache/cache.h"
#include "memory-system/hierarchy.h"
#include "utils.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>

constexpr char instruction_path[] = "./matmul.matv";

// Global dictionary to hold configuration key-value pairs
std::map<std::string, uint> g_config;

void loadConfigFile(const std::string& path)
{
    std::ifstream infile(path);
    if (!infile.is_open()) {
        std::cerr << "Warning: Could not open config file: " << path
                  << ". Using defaults." << std::endl;
        return;
    }
    std::string line;
    while (std::getline(infile, line)) {
        // Remove trailing carriage returns/whitespace
        if (!line.empty() && line.back() == '\r')
            line.pop_back();
        if (line.empty() || line[0] == '#')
            continue;

        std::size_t sep = line.find('=');
        if (sep == std::string::npos)
            continue;

        std::string key     = line.substr(0, sep);
        std::string val_str = line.substr(sep + 1);

        std::stringstream ss(val_str);
        uint val;
        if (ss >> val) {
            g_config[key] = val;
        }
    }
}

// Helper function to get config values with fallback defaults
uint getConfig(const std::string& key, uint default_val)
{
    auto it = g_config.find(key);
    if (it != g_config.end()) {
        return it->second;
    }
    return default_val;
}

void generateInstructions(uint m, uint n, uint k)
{
    uint a_h  = getConfig("A_HEIGHT_DIM", 100);
    uint a_w  = getConfig("A_WIDTH_DIM", 100);
    uint a_pw = getConfig("A_PRECISION_BYTES", 8);
    uint b_pw = getConfig("B_PRECISION_BYTES", 2);

    Addr a_addr = 1024;
    CACHESIM_ALIGN(a_addr, g_page_size);
    InstGenerator::GhostMat A{a_w, a_h, a_pw, a_addr};

    Addr b_addr = A.total_byte_size;
    CACHESIM_ALIGN(b_addr, g_page_size);
    InstGenerator::GhostMat B{a_w, a_w, b_pw, b_addr};

    InstGenerator gen{A, B};

    std::ofstream ofs(instruction_path);
    if (!ofs.is_open()) {
        std::cerr << "error opening file" << std::endl;
    }

    InstGenerator::TileShape tile{m, n, k};
    gen.generate(tile, ofs);
}

void generatePrngInstructions(uint m, uint n, uint k)
{
    uint a_h  = getConfig("A_HEIGHT_DIM", 100);
    uint a_w  = getConfig("A_WIDTH_DIM", 100);
    uint a_pw = getConfig("A_PRECISION_BYTES", 8);
    uint b_w  = getConfig("B_WIDTH_DIM", 100);
    uint b_pw = getConfig("B_PRECISION_BYTES", 2);

    InstGenerator::GhostMat A{a_w, a_h, a_pw, 0};
    InstGenerator::GhostMat B{b_w, a_w, b_pw, 0};
    InstGenerator gen{A, B};

    std::ofstream ofs(instruction_path);
    if (!ofs.is_open()) {
        std::cerr << "error opening file" << std::endl;
    }

    InstGenerator::TileShape tile{m, n, k};
    gen.generatePrng(tile, ofs);
}

int main(int argc, char* argv[])
{
    bool b_generated = false;
    uint dims[3];
    int positional = 0;
    std::string trace_file_path;
    std::string config_file_path = "";

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--Bgenerated") {
            b_generated = true;
        } else if (arg == "--trace_file") {
            if (i + 1 >= argc) {
                std::cerr << "--trace_file requires a filename" << std::endl;
                exit(1);
            }
            trace_file_path = argv[++i];
        } else if (arg == "--config") {
            if (i + 1 >= argc) {
                std::cerr << "--config requires a configuration filename"
                          << std::endl;
                exit(1);
            }
            config_file_path = argv[++i];
        } else if (positional < 3) {
            dims[positional++] = std::atoi(argv[i]);
        } else {
            std::cerr << "unexpected argument: " << arg << std::endl;
            exit(1);
        }
    }

    if (positional != 3) {
        std::cerr << "usage: " << argv[0]
                  << " [--Bgenerated] [--trace_file <file>] [--config <file>] "
                     "<m> <n> <k>"
                  << std::endl;
        exit(1);
    }

    // Load config variables if file parameter is given
    if (!config_file_path.empty()) {
        loadConfigFile(config_file_path);
    }

    // Dynamically assign parameters from our configuration file or map
    MemoryHierarchy::Parameters mp{

        .l1               = {.name      = "L1",
                             .size      = getConfig("L1_SIZE_BYTES", 256),
                             .line_size = getConfig("L1_LINE_SIZE_BYTES", 16),
                             .assoc     = getConfig("L1_ASSOC", 4)},
        .l1_access_cycles = getConfig("L1_ACCESS_CYCLES", 4),

        .l2 = {.name      = "L2",
               .size      = getConfig("L2_SIZE_BYTES", 1024),
               .line_size = getConfig("L2_LINE_SIZE_BYTES",
                                      16), // usually matches L1 line size
               .assoc     = getConfig("L2_ASSOC", 8)},
        .l2_access_cycles = getConfig("L2_ACCESS_CYCLES", 15),

        .mem_access_cycles = getConfig("MEM_ACCESS_CYCLES", 180),

    };

    size_t cpu_cycles = 0;
    MemoryHierarchy mem(mp, cpu_cycles);

    if (b_generated) {
        generatePrngInstructions(dims[0], dims[1], dims[2]);
    } else {
        generateInstructions(dims[0], dims[1], dims[2]);
    }

    Interpeter inter(instruction_path, mem, trace_file_path, cpu_cycles);

    std::cout << "----------------------------" << std::endl;
    std::cout << dims[0] << ' ' << dims[1] << ' ' << dims[2] << std::endl;
    std::cout << "----------------------------" << std::endl;

    inter.run();

    const Cache::Stats& s = mem.l1().stats();
    const size_t total    = s.hits + s.misses;
    const double hit_rate = total ? (double)s.hits / (double)total : 0.0;

    printf("--- %s ---\n", mem.l1().name());
    printf("Hit rate:  %.03f\n", hit_rate);
    printf("TagLookup: %llu\n", (unsigned long long)s.tag_lookups);
    printf("LineFill:  %llu\n", (unsigned long long)s.line_fills);
    printf("Evict:     %llu\n", (unsigned long long)s.evicts);

    const Cache::Stats& s2 = mem.l2().stats();
    const size_t total2    = s2.hits + s2.misses;
    const double hit_rate2 = total2 ? (double)s2.hits / (double)total2 : 0.0;
    printf("--- %s ---\n", mem.l2().name());
    printf("Hit rate:  %.03f\n", hit_rate2);
    printf("TagLookup: %llu\n", (unsigned long long)s2.tag_lookups);
    printf("LineFill:  %llu\n", (unsigned long long)s2.line_fills);
    printf("Evict:     %llu\n", (unsigned long long)s2.evicts);

    return 0;
}
