#include "cachesim.h"
#include "my_utils.h"
#include "registry.h"
#include <cassert>
#include <iostream>
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

/* return 2^exponent */
constexpr int ttp(int exponent)
{
    return (1 << exponent);
}

} // namespace

AddrSplitter::AddrSplitter(int n_of_sets, int block_size)
    : block_size_(block_size),
      b_tag_size_(B_ADDR_SIZE - block_size - my_log2(n_of_sets)),
      tag_mask_(~((1 << (B_ADDR_SIZE - b_tag_size_)) - 1)),
      set_mask_(((1 << my_log2(n_of_sets)) - 1) << block_size_)
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
                       int assoc, bool write_alloc, int mem_cycles)
    : level_nmbr_(level), size_(size), cycles_(cycles), assoc_(ttp(assoc)),
      write_alloc_(write_alloc), mem_cycles_(mem_cycles),
      splitter((ttp(size) / ttp(assoc)) / ttp(block_size), block_size)
{
    for (int i = 0; i < ((ttp(size) / ttp(assoc)) / ttp(block_size)); ++i) {
        sets_.emplace_back(assoc_);
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
                     bool write_alloc)
    : block_size_(block_size), mem_cycles_(mem_cycles),
      write_alloc_(write_alloc)
{
    // construct the levels vector
    for (const auto& level_config : cache_levels) {
        levels_.push_back(std::make_unique<CacheLevel>(
            level_config.level, level_config.size, block_size_,
            level_config.cycles, level_config.assoc, write_alloc_,
            mem_cycles_));
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
    }
    gRegistry().reg_stat<size_t>("CacheUnit: total access cycles", [this]() {
        size_t total_cycles = 0;
        for (const auto& lvl : levels_) {
            total_cycles += lvl->n_of_access_ * lvl->cycles_;
            total_cycles += lvl->n_of_dram_access_ * mem_cycles_;
        }
        return total_cycles;
    });
    gRegistry().reg_stat<size_t>("CacheUnit: total number of access", [this]() {
        auto& lvl = this->levels_[0];
        return lvl->n_of_access_;
    });

    gRegistry().reg_stat<double>("CacheUnit: cache avg_access_time", [this]() {
        size_t total_access = levels_[0]->n_of_access_;
        if (!total_access)
            return 0.0;

        size_t total_cycles = 0;
        for (const auto& lvl : levels_) {
            total_cycles += lvl->n_of_access_ * lvl->cycles_;
            total_cycles += lvl->n_of_dram_access_ * mem_cycles_;
        }
        return (double)total_cycles / total_access;
    });
}
