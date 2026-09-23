#include "my_utils.h"

class MatrixFactory
{
    using MatTuple          = std::tuple<Matrix, Matrix, Matrix>;
    using MatSeedArrayTuple = std::tuple<Matrix, SeedArray, Matrix>;

    static constexpr uint32_t kAlign_ = 0b100;

  public:
    MatrixFactory(uint32_t m, uint32_t k, uint32_t n, uint32_t small_percision,
                  uint32_t ratio, uint32_t seed_perc = 1);

    MatSeedArrayTuple create_fifo_source();

    MatTuple create_memory_source();

  private:
    const uint32_t small_perc_;
    const uint32_t ratio_;
    const uint32_t m_, k_, n_;
    const uint32_t seed_perc_;
    SimpleRandomNumberGenerator generate_;
};
