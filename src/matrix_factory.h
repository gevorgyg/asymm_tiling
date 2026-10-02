#include "my_utils.h"

class MatrixFactory
{

    static constexpr uint32_t kAlign_ = 0b100;
    // fixed (not null) base so runs are reproducible, A starts here
    static constexpr RawAddr kBaseAddr_ = 0x1000;

  public:
    // aligned: pad every row to whole cache lines (line_bytes) and start
    // every matrix on a line, so a row of width w is exactly
    // ceil(w * elem / line_bytes) lines. Off: rows are packed and B / C
    // follow the previous matrix at 4-byte alignment.
    MatrixFactory(uint32_t m, uint32_t k, uint32_t n, uint32_t small_percision,
                  uint32_t ratio, size_t line_bytes = 64, bool aligned = false);

    Mat3Tuple create_mats();

  private:
    const uint32_t small_perc_;
    const uint32_t ratio_;
    const uint32_t m_, k_, n_;
    const size_t line_bytes_;
    const bool aligned_;

    Matrix make(RawAddr base, size_t elem_size, size_t height,
                size_t width) const;
    RawAddr next_base(const Matrix& prev) const;
};
