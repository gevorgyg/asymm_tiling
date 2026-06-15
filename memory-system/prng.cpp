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

    trace.push_back(std::make_unique<IsGenerated>(*this, addr));
    trace.back()->perform(trace);

    // First generation and re-derivation cost the same: any line is produced
    // from its window offset alone.
    trace.push_back(std::make_unique<Generate>(*this, addr));
    trace.back()->perform(trace);
}

void PrngDev::write(Addr addr, size_t /*size*/, Trace& /*trace*/)
{
    std::cerr << "PRNG window is read-only: write @0x" << std::hex << addr
              << std::dec << std::endl;
    exit(1);
}


// --- PrngDev::IsGenerated ----------------------------------------------------

PrngDev::IsGenerated::IsGenerated(PrngDev& dev, Addr byte_addr)
    : dev_(dev), byte_addr_(byte_addr), cost_(dev.accessCycles())
{
}

void PrngDev::IsGenerated::perform(Trace& /*trace*/)
{
    generated_ = dev_.isGenerated(byte_addr_);
}

void PrngDev::IsGenerated::print(std::ostream& os) const
{
    os << "PRNG IsGenerated @0x" << std::hex << byte_addr_ << std::dec << " "
       << (generated_ ? "YES" : "NO") << " (" << cost_ << " cy)";
}


// --- PrngDev::Generate --------------------------------------------------------

PrngDev::Generate::Generate(PrngDev& dev, Addr byte_addr)
    : dev_(dev), byte_addr_(byte_addr), cost_(dev.gen_cost_per_line_)
{
}

void PrngDev::Generate::perform(Trace& /*trace*/)
{
    regen_ = dev_.isGenerated(byte_addr_);
    if (regen_) {
        ++dev_.stats_.regenerates;
    } else {
        ++dev_.stats_.generates;
    }

    const Addr line_end = dev_.lineBase(byte_addr_) + dev_.line_size_;
    dev_.head_          = std::max(dev_.head_, line_end);
}

void PrngDev::Generate::print(std::ostream& os) const
{
    os << "PRNG Generate line @0x" << std::hex << dev_.lineBase(byte_addr_)
       << std::dec << " (" << cost_ << " cy)" << (regen_ ? " REGEN" : "");
}
