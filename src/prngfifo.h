#ifndef PRNG_FIFO_H_
#define PRNG_FIFO_H_

class PrngFifo
{
  public:
    PrngFifo(size_t capacity, size_t generation_cost, size_t accsess_cost);

    // pop into register
    void pop(const size_t elements, size_t& cur_cycles);

    void load_seed();

  private:
    size_t size_{0};
    const size_t capacity_;
    const size_t generation_cost_; // per element
    const size_t accsess_cost_;

    // stats
    uint64_t pops_{0};
    uint64_t stalls_{0};
    uint64_t stall_cycles_{0};
};

#endif
