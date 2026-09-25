#include "prngfifo.h"
#include "registry.h"

PrngFifo::PrngFifo(size_t capacity, size_t generation_cost, size_t accsess_cost,
                   size_t seed_size)
    : capacity_(1 << capacity), generation_cost_(generation_cost),
      accsess_cost_(accsess_cost), seed_size_(seed_size)
{
}

void PrngFifo::pop(const size_t elements)
{
    size_t generated_elements = 0;

    if (generation_cost_ != 0) {
        generated_elements =
            (Clock::cur_cycles() - prev_cycles_) / generation_cost_;
        size_ = std::min(size_ + generated_elements, capacity_);
    } else {
        size_ = capacity_;
    }

    if (elements > size_) {
        size_t sc = generation_cost_ * (elements - size_);

        Clock::tick(sc);
        prev_cycles_ += sc;
        size_ = elements;

        ++stalls_;
        stall_cycles_ += sc;
    }

    Clock::tick(accsess_cost_);
    size_ -= elements;
    prev_cycles_ += generated_elements * generation_cost_;

    ++pops_;
}

void PrngFifo::load_seed()
{
    // restert the generation proccess to get the same numbers for each tile
    size_        = 0;
    prev_cycles_ = Clock::cur_cycles();
}

size_t PrngFifo::seed_size() const
{
    return seed_size_;
}

void PrngFifo::register_stats() const
{
    ASYMT_PRNGFIFO_STATS(ASYMT_REGISTER_NAME);

    gRegistry().reg_stat<double>("PrngFifo: Stall Rate [%]", [this]() {
        return pops_ ? ((double)stalls_ / pops_) * 100.0 : 0.0;
    });
}
