#include "hierarchy.h"


void AddrRouter::read(Addr addr, size_t size, Trace& trace)
{
    if (prng_.contains(addr)) {
        prng_.read(addr, size, trace);
    } else {
        fallthrough_.read(addr, size, trace);
    }
}

void AddrRouter::write(Addr addr, size_t size, Trace& trace)
{
    if (prng_.contains(addr)) {
        prng_.write(addr, size, trace);
    } else {
        fallthrough_.write(addr, size, trace);
    }
}

MemoryHierarchy::MemoryHierarchy(Parameters p)
    : MemoryObject(0),
      mem_(p.mem_access_cycles),
      l2_(p.l2_access_cycles, p.l2, std::make_unique<FifoPolicy>(), &mem_),
      prng_(p.prng),
      router_(prng_, l2_),
      l1_(p.l1_access_cycles, p.l1, std::make_unique<FifoPolicy>(), &router_)
{
}

void MemoryHierarchy::read(Addr addr, size_t size, Trace& trace)
{
    l1_.read(addr, size, trace);
}

void MemoryHierarchy::write(Addr addr, size_t size, Trace& trace)
{
    l1_.write(addr, size, trace);
}
