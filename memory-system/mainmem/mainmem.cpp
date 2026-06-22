#include "mainmem.h"
#include "mainmem_actions.h"


void MainMemory::read(Addr addr, size_t /*size*/, Trace& trace)
{
    trace.push_back(std::make_unique<MemoryAccess>(accessCycles(), addr));
}

void MainMemory::write(Addr addr, size_t /*size*/, Trace& trace)
{
    trace.push_back(std::make_unique<MemoryAccess>(accessCycles(), addr));
}
