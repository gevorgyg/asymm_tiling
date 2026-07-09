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
#include <vector>

constexpr char instruction_path[] = "./matmul.matv";


enum class BSource    { Memory, PrngMem, PrngFifo, PrngFifoPipelined };
enum class Stationary { C, B };


WritePolicy parseWritePolicy(const std::string& str)
{
    if (str == "WRITE_THROUGH") return WritePolicy::WRITE_THROUGH;
    if (str == "WRITE_BACK")    return WritePolicy::WRITE_BACK;
    std::cerr << "error: unknown write policy: " << str << std::endl;
    exit(1);
}

BSource parseBSource(const std::string& str)
{
    if (str == "mem")                   return BSource::Memory;
    if (str == "prng_mem")              return BSource::PrngMem;
    if (str == "prng_fifo")             return BSource::PrngFifo;
    if (str == "prng_fifo_pipelined")   return BSource::PrngFifoPipelined;
    std::cerr << "error: --Bsource must be one of {mem, prng_mem, prng_fifo, prng_fifo_pipelined}; got '"
              << str << "'\n";
    exit(1);
}

Stationary parseStationary(const std::string& str)
{
    if (str == "C") return Stationary::C;
    if (str == "B") return Stationary::B;
    std::cerr << "error: --stationary must be B or C; got '" << str << "'\n";
    exit(1);
}

void generateInstructions(const Config& c, bool b_stationary, bool b_fifo,
                          uint reg_m, uint reg_n, uint reg_k, uint seed_bytes,
                          bool b_fifo_pipelined = false)
{
    InstGenerator gen{InstGenerator::Params{
        .a_height    = c.a_height,
        .a_width     = c.a_width,
        .b_width     = c.b_width,
        .a_precision = c.a_precision,
        .b_precision = c.b_precision,
        .reg_m       = reg_m,
        .reg_n       = reg_n,
        .reg_k       = reg_k,
        .seed_bytes  = seed_bytes,
    }};

    std::ofstream ofs(instruction_path);
    if (!ofs.is_open()) {
        std::cerr << "error opening file" << std::endl;
        exit(1);
    }

    InstGenerator::TileShape tile{c.tile_m, c.tile_n, c.tile_k};
    gen.generate(tile, ofs, b_stationary, b_fifo, b_fifo_pipelined);
}


// Config keys whose values are ignored under the current CLI flag combination.
// Used by both --- UNUSED OPTIONS --- output (humans) and the experiment
// harness (cache-key normalization).
std::vector<const char*> unusedConfigKeys(BSource source, bool use_3dregisters,
                                          bool record_mulac)
{
    std::vector<const char*> u;
    if (source != BSource::PrngMem) {
        u.push_back("PRNG_ACCESS_CYCLES");
        u.push_back("PRNG_GEN_COST_PER_LINE");
    }
    if (source != BSource::PrngFifo && source != BSource::PrngFifoPipelined) {
        u.push_back("PRNG_FIFO_CAPACITY");
        u.push_back("PRNG_FIFO_GEN_COST");
        u.push_back("PRNG_FIFO_SEED_BYTES");
    }
    if (!use_3dregisters) {
        u.push_back("REG_M");
        u.push_back("REG_N");
        u.push_back("REG_K");
    }
    if (!record_mulac) {
        u.push_back("MULAC_CYCLES");
    }
    return u;
}


void printCacheTable(const Cache& l1, const Cache& l2)
{
    const auto& a = l1.stats();
    const auto& b = l2.stats();
    const double hr_a = (a.hits + a.misses) ? (double)a.hits / (a.hits + a.misses) : 0.0;
    const double hr_b = (b.hits + b.misses) ? (double)b.hits / (b.hits + b.misses) : 0.0;

    printf("| Cache | Hit rate | TagLookup | LineFill | Evict | Writeback | BytesIn | BytesOut |\n");
    printf("|---|---|---|---|---|---|---|---|\n");
    printf("| %s | %.03f | %llu | %llu | %llu | %llu | %llu | %llu |\n", l1.name(), hr_a,
           (unsigned long long)a.tag_lookups,
           (unsigned long long)a.line_fills,
           (unsigned long long)a.evicts,
           (unsigned long long)a.writebacks,
           (unsigned long long)a.bytes_in,
           (unsigned long long)a.bytes_out);
    printf("| %s | %.03f | %llu | %llu | %llu | %llu | %llu | %llu |\n", l2.name(), hr_b,
           (unsigned long long)b.tag_lookups,
           (unsigned long long)b.line_fills,
           (unsigned long long)b.evicts,
           (unsigned long long)b.writebacks,
           (unsigned long long)b.bytes_in,
           (unsigned long long)b.bytes_out);
}

// L2 is the only client of main memory, so DRAM traffic is L2's boundary
// traffic seen from the other side: reads = L2 fills, writes = L2 pushes.
void printDramTable(const Cache& l2)
{
    const auto& s = l2.stats();
    printf("\n| DRAM | BytesRead | BytesWritten |\n");
    printf("|---|---|---|\n");
    printf("| DRAM | %llu | %llu |\n",
           (unsigned long long)s.bytes_in,
           (unsigned long long)s.bytes_out);
}

void printPrngTable(const PrngDev::Stats& s)
{
    printf("\n| PRNG | Generate | Regenerate |\n");
    printf("|---|---|---|\n");
    printf("| PRNG | %llu | %llu |\n",
           (unsigned long long)s.generates,
           (unsigned long long)s.regenerates);
}

void printPrngFifoTable(const PrngFifoDev::Stats& s)
{
    printf("\n| PRNG FIFO | Starts | Stops | Reads | Stalls | StallCycles | Generates |\n");
    printf("|---|---|---|---|---|---|---|\n");
    printf("| PRNG FIFO | %llu | %llu | %llu | %llu | %llu | %llu |\n",
           (unsigned long long)s.starts,
           (unsigned long long)s.stops,
           (unsigned long long)s.reads,
           (unsigned long long)s.stalls,
           (unsigned long long)s.stall_cycles,
           (unsigned long long)s.generates);
}

void printPrngFifoPipelinedTable(const PrngFifoPipelinedDev::Stats& s)
{
    printf("\n| PRNG FIFO Pipelined | Starts | Stops | Swaps | Reads | Stalls | StallCycles | Generates | PrefillGenerates |\n");
    printf("|---|---|---|---|---|---|---|---|---|\n");
    printf("| PRNG FIFO Pipelined | %llu | %llu | %llu | %llu | %llu | %llu | %llu | %llu |\n",
           (unsigned long long)s.starts,
           (unsigned long long)s.stops,
           (unsigned long long)s.swaps,
           (unsigned long long)s.reads,
           (unsigned long long)s.stalls,
           (unsigned long long)s.stall_cycles,
           (unsigned long long)s.generates,
           (unsigned long long)s.prefill_generates);
}

void printSystemTable(size_t cycles)
{
    printf("\n| System | Cycles |\n");
    printf("|---|---|\n");
    printf("| System | %llu |\n", (unsigned long long)cycles);
}


int main(int argc, char* argv[])
{
    BSource     b_source         = BSource::Memory;
    Stationary  stationary       = Stationary::C;
    std::string config_path      = "default.config";
    std::string trace_file_path  = "trace.log";
    std::string assembler_input;
    int         trace_level      = Interpreter::trace_instructions;
    bool        use_3dregisters  = false;
    bool        mulac_norecord   = false;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        const auto need_arg = [&](const char* flag) {
            if (i + 1 >= argc) {
                std::cerr << flag << " requires an argument\n";
                exit(1);
            }
            return std::string(argv[++i]);
        };

        if      (arg == "--Bsource")         b_source        = parseBSource(need_arg("--Bsource"));
        else if (arg == "--stationary")      stationary      = parseStationary(need_arg("--stationary"));
        else if (arg == "--config")          config_path     = need_arg("--config");
        else if (arg == "--trace_file")      trace_file_path = need_arg("--trace_file");
        else if (arg == "--assembler_input") assembler_input = need_arg("--assembler_input");
        else if (arg == "--3dregisters")     use_3dregisters = true;
        else if (arg == "--mulac_norecord")  mulac_norecord  = true;
        else if (arg == "--trace_level") {
            trace_level = std::atoi(need_arg("--trace_level").c_str());
            if (trace_level < Interpreter::trace_instructions ||
                trace_level > Interpreter::trace_actions) {
                std::cerr << "--trace_level must be 0, 1 or 2\n";
                exit(1);
            }
        } else {
            std::cerr << "unexpected argument: " << arg << '\n'
                      << "see README.md for the supported flags.\n";
            exit(1);
        }
    }

    const Config cfg = loadConfig(config_path);

    // Apply CLI gates to config values: a flag absent means the corresponding
    // config block is unused, and its values are zeroed before reaching the
    // simulator. This is the *one* place "feature on/off" is decided.
    uint reg_m = 0, reg_n = 0, reg_k = 0;
    if (use_3dregisters) {
        if (cfg.reg_m == 0 || cfg.reg_n == 0 || cfg.reg_k == 0) {
            std::cerr << "error: --3dregisters requires REG_M, REG_N, REG_K > 0 in config\n";
            exit(1);
        }
        reg_m = cfg.reg_m;
        reg_n = cfg.reg_n;
        reg_k = cfg.reg_k;
    }

    const bool record_mulac = !mulac_norecord;
    uint mulac_cycles = 0;
    if (record_mulac) {
        mulac_cycles = cfg.mulac_cycles;
    }

    const bool b_generated        = (b_source == BSource::PrngMem);
    const bool b_fifo             = (b_source == BSource::PrngFifo);
    const bool b_fifo_pipelined   = (b_source == BSource::PrngFifoPipelined);
    const bool b_stationary       = (stationary == Stationary::B);

    if (b_fifo_pipelined && (!use_3dregisters || b_stationary)) {
        std::cerr << "error: --Bsource prng_fifo_pipelined requires --stationary C and --3dregisters\n";
        exit(1);
    }


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

        .prng_fifo = {.ctrl_start_addr = 0xFF000000,
                      .ctrl_stop_addr  = 0xFF00000C,
                      .seed_addr       = 0xFF000004,
                      .data_start_addr = 0xFF000008,
                      .data_end_addr   = 0xFF100008,
                      .access_cycles   = cfg.prng_access_cycles,
                      .fifo_capacity   = b_fifo ? cfg.prng_fifo_capacity : 0,
                      .gen_cost        = b_fifo ? cfg.prng_fifo_gen_cost : 0},

        .prng_fifo_pipelined = {.pref_seed_addr   = 0xFF200000,
                                .pref_start_addr  = 0xFF200004,
                                .swap_addr        = 0xFF200008,
                                .stop_addr        = 0xFF20000C,
                                .data_start_addr  = 0xFF200010,
                                .data_end_addr    = 0xFF300010,
                                .access_cycles    = cfg.prng_access_cycles,
                                .fifo_capacity    = b_fifo_pipelined ? cfg.prng_fifo_capacity : 0,
                                .gen_cost         = b_fifo_pipelined ? cfg.prng_fifo_gen_cost : 0},
    };

    size_t cpu_cycles = 0;
    MemoryHierarchy mem(mp, cpu_cycles);

    std::string run_path = instruction_path;
    if (!assembler_input.empty()) {
        run_path = assembler_input;
    } else {
        generateInstructions(cfg, b_stationary, b_fifo, reg_m, reg_n, reg_k,
                             cfg.prng_fifo_seed_bytes, b_fifo_pipelined);
    }

    Interpreter::Options opts{
        .trace_file_path = trace_file_path,
        .trace_level     = static_cast<Interpreter::TraceLevel>(trace_level),
        .reg_m           = reg_m,
        .reg_n           = reg_n,
        .reg_k           = reg_k,
        .mulac_cycles    = mulac_cycles,
    };
    Interpreter inter(run_path, mem, opts, cpu_cycles);

    inter.run();

    // Traffic ledger must include data still resident at exit: every dirty
    // line is written back (stats only, no cycle cost).
    mem.flushCaches();

    // Header: which config blocks were ignored by this run.
    printf("--- UNUSED OPTIONS ---\n");
    for (const char* k : unusedConfigKeys(b_source, use_3dregisters, record_mulac)) {
        printf("# %s\n", k);
    }
    printf("--- END ---\n\n");

    printCacheTable(mem.l1(), mem.l2());
    printDramTable(mem.l2());
    if (b_generated)      printPrngTable(mem.prng().stats());
    if (b_fifo)           printPrngFifoTable(mem.prng_fifo().stats());
    if (b_fifo_pipelined) printPrngFifoPipelinedTable(mem.prng_fifo_pipelined().stats());
    printSystemTable(cpu_cycles);

    return 0;
}
