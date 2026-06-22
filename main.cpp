#include "config.h"
#include "instruction-stream-generator/instgen.h"
#include "interpreter/interpreter.h"
#include "memory-system/cache/cache.h"
#include "memory-system/hierarchy.h"
#include "utils.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

constexpr char instruction_path[] = "./matmul.matv";


WritePolicy parseWritePolicy(const std::string& str)
{
    if (str == "WRITE_THROUGH") return WritePolicy::WRITE_THROUGH;
    if (str == "WRITE_BACK")    return WritePolicy::WRITE_BACK;
    std::cerr << "error: unknown write policy: " << str << std::endl;
    exit(1);
}

void generateInstructions(const Config& c, uint m, uint n, uint k,
                          bool b_stationary, bool b_fifo)
{
    InstGenerator gen{InstGenerator::Params{
        .a_height    = c.a_height,
        .a_width     = c.a_width,
        .b_width     = c.b_width,
        .a_precision = c.a_precision,
        .b_precision = c.b_precision,
        .reg_m       = c.reg_m,
        .reg_n       = c.reg_n,
        .reg_k       = c.reg_k,
    }};

    std::ofstream ofs(instruction_path);
    if (!ofs.is_open()) {
        std::cerr << "error opening file" << std::endl;
        exit(1);
    }

    InstGenerator::TileShape tile{m, n, k};
    gen.generate(tile, ofs, b_stationary, b_fifo);
}

int main(int argc, char* argv[])
{
    bool b_generated  = false;
    bool b_fifo       = false;
    bool b_stationary = false;
    uint dims[3];
    int positional = 0;
    std::string trace_file_path;
    std::string trace_input_path = "";
    std::string config_file_path = "";
    int trace_level              = Interpreter::trace_actions;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--Bgenerated") {
            b_generated = true;
        } else if (arg == "--Bfifo") {
            b_fifo = true;
        } else if (arg == "--Bstationary") {
            b_stationary = true;
        } else if (arg == "--trace_file") {
            if (i + 1 >= argc) { std::cerr << "--trace_file requires a filename\n"; exit(1); }
            trace_file_path = argv[++i];
        } else if (arg == "--trace_input") {
            if (i + 1 >= argc) { std::cerr << "--trace_input requires a filename\n"; exit(1); }
            trace_input_path = argv[++i];
        } else if (arg == "--trace_level") {
            if (i + 1 >= argc) {
                std::cerr << "--trace_level requires 0|1|2\n";
                exit(1);
            }
            trace_level = std::atoi(argv[++i]);
            if (trace_level < Interpreter::trace_instructions ||
                trace_level > Interpreter::trace_actions) {
                std::cerr << "--trace_level must be 0, 1 or 2\n";
                exit(1);
            }
        } else if (arg == "--config") {
            if (i + 1 >= argc) { std::cerr << "--config requires a filename\n"; exit(1); }
            config_file_path = argv[++i];
        } else if (positional < 3) {
            dims[positional++] = std::atoi(argv[i]);
        } else {
            std::cerr << "unexpected argument: " << arg << std::endl;
            exit(1);
        }
    }

    if (b_generated && b_fifo) {
        std::cerr << "error: --Bgenerated and --Bfifo are mutually exclusive.\n";
        exit(1);
    }
    if (positional != 3) {
        std::cerr << "usage: " << argv[0]
                  << " [--Bgenerated] [--Bfifo] [--Bstationary] "
                     "[--trace_file <file>] [--trace_level <0|1|2>] "
                     "[--config <file>] [--trace_input <file>] <m> <n> <k>\n";
        exit(1);
    }

    if (config_file_path.empty()) config_file_path = "default.config";
    const Config cfg = loadConfig(config_file_path);

    // B lives right after A; with --Bgenerated those addresses are served by
    // the PRNG device instead of L2/memory. A zero-byte window disables it.
    const uint a_bytes = cfg.a_height * cfg.a_width  * cfg.a_precision;
    const uint b_bytes = cfg.a_width  * cfg.b_width  * cfg.b_precision;

    MemoryHierarchy::Parameters mp{
        .l1 = {.name         = "L1",
               .size         = cfg.l1.size_bytes,
               .line_size    = cfg.l1.line_size_bytes,
               .assoc        = cfg.l1.assoc,
               .write_policy = parseWritePolicy(cfg.l1.write_policy)},
        .l1_access_cycles = cfg.l1.access_cycles,
        .l1_policy        = cfg.l1.replacement_policy,

        .l2 = {.name         = "L2",
               .size         = cfg.l2.size_bytes,
               .line_size    = cfg.l2.line_size_bytes,
               .assoc        = cfg.l2.assoc,
               .write_policy = parseWritePolicy(cfg.l2.write_policy)},
        .l2_access_cycles = cfg.l2.access_cycles,
        .l2_policy        = cfg.l2.replacement_policy,

        .mem_access_cycles = cfg.mem_access_cycles,

        .prng = {.base_addr         = a_bytes,
                 .window_bytes      = b_generated ? b_bytes : 0,
                 .line_size         = cfg.l1.line_size_bytes,
                 .access_cycles     = cfg.prng_access_cycles,
                 .gen_cost_per_line = cfg.prng_gen_cost_per_line},

        .prng_fifo = {.ctrl_start_addr = 0xFF000000, // MMIO addresses
                      .ctrl_stop_addr  = 0xFF00000C,
                      .seed_addr       = 0xFF000004,
                      .data_start_addr = 0xFF000008,
                      .data_end_addr   = 0xFF100008,
                      .access_cycles   = cfg.prng_access_cycles,
                      .fifo_capacity   = b_fifo ? cfg.prng_fifo_capacity : 0,
                      .gen_cost        = b_fifo ? cfg.prng_fifo_gen_cost : 0},
    };

    size_t cpu_cycles = 0;
    MemoryHierarchy mem(mp, cpu_cycles);

    std::string run_path = instruction_path;
    if (!trace_input_path.empty()) {
        run_path = trace_input_path;
    } else {
        generateInstructions(cfg, dims[0], dims[1], dims[2], b_stationary, b_fifo);
    }

    Interpreter::Options opts{
        .trace_file_path = trace_file_path,
        .trace_level     = static_cast<Interpreter::TraceLevel>(trace_level),
        .reg_m           = cfg.reg_m,
        .reg_n           = cfg.reg_n,
        .reg_k           = cfg.reg_k,
        .mulac_cycles    = cfg.mulac_cycles,
    };
    Interpreter inter(run_path, mem, opts, cpu_cycles);

    std::cout << "----------------------------\n"
              << dims[0] << ' ' << dims[1] << ' ' << dims[2] << '\n'
              << "----------------------------\n";

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
