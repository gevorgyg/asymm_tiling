#include "cachesim.h"
#include "my_utils.h"
#include <array>
#include <cstdint>
#include <cstdio>
#include <fmt/printf.h>
#include <spdlog/async.h>
#include <spdlog/sinks/ansicolor_sink.h>
#include <spdlog/spdlog.h>

static inline size_t ceil(const size_t x, const size_t y)
{
    return (x + y - 1) / y;
}

struct Matrix {
    RawAddr base{};

    size_t elem_size{};

    size_t height{};
    size_t width{};
};

struct Tile {
    const Matrix& parent_mat;
    RawAddr base;

    size_t height;
    size_t width;

    RawAddr get_addr(const size_t row, const size_t col) const
    {
        return base + (col + row * parent_mat.width) * parent_mat.elem_size;
    }
};

class MultipUnit
{
  public:
    MultipUnit(CacheUnit& cache, Matrix a, Matrix b, Matrix c, size_t tile_w,
               size_t tile_h)
        : cache_(cache), a_(a), b_(b), c_(c), tile_w_(tile_w), tile_h_(tile_h)
    {
    }

    void output_stat_mul() const
    {
        cache_level_mult(&MultipUnit::output_tile_mul);
    }

    void weight_stat_mul() const
    {
        cache_level_mult(&MultipUnit::weight_tile_mul);
    }

  private:
    CacheUnit& cache_;
    Matrix a_, b_, c_;

    size_t tile_w_{};
    size_t tile_h_{};

    size_t inner_dim_{a_.width};
    size_t reg_dim_{4};
    size_t cache_line_size_{64};

    void load_into_reg(const Tile& t, size_t r, size_t c) const
    {
        calculate_addr(t, r, c, 'r');
    }

    void store_from_reg(const Tile& t, size_t r, size_t c) const
    {
        calculate_addr(t, r, c, 'w');
    }

    void mulacc() const
    {
        // add dummy cycles
    }

    void weight_tile_mul(const Tile& a, const Tile& b, const Tile& c) const
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

    void output_tile_mul(const Tile& a, const Tile& b, const Tile& c) const
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

    using MultiplyMode = void (MultipUnit::*)(const Tile&, const Tile&,
                                              const Tile&) const;

    inline void cache_level_mult(MultiplyMode mult_func) const
    {
        Tile ta{a_, a_.base, tile_h_, a_.width};
        Tile tb{b_, b_.base, b_.height, tile_w_};
        Tile tc{c_, c_.base, tile_h_, tile_w_};

        for (int row = 0; row < ceil(a_.height, tile_h_); ++row) {
            ta.base = a_.base + (row * a_.width * tile_h_) * a_.elem_size;
            for (int col = 0; col < ceil(b_.width, tile_w_); ++col) {
                tb.base = b_.base + (col * tile_w_) * b_.elem_size;
                tc.base = c_.base + (col * tile_w_ + row * c_.width * tile_h_) *
                                        c_.elem_size;

                (this->*mult_func)(ta, tb, tc);
            }
        }
    }

    inline void calculate_addr(const Tile& t, size_t r, size_t c,
                               char operation) const
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
};

struct MatrixFactory {
    uint32_t small_perc_;
    uint32_t ratio_;
    uint32_t m_, k_, n_;
    SimpleRandomNumberGenerator generate;

    MatrixFactory(uint32_t m, uint32_t k, uint32_t n, uint32_t small_percision,
                  uint32_t ratio)
        : small_perc_(small_percision), ratio_(ratio), m_(m), k_(k), n_(n)
    {
    }

    std::array<Matrix, 3> create()
    {
        static constexpr uint32_t kAlign = 0x40;

        RawAddr start_addr   = generate();
        RawAddr aligned_addr = (start_addr / kAlign) * kAlign;
        RawAddr next_addr =
            ceil(aligned_addr + small_perc_ * ratio_ * m_ * k_, kAlign) *
            kAlign;
        RawAddr final_addr =
            ceil(next_addr + small_perc_ * k_ * n_, kAlign) * kAlign;

        std::array<Matrix, 3> ret_arr = {
            Matrix{aligned_addr, small_perc_ * ratio_, m_, k_},
            Matrix{next_addr, small_perc_, k_, n_},
            Matrix{final_addr, small_perc_ * ratio_, m_, n_},
        };

        return ret_arr;
    }
};

int main()
{
    // init logger
    spdlog::init_thread_pool(8192, 1);
    std::shared_ptr<spdlog::logger> bg_console_logger =
        spdlog::create_async<spdlog::sinks::ansicolor_stdout_sink_mt>(
            "b_console_logger");
    spdlog::set_default_logger(bg_console_logger);
    spdlog::info("Initialized Async Logger");

    CacheUnit& cache =
        CacheUnit::getInstance(6, 100, 14, 4, 3, 16, 20, 3, true);

    // create matrices
    MatrixFactory mat_factory(100, 100, 100, 1, 4);
    auto [a, b, c] = mat_factory.create();
    MultipUnit m{cache, a, b, c, 25, 25};

    // start simulation
    m.weight_stat_mul();

    fmt::printf("\n--- SIMULATION RESULTS ---\n");
    fmt::printf("L1 Miss Rate: %.4f%%\n", cache.calc_L1_miss_rate() * 100.0);
    fmt::printf("L2 Miss Rate: %.4f%%\n", cache.calc_L2_miss_rate() * 100.0);
    fmt::printf("Avg Access Time: %.2f cycles\n", cache.calc_avg_access_time());

    return 0;
}
