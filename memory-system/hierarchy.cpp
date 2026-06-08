#include "hierarchy.h"

#include <ostream>


// --- MainMemory ---------------------------------------------------------

Trace MainMemory::read(Addr addr, size_t /*size*/)
{
    Trace trace;
    trace.push_back(std::make_unique<MemoryAccess>(accessCycles(), addr));
    trace.back()->perform(trace);
    return trace;
}

Trace MainMemory::write(Addr addr, size_t /*size*/)
{
    Trace trace;
    trace.push_back(std::make_unique<MemoryAccess>(accessCycles(), addr));
    trace.back()->perform(trace);
    return trace;
}


// --- MemoryAccess -------------------------------------------------------

void MemoryAccess::print(std::ostream& os) const
{
    os << "MemoryAccess @0x" << std::hex << addr_ << std::dec << " ("
       << cost_ << " cy)";
}


// --- MemoryHierarchy ----------------------------------------------------

MemoryHierarchy::MemoryHierarchy(Parameters p)
    : MemoryObject(0),
      policy_(),
      mem_(p.mem_access_cycles),
      l1_(p.l1_access_cycles, p.l1, policy_, &mem_)
{
}

Trace MemoryHierarchy::read(Addr addr, size_t size)
{
    return l1_.read(addr, size);
}

Trace MemoryHierarchy::write(Addr addr, size_t size)
{
    return l1_.write(addr, size);
}
