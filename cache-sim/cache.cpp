#include "cache.h"
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

// ---------------------------- HELPER FUNCTIONS ---------------------------- //

/* simple log function */
static int my_log2(int size) {
    short result = 0;
    while (size >>= 1)
        result++;
    return result;
}

/* return 2^exponent */
static int ttp(int exponent) {
    return (1 << exponent);
}

// ---------------------------- SIMULATOR ----------------------------  //

simulator::simulator(int _block_size, int _mem_cycles, int _l1_size,
                     int _l1_cycles, int _l1_assoc, int _l2_size,
                     int _l2_cycles, int _l2_assoc, bool _write_alloc)
    : block_size(_block_size), mem_cycles(_mem_cycles), l1_size(_l1_size),
      l1_cycles(_l1_cycles), l1_assoc(_l1_assoc), l2_size(_l2_size),
      l2_cycles(_l2_cycles), l2_assoc(_l2_assoc), write_alloc(_write_alloc),
      L1(l1_size, block_size, l1_cycles, l1_assoc, write_alloc),
      L2(l2_size, block_size, l2_cycles, l2_assoc, write_alloc) {}

simulator &simulator::getInstance(int _block_size, int _mem_cycles,
                                  int _l1_size, int _l1_cycles, int _l1_assoc,
                                  int _l2_size, int _l2_cycles, int _l2_assoc,
                                  bool _write_alloc) {

    /* Creating a static instance of the simulator because we don't need more
     * than one
     */
    static simulator instance(_block_size,
                              _mem_cycles,
                              _l1_size,
                              _l1_cycles,
                              _l1_assoc,
                              _l2_size,
                              _l2_cycles,
                              _l2_assoc,
                              _write_alloc);
    return instance;
}

void simulator::do_read(addr_t address) {
    addr_t victim_address = 0;
    log_l1_access();
    if (!L1.find_and_read_data(address)) {
        log_l2_access();
        if (!L2.find_and_read_data(address)) {
            /* We didn't find the data in L2 and L1, so we need to get it from
             * memory. */
            log_mem_access();

            /* start snoop */
            victim_address = L2.find_victim(address);
            if (L1.is_victim_dirty(victim_address)) {
                /* write to L2 */
                L2.dirtify_victim(victim_address);
            }
            L1.invalidate_victim(victim_address);
            /*
            if (L2.is_victim_dirty(victim_address)) {
                <write to memeory>
            }
            * no need for this, because write back is done in the background,
            * but this is what is happening in the background.
            */
            L2.invalidate_victim(victim_address);

            /* end of snoop, write new data into L2 */
            L2.insert_new_data(address);
        }

        /* find a place to write into L1 */
        victim_address = L1.find_victim(address);
        if (L1.is_victim_dirty(victim_address)) {
            /* write to L2 */
            L2.dirtify_victim(victim_address);
        }
        L1.invalidate_victim(victim_address);

        /* end of snoop, write new data into L1 */
        L1.insert_new_data(address);
    }
}

void simulator::do_write(addr_t address) {
    if (write_alloc) {
        addr_t victim_address = 0;
        log_l1_access();
        if (!L1.find_and_write_data(address)) {
            log_l2_access();
            if (!L2.find_and_read_data(address)) {
                /* We didn't find the data in L2 and L1, so we need to get it
                 * from memory. */
                log_mem_access();

                /* start snoop */
                victim_address = L2.find_victim(address);
                if (L1.is_victim_dirty(victim_address)) {
                    /* write to L2 */
                    L2.dirtify_victim(victim_address);
                }
                L1.invalidate_victim(victim_address);
                /*
                if (L2.is_victim_dirty(victim_address)) {
                    <write to memeory>
                }
                */
                L2.invalidate_victim(victim_address);

                /* end of snoop, write new data into L2 */
                L2.insert_new_data(address);
            }

            /* find a place to write into L1 */
            victim_address = L1.find_victim(address);
            if (L1.is_victim_dirty(victim_address)) {
                /* write to L2 */
                L2.dirtify_victim(victim_address);
            }
            L1.invalidate_victim(victim_address);

            /* end of snoop, write new data into L1 */
            L1.insert_dirty_new_data(address);
        }
    } else { /* no write allocate, very simple */
        log_l1_access();
        if (!L1.find_and_write_data(address)) {
            log_l2_access();
            if (!L2.find_and_write_data(address)) {
                log_mem_access();
            }
        }
    }
}

void simulator::log_l1_access() {
    /* only need to increment the access amount of the first access try, that
     * always starts at L1 */
    n_of_access++;
    total_access_cycles += l1_cycles;
}

void simulator::log_l2_access() {
    total_access_cycles += l2_cycles;
}

void simulator::log_mem_access() {
    total_access_cycles += mem_cycles;
}

void simulator::process_request(char operation, addr_t address) {
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

double simulator::calc_L1_miss_rate() const {
    return (double)L1.get_n_misses() / (double)L1.get_n_access();
}
double simulator::calc_L2_miss_rate() const {
    return (double)L2.get_n_misses() / (double)L2.get_n_access();
}
double simulator::calc_avg_access_time() const {
    return (double)total_access_cycles / (double)n_of_access;
}

// ---------------------------- CACHE ----------------------------  //

cache::cache(int _size, int _block_size, int _cycles, int _assoc,
             bool _write_alloc)
    : size(_size), block_size(_block_size), cycles(_cycles), assoc(ttp(_assoc)),
      write_alloc(_write_alloc) {

    n_of_sets = (ttp(size) / assoc) / ttp(block_size);
    b_tag_size = B_ADDR_SIZE - block_size - my_log2(n_of_sets);

    /* create n-ways, each one containing a #set of lines and tag */
    ways =
        std::vector<way>(assoc, way(assoc, n_of_sets, b_tag_size, block_size));

    /* create an LRU queue for each set */
    LRUs = std::vector<LRU>(n_of_sets, LRU(assoc));

    /* create a mask of 111111000000... to get the tag from the address */
    tag_mask = ~((1 << (B_ADDR_SIZE - b_tag_size)) - 1);
    /* create a mask of 000011111000... to get the set from the address */

    int set_bits = my_log2(n_of_sets);
    set_mask = ((1 << set_bits) - 1) << block_size;

    // set_mask = (~((1 << (B_ADDR_SIZE - block_size)) - 1)) & (~tag_mask);
}

tag_t cache::create_tag(addr_t address) const {
    uint32_t tag_nr = (address & tag_mask) >> (B_ADDR_SIZE - b_tag_size);
    return tag_t(b_tag_size, address, tag_nr);
}

set_t cache::create_set(addr_t address) const {
    return (address & set_mask) >> block_size;
}

outcome cache::find_and_read_data(addr_t address) {
    tag_t cur_tag = create_tag(address);
    set_t cur_set = create_set(address);
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

addr_t cache::find_victim(addr_t address) {
    set_t cur_set = create_set(address);

    /* nr == number */
    int way_nr = find_empty_space(cur_set); /* find INVALID set */
    if (way_nr != -1) return address;

    /* only if there is no empty space, we pick a victim, to avoid sending junk
     * data back */
    way_nr = get_lru_way(cur_set); /* victim */
    return ways[way_nr].get_full_address(cur_set);
}

outcome cache::is_victim_dirty(addr_t victim_address) {
    tag_t cur_tag = create_tag(victim_address);
    set_t cur_set = create_set(victim_address);
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (ways[way_nr].find_tag(cur_tag, cur_set)) {
            return ways[way_nr].is_set_dirty(cur_set);
        }
    }
    return false;
}

void cache::invalidate_victim(addr_t victim_address) {
    set_validity_status(victim_address, false);
}

void cache::dirtify_victim(addr_t victim_address) {
    set_dirt_status(victim_address, true);
}

void cache::insert_new_data(addr_t address) {
    tag_t cur_tag = create_tag(address);
    set_t cur_set = create_set(address);

    /* nr == number */
    int way_nr = find_empty_space(cur_set); /* find INVALID set */
    /* Insert a new tag */
    ways[way_nr].insert_tag(cur_tag, cur_set);
    /* update LRU queue */
    LRUs[cur_set].update_queue(way_nr);
}

void cache::insert_dirty_new_data(addr_t address) {
    tag_t cur_tag = create_tag(address);
    set_t cur_set = create_set(address);

    /* nr == number */
    int way_nr = find_empty_space(cur_set); /* find INVALID set */
    /* Insert a new dirty tag */
    ways[way_nr].insert_tag(cur_tag, cur_set);
    ways[way_nr].set_dirt_status(cur_set, true);
    /* update LRU queue */
    LRUs[cur_set].update_queue(way_nr);
}

outcome cache::find_and_write_data(addr_t address) {
    tag_t cur_tag = create_tag(address);
    set_t cur_set = create_set(address);
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

int cache::find_empty_space(set_t set) const {
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (!ways[way_nr].check_set_valid(set)) return way_nr;
    }

    return -1;
}

int cache::get_lru_way(set_t set) const {
    return LRUs[set].get_lru();
}

void cache::set_dirt_status(addr_t address, bool status) {
    tag_t cur_tag = create_tag(address);
    set_t cur_set = create_set(address);
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (ways[way_nr].find_tag(cur_tag, cur_set)) {
            ways[way_nr].set_dirt_status(cur_set, status);

            /* a write is an access, so we need to update the LRU */
            LRUs[cur_set].update_queue(way_nr);
        }
    }
}

void cache::set_validity_status(addr_t address, bool status) {
    tag_t cur_tag = create_tag(address);
    set_t cur_set = create_set(address);
    for (size_t way_nr = 0; way_nr < ways.size(); way_nr++) {
        if (ways[way_nr].find_tag(cur_tag, cur_set)) {
            ways[way_nr].set_valid_status(cur_set, status);
        }
    }
}

size_t cache::get_n_access() const {
    return n_of_access;
}
size_t cache::get_n_hits() const {
    return n_of_hits;
}
size_t cache::get_n_misses() const {
    return n_of_misses;
}

// ---------------------------- WAY ----------------------------  //

way::way(int _assoc, int _n_of_lines, int _b_tag_size, int _block_size)
    : assoc(_assoc), n_of_lines(_n_of_lines), b_tag_size(_b_tag_size),
      block_size(_block_size), tags(n_of_lines, tag_t(b_tag_size)) {}

bool way::find_tag(tag_t tag, set_t set) const {
    return (tags[set] == tag) && tags[set].is_valid();
}

void way::insert_tag(tag_t tag, set_t set) {
    tags[set].validate_and_insert(tag);
}

bool way::check_set_valid(set_t set) const {
    return tags[set].is_valid();
}

bool way::is_set_dirty(set_t set) const {
    return tags[set].is_dirty();
}

void way::set_dirt_status(set_t set, bool status) {
    tags[set].set_dirty(status);
}

void way::set_valid_status(set_t set, bool status) {
    tags[set].set_valid(status);
}

addr_t way::get_full_address(set_t set) const {
    return tags[set].get_full_address();
}

// ---------------------------- TAG ----------------------------  //

tag_t::tag_t(int _b_tag_size, addr_t address, uint32_t _data)
    : data(_data), full_address(address), b_tag_size(_b_tag_size), valid(false),
      dirty(false) {}

tag_t &tag_t::operator=(const tag_t &other) {
    data = other.data;
    full_address = other.full_address;
    b_tag_size = other.b_tag_size;
    valid = other.valid;
    dirty = other.dirty;

    return *this;
}

bool tag_t::operator==(const tag_t &other) const {
    return data == other.data;
}

void tag_t::validate_and_insert(const tag_t &other) {
    data = other.data;
    full_address = other.full_address;
    b_tag_size = other.b_tag_size;
    valid = true;
    dirty = false;
}

uint32_t tag_t::get_data() const {
    return data;
}

addr_t tag_t::get_full_address() const {
    return full_address;
}

bool tag_t::is_valid() const {
    return valid;
}

bool tag_t::is_dirty() const {
    return dirty;
}

void tag_t::set_data(uint32_t _data) {
    data = _data;
}

void tag_t::set_valid(bool state) {
    valid = state;
}

void tag_t::set_dirty(bool state) {
    dirty = state;
}

// ---------------------------- TAG ----------------------------  //

LRU::LRU(int _assoc) : assoc(_assoc), queue(assoc) {
    for (int i = 0; i < assoc; i++) {
        queue[i] = i;
    }
}

int LRU::get_lru() const {
    for (size_t i = 0; i < queue.size(); i++) {
        if (queue[i] == 0) return i;
    }

    /* shouldn't happen, bubble to top */
    throw std::logic_error("didn't find 0 element");
}

/* one to one copy of what is taught in class */
void LRU::update_queue(size_t index) {
    uint32_t x = queue[index];
    queue[index] = assoc - 1;
    for (size_t i = 0; i < queue.size(); i++) {
        if ((i != index) && (queue[i] > x)) queue[i]--;
    }
}
