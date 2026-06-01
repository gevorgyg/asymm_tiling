#ifndef CACHE_SIM_H_
#define CACHE_SIM_H_

#include <cassert>
#include <cstdio>
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

struct RecordBook {
    struct CacheStats {
        size_t nr_access = 0;
        size_t nr_misses = 0;
        size_t nr_hits   = 0;
    };

    // sim
    size_t total_access_cycles   = 0;
    size_t nr_total_cache_access = 0;

    // l1
    CacheStats l1_book_;

    // l2
    CacheStats l2_book_;

    // prng gen
    size_t nr_fifo_access = 0;

    // calc functions
    double calc_L1_miss_rate() const
    {
        return (double)l1_book_.nr_misses / (double)l1_book_.nr_access;
    }
    double calc_L2_miss_rate() const
    {
        return (double)l2_book_.nr_misses / (double)l2_book_.nr_access;
    }
    double calc_avg_access_time() const
    {
        return (double)total_access_cycles / (double)nr_total_cache_access;
    }

    void printStats() const
    {
        printf("--- Workload Statistics ---\n");
        printf("L1 Miss Rate: %.03f\n", calc_L1_miss_rate());
        printf("L2 Miss Rate: %.03f\n", calc_L2_miss_rate());
        printf("Average Memory Access Time: %.03f cycles\n",
               calc_avg_access_time());
    }
};

class PrngDevSim
{
  public:
    explicit PrngDevSim(RecordBook& rb, uint max_fifo_size = def_size,
                        uint generation_cost = def_gen_cost,
                        uint access_cost     = def_access_cost)
        : rb_(rb), generation_cost_(generation_cost), access_cost_(access_cost),
          max_fifo_size_(max_fifo_size)
    {
    }

    void pop()
    {
        size_t stall_amount = 0;

        ++rb_.nr_fifo_access;
        rb_.total_access_cycles += access_cost_;

        addToFifo();

        if (!cur_fifo_size_) {
            size_t delta_cycles = rb_.total_access_cycles - last_cpu_cycles_;
            stall_amount        = generation_cost_ - delta_cycles;

            rb_.total_access_cycles += stall_amount;

            // now we add the value
            // and
            // now we pop the value (logically)

            last_cpu_cycles_ = rb_.total_access_cycles;
        }
    }

  private:
    void addToFifo()
    {
        size_t delta_cycles = rb_.total_access_cycles - last_cpu_cycles_;

        size_t to_add = delta_cycles / generation_cost_;
        if (!to_add) {
            return;
        }

        size_t leftover = delta_cycles % generation_cost_;

        cur_fifo_size_ += to_add;

        last_cpu_cycles_ = rb_.total_access_cycles + leftover;
    }

    static constexpr int def_access_cost = 6;
    static constexpr int def_gen_cost    = 12;
    static constexpr int def_size        = 1024;

    const uint max_fifo_size_;
    const uint generation_cost_;
    const uint access_cost_;

    uint cur_fifo_size_     = 0;
    size_t last_cpu_cycles_ = 0;

    RecordBook& rb_;
};

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

class Cache
{
  public:
    Cache(int size, int block_size, int cycles, int assoc, bool write_alloc,
          RecordBook::CacheStats& rb);

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

    std::vector<Set> sets_;
    RecordBook::CacheStats& rb_;
};

class simulator
{
  public:
    simulator(const simulator&)            = delete;
    simulator& operator=(const simulator&) = delete;

    static simulator& getInstance(int block_size, int mem_cycles, int l1_size,
                                  int l1_cycles, int l1_assoc, int l2_size,
                                  int l2_cycles, int l2_assoc, bool write_alloc,
                                  RecordBook& rb);

    void process_request(char operation, RawAddr address);

  private:
    simulator(int block_size, int mem_cycles, int l1_size, int l1_cycles,
              int l1_assoc, int l2_size, int l2_cycles, int l2_assoc,
              bool write_alloc, RecordBook& rb);

    const int block_size_;
    const int mem_cycles_;
    const int l1_size_;
    const int l1_cycles_;
    const int l1_assoc_;
    const int l2_size_;
    const int l2_cycles_;
    const int l2_assoc_;

    const bool write_alloc_;

    Cache l1_;
    Cache l2_;

    RecordBook& br_;

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
