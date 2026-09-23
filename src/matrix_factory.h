#include "my_utils.h"

class MatrixFactory
{
    using MatTuple          = std::tuple<Matrix, Matrix, Matrix>;
    using MatSeedArrayTuple = std::tuple<Matrix, Matrix, Matrix>;

  public:
    MatrixFactory(uint32_t m, uint32_t k, uint32_t n, uint32_t small_percision,
                  uint32_t ratio);

    MatSeedArrayTuple create_fifo_source()
    {
    }

    MatTuple create_memory_source();

  private:
    uint32_t small_perc_;
    uint32_t ratio_;
    uint32_t m_, k_, n_;
    SimpleRandomNumberGenerator generate_;
};
