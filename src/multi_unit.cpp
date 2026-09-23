#include "multi_unit.h"

MultiUnit::MultiUnit(CacheUnit cache, std::tuple<Matrix, Matrix, Matrix> mats,
                     size_t tile_w, size_t tile_h)
    : cache_(cache), a_(std::get<0>(mats)), b_(std::get<1>(mats)),
      c_(std::get<2>(mats)), tile_w_(tile_w), tile_h_(tile_h)
{
}

MultiUnit::MultiUnit(CacheUnit cache,
                     std::tuple<Matrix, SeedArray, Matrix> mats, size_t tile_w,
                     size_t tile_h)
    : cache_(cache), a_(std::get<0>(mats)), seeds_(std::get<1>(mats)),
      c_(std::get<2>(mats)), tile_w_(tile_w), tile_h_(tile_h)
{
}

void MultiUnit::output_stat_mul()
{
    cache_level_multi(&MultiUnit::output_tile_mul);
}

void MultiUnit::weight_stat_mul()
{
    cache_level_multi(&MultiUnit::weight_tile_mul);
}

const CacheUnit& MultiUnit::cache() const
{
    return cache_;
}

void MultiUnit::load_into_reg(const Tile& t, size_t r, size_t c)
{
    calculate_addr(t, r, c, 'r');
}

void MultiUnit::store_from_reg(const Tile& t, size_t r, size_t c)
{
    calculate_addr(t, r, c, 'w');
}

void MultiUnit::mulacc() const
{
    // add dummy cycles
}

void MultiUnit::weight_tile_mul(const Tile& a, const Tile& b, const Tile& c)
{
    for (size_t k = 0; k < ceil(inner_dim_, reg_dim_); ++k) {
        for (size_t col = 0; col < ceil(b.width, reg_dim_); ++col) {
            load_into_reg(b, k, col);
            for (size_t row = 0; row < ceil(a.height, reg_dim_); ++row) {
                load_into_reg(a, row, k);
                load_into_reg(c, row, col);
                mulacc();
                store_from_reg(c, row, col);
            }
        }
    }
}

void MultiUnit::output_tile_mul(const Tile& a, const Tile& b, const Tile& c)
{
    for (size_t row = 0; row < ceil(a.height, reg_dim_); ++row) {
        for (size_t col = 0; col < ceil(b.width, reg_dim_); ++col) {
            load_into_reg(c, row, col);
            for (size_t k = 0; k < ceil(inner_dim_, reg_dim_); ++k) {
                load_into_reg(a, row, k);
                load_into_reg(b, k, col);
                mulacc();
            }
            store_from_reg(c, row, col);
        }
    }
}

void MultiUnit::cache_level_multi(MultiplyMode mult_func)
{
    Tile ta{a_, a_.base, tile_h_, a_.width};
    Tile tb{b_, b_.base, b_.height, tile_w_};
    Tile tc{c_, c_.base, tile_h_, tile_w_};

    for (int row = 0; row < ceil(a_.height, tile_h_); ++row) {
        ta.base = a_.base + (row * a_.width * tile_h_) * a_.elem_size;
        for (int col = 0; col < ceil(b_.width, tile_w_); ++col) {
            tb.base = b_.base + (col * tile_w_) * b_.elem_size;
            tc.base = c_.base +
                      (col * tile_w_ + row * c_.width * tile_h_) * c_.elem_size;

            (this->*mult_func)(ta, tb, tc);
        }
    }
}

void MultiUnit::calculate_addr(const Tile& t, size_t r, size_t c,
                               char operation)
{
    size_t row           = r * reg_dim_;
    size_t col           = c * reg_dim_;
    size_t row_byte_size = reg_dim_ * t.parent_mat.elem_size;

    for (size_t i = 0; i < reg_dim_; ++i) {
        RawAddr addr                     = t.get_addr(row + i, col);
        RawAddr cache_aligned_addr_start = addr & ~(cache_line_size_ - 1);
        RawAddr cache_aligned_addr_end =
            (addr + row_byte_size - 1) & ~(cache_line_size_ - 1);

        for (size_t line = cache_aligned_addr_start;
             line <= cache_aligned_addr_end; line += cache_line_size_) {
            cache_.process_request(operation, line);
        }
    }
}
