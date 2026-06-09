#include "prng_record.h"

#include <algorithm>


PrngDevSim::PrngDevSim(size_t& cpu_cycles, uint max_fifo_size,
                       uint generation_cost, uint access_cost, uint seed_cost)
    : max_fifo_size_(max_fifo_size), generation_cost_(generation_cost),
      access_cost_(access_cost), seed_cost_(seed_cost), cpu_cycles_(cpu_cycles)
{
}

void PrngDevSim::reseed()
{
    cpu_cycles_ += seed_cost_;
    cur_fifo_size_   = 0;
    last_cpu_cycles_ = cpu_cycles_;
}

void PrngDevSim::pop()
{
    size_t stall_amount = 0;

    cpu_cycles_ += access_cost_;

    addToFifo();

    if (!cur_fifo_size_) {
        size_t delta_cycles = cpu_cycles_ - last_cpu_cycles_;
        stall_amount        = generation_cost_ - delta_cycles;

        cpu_cycles_ += stall_amount;

        last_cpu_cycles_ = cpu_cycles_;
    } else {
        --cur_fifo_size_;
    }
}

void PrngDevSim::addToFifo()
{
    size_t delta_cycles = cpu_cycles_ - last_cpu_cycles_;

    uint to_add = delta_cycles / generation_cost_;
    if (!to_add) {
        return;
    }

    size_t leftover = delta_cycles % generation_cost_;

    cur_fifo_size_ = std::min(cur_fifo_size_ + to_add, max_fifo_size_);

    last_cpu_cycles_ = cpu_cycles_ - leftover;
}
