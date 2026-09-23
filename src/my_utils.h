#ifndef MY_UTILS_H_
#define MY_UTILS_H_

#include <random>

using RawAddr  = uint64_t;
using Tag      = uint64_t;
using BitMask  = uint64_t;
using SetIndex = uint64_t;
using DirtyBit = bool;
using Outcome  = bool;

struct SeedArray {
    RawAddr base{};

    size_t elem_size{};
    size_t size{};
};

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
