#ifndef MY_UTILS_H_
#define MY_UTILS_H_

#include <random>

struct SimpleRandomNumberGenerator {
    std::random_device rd_dev;
    std::mt19937_64 mt_eng;
    std::uniform_int_distribution<uint64_t> uni_dist;

    SimpleRandomNumberGenerator();

    uint64_t operator()();
};

#endif
