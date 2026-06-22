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

MemoryHierarchy::MemoryHierarchy(Parameters p, const size_t& cpu_cycles)
    : mem_(p.mem_access_cycles),
      l2_(p.l2_access_cycles, p.l2, parsePolicy(p.l2_policy), &mem_),
      prng_(p.prng),
      prng_fifo_(p.prng_fifo, cpu_cycles),
      router_(prng_, l2_),
      l1_(p.l1_access_cycles, p.l1, parsePolicy(p.l1_policy), &router_)
{
}

void MemoryHierarchy::access(Addr addr, size_t size, bool is_write, Trace& trace)
{
    // FIFO MMIO is the only path that bypasses L1. Caches don't see these
    // addresses at all -- the device handles control/seed/data reads itself.
    if (prng_fifo_.contains(addr)) {
        if (is_write) prng_fifo_.write(addr, size, trace);
        else          prng_fifo_.read(addr, size, trace);
        return;
    }

    if (is_write) l1_.write(addr, size, trace);
    else          l1_.read(addr, size, trace);
}
