#include "multi_unit.h"
#include "matrix_factory.h"
#include "my_utils.h"
#include "registry.h"

MultiUnit::MultiUnit(const MyOptions& options)
    : options_(options),
      b_source_(options_.b_source),
      cache_(options_.block_size, options_.mem_cycles, options_.l1_size,
             options_.l1_cycles, options_.l1_assoc, options_.l2_size,
             options_.l2_cycles, options_.l2_assoc, options_.write_alloc,
             options_.policy),
      prng_fifo_(options_.capacity, options_.generation_cost,
                 options_.accsess_cost, options_.seed_size),
      tile_w_(options_.tile_w), tile_h_(options_.tile_h)
{
    // create matrices
    MatrixFactory mat_factory{options.m,     options.k,
                              options.n,     options.small_percision,
                              options.ratio, cache_line_size_,
                              options.aligned};

    auto mats = mat_factory.create_mats();

    a_ = std::get<0>(mats);
    b_ = std::get<1>(mats);
    c_ = std::get<2>(mats);

    register_stats();

    if (options_.mult_oriantation == MyOptions::output) {
        run_matmul = &MultiUnit::output_stat_matmul;
    } else {
        run_matmul = &MultiUnit::weight_stat_matmul;
    }
}

void MultiUnit::output_stat_matmul()
{
    tile_mul(&MultiUnit::reg_output_mul);
}

void MultiUnit::weight_stat_matmul()
{
    tile_mul(&MultiUnit::reg_weight_mul);
}

const CacheUnit& MultiUnit::cache() const
{
    return cache_;
}
const PrngFifo& MultiUnit::prng_fifo() const
{
    return prng_fifo_;
}

void MultiUnit::load_into_reg(const Tile& t, size_t r, size_t c)
{
    if (b_source_ == BSource::fifo && &t.parent_mat == &b_) {
        prng_fifo_.pop(block_rows(t, r) * block_cols(t, c));
        return;
    }

    calculate_addr(t, r, c, 'r');
}

void MultiUnit::store_from_reg(const Tile& t, size_t r, size_t c)
{
    calculate_addr(t, r, c, 'w');
}

void MultiUnit::mulacc() const
{
    Clock::tick(mulacc_cost_);
}

void MultiUnit::reg_weight_mul(const Tile& a, const Tile& b, const Tile& c)
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

void MultiUnit::reg_output_mul(const Tile& a, const Tile& b, const Tile& c)
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

void MultiUnit::tile_mul(MultiplyMode mult_func)
{
    Tile ta{a_, a_.base, tile_h_, a_.width};
    Tile tb{b_, b_.base, b_.height, tile_w_};
    Tile tc{c_, c_.base, tile_h_, tile_w_};

    const size_t seed_size = prng_fifo_.seed_size();

    for (int row = 0; row < ceil(a_.height, tile_h_); ++row) {
        ta.base = a_.addr(row * tile_h_, 0);
        // the last tile row / column only covers what is left of the matrix
        ta.height = tc.height = std::min(tile_h_, a_.height - row * tile_h_);
        for (int col = 0; col < ceil(b_.width, tile_w_); ++col) {
            tb.base = b_.addr(0, col * tile_w_);
            tc.base = c_.addr(row * tile_h_, col * tile_w_);
            tb.width = tc.width = std::min(tile_w_, b_.width - col * tile_w_);

            if (b_source_ == BSource::fifo) {
                RawAddr seed_addr = b_.base + col * seed_size;
                cache_.process_request('r', seed_addr);
                prng_fifo_.load_seed();
            }

            (this->*mult_func)(ta, tb, tc);
        }
    }
}

void MultiUnit::calculate_addr(const Tile& t, size_t r, size_t c,
                               char operation)
{
    size_t row           = r * reg_dim_;
    size_t col           = c * reg_dim_;
    size_t row_byte_size = block_cols(t, c) * t.parent_mat.elem_size;

    for (size_t i = 0; i < block_rows(t, r); ++i) {
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

size_t MultiUnit::block_rows(const Tile& t, size_t r) const
{
    return std::min(reg_dim_, t.height - r * reg_dim_);
}

size_t MultiUnit::block_cols(const Tile& t, size_t c) const
{
    return std::min(reg_dim_, t.width - c * reg_dim_);
}

void MultiUnit::register_stats() const
{
    gRegistry().reg_stat<size_t>("Simulation: Total cycles",
                                 [this]() { return Clock::cur_cycles(); });
    gRegistry().reg_stat<double>("Simulation: Total MACs", [this]() {
        size_t macs = c_.height * c_.width * inner_dim_;
        return Clock::cur_cycles() ? (double)macs / Clock::cur_cycles() : 0.0;
    });

    prng_fifo_.register_stats();
    cache_.register_stats();
}
