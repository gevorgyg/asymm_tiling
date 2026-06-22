#pragma once

#include "../action.h"
#include "../memory_object.h"

#include <cstdint>


// On-demand generator backing B. Serves L1 misses that land inside its
// window by producing exactly one cache line per request. The byte at window
// offset k is a pure function of k (counter-based stream), so an evicted line
// is re-derivable at the same cost as its first generation; the only mutable
// state is a high-water mark that lets isGenerated() answer arithmetically.
class PrngDev : public MemoryObject
{
  public:
    struct InitParameters {
        Addr   base_addr;         // window start (B's base); line-aligned
        size_t window_bytes;      // window extent; 0 disables the device
        size_t line_size;         // generation granularity == L1 line size
        uint   access_cycles;     // per-request overhead, charged by IsGenerated
        uint   gen_cost_per_line; // flat cost of one Generate
    };

    struct Stats {
        uint64_t generates   = 0;
        uint64_t regenerates = 0; // lines re-derived after an L1 eviction
    };

    explicit PrngDev(InitParameters p);

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override; // hard error

    bool contains(Addr addr) const { return addr >= base_ && addr < end_; }

    // Has the line holding `addr` ever been emitted? True iff its base is
    // below the high-water mark -- no tag storage involved.
    bool isGenerated(Addr addr) const { return lineBase(addr) < head_; }

    size_t       lineSize() const { return line_size_; }
    const Stats& stats() const    { return stats_; }

  private:
    Addr lineBase(Addr addr) const { return addr - addr % line_size_; }

    Addr   base_;
    Addr   end_;
    size_t line_size_;
    uint   gen_cost_per_line_;
    Addr   head_; // one past the highest byte ever generated
    Stats  stats_;
};
