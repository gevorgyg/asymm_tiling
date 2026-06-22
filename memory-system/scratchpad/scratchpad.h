#pragma once

#include "../memory_object.h"
#include "scratchpad_action.h"
#include <vector>

class ScratchpadDev : public MemoryObject
{
  public:
    struct Stats {
        size_t element_reads   = 0;
        size_t element_writes  = 0;
        size_t tile_reads      = 0;
        size_t tile_writes     = 0;
        size_t conflict_stalls = 0; // extra cycles lost to bank conflicts
    };

    ScratchpadDev(uint access_cycles, uint banks, uint word_size_bytes,
                  Addr base_addr, Addr end_addr);

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

    uint accessTile(Addr base_addr, uint t_width, uint t_height, uint stride,
                    uint elem_width, bool is_write, Trace& trace);

    bool contains(Addr addr) const { return addr >= base_ && addr < end_; }

    const Stats& stats() const { return stats_; }

  private:
    uint              banks_;
    uint              word_size_bytes_;
    Addr              base_;
    Addr              end_;
    std::vector<uint> bank_counts_;
    Stats             stats_;
};
