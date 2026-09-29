#ifndef MULTI_UNIT_H_
#define MULTI_UNIT_H_

#include "cachesim.h"
#include "my_options.h"
#include "my_utils.h"
#include "prngfifo.h"

class MultiUnit
{
    using MultiplyMode = void (MultiUnit::*)(const Tile&, const Tile&,
                                             const Tile&);

  public:
    MultiUnit(const MyOptions& options);

    void run()
    {
        (this->*run_matmul)();
    }

    const CacheUnit& cache() const;
    const PrngFifo& prng_fifo() const;

    void register_stats() const;

  private:
    const MyOptions& options_;

    BSource b_source_;

    CacheUnit cache_;
    PrngFifo prng_fifo_;

    Matrix a_, b_, c_;

    const size_t tile_w_{};
    const size_t tile_h_{};

    const size_t inner_dim_{options_.k};
    const size_t reg_dim_{options_.reg_dim};
    const size_t cache_line_size_{size_t{1} << options_.block_size};
    const size_t mulacc_cost_{options_.mulacc_cost};

    void (MultiUnit::*run_matmul)();

    void output_stat_matmul();

    void weight_stat_matmul();

    void load_into_reg(const Tile& t, size_t r, size_t c);

    void store_from_reg(const Tile& t, size_t r, size_t c);

    void mulacc() const;

    void reg_weight_mul(const Tile& a, const Tile& b, const Tile& c);

    void reg_output_mul(const Tile& a, const Tile& b, const Tile& c);

    void tile_mul(MultiplyMode mult_func);

    void calculate_addr(const Tile& t, size_t r, size_t c, char operation);
};

#endif
