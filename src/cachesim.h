#ifndef CACHE_SIM_H_
#define CACHE_SIM_H_

#include "my_utils.h"

#include <cassert>
#include <list>
#include <memory>
#include <unordered_map>
#include <utility>
#include <vector>

struct AddrParts {
    RawAddr raw;
    Tag tag;
    SetIndex set;
};

// way
class CacheLine
{
  public:
    using QueuePos = std::list<Tag>::iterator;

    CacheLine(RawAddr addr);

    void setQueuePos(QueuePos pos);

    QueuePos getQueuePos() const;

    void markDirty();

    bool isDirty() const;

    RawAddr getAddr() const;

  private:
    RawAddr addr_;
    QueuePos ptr_;
    DirtyBit dirty_ = false;
};

using Insertion = std::pair<CacheLine*, Outcome>;

class Set
{
  public:
    using Data = std::unordered_map<Tag, CacheLine>::iterator;

    Set(int assoc);

    // front = most recent
    // back = least recent

    CacheLine* lookup(Tag tag);

    void invalidate(Tag tag);

    Insertion insert(const AddrParts& addr, RawAddr& evicted_addr,
                     DirtyBit& evicted_dirty);

  private:
    void updateQueue(Data target);

    std::unordered_map<Tag, CacheLine> ways_; // each way is a cacheline

    std::list<Tag> lru_queue_;

    size_t max_size_;
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

class CacheLevel
{
    friend class CacheUnit;

  public:
    CacheLevel(int level, int size, int block_size, int cycles, int assoc,
               bool write_alloc);

    size_t get_n_access() const;
    size_t get_n_hits() const;
    size_t get_n_misses() const;

    const AddrSplitter splitter;

    CacheLine* lookup(const AddrParts& addr);

    CacheLine* lookupNoUpdate(const AddrParts& addr);

    void invalidate(const AddrParts& addr);

    Insertion insert(const AddrParts& addr, RawAddr& evicted_addr,
                     DirtyBit& evicted_dirty);

  private:
    const uint32_t level_;
    const uint32_t size_;
    const uint32_t cycles_;
    const uint32_t assoc_;
    const bool write_alloc_;

    CacheLevel* upper_level_;
    CacheLevel* lower_level_;

    // data for printing
    size_t n_of_access_ = 0;
    size_t n_of_misses_ = 0;
    size_t n_of_hits_   = 0;
    // ---------------

    std::vector<Set> sets_;
};

struct CacheLevelConfig {
    uint32_t level;
    uint32_t size;
    uint32_t cycles;
    uint32_t assoc;
};

class CacheUnit
{
  public:
    CacheUnit(int block_size, int mem_cycles,
              const std::vector<CacheLevelConfig>& cache_levels,
              bool write_alloc);

    void process_request(char operation, RawAddr address);
    void register_stats() const;

    double calc_L1_miss_rate() const;
    double calc_L2_miss_rate() const;
    double calc_avg_access_time() const;

  private:
    const int block_size_;
    const int mem_cycles_;
    const bool write_alloc_;

    using CacheLevelPtr = std::unique_ptr<CacheLevel>;
    std::vector<CacheLevelPtr> levels_;

    enum state {
        search_l1,
        search_l2,
        insert_l1,
        insert_l2,
        write_back_l2,
    };
    state cur_state;

    void do_read(RawAddr address);

    void do_write(RawAddr address);

    void do_write_allocate(RawAddr address);

    void do_write_simple(RawAddr address);

    void log_l1_access();

    void log_l2_access();
    void log_mem_access();

    // data for printing
    size_t total_access_cycles_ = 0;
    size_t total_n_of_access_   = 0;
    // ---------------
};

#endif
