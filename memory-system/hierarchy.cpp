#include "hierarchy.h"


MemoryHierarchy::MemoryHierarchy(Parameters p)
    : MemoryObject(0),
      mem_(p.mem_access_cycles),
      l1_(p.l1_access_cycles, p.l1, std::make_unique<FifoPolicy>(), &mem_)
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
