#include "matrix_factory.h"
#include "my_utils.h"

MatrixFactory::MatrixFactory(uint32_t m, uint32_t k, uint32_t n,
                             uint32_t small_percision, uint32_t ratio,
                             uint32_t seed_perc)
    : small_perc_(small_percision), ratio_(ratio), m_(m), k_(k), n_(n),
      seed_perc_(seed_perc)
{
}

Mat3Tuple MatrixFactory::create_mats()
{
    RawAddr start_addr   = generate_();
    RawAddr aligned_addr = start_addr & ~(kAlign_ - 1);
    RawAddr next_addr =
        (aligned_addr + small_perc_ * ratio_ * m_ * k_) & ~(kAlign_ - 1);
    RawAddr final_addr = (next_addr + small_perc_ * k_ * n_) & ~(kAlign_ - 1);

    Mat3Tuple ret_arr = {
        Matrix{aligned_addr, small_perc_ * ratio_, m_, k_},
        Matrix{next_addr, small_perc_, k_, n_},
        Matrix{final_addr, small_perc_ * ratio_, m_, n_},
    };

    return ret_arr;
}
