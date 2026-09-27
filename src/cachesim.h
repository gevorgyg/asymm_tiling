#ifndef CACHE_SIM_H_
#define CACHE_SIM_H_

#include "my_utils.h"

#include <algorithm>
#include <cassert>
#include <memory>
#include <spdlog/spdlog.h>
#include <vector>

struct CacheLevelConfig {
    uint32_t level;
    uint32_t size;
    uint32_t cycles;
    uint32_t assoc;
};

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

class ReplacementPolicy
{
  public:
    virtual ~ReplacementPolicy()        = default;
    virtual void touch(size_t way)      = 0;
    virtual void insert(size_t way)     = 0;
    virtual void invalidate(size_t way) = 0;
    virtual size_t find_victim() const  = 0;
};

class LruPolicy : public ReplacementPolicy
{
  public:
    explicit LruPolicy(size_t assoc)
    {
        order_.reserve(assoc);
        for (size_t i = 0; i < assoc; ++i)
            order_.push_back(i);
    }

    void touch(size_t way) override
    {
        auto it = std::find(order_.begin(), order_.end(), way);
        if (it != order_.end()) {
            std::rotate(order_.begin(), it, it + 1);
        }
    }

    virtual void insert(size_t way) override
    {
        touch(way);
    }

    virtual void invalidate(size_t way) override
    {
    }

    virtual size_t find_victim() const override
    {
        return order_.back();
    }

  private:
    std::vector<WayIndex> order_;
};

class FifoPolicy : public ReplacementPolicy
{
};

class RandomPolicy : public ReplacementPolicy
{
};

struct CacheLine /* (aka way) */ {
    RawAddr addr   = 0;
    Tag tag        = 0;
    ValidBit valid = false;
    DirtyBit dirty = false;
};

class Set
{
  public:
    Set(int assoc) : ways_(assoc), policy_(std::make_unique<LruPolicy>(assoc))
    {
    }

    CacheLine* find(const AddrParts& addr)
    {
        auto it = std::find_if(
            ways_.begin(), ways_.end(), [&](const CacheLine& line) -> bool {
                return ((line.tag == addr.tag) && line.valid);
            });

        if (it == ways_.end()) {
            return nullptr;
        }

        // relevant only for lru
        policy_->touch(it - ways_.begin());

        return &(*it);
    }

    bool try_insert(const CacheLine& new_line)
    {
        for (int i = 0; i < ways_.size(); ++i) {
            if (!ways_[i].valid) {
                ways_[i] = new_line;
                policy_->insert(i);
                return true;
            }
        }

        return false;
    }

    std::unique_ptr<CacheLine> insert(const CacheLine& new_line)
    {
        size_t victim_index = policy_->find_victim();
        auto victim         = std::make_unique<CacheLine>(ways_[victim_index]);
        ways_[victim_index] = new_line;

        policy_->insert(victim_index);

        return victim;
    }

  private:
    std::vector<CacheLine> ways_; // each way is a cacheline
    std::unique_ptr<ReplacementPolicy> policy_;
};

// farward declare
class CacheUnit;

class CacheLevel
{
    friend class CacheUnit;

  public:
    CacheLevel(int level, int size, int block_size, int cycles, int assoc,
               bool write_alloc, int mem_cycles);

    CacheLine* find(const AddrParts& addr)
    {
        CacheLine* target = sets_[addr.set].find(addr);
        if (!target) {
            return nullptr;
        }
        return target;
    }

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
        if (victim->dirty) {
            if (lower_level_) {
                lower_level_->insert(*victim);
            } else {
                log_mem_access();
            }
        }
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
            log_mem_access();
        }

        insert(CacheLine{raw_addr, addr.tag, true, false});
    }

    void write(const RawAddr& raw_addr)
    {
        auto addr = splitter(raw_addr);

        if (write_alloc_) {
            read(raw_addr);
            CacheLine* target = find(addr);
            if (target) {
                target->dirty = true;
            }
            return;
        }

        CacheLine* target = find(addr);
        if (!target) {
            if (lower_level_) {
                lower_level_->write(raw_addr);
            } else {
                log_mem_access();
            }
            return;
        }

        target->dirty = true;
    }

    const AddrSplitter splitter;

  private:
    const uint32_t level_nmbr_;
    const uint32_t size_;
    const uint32_t cycles_;
    const uint32_t assoc_;
    const bool write_alloc_;

    CacheLevel* upper_level_;
    CacheLevel* lower_level_;

    int mem_cycles_;

    std::vector<Set> sets_;

    size_t n_of_misses_      = 0;
    size_t n_of_hits_        = 0;
    size_t n_of_access_      = 0;
    size_t n_of_dram_access_ = 0;

    void log_mem_access()
    {
        ++n_of_dram_access_;
        Clock::tick(mem_cycles_);
    }
};

class CacheUnit
{
    friend CacheLevel;
    using CacheLevelPtr = std::unique_ptr<CacheLevel>;

  public:
    CacheUnit(int block_size, int mem_cycles,
              const std::vector<CacheLevelConfig>& cache_levels,
              bool write_alloc);

    CacheUnit(int block_size, int mem_cycles, int l1_size, int l1_cycles,
              int l1_assoc, int l2_size, int l2_cycles, int l2_assoc,
              bool write_alloc)
        : CacheUnit(block_size, mem_cycles,
                    std::vector<CacheLevelConfig>{
                        {1, static_cast<uint32_t>(l1_size),
                         static_cast<uint32_t>(l1_cycles),
                         static_cast<uint32_t>(l1_assoc)},
                        {2, static_cast<uint32_t>(l2_size),
                         static_cast<uint32_t>(l2_cycles),
                         static_cast<uint32_t>(l2_assoc)}},
                    write_alloc)
    {
    }

    void process_request(char operation, RawAddr address);
    void register_stats() const;

  private:
    std::vector<CacheLevelPtr> levels_;

    const int block_size_;
    const int mem_cycles_;
    const bool write_alloc_;

    void do_read(RawAddr address)
    {
        levels_[0]->read(address);
    }
    void do_write(RawAddr address)
    {
        levels_[0]->write(address);
    }

    void log_mem_access()
    {
        Clock::tick(mem_cycles_);
    }
};

#endif
