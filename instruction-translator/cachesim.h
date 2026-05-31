#ifndef CACHE_SIM_H_
#define CACHE_SIM_H_

#include <cassert>
#include <list>
#include <unordered_map>
#include <utility>
#include <vector>

using uint     = unsigned int;
using Tag      = uint;
using BitMask  = uint;
using RawAddr  = uint;
using SetIndex = uint;
using DirtyBit = bool;
using Outcome  = bool;

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

    std::unordered_map<Tag, CacheLine> ways_;

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

class cache
{
  public:
    cache(int size, int block_size, int cycles, int assoc, bool write_alloc);

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
    const int size_; // = cache size
    const int cycles_;
    const int assoc_;
    const bool write_alloc_;

    // data for printing
    size_t n_of_access = 0;
    size_t n_of_misses = 0;
    size_t n_of_hits   = 0;
    // ---------------

    std::vector<Set> sets_;
};

class simulator
{
  public:
    simulator(const simulator&)            = delete;
    simulator& operator=(const simulator&) = delete;

    static simulator& getInstance(int block_size, int mem_cycles, int l1_size,
                                  int l1_cycles, int l1_assoc, int l2_size,
                                  int l2_cycles, int l2_assoc,
                                  bool write_alloc);

    void process_request(char operation, RawAddr address);

    double calc_L1_miss_rate() const;
    double calc_L2_miss_rate() const;
    double calc_avg_access_time() const;
    void logPrngCycles()
    {
        ++n_prng_access;
    }

  private:
    simulator(int block_size, int mem_cycles, int l1_size, int l1_cycles,
              int l1_assoc, int l2_size, int l2_cycles, int l2_assoc,
              bool write_alloc);

    const int block_size_;
    const int mem_cycles_;
    const int l1_size_;
    const int l1_cycles_;
    const int l1_assoc_;
    const int l2_size_;
    const int l2_cycles_;
    const int l2_assoc_;

    // data for printing
    size_t total_access_cycles = 0;
    size_t n_of_access         = 0;
    // ---------------

    const bool write_alloc_;

    cache l1_;
    cache l2_;

    enum state {
        search_l1,
        search_l2,
        insert_l1,
        insert_l2,
        snoop_l1,
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
};

#endif
