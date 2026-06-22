#include "scratchpad.h"
#include <algorithm>

ScratchpadDev::ScratchpadDev(uint access_cycles, uint banks, uint word_size_bytes)
    : MemoryObject(access_cycles), banks_(banks), word_size_bytes_(word_size_bytes)
{
    bank_counts_.resize(banks_, 0);
}

void ScratchpadDev::read(Addr addr, size_t /*size*/, Trace& trace)
{
    trace.push_back(std::make_unique<ScratchpadAction>(ScratchpadOp::READ, addr, 1, 1, accessCycles()));
}

void ScratchpadDev::write(Addr addr, size_t /*size*/, Trace& trace)
{
    trace.push_back(std::make_unique<ScratchpadAction>(ScratchpadOp::WRITE, addr, 1, 1, accessCycles()));
}

uint ScratchpadDev::accessTile(Addr base_addr, uint t_width, uint t_height, uint stride,
                               uint elem_width, bool is_write, Trace& trace)
{
    // Reset our pre-allocated count array to zero
    std::fill(bank_counts_.begin(), bank_counts_.end(), 0);

    for (uint row = 0; row < t_height; ++row) {
        for (uint col = 0; col < t_width; ++col) {
            const Addr addr = base_addr + (row * stride + col) * elem_width;
            const uint bank = (addr / word_size_bytes_) % banks_;
            bank_counts_[bank]++;
        }
    }

    uint max_conflicts = 0;
    for (uint count : bank_counts_) {
        if (count > max_conflicts) {
            max_conflicts = count;
        }
    }

    trace.push_back(std::make_unique<ScratchpadAction>(
        is_write ? ScratchpadOp::WRITE : ScratchpadOp::READ,
        base_addr, t_width, t_height, max_conflicts));

    return max_conflicts;
}
