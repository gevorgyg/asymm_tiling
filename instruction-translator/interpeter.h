#ifndef INTERPETER_H_
#define INTERPETER_H_

#include "cachesim.h"

#include <array>
#include <filesystem>
#include <fstream>

class Interpeter
{
  public:
    Interpeter(std::filesystem::path input_file, Simulator& cache_sim,
               RecordBook& rb);

    Interpeter(const Interpeter&)            = delete;
    Interpeter& operator=(const Interpeter&) = delete;

    void run();

  private:
    using Addr = unsigned int;
    using uint = unsigned int;

    inline static constexpr int nr_vec_regs = 3;

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

    void stall(size_t amount);

    void handleTload();
    void handleTmove();
    void handleMulAcc();
    void startRng();
    void stopRng();

    void handleCmd();
    cmd readCmd();

    void trim_prefix_spaces();

    std::ifstream in_stream_;
    int line_;
    Addr magic_addr_ = 0;
    RecordBook& rb_;

    std::array<vec_reg, 3> vec_regs_;
    PrngDevSim prng_dev_;
    Simulator& cache_sim_;
};

#endif
