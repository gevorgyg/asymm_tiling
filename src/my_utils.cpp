#include "my_utils.h"

SimpleRandomNumberGenerator::SimpleRandomNumberGenerator()
    : rd_dev(), mt_eng(rd_dev()), uni_dist(1, 0xffffffff)
{
}
uint64_t SimpleRandomNumberGenerator::operator()()
{
    return uni_dist(mt_eng);
}
