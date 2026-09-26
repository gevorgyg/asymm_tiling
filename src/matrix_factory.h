#include "my_utils.h"

class MatrixFactory
{

    static constexpr uint32_t kAlign_ = 0b100;

  public:
    MatrixFactory(uint32_t m, uint32_t k, uint32_t n, uint32_t small_percision,
                  uint32_t ratio);

    Mat3Tuple create_mats();

  private:
    const uint32_t small_perc_;
    const uint32_t ratio_;
    const uint32_t m_, k_, n_;
    SimpleRandomNumberGenerator generate_;
};
