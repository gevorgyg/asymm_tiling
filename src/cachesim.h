#ifndef CACHE_SIM_H_
#define CACHE_SIM_H_

#include "my_utils.h"

#include <algorithm>
#include <cassert>
#include <memory>
#include <spdlog/spdlog.h>
#include <string>
#include <vector>

struct CacheLevelConfig {
    uint32_t level;
    uint32_t size;
    uint32_t cycles;
    uint32_t assoc;
};

// why a cache level with this geometry (all log2) can't be built, or "" if it
// can. CacheLevel throws std::invalid_argument with this message.
std::string cache_geometry_error(int level, int size, int block_size,
                                 int assoc);

struct AddrParts {
    RawAddr raw;
    Tag tag;
    SetIndex set;
};

class AddrSplitter
{
  public:
    AddrSplitter(int n_of_sets, int block_size);

    AddrParts operator()(RawAddr addr) const;

  private:
    const int block_size_;
    const int b_tag_size_;
    const BitMask tag_mask_;
    const BitMask set_mask_;

    Tag create_tag(RawAddr address) const;

    SetIndex create_index(RawAddr address) const;
};

struct CacheLine /* (aka way) */ {
    RawAddr addr   = 0;
    Tag tag        = 0;
    ValidBit valid = false;
    DirtyBit dirty = false;

    // age stamp, set by the owning Set when the line is filled and (except
    // for fifo) when it is used
    uint64_t stamp = 0;
};

// Replacement by age stamps. Every stamp is the set's next counter value, so
// stamps in a set are unique and order the lines by age.
//
//   policy | stamp on fill | stamp on hit | victim
//   lru    | yes           | yes          | smallest stamp (least recent)
//   fifo   | yes           | no           | smallest stamp (oldest fill)
//   mru    | yes           | yes          | largest stamp (most recent)
//   random | yes           | yes          | way (rng % ways), deterministic
//
// Free ways are always used before anything is evicted, lowest way first.
class Set
{
  public:
    Set(size_t assoc, ReplPolicy policy, uint64_t seed)
        : ways_(assoc), policy_(policy), rng_(seed)
    {
        assert(seed != 0); // xorshift gets stuck at 0
    }

    // lookup without updating the stamps
    CacheLine* peek(const AddrParts& addr)
    {
        auto it = std::find_if(
            ways_.begin(), ways_.end(), [&](const CacheLine& line) -> bool {
                return ((line.tag == addr.tag) && line.valid);
            });

        if (it == ways_.end()) {
            return nullptr;
        }

        return &(*it);
    }

    // demand lookup, a hit refreshes the stamp (except for fifo)
    CacheLine* find(const AddrParts& addr)
    {
        CacheLine* line = peek(addr);

        if (line && policy_ != ReplPolicy::fifo) {
            stamp(*line);
        }

        return line;
    }

    // insert into the lowest free way, false if the set is full
    bool try_insert(const CacheLine& new_line)
    {
        for (auto& way : ways_) {
            if (!way.valid) {
                way = new_line;
                stamp(way);
                return true;
            }
        }

        return false;
    }

    // replace the victim (the set must be full), returns the evicted line by
    // value (a copy, no heap allocation)
    CacheLine insert(const CacheLine& new_line)
    {
        CacheLine& way   = ways_[victim_index()];
        CacheLine victim = way;
        way              = new_line;
        stamp(way);

        return victim;
    }

  private:
    std::vector<CacheLine> ways_; // each way is a cacheline
    const ReplPolicy policy_;
    uint64_t clock_ = 0; // last stamp handed out in this set
    uint64_t rng_;       // xorshift64 state, only used by random

    void stamp(CacheLine& line)
    {
        line.stamp = ++clock_;
    }

    size_t victim_index()
    {
        auto by_stamp = [](const CacheLine& a, const CacheLine& b) {
            return a.stamp < b.stamp;
        };

        switch (policy_) {
        case ReplPolicy::lru:
        case ReplPolicy::fifo:
            return std::min_element(ways_.begin(), ways_.end(), by_stamp) -
                   ways_.begin();
        case ReplPolicy::mru:
            return std::max_element(ways_.begin(), ways_.end(), by_stamp) -
                   ways_.begin();
        case ReplPolicy::random:
            return next_random() % ways_.size();
        }

        assert(false && "unknown replacement policy");
        return 0;
    }

    // xorshift64 (Marsaglia), must match tests/ref_cache.py
    uint64_t next_random()
    {
        rng_ ^= rng_ << 13;
        rng_ ^= rng_ >> 7;
        rng_ ^= rng_ << 17;
        return rng_;
    }
};

// farward declare
class CacheUnit;

class CacheLevel
{
    friend class CacheUnit;

  public:
    CacheLevel(int level, int size, int block_size, int cycles, int assoc,
               bool write_alloc, int mem_cycles, ReplPolicy policy);

    // demand lookup, a hit updates the replacement policy
    CacheLine* find(const AddrParts& addr)
    {
        return sets_[addr.set].find(addr);
    }

    // lookup without updating the replacement policy
    CacheLine* peek(const AddrParts& addr)
    {
        return sets_[addr.set].peek(addr);
    }

    // insert a line that is not present, a dirty victim is written back
    void insert(const CacheLine& new_line)
    {
        SetIndex set = splitter(new_line.addr).set;

        bool outcome = sets_[set].try_insert(new_line);

        if (outcome) {
            // found empty space
            return;
        }

        // need to evict, do write back
        auto victim = sets_[set].insert(new_line);
        if (victim.dirty) {
            ++n_of_writebacks_;
            if (lower_level_) {
                lower_level_->writeback(victim.addr);
            }
            // else the victim goes to memory: counted by n_of_writebacks_ of
            // the last level, free like every writeback
        }
    }

    // a dirty line evicted from the level above. Free: no cycles and not
    // counted as an access. Present -> mark dirty in place without touching
    // LRU, absent -> install dirty (no memory fetch, the whole line is written)
    void writeback(const RawAddr& raw_addr)
    {
        auto addr = splitter(raw_addr);

        CacheLine* target = peek(addr);
        if (target) {
            target->dirty = true;
            return;
        }

        insert(CacheLine{raw_addr, addr.tag, true, true});
    }

    void read(const RawAddr& raw_addr)
    {
        ++n_of_access_;
        Clock::tick(cycles_);

        auto addr = splitter(raw_addr);

        CacheLine* target = find(addr);

        if (target) {
            ++n_of_hits_;
            return;
        }

        ++n_of_misses_;

        if (lower_level_) {
            lower_level_->read(raw_addr);
        } else {
            ++n_of_mem_reads_;
            Clock::tick(mem_cycles_);
        }

        insert(CacheLine{raw_addr, addr.tag, true, false});
    }

    void write(const RawAddr& raw_addr)
    {
        auto addr = splitter(raw_addr);

        if (write_alloc_) {
            // same fills and latency as a read, then dirty the line
            read(raw_addr);
            CacheLine* target = peek(addr);
            assert(target);
            target->dirty = true;
            return;
        }

        ++n_of_access_;
        Clock::tick(cycles_);

        CacheLine* target = find(addr);

        if (target) {
            ++n_of_hits_;
            target->dirty = true;
            return;
        }

        ++n_of_misses_;

        // no write allocate: pass the write down, allocate nowhere
        if (lower_level_) {
            lower_level_->write(raw_addr);
        } else {
            ++n_of_mem_write_misses_;
            Clock::tick(mem_cycles_);
        }
    }

    // keep as the first data member: its initialization validates the
    // geometry before the other members use it (see CacheLevel::CacheLevel)
    const AddrSplitter splitter;

  private:
    const uint32_t level_nmbr_;
    const uint32_t size_;
    const uint32_t cycles_;
    const uint32_t assoc_;
    const bool write_alloc_;

    CacheLevel* upper_level_ = nullptr;
    CacheLevel* lower_level_ = nullptr;

    int mem_cycles_;

    std::vector<Set> sets_;

    size_t n_of_misses_     = 0;
    size_t n_of_hits_       = 0;
    size_t n_of_access_     = 0;
    size_t n_of_writebacks_ = 0; // dirty lines evicted from this level

    // memory traffic, only the last level has these
    size_t n_of_mem_reads_        = 0; // demand read misses
    size_t n_of_mem_write_misses_ = 0; // demand write misses (no write alloc)

    bool is_last() const
    {
        return lower_level_ == nullptr;
    }

    // memory writes: demand write misses and (free) writebacks
    size_t n_of_mem_writes() const
    {
        return n_of_mem_write_misses_ + (is_last() ? n_of_writebacks_ : 0);
    }
};

class CacheUnit
{
    friend CacheLevel;
    using CacheLevelPtr = std::unique_ptr<CacheLevel>;

  public:
    CacheUnit(int block_size, int mem_cycles,
              const std::vector<CacheLevelConfig>& cache_levels,
              bool write_alloc, ReplPolicy policy);

    CacheUnit(int block_size, int mem_cycles, int l1_size, int l1_cycles,
              int l1_assoc, int l2_size, int l2_cycles, int l2_assoc,
              bool write_alloc, ReplPolicy policy)
        : CacheUnit(
              block_size, mem_cycles,
              std::vector<CacheLevelConfig>{{1, static_cast<uint32_t>(l1_size),
                                             static_cast<uint32_t>(l1_cycles),
                                             static_cast<uint32_t>(l1_assoc)},
                                            {2, static_cast<uint32_t>(l2_size),
                                             static_cast<uint32_t>(l2_cycles),
                                             static_cast<uint32_t>(l2_assoc)}},
              write_alloc, policy)
    {
    }

    void process_request(char operation, RawAddr address);
    void register_stats() const;

    struct LevelStats {
        size_t accesses;
        size_t hits;
        size_t misses;
        size_t writebacks;
        size_t mem_reads;  // non zero only for the last level
        size_t mem_writes; // non zero only for the last level
    };

    size_t n_levels() const
    {
        return levels_.size();
    }

    LevelStats level_stats(size_t level) const
    {
        const auto& lvl = levels_.at(level);
        return {lvl->n_of_access_,     lvl->n_of_hits_,
                lvl->n_of_misses_,     lvl->n_of_writebacks_,
                lvl->n_of_mem_reads_, lvl->n_of_mem_writes()};
    }

    // cycles spent in the cache unit (writebacks are free)
    size_t total_access_cycles() const;

  private:
    std::vector<CacheLevelPtr> levels_;

    const int block_size_;
    const int mem_cycles_;
    const bool write_alloc_;
    const ReplPolicy policy_;

    void do_read(RawAddr address)
    {
        levels_[0]->read(address);
    }
    void do_write(RawAddr address)
    {
        levels_[0]->write(address);
    }
};

#endif
