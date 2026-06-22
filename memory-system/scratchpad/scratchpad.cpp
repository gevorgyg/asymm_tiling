#include "scratchpad.h"
#include <algorithm>

ScratchpadDev::ScratchpadDev(uint access_cycles, uint banks, uint word_size_bytes,
                             Addr base_addr, Addr end_addr)
    : MemoryObject(access_cycles), banks_(banks), word_size_bytes_(word_size_bytes),
      base_(base_addr), end_(end_addr)
{
    bank_counts_.resize(banks_, 0);
}

void ScratchpadDev::read(Addr addr, size_t /*size*/, Trace& trace)
{
    trace.push_back(std::make_unique<ScratchpadAction>(ScratchpadOp::READ, addr, 1, 1, accessCycles()));
    ++stats_.element_reads;
}

void ScratchpadDev::write(Addr addr, size_t /*size*/, Trace& trace)
{
    trace.push_back(std::make_unique<ScratchpadAction>(ScratchpadOp::WRITE, addr, 1, 1, accessCycles()));
    ++stats_.element_writes;
}

uint ScratchpadDev::accessTile(Addr base_addr, uint t_width, uint t_height, uint stride,
                               uint elem_width, bool is_write, Trace& trace)
{
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
        if (count > max_conflicts) max_conflicts = count;
    }

    const uint cycles = max_conflicts * accessCycles();

    trace.push_back(std::make_unique<ScratchpadAction>(
        is_write ? ScratchpadOp::WRITE : ScratchpadOp::READ,
        base_addr, t_width, t_height, cycles));

    if (is_write) ++stats_.tile_writes;
    else          ++stats_.tile_reads;

    // Each bank beyond the first access is a stall (ideal = 1 * accessCycles())
    if (max_conflicts > 1)
        stats_.conflict_stalls += (max_conflicts - 1) * accessCycles();

    return cycles;
}
