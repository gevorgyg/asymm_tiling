// Trace-driven driver for CacheUnit, used by the python differential tests.
//
// usage: cache_driver block mem l1_size l1_cycles l1_assoc
//                     l2_size l2_cycles l2_assoc write_alloc  < trace
//
// Sizes, associativities and the block size are log2, as in config.toml.
// Trace lines are "<r|w> <hex address>". For every access one record is
// printed:
//
//     <cycles> <L1> <L2> <mem>
//
// cycles  - clock delta of the access
// L1, L2  - H (hit), M (miss) or - (level not accessed)
// mem     - number of memory accesses (reads + writes) caused by the access

#include "cachesim.h"

#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char* argv[])
{
    if (argc != 10) {
        std::cerr << "usage: cache_driver block mem l1_size l1_cycles l1_assoc "
                     "l2_size l2_cycles l2_assoc write_alloc < trace\n";
        return 2;
    }

    int a[9];
    for (int i = 0; i < 9; ++i) {
        a[i] = std::atoi(argv[i + 1]);
    }

    CacheUnit cache{a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8] != 0};
    Clock::reset();

    const size_t n_levels = cache.n_levels();
    std::vector<CacheUnit::LevelStats> before(n_levels);

    char op;
    std::string addr_str;
    std::string out;

    while (std::cin >> op >> addr_str) {
        RawAddr addr = std::stoull(addr_str, nullptr, 16);

        size_t mem_before = 0;
        for (size_t i = 0; i < n_levels; ++i) {
            before[i] = cache.level_stats(i);
            mem_before += before[i].dram_accesses;
        }
        size_t cycles_before = Clock::cur_cycles();

        cache.process_request(op, addr);

        out += std::to_string(Clock::cur_cycles() - cycles_before);

        size_t mem_after = 0;
        for (size_t i = 0; i < n_levels; ++i) {
            auto after = cache.level_stats(i);
            mem_after += after.dram_accesses;

            char outcome = '-';
            if (after.hits > before[i].hits) {
                outcome = 'H';
            } else if (after.misses > before[i].misses) {
                outcome = 'M';
            }
            out += ' ';
            out += outcome;
        }

        out += ' ';
        out += std::to_string(mem_after - mem_before);
        out += '\n';
    }

    std::fwrite(out.data(), 1, out.size(), stdout);
    return 0;
}
