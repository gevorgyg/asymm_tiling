#include <cassert>
#include <iostream>
#include <list>
#include <unordered_map>
#include <vector>

using uint    = unsigned int;
using Tag     = uint;
using BitMask = uint;
using RawAddr = uint;
using SetNr   = uint;
using Outcome = bool;

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
int ttp(int exponent)
{
    return (1 << exponent);
}

} // namespace

struct AddrParts {
    Tag tag;
    SetNr set;
};

// way
class CacheLine
{
  public:
    using QueuePos =
        std::list<std::unordered_map<Tag, CacheLine>::iterator>::iterator;

    void setQueuePos(QueuePos pos)
    {
        ptr_ = pos;
    }

    QueuePos getQueuePos() const
    {
        return ptr_;
    }

  private:
    QueuePos ptr_;
};

class Set
{
  public:
    using Data = std::unordered_map<Tag, CacheLine>::iterator;

    Set(int assoc) : max_size_(assoc)
    {
    }

    void insert(Tag tag)
    {
        // front = most recent
        // back = least recent

        auto target = ways_.find(tag);
        if (target == ways_.end()) {         // not found
            if (ways_.size() >= max_size_) { // full set
                removeVictim();
            }

            auto insertion_result = ways_.insert({tag, CacheLine{}});
            if (insertion_result.second == false) {
                std::cerr << "failed insertion into hash map, shouldn't "
                             "happen! Exiting..."
                          << std::endl;
                exit(1);
            }

            auto new_data = insertion_result.first;

            lru_queue_.push_front(new_data);

            new_data->second.setQueuePos(lru_queue_.begin());

        } else { // found
            updateQueue(target);
        }
    }

  private:
    void removeVictim()
    {
        ways_.erase(lru_queue_.back());
        lru_queue_.pop_back();
    }

    void updateQueue(Data target)
    {
        const CacheLine& data = target->second;
        auto queue_pos        = data.getQueuePos();
        lru_queue_.splice(lru_queue_.begin(), lru_queue_, queue_pos);

        assert(data.getQueuePos() == lru_queue_.begin());
    }

    std::unordered_map<Tag, CacheLine> ways_;

    std::list<Data> lru_queue_;

    size_t max_size_;
};

class cache
{
  public:
    // int size_;       // = cache size
    // int block_size_; // = line size
    // int cycles_;
    // int assoc_;
    // int n_of_sets; // implicitly, this is also the n_of_tags
    // int b_tag_size;

    cache(int size, int block_size, int cycles, int assoc, bool write_alloc)
        : size_(size), block_size_(block_size), cycles_(cycles),
          assoc_(ttp(assoc)), n_of_sets_((ttp(size) / assoc) / ttp(block_size)),
          b_tag_size_(B_ADDR_SIZE - block_size - my_log2(n_of_sets_)),
          write_alloc_(write_alloc),
          tag_mask_(~((1 << (B_ADDR_SIZE - b_tag_size_)) - 1)),
          set_mask_(((1 << my_log2(n_of_sets_)) - 1) << block_size),
          sets_(n_of_sets_, Set{assoc_})
    {
    }

    /* find_data:
     * Travese every way and check the tag at that way. If found matching tag,
     * then it's a hit. If finished traversing every way and no match then it's
     * a miss.
     */
    Outcome find_and_read_data(RawAddr address);

    /* find_victim:
     * Check if there is empty space, if no, find a victim with LRU.
     */
    RawAddr find_victim(RawAddr address);

    Outcome is_victim_dirty(RawAddr victim_address);

    /* invalidate_victim:
     * Just invalidate the victim.
     */
    void invalidate_victim(RawAddr victim_address);

    void dirtify_victim(RawAddr victim_address);

    /* insert_new_data:
     * Insert new data that was missing before
     */
    void insert_new_data(RawAddr address);

    void insert_dirty_new_data(RawAddr address);

    /* write_back:
     * Straight up insert at the address provided
     */
    Outcome find_and_write_data(RawAddr address);

    /* mark_dirty:
     * This is for a write operation. To write after a snoop or a write
     * operation
     */
    void set_dirt_status(RawAddr address, bool status);

    /* invalidate:
     * Mark invalid after a write to a lower level
     */
    void set_validity_status(RawAddr address, bool status);

    size_t get_n_access() const;
    size_t get_n_hits() const;
    size_t get_n_misses() const;

  private:
    const int size_;       // = cache size
    const int block_size_; // = line size
    const int cycles_;
    const int assoc_;
    const int n_of_sets_; // implicitly, this is also the n_of_tags
    const int b_tag_size_;
    const bool write_alloc_;

    const BitMask tag_mask_;
    const BitMask set_mask_;

    // data for printing
    size_t n_of_access = 0;
    size_t n_of_misses = 0;
    size_t n_of_hits   = 0;
    // ---------------

    std::vector<Set> sets_;

    AddrParts splitAddr(RawAddr addr) const
    {
        return {create_tag(addr), create_set(addr)};
    }

    Tag create_tag(RawAddr address) const
    {
        return (address & tag_mask_) >> (B_ADDR_SIZE - b_tag_size_);
    }

    SetNr create_set(RawAddr address) const
    {
        return (address & set_mask_) >> block_size_;
    }
};

class simulator
{
  public:
    simulator(const simulator&)            = delete;
    simulator& operator=(const simulator&) = delete;

    static simulator& getInstance(int _block_size, int _mem_cycles,
                                  int _l1_size, int _l1_cycles, int _l1_assoc,
                                  int _l2_size, int _l2_cycles, int _l2_assoc,
                                  bool _write_alloc)
    {

        /* Creating a static instance of the simulator because we don't need
         * more than one
         */
        static simulator instance(_block_size, _mem_cycles, _l1_size,
                                  _l1_cycles, _l1_assoc, _l2_size, _l2_cycles,
                                  _l2_assoc, _write_alloc);
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
            throw std::logic_error("No such operation"); /* shouldn't happen */
        }
    }

    double calc_L1_miss_rate() const
    {
        return (double)L1_.get_n_misses() / (double)L1_.get_n_access();
    }
    double calc_L2_miss_rate() const
    {
        return (double)L2_.get_n_misses() / (double)L2_.get_n_access();
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
          L1_(l1_size, block_size, l1_cycles, l1_assoc, write_alloc),
          L2_(l2_size, block_size, l2_cycles, l2_assoc, write_alloc)
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

    cache L1_;
    cache L2_;

    void do_read(RawAddr address)
    {
        RawAddr victim_address = 0;
        log_l1_access();
        if (!L1_.find_and_read_data(address)) {
            log_l2_access();
            if (!L2_.find_and_read_data(address)) {
                /* We didn't find the data in L2 and L1, so we need to get it
                 * from memory. */
                log_mem_access();

                /* start snoop */
                victim_address = L2_.find_victim(address);
                if (L1_.is_victim_dirty(victim_address)) {
                    /* write to L2 */
                    L2_.dirtify_victim(victim_address);
                }
                L1_.invalidate_victim(victim_address);
                /*
                if (L2.is_victim_dirty(victim_address)) {
                    <write to memeory>
                }
                * no need for this, because write back is done in the
                background,
                * but this is what is happening in the background.
                */
                L2_.invalidate_victim(victim_address);

                /* end of snoop, write new data into L2 */
                L2_.insert_new_data(address);
            }

            /* find a place to write into L1 */
            victim_address = L1_.find_victim(address);
            if (L1_.is_victim_dirty(victim_address)) {
                /* write to L2 */
                L2_.dirtify_victim(victim_address);
            }
            L1_.invalidate_victim(victim_address);

            /* end of snoop, write new data into L1 */
            L1_.insert_new_data(address);
        }
    }
    void do_write(RawAddr address)
    {
        if (write_alloc_) {
            RawAddr victim_address = 0;
            log_l1_access();
            if (!L1_.find_and_write_data(address)) {
                log_l2_access();
                if (!L2_.find_and_read_data(address)) {
                    /* We didn't find the data in L2 and L1, so we need to get
                     * it from memory. */
                    log_mem_access();

                    /* start snoop */
                    victim_address = L2_.find_victim(address);
                    if (L1_.is_victim_dirty(victim_address)) {
                        /* write to L2 */
                        L2_.dirtify_victim(victim_address);
                    }
                    L1_.invalidate_victim(victim_address);
                    /*
                    if (L2.is_victim_dirty(victim_address)) {
                        <write to memeory>
                    }
                    */
                    L2_.invalidate_victim(victim_address);

                    /* end of snoop, write new data into L2 */
                    L2_.insert_new_data(address);
                }

                /* find a place to write into L1 */
                victim_address = L1_.find_victim(address);
                if (L1_.is_victim_dirty(victim_address)) {
                    /* write to L2 */
                    L2_.dirtify_victim(victim_address);
                }
                L1_.invalidate_victim(victim_address);

                /* end of snoop, write new data into L1 */
                L1_.insert_dirty_new_data(address);
            }
        } else { /* no write allocate, very simple */
            log_l1_access();
            if (!L1_.find_and_write_data(address)) {
                log_l2_access();
                if (!L2_.find_and_write_data(address)) {
                    log_mem_access();
                }
            }
        }
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
