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
std::map<std::string, std::string> g_config_str;

void createDefaultConfigFile(const std::string& path)
{
    std::ofstream outfile(path);
    if (!outfile.is_open()) {
        std::cerr << "error: could not create default config file at: " << path << std::endl;
        exit(1);
    }
    outfile << "# Matrix dimensions (elements)\n"
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
            << "PRNG_FIFO_GEN_COST=10\n";
    outfile.close();
    std::cout << "Config file not found. Created a default configuration at: " << path << std::endl;
}

void loadConfigFile(const std::string& path)
{
    std::ifstream infile(path);
    if (!infile.is_open()) {
        createDefaultConfigFile(path);
        infile.open(path);
        if (!infile.is_open()) {
            std::cerr << "error: could not open config file after creation: " << path << std::endl;
            exit(1);
        }
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

        // Trim horizontal whitespaces from key and value
        size_t key_start = key.find_first_not_of(" \t");
        size_t key_end = key.find_last_not_of(" \t");
        if (key_start != std::string::npos && key_end != std::string::npos) {
            key = key.substr(key_start, key_end - key_start + 1);
        }

        size_t val_start = val_str.find_first_not_of(" \t");
        size_t val_end = val_str.find_last_not_of(" \t");
        if (val_start != std::string::npos && val_end != std::string::npos) {
            val_str = val_str.substr(val_start, val_end - val_start + 1);
        }

        g_config_str[key] = val_str;

        std::stringstream ss(val_str);
        uint val;
        if (ss >> val) {
            g_config[key] = val;
        }
    }
}

// Get a config value. Missing keys are a hard error -- the config file is the
// single source of truth.
uint getConfig(const std::string& key)
{
    auto it = g_config.find(key);
    if (it == g_config.end()) {
        std::cerr << "error: missing required config key: " << key << std::endl;
        exit(1);
    }
    return it->second;
}

std::string getConfigStr(const std::string& key)
{
    auto it = g_config_str.find(key);
    if (it == g_config_str.end()) {
        std::cerr << "error: missing required config key: " << key << std::endl;
        exit(1);
    }
    return it->second;
}


WritePolicy parseWritePolicy(const std::string& str)
{
    if (str == "WRITE_THROUGH") {
        return WritePolicy::WRITE_THROUGH;
    } else if (str == "WRITE_BACK") {
        return WritePolicy::WRITE_BACK;
    } else {
        std::cerr << "error: unknown write policy: " << str << std::endl;
        exit(1);
    }
}

static InstGenerator makeGen()
{
    return InstGenerator{InstGenerator::Params{
        .a_height    = getConfig("A_HEIGHT_DIM"),
        .a_width     = getConfig("A_WIDTH_DIM"),
        .b_width     = getConfig("B_WIDTH_DIM"),
        .a_precision = getConfig("A_PRECISION_BYTES"),
        .b_precision = getConfig("B_PRECISION_BYTES"),
    }};
}

void generateInstructions(uint m, uint n, uint k, bool b_stationary, bool b_fifo)
{
    InstGenerator gen = makeGen();

    std::ofstream ofs(instruction_path);
    if (!ofs.is_open()) {
        std::cerr << "error opening file" << std::endl;
    }

    InstGenerator::TileShape tile{m, n, k};
    gen.generate(tile, ofs, b_stationary, b_fifo);
}

int main(int argc, char* argv[])
{
    bool b_generated = false;
    bool b_fifo = false;
    bool b_stationary = false;
    uint dims[3];
    int positional = 0;
    std::string trace_file_path;
    std::string trace_input_path = "";
    std::string config_file_path = "";
    int trace_level = Interpeter::trace_actions;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--Bgenerated") {
            b_generated = true;
        } else if (arg == "--Bfifo") {
            b_fifo = true;
        } else if (arg == "--Bstationary") {
            b_stationary = true;
        } else if (arg == "--trace_file") {
            if (i + 1 >= argc) {
                std::cerr << "--trace_file requires a filename" << std::endl;
                exit(1);
            }
            trace_file_path = argv[++i];
        } else if (arg == "--trace_input") {
            if (i + 1 >= argc) {
                std::cerr << "--trace_input requires a filename" << std::endl;
                exit(1);
            }
            trace_input_path = argv[++i];
        } else if (arg == "--trace_level") {
            if (i + 1 >= argc) {
                std::cerr << "--trace_level requires a level (0=instructions, "
                             "1=accesses, 2=actions)"
                          << std::endl;
                exit(1);
            }
            trace_level = std::atoi(argv[++i]);
            if (trace_level < Interpeter::trace_instructions ||
                trace_level > Interpeter::trace_actions) {
                std::cerr << "--trace_level must be 0, 1 or 2" << std::endl;
                exit(1);
            }
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
                  << " [--Bgenerated] [--Bfifo] [--Bstationary] [--trace_file <file>] "
                     "[--trace_level <0|1|2>] [--config <file>] [--trace_input <file>] <m> <n> <k>"
                  << std::endl;
        exit(1);
    }

    // Load config variables (default to default.config if not given)
    if (config_file_path.empty()) {
        config_file_path = "default.config";
    }
    loadConfigFile(config_file_path);

    // B lives right after A; with --Bgenerated those addresses are served by
    // the PRNG device instead of L2/memory. A zero-byte window disables it.
    const uint a_bytes = getConfig("A_HEIGHT_DIM") * getConfig("A_WIDTH_DIM") *
                         getConfig("A_PRECISION_BYTES");
    const uint b_bytes = getConfig("A_WIDTH_DIM") * getConfig("B_WIDTH_DIM") *
                         getConfig("B_PRECISION_BYTES");

    MemoryHierarchy::Parameters mp{

        .l1               = {.name         = "L1",
                             .size         = getConfig("L1_SIZE_BYTES"),
                             .line_size    = getConfig("L1_LINE_SIZE_BYTES"),
                             .assoc        = getConfig("L1_ASSOC"),
                             .write_policy = parseWritePolicy(getConfigStr("L1_WRITE_POLICY"))},
        .l1_access_cycles = getConfig("L1_ACCESS_CYCLES"),
        .l1_policy        = getConfigStr("L1_REPLACEMENT_POLICY"),

        .l2               = {.name         = "L2",
                             .size         = getConfig("L2_SIZE_BYTES"),
                             .line_size    = getConfig("L2_LINE_SIZE_BYTES"),
                             .assoc        = getConfig("L2_ASSOC"),
                             .write_policy = parseWritePolicy(getConfigStr("L2_WRITE_POLICY"))},
        .l2_access_cycles = getConfig("L2_ACCESS_CYCLES"),
        .l2_policy        = getConfigStr("L2_REPLACEMENT_POLICY"),

        .mem_access_cycles = getConfig("MEM_ACCESS_CYCLES"),

        .prng = {.base_addr         = a_bytes,
                 .window_bytes      = b_generated ? b_bytes : 0,
                 .line_size         = getConfig("L1_LINE_SIZE_BYTES"),
                 .access_cycles     = getConfig("PRNG_ACCESS_CYCLES"),
                 .gen_cost_per_line = getConfig("PRNG_GEN_COST_PER_LINE")},

        .prng_fifo = {.ctrl_start_addr = 0xFF000000,
                      .ctrl_stop_addr  = 0xFF00000C,
                      .seed_addr       = 0xFF000004,
                      .data_start_addr = 0xFF000008,
                      .data_end_addr   = 0xFF100008,
                      .access_cycles   = getConfig("PRNG_ACCESS_CYCLES"),
                      .fifo_capacity   = b_fifo ? getConfig("PRNG_FIFO_CAPACITY") : 0,
                      .gen_cost        = b_fifo ? getConfig("PRNG_FIFO_GEN_COST") : 0},

    };

    size_t cpu_cycles = 0;
    MemoryHierarchy mem(mp, cpu_cycles);

    std::string run_path = instruction_path;
    if (!trace_input_path.empty()) {
        run_path = trace_input_path;
    } else {
        generateInstructions(dims[0], dims[1], dims[2], b_stationary, b_fifo);
    }

    Interpeter::Options opts{
        .trace_file_path = trace_file_path,
        .trace_level     = static_cast<Interpeter::TraceLevel>(trace_level),
    };
    Interpeter inter(run_path, mem, opts, cpu_cycles);

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

    if (b_generated) {
        const PrngDev::Stats& ps = mem.prng().stats();
        printf("--- PRNG ---\n");
        printf("Generate:   %llu\n", (unsigned long long)ps.generates);
        printf("Regenerate: %llu\n", (unsigned long long)ps.regenerates);
    }

    if (b_fifo) {
        const PrngFifoDev::Stats& pfs = mem.prng_fifo().stats();
        printf("--- PRNG FIFO ---\n");
        printf("Starts:      %llu\n", (unsigned long long)pfs.starts);
        printf("Stops:       %llu\n", (unsigned long long)pfs.stops);
        printf("Reads:       %llu\n", (unsigned long long)pfs.reads);
        printf("Stalls:      %llu\n", (unsigned long long)pfs.stalls);
        printf("StallCycles: %llu\n", (unsigned long long)pfs.stall_cycles);
        printf("Generates:   %llu\n", (unsigned long long)pfs.generates);
    }

    printf("--- System ---\n");
    printf("Cycles:    %llu\n", (unsigned long long)cpu_cycles);

    return 0;
}
