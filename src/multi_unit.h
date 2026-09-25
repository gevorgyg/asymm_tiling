#ifndef MULTI_UNIT_H_
#define MULTI_UNIT_H_

#include "cachesim.h"
#include "my_utils.h"
#include "prngfifo.h"

class MultiUnit
{
    using MultiplyMode = void (MultiUnit::*)(const Tile&, const Tile&,
                                             const Tile&);

  public:
    enum BSource { fifo, memory };

    MultiUnit(CacheUnit cache, PrngFifo prng_fifo, Mat3Tuple mats,
              size_t tile_w, size_t tile_h, BSource b_source);

    void output_stat_matmul();

    void weight_stat_matmul();

    const CacheUnit& cache() const;
    const PrngFifo& prng_fifo() const;

    void register_stats() const;

  private:
    BSource b_source_;

    CacheUnit cache_;
    PrngFifo prng_fifo_;

    Matrix a_, b_, c_;

    const size_t tile_w_{};
    const size_t tile_h_{};

    const size_t inner_dim_{a_.width};
    const size_t reg_dim_{4};
    const size_t cache_line_size_{64};
    const size_t mulacc_cost_{4};

    void load_into_reg(const Tile& t, size_t r, size_t c);

    void store_from_reg(const Tile& t, size_t r, size_t c);

    void mulacc() const;

    void reg_weight_mul(const Tile& a, const Tile& b, const Tile& c);

    void reg_output_mul(const Tile& a, const Tile& b, const Tile& c);

    void tile_mul(MultiplyMode mult_func);

    void calculate_addr(const Tile& t, size_t r, size_t c, char operation);
};

#endif
