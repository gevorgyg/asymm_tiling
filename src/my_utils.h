#ifndef MY_UTILS_H_
#define MY_UTILS_H_

#include <random>

using RawAddr  = uint64_t;
using Tag      = uint64_t;
using BitMask  = uint64_t;
using SetIndex = uint64_t;
using DirtyBit = bool;
using Outcome  = bool;

#define ASYMT_PRNGFIFO_STATS(X)                                                \
    X(size_t, pops)                                                            \
    X(size_t, stalls)                                                          \
    X(size_t, stall_cycles)

#define ASYMT_CREATE_FIELDS(type, stat) type stat##_{};

#define ASYMT_CREATE_STRING_NAME(name) "PrngFifo: " #name
#define ASYMT_CREATE_FIELD_NAME(name) name##_

#define ASYMT_REGISTER_NAME(type, name)                                        \
    gRegistry().reg_stat(ASYMT_CREATE_STRING_NAME(name),                       \
                         &ASYMT_CREATE_FIELD_NAME(name));

// TODO:
// #define ASYMT_REGISTER_FUNCTION(type, name, func) \
//     gRegistry().reg_stat(ASYMT_CREATE_STRING_NAME(name), \
//                          [this]() { func } ASYMT_CREATE_FIELD_NAME(name));

class Clock
{
  public:
    static void tick(const size_t cycles = 1)
    {
        cycles_ += cycles;
    }

    static void reset()
    {
        cycles_ = 0;
    }

    static size_t cur_cycles()
    {
        return cycles_;
    }

  private:
    inline static size_t cycles_ = 0;
};

struct Matrix {
    RawAddr base{};

    size_t elem_size{};

    size_t height{};
    size_t width{};
};

using Mat3Tuple = std::tuple<Matrix, Matrix, Matrix>;

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

struct SimpleRandomNumberGenerator {
    std::random_device rd_dev;
    std::mt19937_64 mt_eng;
    std::uniform_int_distribution<uint64_t> uni_dist;

    SimpleRandomNumberGenerator();

    uint64_t operator()();
};

inline size_t ceil(const size_t x, const size_t y)
{
    return (x + y - 1) / y;
}

#endif
