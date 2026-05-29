#include "cache.h"
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

// ---------------------------- HELPER FUNCTIONS ---------------------------- //

namespace
{

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

// ---------------------------- SIMULATOR ----------------------------  //

simulator::simulator(int _block_size, int _mem_cycles, int _l1_size,
                     int _l1_cycles, int _l1_assoc, int _l2_size,
                     int _l2_cycles, int _l2_assoc, bool _write_alloc)
    : block_size(_block_size), mem_cycles_(_mem_cycles), l1_size_(_l1_size),
      l1_cycles_(_l1_cycles), l1_assoc_(_l1_assoc), l2_size_(_l2_size),
      l2_cycles_(_l2_cycles), l2_assoc_(_l2_assoc), write_alloc_(_write_alloc),
      L1(l1_size, block_size, l1_cycles, l1_assoc, write_alloc),
      L2(l2_size, block_size, l2_cycles, l2_assoc, write_alloc)
{
}

simulator& simulator::getInstance(int _block_size, int _mem_cycles,
                                  int _l1_size, int _l1_cycles, int _l1_assoc,
                                  int _l2_size, int _l2_cycles, int _l2_assoc,
                                  bool _write_alloc)
{

    /* Creating a static instance of the simulator because we don't need more
     * than one
     */
    static simulator instance(_block_size, _mem_cycles, _l1_size, _l1_cycles,
                              _l1_assoc, _l2_size, _l2_cycles, _l2_assoc,
                              _write_alloc);
    return instance;
}

void simulator::do_read(RawAddr address)
{
    RawAddr victim_address = 0;
    log_l1_access();
    if (!L1_.find_and_read_data(address)) {
        log_l2_access();
        if (!L2_.find_and_read_data(address)) {
            /* We didn't find the data in L2 and L1, so we need to get it from
             * memory. */
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
            * no need for this, because write back is done in the background,
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

void simulator::do_write(RawAddr address)
{
    if (write_alloc_) {
        RawAddr victim_address = 0;
        log_l1_access();
        if (!L1_.find_and_write_data(address)) {
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

void simulator::log_l1_access()
{
    /* only need to increment the access amount of the first access try, that
     * always starts at L1 */
    n_of_access++;
    total_access_cycles += l1_cycles_;
}

void simulator::log_l2_access()
{
    total_access_cycles += l2_cycles_;
}

void simulator::log_mem_access()
{
    total_access_cycles += mem_cycles_;
}

void simulator::process_request(char operation, RawAddr address)
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

double simulator::calc_L1_miss_rate() const
{
    return (double)L1_.get_n_misses() / (double)L1_.get_n_access();
}
double simulator::calc_L2_miss_rate() const
{
    return (double)L2_.get_n_misses() / (double)L2_.get_n_access();
}
double simulator::calc_avg_access_time() const
{
    return (double)total_access_cycles / (double)n_of_access;
}

// ---------------------------- CACHE ----------------------------  //

cache::cache(int _size, int _block_size, int _cycles, int _assoc,
             bool _write_alloc)
    : size_(_size), block_size_(_block_size), cycles_(_cycles),
      assoc_(ttp(_assoc)), write_alloc_(_write_alloc)
{

    n_of_sets_  = (ttp(size_) / assoc_) / ttp(block_size_);
    b_tag_size_ = B_ADDR_SIZE - block_size_ - my_log2(n_of_sets_);

    /* create n-ways, each one containing a #set of lines and tag */
    ways = std::vector<way>(assoc_,
                            way(assoc_, n_of_sets_, b_tag_size_, block_size_));

    /* create an LRU queue for each set */
    LRUs = std::vector<LRU>(n_of_sets_, LRU(assoc_));

    /* create a mask of 111111000000... to get the tag from the address */
    tag_mask_ = ~((1 << (B_ADDR_SIZE - b_tag_size_)) - 1);
    /* create a mask of 000011111000... to get the set from the address */

    int set_bits = my_log2(n_of_sets_);
    set_mask_    = ((1 << set_bits) - 1) << block_size_;

    // set_mask = (~((1 << (B_ADDR_SIZE - block_size)) - 1)) & (~tag_mask);
}

tag_t cache::create_tag(RawAddr address) const
{
    uint32_t tag_nr = (address & tag_mask_) >> (B_ADDR_SIZE - b_tag_size_);
    return tag_t(b_tag_size_, address, tag_nr);
}

SetNr cache::create_set(RawAddr address) const
{
    return (address & set_mask_) >> block_size_;
}

Outcome cache::find_and_read_data(RawAddr address)
{
    tag_t cur_tag = create_tag(address);
    SetNr cur_set = create_set(address);
    n_of_access++;
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (ways[way_nr].find_tag(cur_tag, cur_set)) {
            n_of_hits++;
            /* update LRU queue */
            LRUs[cur_set].update_queue(way_nr);
            return true;
        }
    }
    n_of_misses++;
    return false;
}

RawAddr cache::find_victim(RawAddr address)
{
    SetNr cur_set = create_set(address);

    /* nr == number */
    int way_nr = find_empty_space(cur_set); /* find INVALID set */
    if (way_nr != -1)
        return address;

    /* only if there is no empty space, we pick a victim, to avoid sending junk
     * data back */
    way_nr = get_lru_way(cur_set); /* victim */
    return ways[way_nr].get_full_address(cur_set);
}

Outcome cache::is_victim_dirty(RawAddr victim_address)
{
    tag_t cur_tag = create_tag(victim_address);
    SetNr cur_set = create_set(victim_address);
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (ways[way_nr].find_tag(cur_tag, cur_set)) {
            return ways[way_nr].is_set_dirty(cur_set);
        }
    }
    return false;
}

void cache::invalidate_victim(RawAddr victim_address)
{
    set_validity_status(victim_address, false);
}

void cache::dirtify_victim(RawAddr victim_address)
{
    set_dirt_status(victim_address, true);
}

void cache::insert_new_data(RawAddr address)
{
    tag_t cur_tag = create_tag(address);
    SetNr cur_set = create_set(address);

    /* nr == number */
    int way_nr = find_empty_space(cur_set); /* find INVALID set */
    /* Insert a new tag */
    ways[way_nr].insert_tag(cur_tag, cur_set);
    /* update LRU queue */
    LRUs[cur_set].update_queue(way_nr);
}

void cache::insert_dirty_new_data(RawAddr address)
{
    tag_t cur_tag = create_tag(address);
    SetNr cur_set = create_set(address);

    /* nr == number */
    int way_nr = find_empty_space(cur_set); /* find INVALID set */
    /* Insert a new dirty tag */
    ways[way_nr].insert_tag(cur_tag, cur_set);
    ways[way_nr].set_dirt_status(cur_set, true);
    /* update LRU queue */
    LRUs[cur_set].update_queue(way_nr);
}

Outcome cache::find_and_write_data(RawAddr address)
{
    tag_t cur_tag = create_tag(address);
    SetNr cur_set = create_set(address);
    n_of_access++;
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (ways[way_nr].find_tag(cur_tag, cur_set)) {
            ways[way_nr].set_dirt_status(cur_set, true);

            /* update LRU queue */
            LRUs[cur_set].update_queue(way_nr);

            n_of_hits++;
            return true;
        }
    }

    n_of_misses++;
    return false;
}

int cache::find_empty_space(SetNr set) const
{
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (!ways[way_nr].check_set_valid(set))
            return way_nr;
    }

    return -1;
}

int cache::get_lru_way(SetNr set) const
{
    return LRUs[set].get_lru();
}

void cache::set_dirt_status(RawAddr address, bool status)
{
    tag_t cur_tag = create_tag(address);
    SetNr cur_set = create_set(address);
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (ways[way_nr].find_tag(cur_tag, cur_set)) {
            ways[way_nr].set_dirt_status(cur_set, status);

            /* a write is an access, so we need to update the LRU */
            LRUs[cur_set].update_queue(way_nr);
        }
    }
}

void cache::set_validity_status(RawAddr address, bool status)
{
    tag_t cur_tag = create_tag(address);
    SetNr cur_set = create_set(address);
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (ways[way_nr].find_tag(cur_tag, cur_set)) {
            ways[way_nr].set_valid_status(cur_set, status);
        }
    }
}

size_t cache::get_n_access() const
{
    return n_of_access;
}
size_t cache::get_n_hits() const
{
    return n_of_hits;
}
size_t cache::get_n_misses() const
{
    return n_of_misses;
}

// ---------------------------- WAY ----------------------------  //

way::way(int _assoc, int _n_of_lines, int _b_tag_size, int _block_size)
    : assoc(_assoc), n_of_lines(_n_of_lines), b_tag_size(_b_tag_size),
      block_size(_block_size), tags(n_of_lines, tag_t(b_tag_size))
{
}

bool way::find_tag(const tag_t& tag, const SetNr set) const
{
    return (tags[set] == tag) && tags[set].is_valid();
}

void way::insert_tag(const tag_t& tag, const SetNr set)
{
    tags[set].validate_and_insert(tag);
}

bool way::check_set_valid(const SetNr set) const
{
    return tags[set].is_valid();
}

bool way::is_set_dirty(SetNr set) const
{
    return tags[set].is_dirty();
}

void way::set_dirt_status(SetNr set, bool status)
{
    tags[set].set_dirty(status);
}

void way::set_valid_status(SetNr set, bool status)
{
    tags[set].set_valid(status);
}

RawAddr way::get_full_address(SetNr set) const
{
    return tags[set].get_full_address();
}

// ---------------------------- TAG ----------------------------  //

tag_t::tag_t(int _b_tag_size, RawAddr address, uint32_t _data)
    : data(_data), full_address(address), b_tag_size(_b_tag_size), valid(false),
      dirty(false)
{
}

tag_t& tag_t::operator=(const tag_t& other)
{
    data         = other.data;
    full_address = other.full_address;
    b_tag_size   = other.b_tag_size;
    valid        = other.valid;
    dirty        = other.dirty;

    return *this;
}

bool tag_t::operator==(const tag_t& other) const
{
    return data == other.data;
}

void tag_t::validate_and_insert(const tag_t& other)
{
    data         = other.data;
    full_address = other.full_address;
    b_tag_size   = other.b_tag_size;
    valid        = true;
    dirty        = false;
}

uint32_t tag_t::get_data() const
{
    return data;
}

RawAddr tag_t::get_full_address() const
{
    return full_address;
}

bool tag_t::is_valid() const
{
    return valid;
}

bool tag_t::is_dirty() const
{
    return dirty;
}

void tag_t::set_data(uint32_t _data)
{
    data = _data;
}

void tag_t::set_valid(bool state)
{
    valid = state;
}

void tag_t::set_dirty(bool state)
{
    dirty = state;
}

// ---------------------------- TAG ----------------------------  //

LRU::LRU(int assoc) : assoc_(assoc), queue_(assoc)
{
    for (int i = 0; i < assoc_; i++) {
        queue_[i] = i;
    }
}

int LRU::get_lru() const
{
    for (size_t i = 0; i < queue_.size(); i++) {
        if (queue_[i] == 0)
            return i;
    }

    /* shouldn't happen, bubble to top */
    throw std::logic_error("didn't find 0 element");
}

/* one to one copy of what is taught in class */
void LRU::update_queue(size_t index)
{
    uint32_t x    = queue_[index];
    queue_[index] = assoc_ - 1;
    for (size_t i = 0; i < queue_.size(); i++) {
        if ((i != index) && (queue_[i] > x))
            queue_[i]--;
    }
}
