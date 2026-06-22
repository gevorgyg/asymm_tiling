#include "prng.h"

#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <ostream>


// --- PrngDev ----------------------------------------------------------------

PrngDev::PrngDev(InitParameters p)
    : MemoryObject(p.access_cycles),
      base_(p.base_addr),
      end_(p.base_addr + p.window_bytes),
      line_size_(p.line_size),
      gen_cost_per_line_(p.gen_cost_per_line),
      head_(p.base_addr)
{
    assert(line_size_ > 0);
    assert(base_ % line_size_ == 0);
    assert(end_ % line_size_ == 0);
}

void PrngDev::read(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));

    const bool was_generated = isGenerated(addr);
    trace.push_back(std::make_unique<IsGenerated>(addr, accessCycles(), was_generated));

    if (was_generated) {
        ++stats_.regenerates;
    } else {
        ++stats_.generates;
    }
    const Addr line_base = lineBase(addr);
    head_ = std::max(head_, static_cast<Addr>(line_base + line_size_));

    // First generation and re-derivation cost the same: any line is produced
    // from its window offset alone.
    trace.push_back(std::make_unique<Generate>(line_base, gen_cost_per_line_, was_generated));
}

void PrngDev::write(Addr addr, size_t /*size*/, Trace& /*trace*/)
{
    std::cerr << "PRNG window is read-only: write @0x" << std::hex << addr
              << std::dec << std::endl;
    exit(1);
}


// --- PrngDev::IsGenerated ----------------------------------------------------

void PrngDev::IsGenerated::print(std::ostream& os) const
{
    os << "PRNG IsGenerated @0x" << std::hex << byte_addr_ << std::dec << " "
       << (generated_ ? "YES" : "NO") << " (" << cost_ << " cy)";
}


// --- PrngDev::Generate -------------------------------------------------------

void PrngDev::Generate::print(std::ostream& os) const
{
    os << "PRNG Generate line @0x" << std::hex << line_base_ << std::dec
       << " (" << cost_ << " cy)" << (regen_ ? " REGEN" : "");
}
