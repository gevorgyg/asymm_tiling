#ifndef PRNG_RECORD_H_
#define PRNG_RECORD_H_

#include "../utils.h"

#include <cstddef>

// PRNG device model. Tracks a FIFO of pre-generated values and stalls the
// caller when it underruns. Costs are accumulated into the externally-owned
// cpu_cycles counter so the timing model stays consistent with the rest of
// the simulator.
class PrngDevSim
{
  public:
    explicit PrngDevSim(size_t& cpu_cycles, uint max_fifo_size = def_size,
                        uint generation_cost = def_gen_cost,
                        uint access_cost     = def_access_cost,
                        uint seed_cost       = def_seed_cost);

    void pop();
    void reseed();

  private:
    void addToFifo();

    static constexpr int def_access_cost = 6;
    static constexpr int def_gen_cost    = 12;
    static constexpr int def_seed_cost   = 4;
    static constexpr int def_size        = 1024;

    const uint max_fifo_size_;
    const uint generation_cost_;
    const uint access_cost_;
    const uint seed_cost_;

    uint   cur_fifo_size_   = 0;
    size_t last_cpu_cycles_ = 0;

    size_t& cpu_cycles_;
};

#endif
