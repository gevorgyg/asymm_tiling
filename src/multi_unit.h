#ifndef MULTI_UNIT_H_
#define MULTI_UNIT_H_

#include "cachesim.h"
#include "my_utils.h"

class MultipUnit
{
    using MultiplyMode = void (MultipUnit::*)(const Tile&, const Tile&,
                                              const Tile&);

  public:
    MultipUnit(CacheUnit cache, std::tuple<Matrix, Matrix, Matrix> mats,
               size_t tile_w, size_t tile_h);

    MultipUnit(CacheUnit cache, std::tuple<Matrix, SeedArray, Matrix> mats,
               size_t tile_w, size_t tile_h);

    void output_stat_mul();

    void weight_stat_mul();

    const CacheUnit& get_cache_unit() const;

  private:
    CacheUnit cache_;
    Matrix a_, b_, c_;
    SeedArray seeds_;

    size_t tile_w_{};
    size_t tile_h_{};

    size_t inner_dim_{a_.width};
    size_t reg_dim_{4};
    size_t cache_line_size_{64};

    void load_into_reg(const Tile& t, size_t r, size_t c);

    void store_from_reg(const Tile& t, size_t r, size_t c);

    void mulacc() const;

    void weight_tile_mul(const Tile& a, const Tile& b, const Tile& c);

    void output_tile_mul(const Tile& a, const Tile& b, const Tile& c);

    void cache_level_mult(MultiplyMode mult_func);

    void calculate_addr(const Tile& t, size_t r, size_t c, char operation);
};

#endif
