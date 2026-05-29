#ifndef CACHE_H
#define CACHE_H

#include <cstdint>
#include <vector>

using BitMask = uint32_t;
using RawAddr = uint32_t;
using SetNr   = uint32_t;
using Outcome = bool;

class LRU
{
  public:
    LRU(int assoc);

    int get_lru() const;
    void update_queue(size_t index);

  private:
    int assoc_;
    std::vector<uint32_t> queue_;
};

class tag_t
{
  public:
    tag_t(int _b_tag_size, RawAddr address = 0, uint32_t _data = 0);
    tag_t& operator=(const tag_t& other);

    /* operator==:
     * Very simple intager comperison.
     */
    bool operator==(const tag_t& other) const;

    void validate_and_insert(const tag_t& other);

    /* get_data(), is_valid and is_dirty:
     * Getters for the data, valid and dirty fields.
     */
    uint32_t get_data() const;
    RawAddr get_full_address() const;
    bool is_valid() const;
    bool is_dirty() const;

    /* set_...():
     * Setters for the data, valid and dirty fields.
     */
    void set_data(uint32_t _data);
    void set_valid(bool state);
    void set_dirty(bool state);

  private:
    uint32_t data;
    RawAddr full_address;
    int b_tag_size; // likely not needed, might remove

    bool valid;
    bool dirty;
};

class way
{
  public:
    way(int _assoc, int _n_of_lines, int _b_tag_size, int _block_size);

    /* check_tag:
     * Check if the tag provided and tag at the index of the set are the same
     * and return true if yes and false if no.
     */
    bool find_tag(const tag_t& tag, const SetNr set) const;

    /* insert_tag:
     * Just put the tag at the index of the set and mark the dirty and valid
     * bits as needed.
     */
    void insert_tag(const tag_t& tag, const SetNr set);

    bool check_set_valid(SetNr set) const;

    bool is_set_dirty(SetNr set) const;

    void set_dirt_status(SetNr set, bool status);

    void set_valid_status(SetNr set, bool status);

    RawAddr get_full_address(SetNr set) const;

  private:
    int assoc;
    int n_of_lines; // = n_of_tags
    int b_tag_size;
    int block_size;

    std::vector<tag_t> tags;
};

class cache
{
  public:
    cache(int _size, int _block_size, int _cycles, int _assoc,
          bool _write_alloc);

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
    static constexpr int B_ADDR_SIZE     = 32;
    static constexpr int B_ALIGN_SIZE    = 2;
    static constexpr int B_METADATA_SIZE = 2;

    int size_;       // = cache size
    int block_size_; // = line size
    int cycles_;
    int assoc_;
    int n_of_sets_; // implicitly, this is also the n_of_tags
    int b_tag_size_;

    // data for printing
    size_t n_of_access = 0;
    size_t n_of_misses = 0;
    size_t n_of_hits   = 0;
    // ---------------

    bool write_alloc_;

    std::vector<way> ways;
    std::vector<LRU> LRUs;

    BitMask tag_mask_;
    BitMask set_mask_;

    /* create_tag and create_set:
     * Create a tag and set from the address using the mask, to send forward to
     * the way and tag class for comperison and processing.
     */
    tag_t create_tag(RawAddr address) const;
    SetNr create_set(RawAddr address) const;
    int find_empty_space(SetNr set) const; // TODO
    int get_lru_way(SetNr set) const;      // TODO
};

class simulator
{
  public:
    simulator(const simulator&)            = delete;
    simulator& operator=(const simulator&) = delete;

    static simulator& getInstance(int _block_size, int _mem_cycles,
                                  int _l1_size, int _l1_cycles, int _l1_assoc,
                                  int _l2_size, int _l2_cycles, int _l2_assoc,
                                  bool _write_alloc);

    void process_request(char operation, RawAddr address);

    double calc_L1_miss_rate() const;
    double calc_L2_miss_rate() const;
    double calc_avg_access_time() const;

  private:
    simulator(int _block_size, int _mem_cycles, int _l1_size, int _l1_cycles,
              int _l1_assoc, int _l2_size, int _l2_cycles, int _l2_assoc,
              bool _write_alloc); // singleton

    int block_size_;
    int mem_cycles_;
    int l1_size_;
    int l1_cycles_;
    int l1_assoc_;
    int l2_size_;
    int l2_cycles_;
    int l2_assoc_;

    // data for printing
    size_t total_access_cycles = 0;
    size_t n_of_access         = 0;
    // ---------------

    bool write_alloc_;

    cache L1_;
    cache L2_;

    void do_read(RawAddr address);
    void do_write(RawAddr address);

    void log_l1_access();
    void log_l2_access();
    void log_mem_access();
};

#endif
