#include <cstdint>
#include <cstdio>
#include <limits>
#include <random>

struct SimpleRandomNumberGenerator {
    std::random_device rd_dev;
    std::mt19937_64 mt_eng;
    std::uniform_int_distribution<uint64_t> uni_dist;

    SimpleRandomNumberGenerator()
        : rd_dev(), mt_eng(rd_dev()), uni_dist(1, 0xffffffff)
    {
    }

    uint64_t operator()()
    {
        return uni_dist(mt_eng);
    }
};

int main()
{
    SimpleRandomNumberGenerator generate{};

    printf("random number: %lX\n", generate());

    return 0;
}
