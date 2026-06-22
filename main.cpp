#include "config.h"
#include "instruction-stream-generator/instgen.h"
#include "interpreter/interpreter.h"
#include "memory-system/address_map.h"
#include "memory-system/cache/cache.h"
#include "memory-system/hierarchy.h"
#include "utils.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

constexpr char instruction_path[] = "./matmul.matv";

// ---------------------------------------------------------------------------
// Arg parsing
// ---------------------------------------------------------------------------

struct Args {
    bool b_generated  = false;
    bool b_fifo       = false;
    bool b_stationary = false;
    bool b_scratchpad = false;
    uint dims[3]      = {};
    std::string trace_file_path;
    std::string trace_input_path;
    std::string config_file_path;
    std::string stat_file_path;
    int trace_level = Interpreter::trace_actions;
};

Args parseArgs(int argc, char* argv[])
{
    Args a;
    int positional = 0;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--Bgenerated") {
            a.b_generated = true;
        } else if (arg == "--Bfifo") {
            a.b_fifo = true;
        } else if (arg == "--Bstationary") {
            a.b_stationary = true;
        } else if (arg == "--scratchpad") {
            a.b_scratchpad = true;
        } else if (arg == "--trace_file") {
            if (i + 1 >= argc) {
                std::cerr << "--trace_file requires a filename\n";
                exit(1);
            }
            a.trace_file_path = argv[++i];
        } else if (arg == "--stat_file" || arg == "--stat-file") {
            if (i + 1 >= argc) {
                std::cerr << "--stat_file requires a filename\n";
                exit(1);
            }
            a.stat_file_path = argv[++i];
        } else if (arg == "--trace_input") {
            if (i + 1 >= argc) {
                std::cerr << "--trace_input requires a filename\n";
                exit(1);
            }
            a.trace_input_path = argv[++i];
        } else if (arg == "--trace_level") {
            if (i + 1 >= argc) {
                std::cerr << "--trace_level requires 0|1|2\n";
                exit(1);
            }
            a.trace_level = std::atoi(argv[++i]);
            if (a.trace_level < Interpreter::trace_instructions ||
                a.trace_level > Interpreter::trace_actions) {
                std::cerr << "--trace_level must be 0, 1 or 2\n";
                exit(1);
            }
        } else if (arg == "--config") {
            if (i + 1 >= argc) {
                std::cerr << "--config requires a filename\n";
                exit(1);
            }
            a.config_file_path = argv[++i];
        } else if (positional < 3) {
            a.dims[positional++] = std::atoi(argv[i]);
        } else {
            std::cerr << "unexpected argument: " << arg << std::endl;
            exit(1);
        }
    }

    if (a.b_generated && a.b_fifo) {
        std::cerr
            << "error: --Bgenerated and --Bfifo are mutually exclusive.\n";
        exit(1);
    }
    if (positional != 3) {
        std::cerr << "usage: " << argv[0]
                  << " [--Bgenerated] [--Bfifo] [--Bstationary] [--scratchpad] "
                     "[--trace_file <file>] [--trace_level <0|1|2>] "
                     "[--stat_file <file>] "
                     "[--config <file>] [--trace_input <file>] <m> <n> <k>\n";
        exit(1);
    }

    return a;
}

// ---------------------------------------------------------------------------
// Config → hierarchy params
// ---------------------------------------------------------------------------

MemoryHierarchy::Parameters buildMemParams(const Config& cfg, bool b_generated,
                                           bool b_fifo)
{
    const uint a_bytes = cfg.a_height * cfg.a_width * cfg.a_precision;
    const uint b_bytes = cfg.a_width * cfg.b_width * cfg.b_precision;

    return {
        .l1               = {.name         = "L1",
                             .size         = cfg.l1.size_bytes,
                             .line_size    = cfg.l1.line_size_bytes,
                             .assoc        = cfg.l1.assoc,
                             .write_policy = cfg.l1.write_policy},
        .l1_access_cycles = cfg.l1.access_cycles,
        .l1_policy        = cfg.l1.replacement_policy,

        .l2               = {.name         = "L2",
                             .size         = cfg.l2.size_bytes,
                             .line_size    = cfg.l2.line_size_bytes,
                             .assoc        = cfg.l2.assoc,
                             .write_policy = cfg.l2.write_policy},
        .l2_access_cycles = cfg.l2.access_cycles,
        .l2_policy        = cfg.l2.replacement_policy,

        .mem_access_cycles = cfg.mem_access_cycles,

        .prng = {.base_addr         = a_bytes,
                 .window_bytes      = b_generated ? b_bytes : 0u,
                 .line_size         = cfg.l1.line_size_bytes,
                 .access_cycles     = cfg.prng_access_cycles,
                 .gen_cost_per_line = cfg.prng_gen_cost_per_line},

        .prng_fifo = {.ctrl_start_addr = FIFO_CTRL_START_ADDR,
                      .ctrl_stop_addr  = FIFO_CTRL_STOP_ADDR,
                      .seed_addr       = FIFO_SEED_ADDR,
                      .data_start_addr = FIFO_DATA_START_ADDR,
                      .data_end_addr   = FIFO_DATA_END_ADDR,
                      .access_cycles   = cfg.prng_access_cycles,
                      .fifo_capacity   = b_fifo ? cfg.prng_fifo_capacity : 0u,
                      .gen_cost        = b_fifo ? cfg.prng_fifo_gen_cost : 0u},
        .sp_access_cycles   = cfg.sp_access_cycles,
        .sp_banks           = cfg.sp_banks,
        .sp_word_size_bytes = cfg.sp_word_size_bytes,
    };
}

// ---------------------------------------------------------------------------
// Instruction generation
// ---------------------------------------------------------------------------

void generateInstructions(const Config& c, uint m, uint n, uint k,
                          bool b_stationary, bool b_fifo, bool b_scratchpad)
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

    gen.generate({m, n, k}, ofs, b_stationary, b_fifo, b_scratchpad);
}

// ---------------------------------------------------------------------------
// Stats output
// ---------------------------------------------------------------------------

void printStats(const MemoryHierarchy& mem, size_t cpu_cycles, bool b_generated,
                bool b_fifo)
{
    auto cacheBlock = [](const char* name, const Cache::Stats& s) {
        const size_t total    = s.hits + s.misses;
        const double hit_rate = total ? (double)s.hits / total : 0.0;
        printf("--- %s ---\n", name);
        printf("Hit rate:  %.03f\n", hit_rate);
        printf("TagLookup: %llu\n", (unsigned long long)s.tag_lookups);
        printf("LineFill:  %llu\n", (unsigned long long)s.line_fills);
        printf("Evict:     %llu\n", (unsigned long long)s.evicts);
    };

    cacheBlock(mem.l1().name(), mem.l1().stats());
    cacheBlock(mem.l2().name(), mem.l2().stats());

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

    {
        const ScratchpadDev::Stats& ss = mem.scratchpad().stats();
        printf("--- Scratchpad ---\n");
        printf("TileReads:      %llu\n", (unsigned long long)ss.tile_reads);
        printf("TileWrites:     %llu\n", (unsigned long long)ss.tile_writes);
        printf("ConflictStalls: %llu\n", (unsigned long long)ss.conflict_stalls);
    }

    printf("--- System ---\n");
    printf("Cycles:    %llu\n", (unsigned long long)cpu_cycles);
}

void writeStatsFile(const std::string& path, const MemoryHierarchy& mem,
                    size_t cpu_cycles, bool b_generated, bool b_fifo)
{
    std::ofstream out(path);
    if (!out.is_open()) {
        std::cerr << "error opening stat file: " << path << std::endl;
        return;
    }

    out << "| Component | Metric | Value |\n";
    out << "| :--- | :--- | :--- |\n";

    auto cacheRows = [&](const char* comp, const Cache::Stats& s) {
        const size_t total    = s.hits + s.misses;
        const double hit_rate = total ? (double)s.hits / total : 0.0;
        char buffer[128];
        snprintf(buffer, sizeof(buffer), "| %s | Hit Rate | %.03f |\n", comp,
                 hit_rate);
        out << buffer;
        out << "| " << comp << " | TagLookup | " << s.tag_lookups << " |\n";
        out << "| " << comp << " | LineFill | " << s.line_fills << " |\n";
        out << "| " << comp << " | Evict | " << s.evicts << " |\n";
    };

    cacheRows("L1 Cache", mem.l1().stats());
    cacheRows("L2 Cache", mem.l2().stats());

    if (b_generated) {
        const PrngDev::Stats& ps = mem.prng().stats();
        out << "| PRNG | Generate | " << ps.generates << " |\n";
        out << "| PRNG | Regenerate | " << ps.regenerates << " |\n";
    } else {
        out << "| PRNG | Generate | - |\n";
        out << "| PRNG | Regenerate | - |\n";
    }

    if (b_fifo) {
        const PrngFifoDev::Stats& pfs = mem.prng_fifo().stats();
        out << "| PRNG FIFO | Starts | " << pfs.starts << " |\n";
        out << "| PRNG FIFO | Stops | " << pfs.stops << " |\n";
        out << "| PRNG FIFO | Reads | " << pfs.reads << " |\n";
        out << "| PRNG FIFO | Stalls | " << pfs.stalls << " |\n";
        out << "| PRNG FIFO | Stall Cycles | " << pfs.stall_cycles << " |\n";
        out << "| PRNG FIFO | Generates | " << pfs.generates << " |\n";
    } else {
        out << "| PRNG FIFO | Starts | - |\n";
        out << "| PRNG FIFO | Stops | - |\n";
        out << "| PRNG FIFO | Reads | - |\n";
        out << "| PRNG FIFO | Stalls | - |\n";
        out << "| PRNG FIFO | Stall Cycles | - |\n";
        out << "| PRNG FIFO | Generates | - |\n";
    }

    {
        const ScratchpadDev::Stats& ss = mem.scratchpad().stats();
        out << "| Scratchpad | TileReads | "      << ss.tile_reads      << " |\n";
        out << "| Scratchpad | TileWrites | "     << ss.tile_writes     << " |\n";
        out << "| Scratchpad | ConflictStalls | " << ss.conflict_stalls << " |\n";
    }

    out << "| System | Total Cycles | " << cpu_cycles << " |\n";
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

int main(int argc, char* argv[])
{
    const Args args = parseArgs(argc, argv);

    const std::string config_path = args.config_file_path.empty()
                                        ? "default.config"
                                        : args.config_file_path;
    const Config cfg              = loadConfig(config_path);

    size_t cpu_cycles = 0;
    MemoryHierarchy mem(buildMemParams(cfg, args.b_generated, args.b_fifo),
                        cpu_cycles);

    std::string run_path = args.trace_input_path;
    if (run_path.empty()) {
        generateInstructions(cfg, args.dims[0], args.dims[1], args.dims[2],
                             args.b_stationary, args.b_fifo, args.b_scratchpad);
        run_path = instruction_path;
    }

    Interpreter::Options opts{
        .trace_file_path = args.trace_file_path,
        .trace_level  = static_cast<Interpreter::TraceLevel>(args.trace_level),
        .reg_m        = cfg.reg_m,
        .reg_n        = cfg.reg_n,
        .reg_k        = cfg.reg_k,
        .mulac_cycles = cfg.mulac_cycles,
        .sp_banks     = cfg.sp_banks,
        .sp_word_size_bytes = cfg.sp_word_size_bytes,
    };
    Interpreter inter(run_path, mem, opts, cpu_cycles);

    std::cout << "----------------------------\n"
              << args.dims[0] << ' ' << args.dims[1] << ' ' << args.dims[2]
              << '\n'
              << "----------------------------\n";

    inter.run();
    printStats(mem, cpu_cycles, args.b_generated, args.b_fifo);

    if (!args.stat_file_path.empty())
        writeStatsFile(args.stat_file_path, mem, cpu_cycles, args.b_generated,
                       args.b_fifo);

    return 0;
}
