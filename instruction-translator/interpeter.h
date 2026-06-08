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
    Interpeter(std::filesystem::path input_file, MemoryHierarchy& mem);

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

    std::ifstream in_stream_;
    int line_;
    Addr magic_addr_ = 0;

    // Cumulative cycle count; only kept because PrngDevSim's stall model
    // needs a running CPU-time reference. Not printed anywhere.
    size_t total_cycles_ = 0;

    std::array<vec_reg, 3> vec_regs_;
    PrngDevSim prng_dev_;
    MemoryHierarchy& mem_;
};

#endif
