#ifndef INTERPRETER_H_
#define INTERPRETER_H_

#include "../memory-system/hierarchy.h"

#include <array>
#include <filesystem>
#include <fstream>
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

        // Hardware register tile dims. Zero in any dimension disables
        // register-tile checks and switches handleMulAcc to scalar mode.
        uint reg_m = 0;
        uint reg_n = 0;
        uint reg_k = 0;

        // Per-tmulac compute cost. Zero means "don't charge anything".
        uint mulac_cycles = 0;
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

    // Operand pack shared by ltea / tmov / prefetch:
    //     (addr, tile_width, tile_height, stride, elem_width)
    struct TileParams {
        Addr base_addr;
        uint t_width;
        uint t_height;
        uint stride;
        uint elem_width;
    };

    // Dispatch one instruction; returns false at EOF.
    bool handleCmd();

    // Per-op handlers.
    void handleTload();
    void handleTmove();
    void handlePrefetch();
    void handleMulAcc();

    // Parsing helpers.
    TileParams parseTileParams();
    uint       parseReg();
    void       expect(char c, const char* missing, const char* context);
    void       skipSpaces();

    // Cross-cutting helpers.
    void validateRegShape(uint reg, uint t_width, uint t_height) const;
    void setInstHeader(const char* op, const TileParams& p, int reg);
    template <typename F>
    void forEachElement(const TileParams& p, F&& fn) const;

    // Trace I/O.
    void doRead(Addr addr, size_t size);
    void doWrite(Addr addr, size_t size);

    std::ifstream in_stream_;
    int line_;

    // Externally-owned running CPU-cycle counter.
    size_t& cpu_cycles_;

    // Open iff the user passed --trace_file.
    std::ofstream trace_out_;
    TraceLevel    trace_level_;

    // Set by each handler before it returns; consumed by handleCmd when it
    // assembles the top-level Instruction Action for that ISA op.
    std::string inst_header_;

    std::array<vec_reg, 3> vec_regs_;
    MemoryHierarchy& mem_;

    // Hardware register tile + compute cost copied from Options. Used by
    // validateRegShape() and handleMulAcc().
    uint reg_m_;
    uint reg_n_;
    uint reg_k_;
    uint mulac_cycles_;

    Trace inst_trace_;
};

template <typename F>
void Interpreter::forEachElement(const TileParams& p, F&& fn) const
{
    for (uint row = 0; row < p.t_height; ++row) {
        for (uint col = 0; col < p.t_width; ++col) {
            const Addr target = p.base_addr + (row * p.stride + col) * p.elem_width;
            fn(target);
        }
    }
}

#endif
