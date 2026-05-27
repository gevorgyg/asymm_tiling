#ifndef CACHE_H
#define CACHE_H

#include <cstdint>
#include <vector>

typedef uint32_t MASK;
typedef bool outcome;
typedef uint32_t addr_t;
typedef uint32_t set_t;

class LRU {
    int assoc;
    std::vector<uint32_t> queue;

  public:
    LRU(int _assoc);

    int get_lru() const;
    void update_queue(size_t index);
};

class tag_t {
    uint32_t data;
    addr_t full_address;
    int b_tag_size; // likely not needed, might remove

    bool valid;
    bool dirty;

  public:
    tag_t(int _b_tag_size, addr_t address = 0, uint32_t _data = 0);
    tag_t &operator=(const tag_t &other);

    /* operator==:
     * Very simple intager comperison.
     */
    bool operator==(const tag_t &other) const;

    void validate_and_insert(const tag_t &other);

    /* get_data(), is_valid and is_dirty:
     * Getters for the data, valid and dirty fields.
     */
    uint32_t get_data() const;
    addr_t get_full_address() const;
    bool is_valid() const;
    bool is_dirty() const;

    /* set_...():
     * Setters for the data, valid and dirty fields.
     */
    void set_data(uint32_t _data);
    void set_valid(bool state);
    void set_dirty(bool state);
};

class way {
    int assoc;
    int n_of_lines; // = n_of_tags
    int b_tag_size;
    int block_size;

    std::vector<tag_t> tags;

  public:
    way(int _assoc, int _n_of_lines, int _b_tag_size, int _block_size);

    /* check_tag:
     * Check if the tag provided and tag at the index of the set are the same
     * and return true if yes and false if no.
     */
    bool find_tag(tag_t tag, set_t set) const;

    /* insert_tag:
     * Just put the tag at the index of the set and mark the dirty and valid
     * bits as needed.
     */
    void insert_tag(tag_t tag, set_t set);

    bool check_set_valid(set_t set) const;

    bool is_set_dirty(set_t set) const;

    void set_dirt_status(set_t set, bool status);

    void set_valid_status(set_t set, bool status);

    addr_t get_full_address(set_t set) const;
};

class cache {
    static constexpr int B_ADDR_SIZE = 32;
    static constexpr int B_ALIGN_SIZE = 2;
    static constexpr int B_METADATA_SIZE = 2;

    int size;       // = cache size
    int block_size; // = line size
    int cycles;
    int assoc;
    int n_of_sets; // implicitly, this is also the n_of_tags
    int b_tag_size;

    // data for printing
    size_t n_of_access = 0;
    size_t n_of_misses = 0;
    size_t n_of_hits = 0;
    // ---------------

    bool write_alloc;

    std::vector<way> ways;
    std::vector<LRU> LRUs;

    MASK tag_mask;
    MASK set_mask;

  private:
    /* create_tag and create_set:
     * Create a tag and set from the address using the mask, to send forward to
     * the way and tag class for comperison and processing.
     */
    tag_t create_tag(addr_t address) const;
    set_t create_set(addr_t address) const;
    int find_empty_space(set_t set) const; // TODO
    int get_lru_way(set_t set) const;      // TODO

  public:
    cache(int _size, int _block_size, int _cycles, int _assoc,
          bool _write_alloc);

    /* find_data:
     * Travese every way and check the tag at that way. If found matching tag,
     * then it's a hit. If finished traversing every way and no match then it's
     * a miss.
     */
    outcome find_and_read_data(addr_t address);

    /* find_victim:
     * Check if there is empty space, if no, find a victim with LRU.
     */
    addr_t find_victim(addr_t address);

    outcome is_victim_dirty(addr_t victim_address);

    /* invalidate_victim:
     * Just invalidate the victim.
     */
    void invalidate_victim(addr_t victim_address);

    void dirtify_victim(addr_t victim_address);

    /* insert_new_data:
     * Insert new data that was missing before
     */
    void insert_new_data(addr_t address);

    void insert_dirty_new_data(addr_t address);

    /* write_back:
     * Straight up insert at the address provided
     */
    outcome find_and_write_data(addr_t address);

    /* mark_dirty:
     * This is for a write operation. To write after a snoop or a write
     * operation
     */
    void set_dirt_status(addr_t address, bool status);

    /* invalidate:
     * Mark invalid after a write to a lower level
     */
    void set_validity_status(addr_t address, bool status);

    size_t get_n_access() const;
    size_t get_n_hits() const;
    size_t get_n_misses() const;
};

class simulator {
    simulator(int _block_size, int _mem_cycles, int _l1_size, int _l1_cycles,
              int _l1_assoc, int _l2_size, int _l2_cycles, int _l2_assoc,
              bool _write_alloc); // singleton

    int block_size;
    int mem_cycles;
    int l1_size;
    int l1_cycles;
    int l1_assoc;
    int l2_size;
    int l2_cycles;
    int l2_assoc;

    // data for printing
    size_t total_access_cycles = 0;
    size_t n_of_access = 0;
    // ---------------

    bool write_alloc;

    cache L1;
    cache L2;

  private:
    void do_read(addr_t address);
    void do_write(addr_t address);

    void log_l1_access();
    void log_l2_access();
    void log_mem_access();

  public:
    simulator(const simulator &) = delete;
    simulator &operator=(const simulator &) = delete;

    static simulator &getInstance(int _block_size, int _mem_cycles,
                                  int _l1_size, int _l1_cycles, int _l1_assoc,
                                  int _l2_size, int _l2_cycles, int _l2_assoc,
                                  bool _write_alloc);

    void process_request(char operation, addr_t address);

    double calc_L1_miss_rate() const;
    double calc_L2_miss_rate() const;
    double calc_avg_access_time() const;
};

#endif
