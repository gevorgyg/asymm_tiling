#include "mainmem.h"

#include <ostream>


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

void MemoryAccess::print(std::ostream& os) const
{
    os << "MemoryAccess @0x" << std::hex << addr_ << std::dec << " ("
       << cost_ << " cy)";
}
