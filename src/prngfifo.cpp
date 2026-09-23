#include "prngfifo.h"

PrngFifo::PrngFifo(size_t capacity, size_t generation_cost, size_t accsess_cost)
    : capacity_(capacity), generation_cost_(generation_cost),
      accsess_cost_(accsess_cost)
{
}
void PrngFifo::pop(const size_t elements, size_t& cur_cycles)
{
    static size_t prev_cycles = 0;

    if (generation_cost_ != 0) {
        size_ += (cur_cycles - prev_cycles) / generation_cost_;
    } else {
        size_ = capacity_;
    }

    if (elements > size_) {
        size_t sc = generation_cost_ * (elements - size_);

        cur_cycles += sc;
        size_ = elements;

        ++stalls_;
        stall_cycles_ += sc;
    }

    cur_cycles += accsess_cost_;
    size_ -= elements;
    prev_cycles = cur_cycles;

    ++pops_;
}
void PrngFifo::load_seed()
{
    // restert the generation proccess to get the same numbers for each tile
    size_ = 0;
}
