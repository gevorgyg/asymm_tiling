#include "matrix_factory.h"
#include "my_utils.h"

MatrixFactory::MatrixFactory(uint32_t m, uint32_t k, uint32_t n,
                             uint32_t small_percision, uint32_t ratio,
                             size_t line_bytes, bool aligned)
    : small_perc_(small_percision), ratio_(ratio), m_(m), k_(k), n_(n),
      line_bytes_(line_bytes), aligned_(aligned)
{
}

Matrix MatrixFactory::make(RawAddr base, size_t elem_size, size_t height,
                           size_t width) const
{
    size_t stride = width * elem_size;
    if (aligned_) {
        stride = ceil(stride, line_bytes_) * line_bytes_;
    }
    return Matrix{base, elem_size, height, width, stride};
}

RawAddr MatrixFactory::next_base(const Matrix& prev) const
{
    RawAddr end = prev.base + prev.height * prev.stride;
    if (aligned_) {
        return ceil(end, line_bytes_) * line_bytes_;
    }
    // packed layout, kept as is so earlier results stay reproducible
    return end & ~(kAlign_ - 1);
}

Mat3Tuple MatrixFactory::create_mats()
{
    const size_t big = small_perc_ * ratio_;

    Matrix a = make(kBaseAddr_, big, m_, k_);
    Matrix b = make(next_base(a), small_perc_, k_, n_);
    Matrix c = make(next_base(b), big, m_, n_);

    return {a, b, c};
}
