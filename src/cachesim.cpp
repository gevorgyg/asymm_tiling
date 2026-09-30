#include "cachesim.h"
#include "my_utils.h"
#include "registry.h"
#include <cassert>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace
{

constexpr int B_ADDR_SIZE  = 64;
constexpr int B_ALIGN_SIZE = 2;

/* simple log function */
int my_log2(int size)
{
    short result = 0;
    while (size >>= 1)
        result++;
    return result;
}

/* number of ways: assoc, or every line of the cache when assoc = 0 (fully
 * associative). size in bytes, block_size log2 */
int n_of_ways(int size, int block_size, int assoc)
{
    return assoc == 0 ? (size >> block_size) : assoc;
}

/* number of sets of a cache level, throws on a geometry that can't be built.
 * size in bytes, block_size log2, assoc in ways (0 = fully associative) */
int checked_n_of_sets(int level, int size, int block_size, int assoc)
{
    std::string error = cache_geometry_error(level, size, block_size, assoc);
    if (!error.empty()) {
        throw std::invalid_argument(error);
    }

    return (size >> block_size) / n_of_ways(size, block_size, assoc);
}

} // namespace

std::string cache_geometry_error(int level, int size, int block_size, int assoc)
{
    if (size <= 0 || block_size < 0 || assoc < 0) {
        return fmt::format("L{}: size ({} B) must be positive, block size "
                           "({}, log2) and assoc ({} ways) can't be negative",
                           level, size, block_size, assoc);
    }

    if (block_size > 20 || size > (1 << 30)) {
        return fmt::format("L{}: size {} B or block size 2^{} B is too large "
                           "(max 2^30 B and 2^20 B)",
                           level, size, block_size);
    }

    const int line = 1 << block_size;
    if (size % line != 0) {
        return fmt::format("L{}: size {} B is not a whole number of {} B lines",
                           level, size, line);
    }

    const int lines = size / line;
    const int ways  = n_of_ways(size, block_size, assoc);
    if (ways > lines || lines % ways != 0) {
        return fmt::format("L{}: {} lines ({} B) don't split into whole sets "
                           "of {} ways",
                           level, lines, size, ways);
    }

    // the set index is taken from address bits
    const int sets = lines / ways;
    if (sets & (sets - 1)) {
        return fmt::format("L{}: {} B / ({} ways x {} B) = {} sets, which is not "
                           "a power of two",
                           level, size, ways, line, sets);
    }

    return "";
}

CacheLevelConfig config_level(uint32_t level, int size, int cycles, int assoc)
{
    const int bytes = size <= 30 ? (size == 0 ? 0 : 1 << size) : size;
    const int ways  = assoc == -1 ? 0 : 1 << assoc;
    return {level, static_cast<uint32_t>(bytes), static_cast<uint32_t>(cycles),
            static_cast<uint32_t>(ways)};
}

std::string config_level_error(int level, int size, int assoc, int block_size)
{
    if (size < 0) {
        return fmt::format("L{}: size ({}) can't be negative", level, size);
    }
    if (assoc < -1 || assoc > 30) {
        return fmt::format("L{}: assoc ({}, log2) must be between 0 and 30, or "
                           "-1 for fully associative",
                           level, assoc);
    }
    if (size == 0) {
        return level == 1 ? "L1: size can't be 0, L1 must exist" : "";
    }

    const CacheLevelConfig config = config_level(level, size, 0, assoc);
    return cache_geometry_error(level, config.size, block_size, config.assoc);
}

AddrSplitter::AddrSplitter(int n_of_sets, int block_size)
    : block_size_(block_size),
      b_tag_size_(B_ADDR_SIZE - block_size - my_log2(n_of_sets)),
      tag_mask_(~((BitMask{1} << (B_ADDR_SIZE - b_tag_size_)) - 1)),
      set_mask_(((BitMask{1} << my_log2(n_of_sets)) - 1) << block_size_)
{
}

AddrParts AddrSplitter::operator()(RawAddr addr) const
{
    return {addr, create_tag(addr), create_index(addr)};
}

Tag AddrSplitter::create_tag(RawAddr address) const
{
    return (address & tag_mask_) >> (B_ADDR_SIZE - b_tag_size_);
}

SetIndex AddrSplitter::create_index(RawAddr address) const
{
    return (address & set_mask_) >> block_size_;
}

CacheLevel::CacheLevel(int level, int size, int block_size, int cycles,
                       int assoc, bool write_alloc, int mem_cycles,
                       ReplPolicy policy)
    // splitter is the first member initialized, so it validates the geometry
    // before anything else uses it
    : splitter(checked_n_of_sets(level, size, block_size, assoc), block_size),
      level_nmbr_(level), size_(size), cycles_(cycles),
      assoc_(n_of_ways(size, block_size, assoc)), write_alloc_(write_alloc),
      mem_cycles_(mem_cycles)
{
    const int n_of_sets = (size >> block_size) / assoc_;
    for (int i = 0; i < n_of_sets; ++i) {
        // fixed, non zero, per set seed so random replacement is reproducible
        // (must match tests/ref_cache.py)
        const uint64_t seed = (uint64_t(i) + 1) * 0x9E3779B97F4A7C15ULL;
        sets_.emplace_back(assoc_, policy, seed);
    }
}

void CacheUnit::process_request(char operation, RawAddr address)
{
    switch (operation) {
    case 'r':
        do_read(address);
        break;
    case 'w':
        do_write(address);
        break;
    default:
        std::cerr << "No such operation" << std::endl;
        exit(1);
    }
}

CacheUnit::CacheUnit(int block_size, int mem_cycles,
                     const std::vector<CacheLevelConfig>& cache_levels,
                     bool write_alloc, ReplPolicy policy)
    : block_size_(block_size), mem_cycles_(mem_cycles),
      write_alloc_(write_alloc), policy_(policy)
{
    // construct the levels vector, a level of size 0 doesn't exist (e.g.
    // l2_size = 0 -> L1 only, L1 misses go to memory)
    for (const auto& level_config : cache_levels) {
        if (level_config.size == 0) {
            continue;
        }
        levels_.push_back(std::make_unique<CacheLevel>(
            level_config.level, level_config.size, block_size_,
            level_config.cycles, level_config.assoc, write_alloc_,
            mem_cycles_, policy_));
    }

    if (levels_.empty()) {
        throw std::invalid_argument("the cache needs at least one level");
    }

    // assign level pointers
    if (levels_.size() == 1) {
        levels_[0]->upper_level_ = nullptr;
        levels_[0]->lower_level_ = nullptr;
    } else {
        for (int i = 0; i < levels_.size(); ++i) {
            if (i == 0) {
                levels_[i]->upper_level_ = nullptr;
                levels_[i]->lower_level_ = levels_[i + 1].get();
            } else if (i >= levels_.size() - 1) {
                levels_[i]->upper_level_ = levels_[i - 1].get();
                levels_[i]->lower_level_ = nullptr;
            } else {
                levels_[i]->upper_level_ = levels_[i - 1].get();
                levels_[i]->lower_level_ = levels_[i + 1].get();
            }
        }
    }
}

void CacheUnit::register_stats() const
{
    if (levels_.empty())
        return;

    for (int i = 0; i < levels_.size(); ++i) {
        int level = i + 1;
        gRegistry().reg_stat(fmt::format("CacheUnit: L{} accesses", level),
                             &levels_[i]->n_of_access_);
        gRegistry().reg_stat(fmt::format("CacheUnit: L{} hits", level),
                             &levels_[i]->n_of_hits_);
        gRegistry().reg_stat(fmt::format("CacheUnit: L{} misses", level),
                             &levels_[i]->n_of_misses_);

        gRegistry().reg_stat<double>(
            fmt::format("CacheUnit: L{} hit_rate %", level),
            [this, i]() {
                auto& lvl = levels_[i];
                return lvl->n_of_access_
                           ? ((double)lvl->n_of_hits_ / lvl->n_of_access_) *
                                 100.0
                           : 0.0;
            });

        gRegistry().reg_stat<double>(
            fmt::format("CacheUnit: L{} local_miss_rate %", level),
            [this, i]() {
                auto& lvl = levels_[i];
                return lvl->n_of_access_
                           ? ((double)lvl->n_of_misses_ / lvl->n_of_access_) *
                                 100.0
                           : 0.0;
            });

        if (i > 0) {
            gRegistry().reg_stat<double>(
                fmt::format("CacheUnit: L{} global_miss_rate %", level),
                [this, i]() {
                    size_t total_access = levels_[0]->n_of_access_;
                    return total_access ? ((double)levels_[i]->n_of_misses_ /
                                           total_access) *
                                              100.0
                                        : 0.0;
                });
        }

        gRegistry().reg_stat(fmt::format("CacheUnit: L{} writebacks", level),
                             &levels_[i]->n_of_writebacks_);
    }
    gRegistry().reg_stat<size_t>("CacheUnit: mem reads", [this]() {
        return levels_.back()->n_of_mem_reads_;
    });
    gRegistry().reg_stat<size_t>("CacheUnit: mem writes", [this]() {
        return levels_.back()->n_of_mem_writes();
    });
    gRegistry().reg_stat<size_t>("CacheUnit: total access cycles",
                                 [this]() { return total_access_cycles(); });
    gRegistry().reg_stat<size_t>("CacheUnit: total number of access", [this]() {
        auto& lvl = this->levels_[0];
        return lvl->n_of_access_;
    });

    gRegistry().reg_stat<double>("CacheUnit: cache avg_access_time", [this]() {
        size_t total_access = levels_[0]->n_of_access_;
        if (!total_access)
            return 0.0;

        return (double)total_access_cycles() / total_access;
    });
}

size_t CacheUnit::total_access_cycles() const
{
    size_t total_cycles = 0;
    for (const auto& lvl : levels_) {
        total_cycles += lvl->n_of_access_ * lvl->cycles_;
    }

    // only demand memory accesses cost cycles, writebacks are free
    const auto& last = levels_.back();
    total_cycles +=
        (last->n_of_mem_reads_ + last->n_of_mem_write_misses_) * mem_cycles_;

    return total_cycles;
}
