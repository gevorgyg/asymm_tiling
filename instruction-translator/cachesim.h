#ifndef CACHE_SIM_H_
#define CACHE_SIM_H_

#include <cassert>
#include <iostream>
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

// TODO: move all of this to a seperate cpp file including the static function
// to avoid seperate static function instantiations
namespace
{

constexpr int B_ADDR_SIZE  = 32;
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

    CacheLine(RawAddr addr) : addr_(addr)
    {
    }

    void setQueuePos(QueuePos pos)
    {
        ptr_ = pos;
    }

    QueuePos getQueuePos() const
    {
        return ptr_;
    }

    void markDirty()
    {
        dirty_ = true;
    }

    bool isDirty() const
    {
        return dirty_;
    }

    RawAddr getAddr() const
    {
        return addr_;
    }

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

    Set(int assoc) : max_size_(assoc)
    {
    }

    // front = most recent
    // back = least recent

    CacheLine* lookup(Tag tag)
    {
        auto target = ways_.find(tag);
        if (target != ways_.end()) { // hit
            updateQueue(target);
            return &target->second;
        }

        return nullptr; // miss
    }

    void invalidate(Tag tag)
    {
        auto target = ways_.find(tag);
        if (target != ways_.end()) {
            lru_queue_.erase(target->second.getQueuePos());
            ways_.erase(target);
        }
    }

    Insertion insert(const AddrParts& addr, RawAddr& evicted_addr,
                     DirtyBit& evicted_dirty)
    {
        auto target = ways_.find(addr.tag);
        if (target != ways_.end()) { // found
            updateQueue(target);
            return {&target->second, false};
        }

        // not found
        bool evicted = false;
        if (ways_.size() >= max_size_) { // full set
            Tag victim_tag = lru_queue_.back();
            Data victim    = ways_.find(victim_tag);

            evicted_addr  = victim->second.getAddr();
            evicted_dirty = victim->second.isDirty();

            ways_.erase(victim);
            lru_queue_.pop_back();

            evicted = true;
        }

        auto insertion_result = ways_.insert({addr.tag, CacheLine(addr.raw)});

        if (insertion_result.second == false) {
            std::cerr << "failed insertion into hash map, shouldn't "
                         "happen! Exiting..."
                      << std::endl;
            exit(1);
        }

        auto new_data = insertion_result.first;

        lru_queue_.push_front(new_data->first);

        new_data->second.setQueuePos(lru_queue_.begin());

        return {&new_data->second, evicted};
    }

  private:
    void updateQueue(Data target)
    {
        const CacheLine& data = target->second;
        auto queue_pos        = data.getQueuePos();
        lru_queue_.splice(lru_queue_.begin(), lru_queue_, queue_pos);

        assert(data.getQueuePos() == lru_queue_.begin());
    }

    std::unordered_map<Tag, CacheLine> ways_;

    std::list<Tag> lru_queue_;

    size_t max_size_;
};

class AddrSplitter
{
  public:
    AddrSplitter(int n_of_sets, int block_size)
        : block_size_(block_size),
          b_tag_size_(B_ADDR_SIZE - block_size - my_log2(n_of_sets)),
          tag_mask_(~((1 << (B_ADDR_SIZE - b_tag_size_)) - 1)),
          set_mask_(((1 << my_log2(n_of_sets)) - 1) << block_size_)
    {
    }

    AddrParts operator()(RawAddr addr) const
    {
        return {addr, create_tag(addr), create_index(addr)};
    }

  private:
    const int block_size_;
    const int b_tag_size_;
    const BitMask tag_mask_;
    const BitMask set_mask_;

    Tag create_tag(RawAddr address) const
    {
        return (address & tag_mask_) >> (B_ADDR_SIZE - b_tag_size_);
    }

    SetIndex create_index(RawAddr address) const
    {
        return (address & set_mask_) >> block_size_;
    }
};

class cache
{
  public:
    cache(int size, int block_size, int cycles, int assoc, bool write_alloc)
        : size_(size), cycles_(cycles), assoc_(ttp(assoc)),
          write_alloc_(write_alloc),
          sets_((ttp(size) / ttp(assoc)) / ttp(block_size), Set{ttp(assoc)}),
          splitter((ttp(size) / ttp(assoc)) / ttp(block_size), block_size)
    {
    }

    size_t get_n_access() const
    {
        return n_of_access;
    }
    size_t get_n_hits() const
    {
        return n_of_hits;
    }
    size_t get_n_misses() const
    {
        return n_of_misses;
    }

    const AddrSplitter splitter;

    CacheLine* lookup(const AddrParts& addr)
    {
        ++n_of_access;
        CacheLine* target = sets_[addr.set].lookup(addr.tag);

        if (target) {
            ++n_of_hits;
        } else {
            ++n_of_misses;
        }

        return target;
    }

    CacheLine* lookupNoUpdate(const AddrParts& addr)
    {
        return sets_[addr.set].lookup(addr.tag);
    }

    void invalidate(const AddrParts& addr)
    {
        sets_[addr.set].invalidate(addr.tag);
    }

    Insertion insert(const AddrParts& addr, RawAddr& evicted_addr,
                     DirtyBit& evicted_dirty)
    {
        return sets_[addr.set].insert(addr, evicted_addr, evicted_dirty);
    }

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
                                  int l2_cycles, int l2_assoc, bool write_alloc)
    {

        /* Creating a static instance of the simulator because we don't need
         * more than one
         */
        static simulator instance(block_size, mem_cycles, l1_size, l1_cycles,
                                  l1_assoc, l2_size, l2_cycles, l2_assoc,
                                  write_alloc);
        return instance;
    }

    void process_request(char operation, RawAddr address)
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

    double calc_L1_miss_rate() const
    {
        return (double)l1_.get_n_misses() / (double)l1_.get_n_access();
    }
    double calc_L2_miss_rate() const
    {
        return (double)l2_.get_n_misses() / (double)l2_.get_n_access();
    }
    double calc_avg_access_time() const
    {
        return (double)total_access_cycles / (double)n_of_access;
    }

  private:
    simulator(int block_size, int mem_cycles, int l1_size, int l1_cycles,
              int l1_assoc, int l2_size, int l2_cycles, int l2_assoc,
              bool write_alloc)
        : block_size_(block_size), mem_cycles_(mem_cycles), l1_size_(l1_size),
          l1_cycles_(l1_cycles), l1_assoc_(l1_assoc), l2_size_(l2_size),
          l2_cycles_(l2_cycles), l2_assoc_(l2_assoc), write_alloc_(write_alloc),
          l1_(l1_size, block_size, l1_cycles, l1_assoc, write_alloc),
          l2_(l2_size, block_size, l2_cycles, l2_assoc, write_alloc)
    {
    }

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

    void do_read(RawAddr address)
    {
        AddrParts l1_addr_parts = l1_.splitter(address);
        AddrParts l2_addr_parts = l2_.splitter(address);

        RawAddr evicted_addr   = 0;
        DirtyBit evicted_dirty = false;

        state cur_state = search_l1;
        bool finish     = false;
        while (!finish) {
            switch (cur_state) {
            case search_l1: {
                log_l1_access();
                CacheLine* found = l1_.lookup(l1_addr_parts);
                if (found) { // hit
                    finish = true;
                } else {
                    cur_state = search_l2;
                }
            } break;
            case search_l2: {
                log_l2_access();
                CacheLine* found = l2_.lookup(l2_addr_parts);
                if (found) { // hit
                    cur_state = insert_l1;
                } else {
                    cur_state = insert_l2;
                }
            } break;
            case insert_l2: {
                log_mem_access();

                Insertion wasEvicted =
                    l2_.insert(l2_addr_parts, evicted_addr, evicted_dirty);

                if (wasEvicted.second) {
                    // write back to memory the evicted data in background
                    cur_state = snoop_l1;
                } else {
                    cur_state = insert_l1;
                }

            } break;
            case snoop_l1: {
                AddrParts l1_snoop_addr_parts = l1_.splitter(evicted_addr);

                // take dirty status of evicted line from L2
                bool should_evict = evicted_dirty;

                CacheLine* victim = l1_.lookupNoUpdate(l1_snoop_addr_parts);
                if (victim) {
                    if (victim->isDirty()) {
                        should_evict = true;
                    }

                    l1_.invalidate(l1_snoop_addr_parts);
                }

                if (should_evict) {
                    // NOTE: maybe not needed if the writes are in
                    // background
                    // log_mem_access();
                }

                cur_state = insert_l1;

            } break;
            case insert_l1: {
                Insertion wasEvicted =
                    l1_.insert(l1_addr_parts, evicted_addr, evicted_dirty);

                if (wasEvicted.second && evicted_dirty) {
                    cur_state = write_back_l2;
                } else {
                    finish = true;
                }
            } break;
            case write_back_l2: {
                AddrParts l2_writeback_addr_parts = l2_.splitter(evicted_addr);

                CacheLine* target = l2_.lookupNoUpdate(l2_writeback_addr_parts);
                if (target) {
                    target->markDirty();
                } else {
                    // shouldn't happen because inclusive cache
                    std::cerr << "cache contradicts inclusivness" << std::endl;
                    exit(1);
                }

                finish = true;
            } break;
            }
        }
    }

    void do_write(RawAddr address)
    {
        if (write_alloc_) {
            do_write_allocate(address);
        } else { // simple write
            do_write_simple(address);
        }
    }

    void do_write_allocate(RawAddr address)
    {
        AddrParts l1_addr_parts = l1_.splitter(address);
        AddrParts l2_addr_parts = l2_.splitter(address);

        RawAddr evicted_addr   = 0;
        DirtyBit evicted_dirty = false;

        state cur_state = search_l1;
        bool finish     = false;
        while (!finish) {
            switch (cur_state) {
            case search_l1: {
                log_l1_access();
                CacheLine* found = l1_.lookup(l1_addr_parts);
                if (found) { // hit
                    found->markDirty();

                    finish = true;
                } else {
                    cur_state = search_l2;
                }
            } break;
            case search_l2: {
                log_l2_access();
                CacheLine* found = l2_.lookup(l2_addr_parts);
                if (found) { // hit
                    cur_state = insert_l1;
                } else {
                    cur_state = insert_l2;
                }
            } break;
            case insert_l2: {
                log_mem_access();

                Insertion wasEvicted =
                    l2_.insert(l2_addr_parts, evicted_addr, evicted_dirty);

                if (wasEvicted.second) {
                    // write back to memory the evicted data in background
                    cur_state = snoop_l1;
                } else {
                    cur_state = insert_l1;
                }

            } break;
            case snoop_l1: {
                AddrParts l1_snoop_addr_parts = l1_.splitter(evicted_addr);

                bool should_evict = evicted_dirty;
                CacheLine* victim = l1_.lookupNoUpdate(l1_snoop_addr_parts);
                if (victim) {
                    if (victim->isDirty()) {
                        should_evict = true;
                    }

                    l1_.invalidate(l1_snoop_addr_parts);
                }

                if (should_evict) {
                    // NOTE: maybe not needed if the writes are in
                    // background
                    // log_mem_access();
                }

                cur_state = insert_l1;

            } break;
            case insert_l1: {
                Insertion result =
                    l1_.insert(l1_addr_parts, evicted_addr, evicted_dirty);

                // mark the NEWLY inserted as dirty
                result.first->markDirty();

                if (result.second && evicted_dirty) {
                    cur_state = write_back_l2;
                } else {
                    finish = true;
                }
            } break;
            case write_back_l2: {
                AddrParts l2_writeback_addr_parts = l2_.splitter(evicted_addr);

                CacheLine* target = l2_.lookupNoUpdate(l2_writeback_addr_parts);
                if (target) {
                    target->markDirty();
                } else {
                    // shouldn't happen because inclusive cache
                    std::cerr << "cache contradicts inclusivness" << std::endl;
                    exit(1);
                }

                finish = true;
            } break;
            }
        }
    }

    void do_write_simple(RawAddr address)
    {
        AddrParts l1_addr_parts = l1_.splitter(address);
        AddrParts l2_addr_parts = l2_.splitter(address);

        log_l1_access();
        CacheLine* target = l1_.lookup(l1_addr_parts);
        if (target) {
            target->markDirty();
            return;
        }

        log_l2_access();
        target = l2_.lookup(l2_addr_parts);
        if (target) {
            target->markDirty();
            return;
        }

        log_mem_access();
    }

    void log_l1_access()
    {
        /* only need to increment the access amount of the first access try,
         * that always starts at L1 */
        n_of_access++;
        total_access_cycles += l1_cycles_;
    }

    void log_l2_access()
    {
        total_access_cycles += l2_cycles_;
    }
    void log_mem_access()
    {
        total_access_cycles += mem_cycles_;
    }
};

#endif
