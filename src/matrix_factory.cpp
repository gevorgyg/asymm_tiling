#include "matrix_factory.h"

MatrixFactory::MatrixFactory(uint32_t m, uint32_t k, uint32_t n,
                             uint32_t small_percision, uint32_t ratio)
    : small_perc_(small_percision), ratio_(ratio), m_(m), k_(k), n_(n)
{
}

MatrixFactory::MatTuple MatrixFactory::create_memory_source()
{
    static constexpr uint32_t kAlign = 0x40;

    RawAddr start_addr   = generate_();
    RawAddr aligned_addr = (start_addr / kAlign) * kAlign;
    RawAddr next_addr =
        ceil(aligned_addr + small_perc_ * ratio_ * m_ * k_, kAlign) * kAlign;
    RawAddr final_addr =
        ceil(next_addr + small_perc_ * k_ * n_, kAlign) * kAlign;

    MatTuple ret_arr = {
        Matrix{aligned_addr, small_perc_ * ratio_, m_, k_},
        Matrix{next_addr, small_perc_, k_, n_},
        Matrix{final_addr, small_perc_ * ratio_, m_, n_},
    };

    return ret_arr;
}
