#include "my_utils.h"
#include <array>
#include <cstdint>
#include <cstdio>
#include <spdlog/async.h>
#include <spdlog/sinks/ansicolor_sink.h>
#include <spdlog/spdlog.h>

using raw_addr = uint64_t;

enum class MatName { in_a, in_b, out_c };

inline size_t ceil(const size_t x, const size_t y)
{
    return (x + y - 1) / y;
}

struct Matrix {
    MatName name{};
    raw_addr base{};

    size_t elem_size{};

    size_t height{};
    size_t width{};
};

struct Tile {
    const Matrix& parent_mat;
    raw_addr base;

    size_t height;
    size_t width;

    raw_addr get_addr(const size_t row, const size_t col) const
    {
        return base + (col + row * parent_mat.width) * parent_mat.elem_size;
    }
};

struct Multipiler {
    Matrix a, b, c;

    size_t tile_w{};
    size_t tile_h{};

    size_t inner_dim{a.width};
    size_t reg_dim{4};
    size_t cache_line_size_{64};

    void load_into_reg(const Tile& t, size_t r, size_t c) const
    {
        size_t row           = r * reg_dim;
        size_t col           = c * reg_dim;
        size_t row_byte_size = reg_dim * t.parent_mat.elem_size;

        spdlog::info("base addr: {}", t.base);
        for (size_t i = 0; i < reg_dim; ++i) {
            raw_addr addr                     = t.get_addr(row + i, col);
            raw_addr cache_aligned_addr_start = addr & ~(cache_line_size_ - 1);
            raw_addr cache_aligned_addr_end =
                (addr + row_byte_size - 1) & ~(cache_line_size_ - 1);

            for (size_t line = cache_aligned_addr_start;
                 line <= cache_aligned_addr_end; line += cache_line_size_) {
                spdlog::info("touched: {} -> {}", line,
                             line + cache_line_size_);
            }
        }
    }

    void store_reg(const Tile& t, size_t r, size_t c) const
    {
    }

    void mulacc() const
    {
    }

    void weight_tile_mul(const Tile& a, const Tile& b, const Tile& c) const
    {
        for (size_t r = 0; r < a.height; ++r) {
            for (size_t c = 0; c < a.width; ++c) {
                // load C(r,c)
                for (size_t k = 0; k < inner_dim; ++k) {
                    // load A(r,k)
                    // load B(k,c)
                }
                // store C(r,c)
            }
        }
    }

    void output_tile_mul(const Tile& a, const Tile& b, const Tile& c) const
    {
        for (size_t row = 0; row < ceil(a.height, reg_dim); ++row) {
            for (size_t col = 0; col < ceil(b.width, reg_dim); ++col) {

                spdlog::info("load C: ");
                load_into_reg(c, row, col);
                for (size_t k = 0; k < ceil(inner_dim, reg_dim); ++k) {
                    spdlog::info("load A: ");
                    load_into_reg(a, row, k);
                    spdlog::info("load B: ");
                    load_into_reg(b, k, col);
                }
                spdlog::info("store C: ");
                store_reg(c, row, col);
            }
        }
    }

    void output_stat_matmul() const
    {
        Tile ta{a, a.base, tile_h, a.width};
        Tile tb{b, b.base, b.height, tile_w};
        Tile tc{c, c.base, tile_h, tile_w};

        for (int row = 0; row < ceil(a.height, tile_h); ++row) {
            ta.base = a.base + (row * a.width * tile_h) * a.elem_size;
            for (int col = 0; col < ceil(b.width, tile_w); ++col) {
                tb.base = b.base + (col * tile_w) * b.elem_size;
                tc.base = c.base +
                          (col * tile_w + row * c.width * tile_h) * c.elem_size;

                spdlog::info("tiles {}, {}", row, col);
                output_tile_mul(ta, tb, tc);
            }
        }
    }

    void weight_stat_matmul(const Matrix& a, const Matrix& b,
                            const Matrix& c) const
    {
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

        raw_addr start_addr   = generate();
        raw_addr aligned_addr = (start_addr / kAlign) * kAlign;
        raw_addr next_addr =
            ceil(aligned_addr + small_perc_ * ratio_ * m_ * k_, kAlign) *
            kAlign;
        raw_addr final_addr =
            ceil(next_addr + small_perc_ * k_ * n_, kAlign) * kAlign;

        std::array<Matrix, 3> ret_arr = {
            Matrix{MatName::in_a, aligned_addr, small_perc_ * ratio_, m_, k_},
            Matrix{MatName::in_b, next_addr, small_perc_, k_, n_},
            Matrix{MatName::out_c, final_addr, small_perc_ * ratio_, m_, n_},
        };

        return ret_arr;
    }
};

int main()
{
    spdlog::init_thread_pool(8192, 1);
    std::shared_ptr<spdlog::logger> bg_console_logger =
        spdlog::create_async<spdlog::sinks::ansicolor_stdout_sink_mt>(
            "b_console_logger");
    spdlog::set_default_logger(bg_console_logger);
    spdlog::info("Initialized Async Logger");

    MatrixFactory mat_factory(100, 100, 100, 1, 4);
    auto [a, b, c] = mat_factory.create();

    Multipiler m{a, b, c, 25, 25};
    m.output_stat_matmul();

    return 0;
}
