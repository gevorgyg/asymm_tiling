#include "mainmem.h"

#include <ostream>


void MainMemory::read(Addr addr, size_t /*size*/, Trace& trace)
{
    trace.push_back(std::make_unique<MemoryAccess>(accessCycles(), addr));
    trace.back()->perform(trace);
}

void MainMemory::write(Addr addr, size_t /*size*/, Trace& trace)
{
    trace.push_back(std::make_unique<MemoryAccess>(accessCycles(), addr));
    trace.back()->perform(trace);
}

void MemoryAccess::print(std::ostream& os) const
{
    os << "MemoryAccess @0x" << std::hex << addr_ << std::dec << " ("
       << cost_ << " cy)";
}
