#ifndef INTERPRETER_H_
#define INTERPRETER_H_

#include "../memory-system/hierarchy.h"

#include <array>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

class Interpreter
{
  public:
    // Trace verbosity: each level includes everything above it.
    //   instructions -- one line per ISA instruction with its cycle total
    //   accesses     -- + one line per element read/write
    //   actions      -- + every device Action (TagLookup, Generate, ...)
    enum TraceLevel {
        trace_instructions = 0,
        trace_accesses     = 1,
        trace_actions      = 2,
    };

    struct Options {
        std::string trace_file_path;
        TraceLevel  trace_level;
    };

    Interpreter(std::filesystem::path input_file, MemoryHierarchy& mem,
               Options opts, size_t& cpu_cycles);

    Interpreter(const Interpreter&)            = delete;
    Interpreter& operator=(const Interpreter&) = delete;

    void run();

  private:
    struct vec_reg {
        Addr base_addr;

        uint t_width;
        uint t_height;
        uint stride;
        uint elem_width;
    };

    enum cmd {
        load_tile,
        move_tile,
        mul_acc,
        prefetch_tile,
        eof,
    };

    void handleTload();
    void handleTmove();
    void handleMulAcc();
    void handlePrefetch();

    void handleCmd();
    cmd readCmd();

    uint parseReg();
    void trim_prefix_spaces();

    void doRead(Addr addr, size_t size);
    void doWrite(Addr addr, size_t size);
    void logAccess(const char* op, Addr addr, uint cycles, const Trace& t);

    std::ifstream in_stream_;
    int line_;

    // Externally-owned running CPU-cycle counter.
    size_t& cpu_cycles_;

    // Open iff the user passed --trace_file.
    std::ofstream trace_out_;
    TraceLevel    trace_level_;

    // Per-instruction trace state: the header is written once the
    // instruction completes (so its cycle total is known), followed by the
    // buffered access/action details.
    std::string        inst_header_;
    std::ostringstream inst_detail_;

    std::array<vec_reg, 3> vec_regs_;
    MemoryHierarchy& mem_;
};

#endif
