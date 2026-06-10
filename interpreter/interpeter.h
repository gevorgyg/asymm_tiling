#ifndef INTERPETER_H_
#define INTERPETER_H_

#include "../memory-system/hierarchy.h"
#include "prng_record.h"

#include <array>
#include <filesystem>
#include <fstream>
#include <string>

class Interpeter
{
  public:
    Interpeter(std::filesystem::path input_file, MemoryHierarchy& mem,
               const std::string& trace_file_path, size_t& cpu_cycles);

    Interpeter(const Interpeter&)            = delete;
    Interpeter& operator=(const Interpeter&) = delete;

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
        start_rng,
        stop_rng,
        eof,
    };

    void handleTload();
    void handleTmove();
    void handleMulAcc();
    void startRng();
    void stopRng();

    void handleCmd();
    cmd readCmd();

    void trim_prefix_spaces();

    void doRead(Addr addr);
    void doWrite(Addr addr);

    void logTrace(const Trace& t);

    std::ifstream in_stream_;
    int line_;

    // Cumulative cycle count reference.
    size_t& total_cycles_;

    // Open iff the user passed --trace_file; one line per performed Action.
    std::ofstream trace_out_;

    std::array<vec_reg, 3> vec_regs_;
    MemoryHierarchy& mem_;
};

#endif
