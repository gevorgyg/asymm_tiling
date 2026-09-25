#ifndef PRNG_FIFO_H_
#define PRNG_FIFO_H_

#include "my_utils.h"

class PrngFifo
{
  public:
    PrngFifo(size_t capacity, size_t generation_cost, size_t accsess_cost,
             size_t seed_size);

    // pop into register
    void pop(const size_t elements);

    void load_seed();

    size_t seed_size() const;
    void register_stats() const;

  private:
    size_t size_{0};
    size_t prev_cycles_ = 0;
    const size_t capacity_;
    const size_t generation_cost_; // per element
    const size_t accsess_cost_;
    const size_t seed_size_;

    ASYMT_PRNGFIFO_STATS(ASYMT_CREATE_FIELDS)
};

#endif
