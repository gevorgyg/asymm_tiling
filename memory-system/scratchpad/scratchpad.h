#pragma once

#include "../memory_object.h"
#include "scratchpad_action.h"
#include <vector>

class ScratchpadDev : public MemoryObject
{
  public:
    ScratchpadDev(uint access_cycles, uint banks, uint word_size_bytes);

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

    uint accessTile(Addr base_addr, uint t_width, uint t_height, uint stride,
                    uint elem_width, bool is_write, Trace& trace);

  private:
    uint              banks_;
    uint              word_size_bytes_;
    std::vector<uint> bank_counts_;
};
